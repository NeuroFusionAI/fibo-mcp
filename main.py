import json
import logging
import argparse

from fastmcp import FastMCP

import fibo
from loader import get_graph


# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


mcp = FastMCP("FIBO")


@mcp.tool()
def sparql(query: str) -> str:
    """Execute SPARQL query on FIBO (Financial Industry Business Ontology).

    FIBO core concepts (hub nodes - start searches from these):
    agreement, contract, financial instrument, security, equity instrument,
    share, debt instrument, derivative instrument, credit agreement, loan,
    bond, preferred share, registered security, financial institution,
    financial service provider, legal entity, sovereign state, currency,
    exchange, corporate action, occurrence, pool, collective investment vehicle

    Returns BM25 suggestions when no results found - use these to refine your search.

    Args:
        query: SPARQL 1.1 query. Use FILTER(CONTAINS(LCASE(?label), "term")) for search.

    Returns:
        JSON with results array, count, and suggestions (if count=0)
    """
    result = fibo.sparql(query)
    return json.dumps(result, indent=2)


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
