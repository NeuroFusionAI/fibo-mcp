"""Constants for FIBO MCP server."""

# LRU cache size for SPARQL queries
SPARQL_CACHE_SIZE = 1000

# Standard RDF/OWL namespace prefixes used purely for documentation /
# query-template hints. The previous mapping included
#   "https://spec.edmcouncil.org/fibo/ontology/": "fibo:"
# which produced display strings like ``fibo:SEC/Equities/EquityInstruments/Share``
# that are **not** valid SPARQL QNames (FIBO local names contain ``/``).
#
# We intentionally drop the FIBO entry here and let RDFLib's namespace
# manager emit the proper module prefixes that are actually loaded from
# the ontology (e.g. ``fibo-sec-eq-eq:Share``, ``fibo-fbc-fi-fi:Security``).
PREFIXES = {
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/2002/07/owl#": "owl:",
    "http://www.w3.org/2004/02/skos/core#": "skos:",
    "https://www.omg.org/spec/Commons/AnnotationVocabulary/": "cmns-av:",
}
