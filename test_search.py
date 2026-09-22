import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

import fibo


@pytest.fixture
def tiny_graph(monkeypatch):
    graph = Graph()
    graph.bind("example", "https://example.org/")
    monkeypatch.setattr(fibo, "get_graph", lambda: graph)
    monkeypatch.setattr(fibo, "_bm25_index", None)
    monkeypatch.setattr(fibo, "_docs_data", None)
    monkeypatch.setattr(fibo, "_exact_matches", {})
    return graph


def add_class(graph, name, label):
    uri = Namespace("https://example.org/")[name]
    graph.add((uri, RDF.type, OWL.Class))
    graph.add((uri, RDFS.label, Literal(label)))
    return uri


@pytest.mark.parametrize("predicate", fibo.SEARCH_ANNOTATIONS)
def test_exact_annotation_returns_grounded_match_even_without_positive_bm25(tiny_graph, predicate):
    uri = add_class(tiny_graph, "Instrument", "financial instrument")
    tiny_graph.add((uri, predicate, Literal("XYZ")))
    row = fibo.fuzzy_search("  xyz  ")[0]
    assert row["uri"] == "example:Instrument"
    assert row["match"] == "ontology_annotation"
    assert row["matched_text"] == "XYZ"
    assert row["match_source"] == str(predicate)


def test_multiple_names_and_definitions_return_one_class(tiny_graph):
    uri = add_class(tiny_graph, "Instrument", "instrument")
    tiny_graph.add((uri, RDFS.label, Literal("financial instrument")))
    tiny_graph.add((uri, SKOS.definition, Literal("first complete definition")))
    tiny_graph.add((uri, SKOS.definition, Literal("second complete definition")))
    rows = fibo.fuzzy_search("instrument")
    assert len(rows) == 1
    assert rows[0]["matched_text"] == "instrument"
    assert rows[0]["def"] in {str(d) for d in tiny_graph.objects(uri, SKOS.definition)}


def test_exact_label_precedes_alias_but_preserves_ambiguous_candidates(tiny_graph):
    synonym = fibo.SEARCH_ANNOTATIONS[0]
    for name in ("B", "A"):
        uri = add_class(tiny_graph, name, name + " class")
        tiny_graph.add((uri, synonym, Literal("money")))
    add_class(tiny_graph, "Z", "money")
    add_class(tiny_graph, "Currency", "currency")
    rows = fibo.fuzzy_search("money")
    assert [row["uri"] for row in rows[:4]] == [
        "example:Z", "example:A", "example:B", "example:Currency"]
    assert rows[3]["match_source"] == "local:CONCEPT_ALIASES"


def test_empty_search_does_not_load_ontology(monkeypatch):
    def unexpected_load():
        raise AssertionError("empty input should not load the graph")
    monkeypatch.setattr(fibo, "get_graph", unexpected_load)
    assert fibo.fuzzy_search(" \n ") == []


def test_exact_share_label_is_first_in_real_fibo():
    row = fibo.fuzzy_search("share", top_k=1)[0]
    assert row["uri"] == "fibo-sec-eq-eq:Share"
    assert row["match_source"] == str(RDFS.label)
