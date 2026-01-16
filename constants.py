"""Constants for FIBO MCP server."""

# LRU cache size for SPARQL queries
SPARQL_CACHE_SIZE = 1000

# Standard RDF/OWL namespace prefixes
PREFIXES = {
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/2002/07/owl#": "owl:",
    "http://www.w3.org/2004/02/skos/core#": "skos:",
    "https://www.omg.org/spec/Commons/AnnotationVocabulary/": "cmns-av:",
    "https://spec.edmcouncil.org/fibo/ontology/": "fibo:",
}
