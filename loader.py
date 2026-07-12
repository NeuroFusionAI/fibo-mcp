import re
import os
import logging
import subprocess
import shutil
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF
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
REVISION_PATH = DATA_DIR / "fibo_revision.txt"
FIBO_REVISION = os.environ.get(
    "FIBO_REVISION",
    "f59157fe156e3d91b1c045222d0a7dc06b7d78a2",
).lower()
if not re.fullmatch(r"[0-9a-fA-F]{40}", FIBO_REVISION):
    raise ValueError("FIBO_REVISION must be a full 40-character Git commit hash")


_graph: Graph | None = None
_materialized: bool = False


def graph_stats(graph: Graph | None = None) -> dict[str, int | str]:
    """Return reproducible base-graph counts with explicit definitions."""
    if graph is None:
        graph = get_graph()
    property_types = {
        RDF.Property,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
    }
    properties = {
        subject
        for property_type in property_types
        for subject in graph.subjects(RDF.type, property_type)
    }
    return {
        "revision": FIBO_REVISION,
        "triples": len(graph),
        "owl_classes": len(set(graph.subjects(RDF.type, OWL.Class))),
        "typed_properties": len(properties),
        "uri_subjects": len({
            subject for subject in graph.subjects() if isinstance(subject, URIRef)
        }),
    }


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
        REVISION_PATH.unlink(missing_ok=True)
        _graph = None
        _materialized = False

    cached_revision = REVISION_PATH.read_text().strip() if REVISION_PATH.exists() else None
    if cached_revision != FIBO_REVISION:
        if STORE_PATH.exists() or MATERIALIZED_PATH.exists():
            logger.warning(
                "Discarding FIBO cache for revision %s; expected %s",
                cached_revision or "unknown",
                FIBO_REVISION,
            )
        STORE_PATH.unlink(missing_ok=True)
        MATERIALIZED_PATH.unlink(missing_ok=True)

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

    logger.info("Materializing OWL-RL inferences; runtime depends on the local environment...")
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

    logger.info("Fetching pinned FIBO revision %s...", FIBO_REVISION)
    try:
        FIBO_DIR.mkdir()
        commands = [
            ["git", "init", str(FIBO_DIR)],
            ["git", "-C", str(FIBO_DIR), "remote", "add", "origin", "https://github.com/edmcouncil/fibo.git"],
            ["git", "-C", str(FIBO_DIR), "fetch", "--depth=1", "origin", FIBO_REVISION],
            ["git", "-C", str(FIBO_DIR), "checkout", "--detach", "FETCH_HEAD"],
        ]
        for command in commands:
            subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone FIBO: {e.stderr}")
        shutil.rmtree(FIBO_DIR, ignore_errors=True)
        raise RuntimeError(f"Failed to fetch pinned FIBO revision {FIBO_REVISION}") from e

    logger.info("Loading all RDF/OWL files into graph...")
    graph = Graph()
    files = list(FIBO_DIR.rglob("*.rdf")) + list(FIBO_DIR.rglob("*.owl"))

    logger.info(f"Found {len(files)} RDF/OWL files to process")
    parse_errors: list[str] = []
    for i, f in enumerate(files, 1):
        if i % 50 == 0:
            logger.info(f"Processing file {i}/{len(files)}...")
        try:
            graph.parse(f, format="xml")
        except Exception as e:
            parse_errors.append(f"{f}: {e}")

    if parse_errors:
        sample = "\n".join(parse_errors[:10])
        shutil.rmtree(FIBO_DIR, ignore_errors=True)
        raise RuntimeError(
            f"FIBO build aborted: {len(parse_errors)} RDF/OWL files failed to parse.\n{sample}"
        )

    logger.info(
        f"Graph loaded with {len(graph)} triples. Serializing to {STORE_PATH}..."
    )
    graph.serialize(STORE_PATH, format="turtle")
    REVISION_PATH.write_text(FIBO_REVISION + "\n")

    logger.info("Cleaning up downloaded files...")
    shutil.rmtree(FIBO_DIR)
    logger.info("FIBO download and serialization complete.")

    return graph
