import json

import fibo
from loader import get_graph


def _json_result(output: str):
    return json.loads(output)


def test_sparql_basic_query():
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?label WHERE {
        ?s rdfs:label ?label .
    } LIMIT 5
    """
    result = _json_result(fibo.sparql(query))
    assert "results" in result
    assert "count" in result
    assert isinstance(result["results"], list)


def test_sparql_text_search():
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

    SELECT ?concept ?label ?definition WHERE {
        ?concept rdfs:label ?label .
        OPTIONAL { ?concept skos:definition ?definition }
        FILTER(CONTAINS(LCASE(?label), "currency"))
    } LIMIT 10
    """
    result = _json_result(fibo.sparql(query))
    assert "results" in result
    assert "suggestions" in result
    assert result["suggestions"]


def test_sparql_property_paths():
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>

    SELECT ?subclass WHERE {
        ?subclass rdfs:subClassOf+ owl:Thing .
    } LIMIT 10
    """
    result = _json_result(fibo.sparql(query))
    assert "results" in result


def test_sparql_aggregation():
    query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>

    SELECT (COUNT(?class) as ?total) WHERE {
        ?class a owl:Class .
    }
    """
    result = _json_result(fibo.sparql(query))
    assert "results" in result
    assert "total" in result["results"][0]


def test_sparql_invalid_query():
    query = "INVALID SPARQL SYNTAX"
    result = _json_result(fibo.sparql(query))
    assert "error" in result


def test_sparql_blocks_remote_service_queries():
    result = _json_result(fibo.sparql(
        'SELECT * WHERE { SERVICE <https://example.com/sparql> { ?s ?p ?o } }'
    ))
    assert "error" in result
    assert "not allowed" in result["error"]


def test_sparql_caps_returned_rows(monkeypatch):
    monkeypatch.setattr(fibo, "SPARQL_MAX_ROWS", 3)
    fibo._cached_sparql.cache_clear()
    result = _json_result(fibo.sparql("SELECT ?s WHERE { ?s ?p ?o }"))
    assert result["count"] == 3
    assert result["truncated"] is True
    fibo._cached_sparql.cache_clear()


def test_sparql_prefix_compression():
    query = """
    SELECT ?p ?v WHERE {
        <https://spec.edmcouncil.org/fibo/ontology/BE/GovernmentEntities/GovernmentEntities/SovereignState> ?p ?v
    }
    """
    result = fibo.sparql(query)
    assert "rdfs:" in result or "owl:" in result or "fibo-" in result


def test_graph_initialization():
    g = get_graph()
    assert g is not None
    assert len(g) > 0


def test_fibo_uri_compaction_uses_queryable_module_prefix():
    """FIBO URIs must be compacted with their loaded module prefix.

    The previous implementation produced strings like
    ``fibo:SEC/Equities/EquityInstruments/Share`` which are syntactically
    invalid SPARQL QNames and therefore cannot be pasted back into a
    follow-up query. The graph already ships a per-module prefix
    (``fibo-sec-eq-eq``) which is queryable.
    """
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?c ?label WHERE {
        ?c rdfs:label ?label .
        FILTER(LCASE(STR(?label)) = "share")
    } LIMIT 5
    """
    result = fibo.sparql(query)
    assert "fibo-sec-eq-eq:Share" in result
    # Regression: the old broken pseudo-CURIE must not leak back in.
    assert "fibo:SEC/Equities/EquityInstruments/Share" not in result


def test_compacted_fibo_module_prefix_is_queryable():
    """The compact form returned by the server must be a valid QName.

    We round-trip the compacted identifier through SPARQL to prove that
    callers can reuse it without first having to look up the absolute IRI.
    """
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?label WHERE {
        fibo-sec-eq-eq:Share rdfs:label ?label .
    } LIMIT 1
    """
    result = _json_result(fibo.sparql(query))
    assert result["results"][0]["label"] == "share"
    assert "error" not in result


def test_bm25_top_k_runtime_override():
    """``fibo.BM25_TOP_K`` must be honoured at call time, not import time."""
    original = fibo.BM25_TOP_K
    try:
        fibo.BM25_TOP_K = 3
        results = fibo.fuzzy_search("currency")
        assert len(results) <= 3
    finally:
        fibo.BM25_TOP_K = original


def test_bm25_suggestions_include_definitions_when_available():
    results = fibo.fuzzy_search("currency")
    assert results
    assert any("def" in row for row in results)


def test_bm25_definitions_are_returned_verbatim():
    """FIBO definitions are bounded prose; we must not silently truncate them.

    Truncation breaks string equality, regex matching, and any downstream
    code path that round-trips definitions back into the graph or compares
    them. The corpus itself is the only legitimate upper bound.
    """
    from rdflib import URIRef
    from loader import get_graph

    graph = get_graph()
    # Re-resolve each suggestion's compact URI back to the absolute IRI used
    # as the BM25 corpus key, so we can compare definitions exactly.
    docs_by_uri = {d["uri"]: d for d in fibo._docs_data or []}

    results = fibo.fuzzy_search("currency")
    checked = 0
    for row in results:
        if "def" not in row:
            continue
        absolute = str(graph.namespace_manager.expand_curie(row["uri"]))
        assert absolute in docs_by_uri, f"compact URI did not round-trip: {row['uri']}"
        full = docs_by_uri[absolute]["definition"]
        assert row["def"] == full, (
            f"suggestion definition was truncated for {row['uri']!r}: "
            f"got {len(row['def'])} chars, corpus has {len(full)} chars"
        )
        assert "…" not in row["def"], "ellipsis sentinel must not appear"
        checked += 1
    assert checked > 0, "no suggestions with definitions were checked"


def test_inspect_returns_incident_semantic_neighborhood():
    result = _json_result(fibo.inspect("fibo-sec-eq-eq:Share"))
    assert result["uri"] == "fibo-sec-eq-eq:Share"
    assert "share" in result["label"]
    assert "parents" in result
    assert "children" in result
    assert "restrictions" in result
    assert any(parent["label"] == "equity instrument" for parent in result["parents"])
