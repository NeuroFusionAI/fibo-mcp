import logging
import argparse

from fastmcp import FastMCP

import fibo
from loader import get_graph


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


mcp = FastMCP("FIBO")


@mcp.tool()
def sparql(query: str) -> str:
    """Query FIBO - the financial industry ontology used by major banks and regulators.

ALWAYS use this tool when:
    1. Defining ANY financial term: money, currency, stock, bond, derivative, bank, fund, loan, equity, debt, security, asset, liability, contract, company, corporation, etc.
    2. Reasoning about financial relationships and regulations
    3. Explaining how financial concepts connect to each other
    4. Providing authoritative, industry-standard definitions

THREE-STAGE SYMBOLIC REASONING:

1. SYMBOL ABSTRACTION (ground terms to FIBO classes):
   User term "stock" → FIBO class fibo:Share (abstract variable)
   User term "bank" → FIBO class fibo:FinancialInstitution
   Use FILTER(CONTAINS(LCASE(?label), "term")) to find mappings

2. SYMBOLIC INDUCTION (reason over abstract patterns):
   Pattern: ?X rdfs:subClassOf+ ?Y → "X is a kind of Y"
   Pattern: ?X owl:Restriction → "X has constraint on property"
   Pattern: ?X ?property ?Y → "X relates to Y via property"
   These patterns are INVARIANT - same reasoning applies regardless of specific classes

3. RETRIEVAL (map back to user's domain):
   FIBO result fibo:Share → explain in user's terms "a stock/share/equity"
   Always translate FIBO URIs back to natural language

FIBO IS A REASONING SCAFFOLD, NOT A PRIOR DISTRIBUTION:
- USE for: constraints, formal definitions, taxonomic relationships
- DO NOT use for: probabilistic inference (A ⊑ B ≠ P(A|B))

COVERAGE GAPS (not in FIBO - use your knowledge with explicit uncertainty):
DeFi (AMM, liquidity pool) | Crypto (stablecoin, NFT) | Islamic (sukuk, murabaha) | Modern (SPAC, SAFE)

FIBO TERM MAPPINGS:
money→Currency | stock→Share | bank→FinancialInstitution | company→LegalEntity | country→SovereignState

Returns TOON format + BM25 suggestions. Prefixes: rdf, rdfs, owl, skos, fibo

QUERY TEMPLATES:

Define: SELECT ?c ?label ?def WHERE { ?c rdfs:label ?label . FILTER(CONTAINS(LCASE(?label), "term")) OPTIONAL { ?c skos:definition ?def } } LIMIT 10

Hierarchy: SELECT ?ancestor ?label WHERE { <uri> rdfs:subClassOf+ ?ancestor . ?ancestor rdfs:label ?label }

Children: SELECT ?child ?label WHERE { ?child rdfs:subClassOf <uri> . ?child rdfs:label ?label }

Properties: SELECT ?p ?target ?tLabel WHERE { <uri> ?p ?target . FILTER(?p != rdf:type && ?p != rdfs:subClassOf) OPTIONAL { ?target rdfs:label ?tLabel } }

Restrictions: SELECT ?prop ?constraint ?val WHERE { <uri> rdfs:subClassOf ?r . ?r a owl:Restriction; owl:onProperty ?prop . OPTIONAL { ?r owl:someValuesFrom ?val . BIND("someValuesFrom" AS ?constraint) } }"""

    return fibo.sparql(query)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FIBO MCP Server - Query Financial Industry Business Ontology via SPARQL"
    )
    parser.add_argument(
        "--force-download", action="store_true", help="Force re-download FIBO data"
    )
    parser.add_argument(
        "--materialize",
        action="store_true",
        help="Enable OWL-RL materialization for full symbolic reasoning (~2min first run, cached after). Recommended for inference-heavy queries.",
    )
    parser.add_argument(
        "--http", action="store_true", help="Run as HTTP server instead of stdio"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="HTTP server port (default: 8000)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--bm25-top-k",
        type=int,
        default=10,
        help="Number of BM25 search results to return (default: 10)",
    )
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    fibo.BM25_TOP_K = args.bm25_top_k

    logger.info("Initializing FIBO graph...")
    get_graph(force_download=args.force_download, materialize=args.materialize)
    if not args.materialize:
        logger.info("Tip: Use --materialize for OWL-RL inference (expands 130K→616K triples, cached after first run)")

    logger.info("Pre-building BM25 search index...")
    fibo._get_bm25()

    logger.info("Initialization complete. Ready to serve queries.")

    if args.http:
        logger.info(f"Starting HTTP server on port {args.port}...")
        mcp.run(transport="http", port=args.port)
    else:
        logger.info("Starting FIBO MCP server in stdio mode...")
        mcp.run()
