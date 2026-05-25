import hashlib
import json
import logging
import re
from functools import lru_cache
from typing import Any

from rdflib import BNode, Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from constants import PREFIXES, SPARQL_CACHE_SIZE
from loader import get_graph

logger = logging.getLogger(__name__)

# Configurable at runtime via main.py --bm25-top-k
BM25_TOP_K = 10

# Definitions are useful for LLM grounding, but BM25 suggestions are side-channel
# hints. Keep them bounded so a typo/lookup query does not drown out SPARQL rows.
SUGGESTION_DEF_MAX_CHARS = 360


def _encode(result: dict[str, Any]) -> str:
    """Return compact JSON for MCP responses.

    Compact JSON is standard, broadly represented in LLM pretraining data, and
    benchmarked slightly smaller than TOON for definition-heavy FIBO payloads.
    """
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def _truncate(text: str, max_chars: int = SUGGESTION_DEF_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _compact_static_uri(uri: str) -> str:
    """Compact a URI using only the static, non-FIBO prefix table.

    This is used as a fallback when RDFLib's namespace manager cannot
    produce a valid QName (typically because the local name would contain
    characters that are illegal in a QName).
    """
    for full, prefix in PREFIXES.items():
        if uri.startswith(full):
            return prefix + uri[len(full):]
    return uri


def _format_node(node: Any, graph: Graph) -> str:
    """Render an RDFLib term as a queryable, human-readable string.

    For :class:`~rdflib.URIRef` we prefer prefixes that the loaded graph
    actually knows about (FIBO ships per-module prefixes such as
    ``fibo-sec-eq-eq``), because those are valid SPARQL QNames and can be
    pasted back into a follow-up query. If no such QName exists we fall
    back to the static prefix table and finally to an angle-bracketed
    absolute IRI.
    """
    if isinstance(node, URIRef):
        try:
            prefix, _namespace, local = graph.namespace_manager.compute_qname(
                node, generate=False
            )
            # ``compute_qname`` does not guarantee a syntactically valid
            # local name; reject anything that contains characters which
            # would make the result unusable in SPARQL.
            if local and not any(ch in local for ch in "/#?"):
                return f"{prefix}:{local}"
        except (KeyError, ValueError):
            pass

        compact = _compact_static_uri(str(node))
        if compact != str(node):
            return compact
        return f"<{node}>"

    if isinstance(node, BNode):
        return f"_:{node}"

    return str(node)


def _resolve_identifier(identifier: str, graph: Graph) -> URIRef:
    """Resolve a queryable QName, ``<IRI>``, or raw IRI to a URIRef."""
    ident = identifier.strip()
    if ident.startswith("<") and ident.endswith(">"):
        return URIRef(ident[1:-1])
    if ident.startswith("http://") or ident.startswith("https://"):
        return URIRef(ident)
    return URIRef(graph.namespace_manager.expand_curie(ident))


def _unique_formatted(nodes: Any, graph: Graph, limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for node in nodes:
        formatted = _format_node(node, graph)
        if formatted in seen:
            continue
        seen.add(formatted)
        out.append(formatted)
        if limit is not None and len(out) >= limit:
            break
    return out


_bm25_index = None
_docs_data = None


def _get_bm25():
    global _bm25_index, _docs_data
    if _bm25_index is None:
        from rank_bm25 import BM25Okapi

        graph = get_graph()
        results = graph.query("""
            SELECT ?c ?label ?def WHERE {
                ?c a <http://www.w3.org/2002/07/owl#Class> .
                ?c <http://www.w3.org/2000/01/rdf-schema#label> ?label .
                OPTIONAL { ?c <http://www.w3.org/2004/02/skos/core#definition> ?def }
            }
        """)
        _docs_data = []
        corpus = []
        for r in results:
            uri, label = str(r.c), str(r.label)  # type: ignore
            defn = str(r["def"]) if r["def"] else ""  # type: ignore
            _docs_data.append({"uri": uri, "label": label, "definition": defn})
            corpus.append(f"{label} {defn}".lower().split())
        _bm25_index = BM25Okapi(corpus)
    return _bm25_index, _docs_data


def _extract_search_term(query: str) -> str | None:
    patterns = [
        r'CONTAINS\s*\(\s*LCASE\s*\(\s*\?\w+\s*\)\s*,\s*["\']([^"\']+)["\']',
        r'CONTAINS\s*\(\s*LCASE\s*\(\s*STR\s*\(\s*\?\w+\s*\)\s*\)\s*,\s*["\']([^"\']+)["\']',
        r'CONTAINS\s*\(\s*STR\s*\(\s*\?\w+\s*\)\s*,\s*["\']([^"\']+)["\']',
        r'CONTAINS\s*\(\s*\?\w+\s*,\s*["\']([^"\']+)["\']',
        r'=\s*["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return None


def fuzzy_search(term: str, top_k: int | None = None) -> list[dict[str, Any]]:
    # ``BM25_TOP_K`` may be mutated at runtime by ``main.py`` (``--bm25-top-k``),
    # so resolve the default lazily instead of binding it at definition time.
    if top_k is None:
        top_k = BM25_TOP_K

    graph = get_graph()
    bm25, docs = _get_bm25()
    scores = bm25.get_scores(term.lower().split())
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    suggestions = []
    for i in top_idx:
        if scores[i] <= 0:
            continue
        suggestion = {
            "uri": _format_node(URIRef(docs[i]["uri"]), graph),
            "label": docs[i]["label"],
            "score": round(scores[i], 2),
        }
        if docs[i]["definition"]:
            suggestion["def"] = _truncate(docs[i]["definition"])
        suggestions.append(suggestion)
    return suggestions


@lru_cache(maxsize=SPARQL_CACHE_SIZE)
def _cached_sparql(query_hash: str, query: str) -> list[dict[str, str]]:
    """Execute SPARQL and return results (cached by query hash)."""
    graph = get_graph()
    results = graph.query(query)
    output = []
    for row in results:
        output.append(
            {
                str(var): _format_node(row[var], graph)
                for var in results.vars
                if row[var] is not None
            }
        )
    return output


def sparql(query: str) -> str:
    logger.info(
        f"Executing SPARQL query: {query[:80]}{'...' if len(query) > 80 else ''}"
    )

    try:
        query_hash = hashlib.sha256(query.encode()).hexdigest()
        output = _cached_sparql(query_hash, query)

        logger.info(f"SPARQL query returned {len(output)} results.")
        result: dict[str, Any] = {"results": output, "count": len(output)}

        term = _extract_search_term(query)
        if term:
            result["suggestions"] = fuzzy_search(term)
            logger.info(
                f"Added {len(result['suggestions'])} BM25 suggestions for '{term}'"
            )

        return _encode(result)

    except Exception as e:
        logger.error(f"SPARQL query failed: {e}")
        return _encode({"error": str(e)})


def search(term: str) -> str:
    results = fuzzy_search(term)
    return _encode({"results": results, "count": len(results)})


def inspect(identifier: str, limit: int = 10) -> str:
    """Return an incident-style semantic neighborhood for one FIBO node.

    The output keeps the compact, queryable ID but places terminology and local
    graph structure next to it: labels, definitions, direct parents/children,
    and OWL restrictions. This is deliberately LLM-friendly: identifiers remain
    short handles, while labels/definitions carry meaning.
    """
    graph = get_graph()
    try:
        uri = _resolve_identifier(identifier, graph)
    except Exception as e:
        return _encode({"error": f"Could not resolve identifier {identifier!r}: {e}"})

    try:
        labels = _unique_formatted(graph.objects(uri, RDFS.label), graph, limit)
        definitions = _unique_formatted(graph.objects(uri, SKOS.definition), graph, limit)

        parent_rows = []
        for parent in graph.objects(uri, RDFS.subClassOf):
            if isinstance(parent, BNode):
                continue
            parent_rows.append(
                {
                    "uri": _format_node(parent, graph),
                    "label": next(
                        (str(label) for label in graph.objects(parent, RDFS.label)), ""
                    ),
                }
            )
            if len(parent_rows) >= limit:
                break

        child_rows = []
        for child in graph.subjects(RDFS.subClassOf, uri):
            child_rows.append(
                {
                    "uri": _format_node(child, graph),
                    "label": next(
                        (str(label) for label in graph.objects(child, RDFS.label)), ""
                    ),
                }
            )
            if len(child_rows) >= limit:
                break

        restriction_rows = []
        for restriction in graph.objects(uri, RDFS.subClassOf):
            if not isinstance(restriction, BNode):
                continue
            if (restriction, RDF.type, OWL.Restriction) not in graph:
                continue

            row: dict[str, str] = {"node": _format_node(restriction, graph)}
            prop = graph.value(restriction, OWL.onProperty)
            if prop is not None:
                row["onProperty"] = _format_node(prop, graph)
                prop_label = graph.value(prop, RDFS.label)
                if prop_label is not None:
                    row["propertyLabel"] = str(prop_label)

            for pred, key in [
                (OWL.someValuesFrom, "someValuesFrom"),
                (OWL.allValuesFrom, "allValuesFrom"),
                (OWL.hasValue, "hasValue"),
                (OWL.onClass, "onClass"),
                (OWL.onDataRange, "onDataRange"),
                (OWL.cardinality, "cardinality"),
                (OWL.minCardinality, "minCardinality"),
                (OWL.maxCardinality, "maxCardinality"),
                (OWL.qualifiedCardinality, "qualifiedCardinality"),
                (OWL.minQualifiedCardinality, "minQualifiedCardinality"),
                (OWL.maxQualifiedCardinality, "maxQualifiedCardinality"),
            ]:
                value = graph.value(restriction, pred)
                if value is not None:
                    row[key] = _format_node(value, graph)

            restriction_rows.append(row)
            if len(restriction_rows) >= limit:
                break

        result: dict[str, Any] = {
            "uri": _format_node(uri, graph),
            "label": labels,
            "def": definitions,
            "parents": parent_rows,
            "children": child_rows,
            "restrictions": restriction_rows,
        }
        return _encode(result)

    except Exception as e:
        logger.error(f"Inspect failed for {identifier!r}: {e}")
        return _encode({"error": str(e)})
