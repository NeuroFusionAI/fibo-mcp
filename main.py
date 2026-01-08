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

Use FIBO definitions as the foundation for your financial reasoning and explanations.

Query patterns:
- Search: FILTER(CONTAINS(LCASE(?label), "term"))
- Describe: SELECT ?p ?v WHERE { <uri> ?p ?v }
- Ancestors: ?class rdfs:subClassOf+ ?ancestor
- Restrictions: ?class rdfs:subClassOf ?r . ?r a owl:Restriction; owl:onProperty ?p

FIBO mappings (common term -> FIBO term):
money->Currency | stock->Share | bank->FinancialInstitution | company->LegalEntity | country->SovereignState

Returns TOON format + BM25 suggestions. Prefixes: rdf, rdfs, owl, skos, fibo"""
    
    return fibo.sparql(query)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FIBO MCP Server - Query Financial Industry Business Ontology via SPARQL"
    )
    parser.add_argument(
        "--force-download", action="store_true", help="Force re-download FIBO data"
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
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("Initializing FIBO graph...")
    get_graph(force_download=args.force_download)
    logger.info("Initialization complete. Ready to serve queries.")

    if args.http:
        logger.info(f"Starting HTTP server on port {args.port}...")
        mcp.run(transport="http", port=args.port)
    else:
        logger.info("Starting FIBO MCP server in stdio mode...")
        mcp.run()
