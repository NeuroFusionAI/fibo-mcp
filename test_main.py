import json
import pytest
from main import traverse, sparql

def test_traverse_search():
    """Test searching for country"""
    result = json.loads(traverse.fn("country"))
    assert "search_results" in result
    assert len(result["search_results"]) > 0

def test_traverse_search_and_explore():
    """Test searching and exploring"""
    result = json.loads(traverse.fn("sovereign state"))
    assert "search_results" in result
    assert "explored" in result
    assert result["explored"]["edges"]["total"] > 0

def test_traverse_uri():
    """Test direct URI exploration"""
    uri = "https://spec.edmcouncil.org/fibo/ontology/FND/Accounting/CurrencyAmount/Currency"
    result = json.loads(traverse.fn(uri))
    assert "uri" in result
    assert "edges" in result
    assert result["edges"]["total"] > 0

def test_traverse_not_found():
    """Test with non-existent concept"""
    result = json.loads(traverse.fn("nonexistentconcept123"))
    assert "error" in result or len(result.get("search_results", [])) == 0

def test_sparql_query():
    """Test raw SPARQL query"""
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?label WHERE {
        ?s rdfs:label ?label .
    } LIMIT 5
    """
    result = json.loads(sparql.fn(query))
    assert "results" in result
    assert len(result["results"]) <= 5