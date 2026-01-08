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
