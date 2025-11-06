import json
import pytest
from main import sparql, init

def test_sparql_basic_query():
    """Test basic SPARQL query"""
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?label WHERE {
        ?s rdfs:label ?label .
    } LIMIT 5
    """
    result = json.loads(sparql.fn(query))
    assert "results" in result
    assert len(result["results"]) <= 5
    assert "count" in result

def test_sparql_text_search():
    """Test SPARQL text search for country-related concepts"""
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    
    SELECT ?concept ?label ?definition WHERE {
        ?concept rdfs:label ?label .
        OPTIONAL { ?concept skos:definition ?definition }
        FILTER(CONTAINS(LCASE(?label), "currency"))
    } LIMIT 10
    """
    result = json.loads(sparql.fn(query))
    assert "results" in result
    # Should find currency-related concepts in FIBO

def test_sparql_property_paths():
    """Test SPARQL property paths for traversal"""
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    
    SELECT ?subclass WHERE {
        ?subclass rdfs:subClassOf+ owl:Thing .
    } LIMIT 10
    """
    result = json.loads(sparql.fn(query))
    assert "results" in result

def test_sparql_aggregation():
    """Test SPARQL aggregation functions"""
    query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    
    SELECT (COUNT(?class) as ?total) WHERE {
        ?class a owl:Class .
    }
    """
    result = json.loads(sparql.fn(query))
    assert "results" in result
    if len(result["results"]) > 0:
        assert "total" in result["results"][0]

def test_sparql_invalid_query():
    """Test handling of invalid SPARQL query"""
    query = "INVALID SPARQL SYNTAX"
    result = json.loads(sparql.fn(query))
    assert "error" in result

def test_graph_initialization():
    """Test that graph initializes properly"""
    g = init()
    assert g is not None
    assert len(g) > 0  # Should have triples loaded