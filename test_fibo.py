import fibo
from loader import get_graph


def test_sparql_basic_query():
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?label WHERE {
        ?s rdfs:label ?label .
    } LIMIT 5
    """
    result = fibo.sparql(query)
    assert "results[" in result
    assert "count:" in result


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
    result = fibo.sparql(query)
    assert "results[" in result
    assert "suggestions[" in result


def test_sparql_property_paths():
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    
    SELECT ?subclass WHERE {
        ?subclass rdfs:subClassOf+ owl:Thing .
    } LIMIT 10
    """
    result = fibo.sparql(query)
    assert "results[" in result


def test_sparql_aggregation():
    query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    
    SELECT (COUNT(?class) as ?total) WHERE {
        ?class a owl:Class .
    }
    """
    result = fibo.sparql(query)
    assert "results[" in result
    assert "total" in result


def test_sparql_invalid_query():
    query = "INVALID SPARQL SYNTAX"
    result = fibo.sparql(query)
    assert "error:" in result


def test_sparql_prefix_compression():
    query = """
    SELECT ?p ?v WHERE {
        <https://spec.edmcouncil.org/fibo/ontology/BE/GovernmentEntities/GovernmentEntities/SovereignState> ?p ?v
    }
    """
    result = fibo.sparql(query)
    assert "rdfs:" in result or "owl:" in result or "fibo:" in result


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
    result = fibo.sparql(query)
    assert "share" in result
    assert "error:" not in result


def test_bm25_top_k_runtime_override():
    """``fibo.BM25_TOP_K`` must be honoured at call time, not import time."""
    original = fibo.BM25_TOP_K
    try:
        fibo.BM25_TOP_K = 3
        results = fibo.fuzzy_search("currency")
        assert len(results) <= 3
    finally:
        fibo.BM25_TOP_K = original
