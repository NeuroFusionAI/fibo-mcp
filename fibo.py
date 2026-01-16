import logging
import re
from typing import Any

from toon_format import encode

from loader import get_graph

logger = logging.getLogger(__name__)

PREFIXES = {
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/2002/07/owl#": "owl:",
    "http://www.w3.org/2004/02/skos/core#": "skos:",
    "https://www.omg.org/spec/Commons/AnnotationVocabulary/": "cmns-av:",
    "https://spec.edmcouncil.org/fibo/ontology/": "fibo:",
}


def _compact_uri(uri: str) -> str:
    for full, prefix in PREFIXES.items():
        if uri.startswith(full):
            return prefix + uri[len(full) :]
    return uri


def _compact_result(row: dict[str, str]) -> dict[str, str]:
    return {k: _compact_uri(v) for k, v in row.items()}


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
        r'CONTAINS\s*\(\s*STR\s*\(\s*\?\w+\s*\)\s*,\s*["\']([^"\']+)["\']',
        r'CONTAINS\s*\(\s*\?\w+\s*,\s*["\']([^"\']+)["\']',
        r'=\s*["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return None


def fuzzy_search(term: str, top_k: int = 5) -> list[dict[str, Any]]:
    bm25, docs = _get_bm25()
    scores = bm25.get_scores(term.lower().split())
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [
        {
            "uri": _compact_uri(docs[i]["uri"]),
            "label": docs[i]["label"],
            "score": round(scores[i], 2),
        }
        for i in top_idx
        if scores[i] > 0
    ]


def sparql(query: str) -> str:
    graph = get_graph()
    logger.info(
        f"Executing SPARQL query: {query[:80]}{'...' if len(query) > 80 else ''}"
    )

    try:
        results = graph.query(query)
        output = []
        for row in results:
            output.append(
                _compact_result(
                    {
                        str(var): str(row[var])
                        for var in results.vars
                        if row[var] is not None
                    }
                )
            )  # type: ignore

        logger.info(f"SPARQL query returned {len(output)} results.")
        result: dict[str, Any] = {"results": output, "count": len(output)}

        term = _extract_search_term(query)
        if term:
            result["suggestions"] = fuzzy_search(term, top_k=10)
            logger.info(
                f"Added {len(result['suggestions'])} BM25 suggestions for '{term}'"
            )

        return encode(result)

    except Exception as e:
        logger.error(f"SPARQL query failed: {e}")
        return encode({"error": str(e)})


def search(term: str) -> str:
    results = fuzzy_search(term, top_k=10)
    return encode({"results": results, "count": len(results)})
