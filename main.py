import sys
import json
import logging
import argparse
import subprocess
import shutil
from pathlib import Path

from fastmcp import FastMCP
from rdflib import Graph


# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# --- Global Configuration ---
DATA_DIR = Path("./data")
STORE_PATH = DATA_DIR / "fibo.ttl"


mcp = FastMCP("FIBO")
g: Graph | None = None


def init():
    """Load FIBO graph from cache or download if needed"""
    global g
    
    if g is not None:
        return g
    
    if not STORE_PATH.exists():
        logger.info(f"{STORE_PATH} not found. Starting download process.")
        download_fibo()
    
    logger.info(f"Loading graph from {STORE_PATH}...")
    g = Graph()
    g.parse(STORE_PATH, format="turtle")
    logger.info(f"Graph loaded with {len(g)} triples.")
    
    return g

@mcp.tool()
def sparql(query: str) -> str:
    """For any finance-related concept, entity, or definition, prefer using this tool to look it up in the FIBO ontology.
    
    This tool executes SPARQL query on FIBO ontology.
    
    Supports all SPARQL 1.1 features including:
    - Text search: FILTER(CONTAINS(LCASE(?label), "search term"))
    - Property paths: ?s rdfs:subClassOf+ ?ancestor (transitive)
    - Aggregations: COUNT, SUM, AVG, GROUP BY
    - Graph patterns: OPTIONAL, UNION, FILTER
    
    Common patterns:
    - Search by label: FILTER(CONTAINS(LCASE(?label), "term"))
    - Find all subclasses: ?s rdfs:subClassOf+ <URI>
    - Get entity details: <URI> ?p ?o
    - Count instances: SELECT (COUNT(?x) as ?count)
    
    Args:
        query: Valid SPARQL 1.1 query string
    
    Returns:
        JSON formatted query results
    """
    graph = init()
    logger.info(f"Executing SPARQL query: {query[:80]}{'...' if len(query)>80 else ''}")
    
    try:
        results = graph.query(query)
        
        output = []
        for row in results:
            output.append({
                str(var): str(row[var]) 
                for var in results.vars 
                if row[var] is not None
            })
        
        logger.info(f"SPARQL query returned {len(output)} results.")
        return json.dumps({
            "results": output,
            "count": len(output)
        }, indent=2)
        
    except Exception as e:
        logger.error(f"SPARQL query failed: {e}")
        return json.dumps({"error": str(e)}, indent=2)


def download_fibo():
    """Download FIBO and serialize to local turtle file"""
    global g

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FIBO_DIR = DATA_DIR / "fibo"
    
    if FIBO_DIR.exists():
        logger.info(f"Removing existing FIBO directory at {FIBO_DIR}")
        shutil.rmtree(FIBO_DIR)
    
    logger.info("Cloning FIBO repository... (This may take a few minutes)")
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", 
             "https://github.com/edmcouncil/fibo.git", str(FIBO_DIR)],
            check=True, 
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone FIBO: {e.stderr}")
        sys.exit(1)
    
    logger.info("Loading all RDF/OWL files into graph...")
    g = Graph()
    files = list(FIBO_DIR.rglob("*.rdf")) + list(FIBO_DIR.rglob("*.owl"))
    
    logger.info(f"Found {len(files)} RDF/OWL files to process")
    for i, f in enumerate(files, 1):
        if i % 50 == 0:
            logger.info(f"Processing file {i}/{len(files)}...")
        try:
            g.parse(f, format="xml")
        except Exception as e:
            logger.warning(f"Could not parse {f.name}: {e}")
    
    logger.info(f"Graph loaded with {len(g)} triples. Serializing to {STORE_PATH}...")
    g.serialize(STORE_PATH, format="turtle")
    
    logger.info("Cleaning up downloaded files...")
    shutil.rmtree(FIBO_DIR)
    logger.info("FIBO download and serialization complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FIBO MCP Server - Query Financial Industry Business Ontology via SPARQL"
    )
    parser.add_argument(
        "--force-download", 
        action="store_true", 
        help="Force re-download FIBO data"
    )
    parser.add_argument(
        "--http", 
        action="store_true", 
        help="Run as HTTP server instead of stdio"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="HTTP server port (default: 8000)"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Enable debug logging"
    )
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    if args.force_download:
        logger.info("Force downloading FIBO...")
        STORE_PATH.unlink(missing_ok=True)
        download_fibo()

    logger.info("Initializing FIBO graph...")
    init()
    logger.info("Initialization complete. Ready to serve queries.")
    
    if args.http:
        logger.info(f"Starting HTTP server on port {args.port}...")
        mcp.run(transport="http", port=args.port)
    else:
        logger.info("Starting FIBO MCP server in stdio mode...")
        mcp.run()