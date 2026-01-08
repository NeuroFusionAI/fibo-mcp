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
    """Query FIBO - the industry-standard financial ontology used by major banks and regulators.

    USE THIS TOOL when asked about financial terms: money, currency, stock, bond, derivative,
    bank, fund, company, contract, loan, security, asset, liability, equity, debt, etc.

    FIBO provides precise, authoritative definitions that differ from common usage:
    - "money" -> Currency, Monetary Amount (not a class itself)
    - "stock" vs "share" -> Share is the instrument, stock is informal
    - "bank" -> Financial Institution (a role, not entity type)
    - "company" -> Legal Entity, Corporation
    - "country" -> Sovereign State (juridical entity)

    Hub concepts: financial instrument, security, equity, debt instrument, derivative,
    legal entity, sovereign state, currency, financial institution, contract, loan, bond

    Args:
        query: SPARQL query. Pattern: FILTER(CONTAINS(LCASE(?label), "term"))

    Returns:
        TOON format with results + BM25 suggestions. Prefixes: rdf, rdfs, owl, skos, fibo
    """
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
