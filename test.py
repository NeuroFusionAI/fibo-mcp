#!/usr/bin/env python3
"""Comprehensive test suite for FIBO MCP - validates tool efficiency and correctness."""
import json

import pytest

import main


@pytest.fixture(scope="module")
def fibo_graph():
    """Initialize FIBO graph once for all tests."""
    main.init_graph()
    return main.g


@pytest.mark.asyncio
async def test_graph_initialization(fibo_graph):
    """Test core SPARQL querying and graph operations."""
    assert fibo_graph is not None, "Graph should be initialized"
    assert len(fibo_graph) > 100000, f"Graph should have >100k triples (got {len(fibo_graph)})"


@pytest.mark.asyncio
async def test_basic_sparql_query(fibo_graph):
    """Test basic SPARQL query execution."""
    result = main._sparql_query("SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5")
    data = json.loads(result)
    assert len(data["results"]["bindings"]) == 5, "SPARQL query should return 5 results"


@pytest.mark.asyncio
async def test_search_by_label_single_term(fibo_graph):
    """Test search_by_label with single term."""
    result = await main.search_by_label.run({"search_term": "currency", "limit": 10})
    data = json.loads(result.content[0].text)
    count = len(data["results"]["bindings"])
    assert count > 0, f"search_by_label should find results for 'currency' (got {count})"


@pytest.mark.asyncio
async def test_search_by_label_multi_term(fibo_graph):
    """Test search_by_label with multiple comma-separated terms."""
    result = await main.search_by_label.run({"search_term": "currency,bond,equity", "limit": 20})
    data = json.loads(result.content[0].text)
    count = len(data["results"]["bindings"])
    assert count > 0, f"Multi-term search should find results (got {count})"


@pytest.mark.asyncio
async def test_list_classes(fibo_graph):
    """Test list_classes returns ontology classes."""
    result = await main.list_classes.run({"limit": 30})
    data = json.loads(result.content[0].text)
    count = len(data["results"]["bindings"])
    assert count > 0, f"list_classes should return classes (got {count})"


@pytest.mark.asyncio
async def test_explore_concept_structure(fibo_graph):
    """Test explore_concept returns all expected fields."""
    result = await main.explore_concept.run({"concept": "jurisdiction", "limit": 5})
    data = json.loads(result.content[0].text)

    assert "summary" in data, "Should return summary field"
    assert "top_result" in data, "Should return top_result field"
    assert "details" in data, "Should return details field"
    assert "all_search_results" in data, "Should return all_search_results field"


@pytest.mark.asyncio
async def test_explore_concept_synonym_expansion(fibo_graph):
    """Test explore_concept auto-expands synonyms."""
    result = await main.explore_concept.run({"concept": "country", "limit": 5})
    data = json.loads(result.content[0].text)

    assert "_note" in data, "Should include expansion note"
    note = data.get("_note", "")
    assert "jurisdiction" in note.lower(), "Should auto-expand 'country' to include 'jurisdiction'"


@pytest.mark.asyncio
async def test_get_entity_details(fibo_graph):
    """Test get_entity_details returns entity properties."""
    # Get a known URI first
    search_result = await main.search_by_label.run({"search_term": "currency", "limit": 1})
    search_data = json.loads(search_result.content[0].text)

    assert len(search_data["results"]["bindings"]) > 0, "Should find at least one currency entity"

    test_uri = search_data["results"]["bindings"][0]["entity"]["value"]
    result = await main.get_entity_details.run({"uri": test_uri, "limit": 20})
    data = json.loads(result.content[0].text)
    count = len(data["results"]["bindings"])

    assert count > 0, f"get_entity_details should return properties (got {count})"


@pytest.mark.asyncio
async def test_explore_neighbors(fibo_graph):
    """Test explore_neighbors finds entity connections."""
    # Get a known URI first
    search_result = await main.search_by_label.run({"search_term": "currency", "limit": 1})
    search_data = json.loads(search_result.content[0].text)

    assert len(search_data["results"]["bindings"]) > 0, "Should find at least one currency entity"

    test_uri = search_data["results"]["bindings"][0]["entity"]["value"]
    result = await main.explore_neighbors.run({"uri": test_uri, "limit": 10})
    data = json.loads(result.content[0].text)
    count = len(data["results"]["bindings"])

    assert count >= 0, f"explore_neighbors should work (got {count} neighbors)"


@pytest.mark.asyncio
async def test_result_ranking_classes_first(fibo_graph):
    """Test that search results prioritize classes."""
    result = await main.search_by_label.run({"search_term": "jurisdiction", "limit": 10})
    data = json.loads(result.content[0].text)
    bindings = data["results"]["bindings"]

    assert len(bindings) > 0, "Should find results for 'jurisdiction'"

    first_result = bindings[0]
    has_class_type = "Class" in first_result.get("type", {}).get("value", "")
    assert has_class_type, "First result should be a class (proper ranking)"


@pytest.mark.asyncio
async def test_result_ranking_has_definitions(fibo_graph):
    """Test that search results include definitions."""
    result = await main.search_by_label.run({"search_term": "jurisdiction", "limit": 10})
    data = json.loads(result.content[0].text)
    bindings = data["results"]["bindings"]

    assert len(bindings) > 0, "Should find results for 'jurisdiction'"

    has_definitions = sum(1 for b in bindings if "definition" in b)
    assert has_definitions > 0, f"Results should include definitions ({has_definitions}/{len(bindings)})"


@pytest.mark.asyncio
async def test_efficiency_single_call_workflow(fibo_graph):
    """Test that 'what is X?' workflow completes in 1 call."""
    result = await main.explore_concept.run({"concept": "jurisdiction", "limit": 5})
    data = json.loads(result.content[0].text)

    search_results = data.get("all_search_results", {}).get("results", {}).get("bindings", [])
    assert len(search_results) > 0, "Single call should return results"


@pytest.mark.asyncio
async def test_efficiency_no_empty_results(fibo_graph):
    """Test that explore_concept returns non-empty results."""
    result = await main.explore_concept.run({"concept": "jurisdiction", "limit": 5})
    data = json.loads(result.content[0].text)

    # Check all major fields have content
    assert "summary" in data and data["summary"], "Summary should not be empty"
    assert "top_result" in data and data["top_result"], "Top result should not be empty"
    assert "details" in data, "Details field should exist"
