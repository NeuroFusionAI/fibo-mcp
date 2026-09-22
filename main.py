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
def search(term: str) -> str:
    """Find FIBO classes when financial terminology needs clarification.

Returns ranked candidates with queryable identifiers and definitions. A search
match is a lookup hint, not proof of equivalence. Use inspect(identifier) to
check a candidate's local relationships; use sparql(query) for graph patterns.
FIBO provides ontology semantics, not company financials, prices, or forecasts.
Use these tools when that semantic context helps the task.
"""

    return fibo.search(term)


@mcp.tool()
def sparql(query: str) -> str:
    """Run a read-only SPARQL SELECT query over FIBO's ontology graph.

Use search(term) to discover identifiers and inspect(identifier) for a class's
definition and direct relationships. Use SPARQL for more specific graph queries.
The rdf, rdfs, owl, skos and loaded FIBO module prefixes are available. Reuse
returned CURIEs or <absolute IRIs>; do not guess identifiers. Add a LIMIT.
Example: SELECT ?parent ?label WHERE { fibo-sec-eq-eq:Share rdfs:subClassOf ?parent .
?parent rdfs:label ?label } LIMIT 10
Returns compact JSON. Ontology relationships do not establish probabilities or
facts about a particular company's accounts.
"""

    return fibo.sparql(query)


@mcp.tool()
def inspect(identifier: str, limit: int = 10) -> str:
    """Resolve a discovered FIBO identifier to its local semantic neighborhood.

Accepts a returned CURIE or absolute IRI. Returns compact JSON with labels,
definitions, direct parent/child classes, and direct OWL restrictions. Use this
after search(term) when these details are needed to interpret a candidate.
"""

    return fibo.inspect(identifier, limit)


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
        help="Enable OWL-RL profile materialization (adds startup time, cached after). Recommended for inference-heavy queries.",
    )
    parser.add_argument(
        "--http", action="store_true", help="Run as HTTP server instead of stdio"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="HTTP server port (default: 8000)"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="HTTP bind host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--allow-remote-http",
        action="store_true",
        help="Acknowledge that a non-loopback HTTP listener needs external authentication and rate limiting",
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
        logger.info("Tip: Use --materialize for OWL-RL inference; the expanded graph is cached after the first run")

    logger.info("Pre-building BM25 search index...")
    fibo._get_bm25()

    logger.info("Initialization complete. Ready to serve queries.")

    if args.http:
        if args.host not in {"127.0.0.1", "localhost", "::1"} and not args.allow_remote_http:
            parser.error("non-loopback --host requires --allow-remote-http")
        logger.info(f"Starting HTTP server on {args.host}:{args.port}...")
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        logger.info("Starting FIBO MCP server in stdio mode...")
        mcp.run()
