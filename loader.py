import sys
import re
import logging
import subprocess
import shutil
from pathlib import Path

from rdflib import Graph
from owlrl import DeductiveClosure, OWLRL_Semantics

logger = logging.getLogger(__name__)


def _fix_dates(ttl: str) -> str:
    return re.sub(
        r'"(\d{4})-(\d{1,2})-(\d{1,2})T',
        lambda m: f'"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}T',
        ttl,
    )


# --- Configuration ---
DATA_DIR = Path(__file__).parent / "data"
STORE_PATH = DATA_DIR / "fibo.ttl"
MATERIALIZED_PATH = DATA_DIR / "fibo_materialized.ttl"


_graph: Graph | None = None
_materialized: bool = False


def get_graph(force_download: bool = False, materialize: bool = False) -> Graph:
    """Load FIBO graph from cache, downloading if needed.

    Args:
        force_download: If True, re-download FIBO even if cache exists.
        materialize: If True, expand graph with OWL-RL inferences (cached after first run).

    Returns:
        Loaded RDF graph with FIBO triples.
    """
    global _graph, _materialized

    if _graph is not None and not force_download:
        if materialize and not _materialized:
            _materialize_graph(_graph)
        return _graph

    if force_download:
        logger.info("Force download requested. Removing cached data...")
        STORE_PATH.unlink(missing_ok=True)
        MATERIALIZED_PATH.unlink(missing_ok=True)
        _graph = None
        _materialized = False

    # Try loading pre-materialized graph first (fast path)
    if materialize and MATERIALIZED_PATH.exists():
        logger.info(f"Loading pre-materialized graph from {MATERIALIZED_PATH}...")
        _graph = Graph()
        content = _fix_dates(MATERIALIZED_PATH.read_text())
        _graph.parse(data=content, format="turtle")
        _materialized = True
        logger.info(f"Materialized graph loaded with {len(_graph)} triples.")
        return _graph

    if STORE_PATH.exists():
        logger.info(f"Loading graph from {STORE_PATH}...")
        _graph = Graph()
        content = _fix_dates(STORE_PATH.read_text())
        _graph.parse(data=content, format="turtle")
        logger.info(f"Graph loaded with {len(_graph)} triples.")
        if materialize:
            _materialize_graph(_graph)
        return _graph

    # Download and build graph
    logger.info(f"{STORE_PATH} not found. Starting download process.")
    _graph = _download_and_build()
    if materialize:
        _materialize_graph(_graph)
    return _graph


def _materialize_graph(graph: Graph) -> None:
    """Expand graph with OWL-RL inferences and cache to disk."""
    global _materialized
    if _materialized:
        return

    logger.info("Materializing OWL-RL inferences (this may take ~2 minutes on first run)...")
    before = len(graph)
    DeductiveClosure(OWLRL_Semantics).expand(graph)
    after = len(graph)
    _materialized = True
    logger.info(f"Graph expanded from {before} to {after} triples (+{after - before} inferred)")

    # Cache materialized graph for fast subsequent loads
    logger.info(f"Caching materialized graph to {MATERIALIZED_PATH}...")
    graph.serialize(MATERIALIZED_PATH, format="turtle")
    logger.info("Materialized graph cached.")


def _download_and_build() -> Graph:
    """Download FIBO repository and build graph from RDF/OWL files."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FIBO_DIR = DATA_DIR / "fibo"

    if FIBO_DIR.exists():
        logger.info(f"Removing existing FIBO directory at {FIBO_DIR}")
        shutil.rmtree(FIBO_DIR)

    logger.info("Cloning FIBO repository... (This may take a few minutes)")
    try:
        subprocess.run(
            [
                "git",
                "clone",
                "--depth=1",
                "https://github.com/edmcouncil/fibo.git",
                str(FIBO_DIR),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone FIBO: {e.stderr}")
        sys.exit(1)

    logger.info("Loading all RDF/OWL files into graph...")
    graph = Graph()
    files = list(FIBO_DIR.rglob("*.rdf")) + list(FIBO_DIR.rglob("*.owl"))

    logger.info(f"Found {len(files)} RDF/OWL files to process")
    for i, f in enumerate(files, 1):
        if i % 50 == 0:
            logger.info(f"Processing file {i}/{len(files)}...")
        try:
            graph.parse(f, format="xml")
        except Exception as e:
            logger.warning(f"Could not parse {f.name}: {e}")

    logger.info(
        f"Graph loaded with {len(graph)} triples. Serializing to {STORE_PATH}..."
    )
    graph.serialize(STORE_PATH, format="turtle")

    logger.info("Cleaning up downloaded files...")
    shutil.rmtree(FIBO_DIR)
    logger.info("FIBO download and serialization complete.")

    return graph
