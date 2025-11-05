import sys, subprocess, logging, argparse
from pathlib import Path
from datetime import datetime
from fastmcp import FastMCP
from rdflib import Graph

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

DATA_DIR = Path("./data")
FIBO_DIR = DATA_DIR / "fibo"
STORE_PATH = DATA_DIR / "fibo.db"
UPDATE_CHECK = DATA_DIR / "last_check.txt"

mcp = FastMCP("FIBO")
g = None

def init_graph():
  global g
  if g is not None:
    return g

  logger.info("initializing rdflib graph")
  g = Graph()

  if STORE_PATH.exists():
    logger.info(f"loading from cache: {STORE_PATH}")
    g.parse(STORE_PATH, format="turtle")
    logger.info(f"loaded {len(g)} triples")
  else:
    logger.info("cache not found, running first-time setup...")
    logger.info("downloading + loading FIBO ontology...")
    if not download_fibo():
      logger.error("setup failed")
      sys.exit(1)
    if not load_fibo():
      logger.error("setup failed")
      sys.exit(1)
    logger.info("setup complete, starting server...")
    g.parse(STORE_PATH, format="turtle")
    logger.info(f"loaded {len(g)} triples")

  return g

def query(sparql_query):
  g = init_graph()
  results = g.query(sparql_query)

  # convert to sparql json format
  bindings = []
  for row in results:
    binding = {}
    for var in results.vars:
      val = row[var]
      if val is not None:
        val_str = str(val)
        binding[str(var)] = {
          "type": "uri" if val_str.startswith("http") else "literal",
          "value": val_str
        }
    bindings.append(binding)

  import json
  return json.dumps({
    "head": {"vars": [str(v) for v in results.vars]},
    "results": {"bindings": bindings}
  })

# basic tools
def _sparql_query(sparql_query: str) -> str:
  return query(sparql_query)

@mcp.tool()
def sparql_query(query: str) -> str:
  """Run custom SPARQL query. For power users only: aggregations, filters, paths, counts.

  STOP: Don't use this for exploration or searching. Use search_by_label (with multiple terms) or list_classes().
  Only use for specific analytical queries the other tools can't handle."""
  return _sparql_query(query)

# Discovery tools (use these first)
@mcp.tool()
def search_by_label(search_term: str, limit: int = 20) -> str:
  """Find entities in FIBO by searching labels. Start here for any query.

  EFFICIENT USAGE - Use comma-separated synonyms in ONE call:
  ✓ "currency,monetary,money"  ✗ Multiple separate calls
  ✓ "jurisdiction,government"  ✗ Just "country" (not in FIBO)

  FIBO uses formal financial terminology. Common domains:
  • Financial: currency, exchange, security, instrument, derivative, bond, swap, option
  • Organizations: organization, corporation, institution, entity, party
  • Legal: agreement, contract, jurisdiction, law, regulation, obligation
  • Markets: market, equity, debt, trading, settlement
  • Accounting: asset, liability, account, income, expense
  • Time: date, period, maturity, duration, schedule

  Returns JSON with: entity URIs, labels, types, definitions (when available)
  Special response fields:
  • _suggestion: Alt matches when no direct results (check this!)
  • _next_steps: Guidance on successful results"""
  lim = min(max(limit, 1), 100)

  # Support multiple search terms separated by comma
  terms = [t.strip() for t in search_term.split(",") if t.strip()]
  if len(terms) > 1:
    # Multiple terms: create OR filter
    filters = " || ".join([f'CONTAINS(LCASE(STR(?label)), LCASE("{term}"))' for term in terms])
    filter_clause = f"FILTER({filters})"
  else:
    # Single term
    filter_clause = f'FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{terms[0]}")))'

  q = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT DISTINCT ?entity ?label ?type ?definition WHERE {{
      ?entity rdfs:label ?label .
      OPTIONAL {{ ?entity a ?type }}
      OPTIONAL {{ ?entity skos:definition ?definition }}
      {filter_clause}
    }} ORDER BY
      (IF(?type = owl:Class, 0, 1))
      (IF(BOUND(?definition), 0, 1))
      ?label
    LIMIT {lim}
  """
  result = query(q)

  # Add guidance based on results
  import json
  from rdflib import RDF, RDFS, OWL
  from rdflib.namespace import SKOS

  data = json.loads(result)

  if len(data["results"]["bindings"]) == 0:
    # Try to find related classes using rdflib graph methods
    init_graph()  # Ensure graph is loaded
    related = []

    # Search for classes with URIs containing search terms
    for term in terms[:3]:  # Check first 3 terms to avoid too much iteration
      term_lower = term.lower()
      for subj in g.subjects(RDF.type, OWL.Class):
        uri_str = str(subj)
        if "spec.edmcouncil.org/fibo/ontology" in uri_str and term_lower in uri_str.lower():
          label = g.value(subj, RDFS.label)
          definition = g.value(subj, SKOS.definition)
          related.append({
            "class": {"type": "uri", "value": uri_str},
            "label": {"type": "literal", "value": str(label)} if label else None,
            "definition": {"type": "literal", "value": str(definition)} if definition else None
          })
          if len(related) >= 5:
            break
      if len(related) >= 5:
        break

    if related:
      data["_suggestion"] = {
        "message": f"No direct label match for '{search_term}', but found {len(related)} related class(es) in FIBO structure:",
        "action": "Use get_entity_details() on these URIs to explore them",
        "related_classes": related
      }
    else:
      # No URI matches either - provide guidance
      data["_suggestion"] = {
        "message": f"No matches found for '{search_term}' in FIBO labels or class URIs.",
        "action": "Try list_classes() to browse available FIBO concepts, or search with broader/alternate financial terminology.",
        "hint": f"Searched terms: {', '.join(terms[:5])}"
      }
  else:
    # Found results - add hint about next steps
    data["_next_steps"] = "Found entities. Use get_entity_details(uri) for full information, or if this is a class, use find_by_type(uri) to see instances."

  return json.dumps(data)

@mcp.tool()
def explore_concept(concept: str, limit: int = 5) -> str:
  """ONE-CALL concept exploration - most efficient for "what is X?" queries.

  Combines search + entity details + hierarchy in a single call. Use this INSTEAD of:
  1. search_by_label → get_entity_details → explore_hierarchy (3 calls)
  2. Multiple searches with different terms (N calls)

  Automatically tries synonym expansion (e.g., "country" → "jurisdiction,government,polity").

  Returns: Comprehensive JSON with search results, top entity details, class hierarchy,
  and related concepts. Check 'summary' field for quick answer.

  Example: explore_concept("country") returns everything about jurisdiction/government concepts."""

  import json

  # Auto-expand common financial concept synonyms
  expansions = {
    "country": "country,jurisdiction,government,polity,sovereign,nation",
    "company": "company,organization,corporation,entity,firm",
    "person": "person,individual,party,agent",
    "bank": "bank,institution,depositary,financial",
    "money": "money,currency,monetary,funds",
  }

  search_term = expansions.get(concept.lower(), concept)

  # Step 1: Search (build SPARQL manually since can't call decorated functions)
  lim = min(max(limit, 1), 100)
  terms = [t.strip() for t in search_term.split(",") if t.strip()]

  if len(terms) > 1:
    filters = " || ".join([f'CONTAINS(LCASE(STR(?label)), LCASE("{term}"))' for term in terms])
    filter_clause = f"FILTER({filters})"
  else:
    filter_clause = f'FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{terms[0]}")))'

  search_q = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT DISTINCT ?entity ?label ?type ?definition WHERE {{
      ?entity rdfs:label ?label .
      OPTIONAL {{ ?entity a ?type }}
      OPTIONAL {{ ?entity skos:definition ?definition }}
      {filter_clause}
    }} ORDER BY
      (IF(?type = owl:Class, 0, 1))
      (IF(BOUND(?definition), 0, 1))
      ?label
    LIMIT {lim}
  """
  search_result = query(search_q)
  search_data = json.loads(search_result)

  # If no results, return early with suggestion
  if len(search_data["results"]["bindings"]) == 0:
    return json.dumps({
      "summary": f"No FIBO entities found for '{concept}'",
      "search": search_data,
      "_suggestion": f"Try broader terminology or list_classes(). Searched: {search_term}"
    })

  # Step 2: Get details on top result
  top_entity = search_data["results"]["bindings"][0]
  top_uri = top_entity["entity"]["value"]
  top_label = top_entity.get("label", {}).get("value", concept)

  details_q = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?property ?value ?valueLabel WHERE {{
      <{top_uri}> ?property ?value .
      OPTIONAL {{ ?value rdfs:label ?valueLabel }}
    }} LIMIT 20
  """
  details_result = query(details_q)
  details_data = json.loads(details_result)

  # Step 3: Get hierarchy if it's a class
  hierarchy_data = {"results": {"bindings": []}}
  if "type" in top_entity:
    type_uri = top_entity["type"]["value"]
    if "Class" in type_uri:
      hierarchy_q = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?related ?label ?type WHERE {{
          {{ <{top_uri}> rdfs:subClassOf+ ?related . BIND("superclass" AS ?type) }}
          UNION
          {{ ?related rdfs:subClassOf+ <{top_uri}> . BIND("subclass" AS ?type) }}
          OPTIONAL {{ ?related rdfs:label ?label }}
        }} ORDER BY ?type ?related LIMIT 10
      """
      hierarchy_result = query(hierarchy_q)
      hierarchy_data = json.loads(hierarchy_result)

  # Step 4: Build summary
  definition = top_entity.get("definition", {}).get("value", "No definition available")

  return json.dumps({
    "summary": f"'{top_label}' in FIBO: {definition[:200]}...",
    "top_result": top_entity,
    "details": details_data,
    "hierarchy": hierarchy_data,
    "all_search_results": search_data,
    "_note": f"Explored '{concept}' with auto-expansion to '{search_term}'"
  })

@mcp.tool()
def list_classes(namespace: str = "https://spec.edmcouncil.org/fibo/ontology/", limit: int = 30) -> str:
  """Browse FIBO classes by popularity (instance count). Use when search_by_label returns no results.

  Returns: Classes with labels, definitions, and instance counts. Use this to discover what entity types exist in FIBO."""
  lim = min(max(limit, 1), 100)
  q = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT DISTINCT ?class ?label ?definition (COUNT(?instance) as ?count) WHERE {{
      ?class a owl:Class .
      OPTIONAL {{ ?class rdfs:label ?label }}
      OPTIONAL {{ ?class skos:definition ?definition }}
      OPTIONAL {{ ?instance a ?class }}
      FILTER(STRSTARTS(STR(?class), "{namespace}"))
      FILTER(!ISBLANK(?class))
    }} GROUP BY ?class ?label ?definition ORDER BY DESC(?count) ?label LIMIT {lim}
  """
  return query(q)

# Detail tools (use after finding URIs)
@mcp.tool()
def get_entity_details(uri: str, limit: int = 50) -> str:
  """Get ALL properties and values of an entity. Comprehensive but token-heavy. Use after search_by_label."""
  lim = min(max(limit, 1), 200)
  q = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?property ?value ?valueLabel WHERE {{
      <{uri}> ?property ?value .
      OPTIONAL {{ ?value rdfs:label ?valueLabel }}
    }} LIMIT {lim}
  """
  return query(q)

@mcp.tool()
def find_by_type(type_uri: str, limit: int = 30) -> str:
  """List all entities of a specific type/class with their definitions. Use after finding a class URI from list_classes."""
  lim = min(max(limit, 1), 200)
  q = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT DISTINCT ?entity ?label ?definition WHERE {{
      ?entity a <{type_uri}> .
      OPTIONAL {{ ?entity rdfs:label ?label }}
      OPTIONAL {{ ?entity skos:definition ?definition }}
    }} ORDER BY ?label LIMIT {lim}
  """
  return query(q)

# Navigation tools (explore relationships)
@mcp.tool()
def explore_hierarchy(uri: str, direction: str = "both", limit: int = 30) -> str:
  """Navigate class hierarchy (multi-hop). Gets superclasses (up), subclasses (down), or both. Use for taxonomies."""
  lim = min(max(limit, 1), 200)
  patterns = {
    "up": f"<{uri}> rdfs:subClassOf+ ?related",
    "down": f"?related rdfs:subClassOf+ <{uri}>",
    "both": f"{{ <{uri}> rdfs:subClassOf+ ?related . BIND(\"superclass\" AS ?type) }} UNION {{ ?related rdfs:subClassOf+ <{uri}> . BIND(\"subclass\" AS ?type) }}"
  }
  q = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?related ?label ?type WHERE {{
      {patterns.get(direction, patterns['both'])}
      OPTIONAL {{ ?related rdfs:label ?label }}
    }} ORDER BY ?type ?related LIMIT {lim}
  """
  return query(q)

@mcp.tool()
def explore_neighbors(uri: str, include_incoming: bool = True, limit: int = 30) -> str:
  """Find direct connections (1-hop). Shows which entities connect via properties. Different from get_entity_details which shows property values."""
  lim = min(max(limit, 1), 200)
  if include_incoming:
    where = f"""
      {{ <{uri}> ?property ?related . BIND("outgoing" AS ?direction) }}
      UNION
      {{ ?related ?property <{uri}> . BIND("incoming" AS ?direction) }}
    """
  else:
    where = f"<{uri}> ?property ?related"

  q = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?property ?related ?label ?direction WHERE {{
      {where}
      FILTER(isURI(?related))
      OPTIONAL {{ ?related rdfs:label ?label }}
    }} ORDER BY ?direction ?property LIMIT {lim}
  """
  return query(q)

@mcp.tool()
def find_path(from_uri: str, to_uri: str, max_depth: int = 2, limit: int = 20) -> str:
  """Find connecting path between two entities. Shows how entities are related through intermediate nodes."""
  md = min(max(max_depth, 1), 3)
  lim = min(max(limit, 1), 100)
  queries = {
    1: f"SELECT DISTINCT ?property ?propertyLabel WHERE {{ <{from_uri}> ?property <{to_uri}> . OPTIONAL {{ ?property rdfs:label ?propertyLabel }} }} LIMIT {lim}",
    2: f"SELECT DISTINCT ?intermediate ?label ?prop1 ?prop2 WHERE {{ <{from_uri}> ?prop1 ?intermediate . ?intermediate ?prop2 <{to_uri}> . OPTIONAL {{ ?intermediate rdfs:label ?label }} FILTER(?intermediate != <{from_uri}> && ?intermediate != <{to_uri}>) }} LIMIT {lim}",
    3: f"SELECT DISTINCT ?intermediate1 ?label1 ?intermediate2 ?label2 ?prop1 ?prop2 ?prop3 WHERE {{ <{from_uri}> ?prop1 ?intermediate1 . ?intermediate1 ?prop2 ?intermediate2 . ?intermediate2 ?prop3 <{to_uri}> . OPTIONAL {{ ?intermediate1 rdfs:label ?label1 }} OPTIONAL {{ ?intermediate2 rdfs:label ?label2 }} FILTER(?intermediate1 != <{from_uri}> && ?intermediate1 != <{to_uri}>) FILTER(?intermediate2 != <{from_uri}> && ?intermediate2 != <{to_uri}>) FILTER(?intermediate1 != ?intermediate2) }} LIMIT {lim}"
  }
  return query(f"PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> {queries[md]}")

# setup
def should_check_updates():
  """Check if we should check for FIBO updates (once per day)."""
  if not UPDATE_CHECK.exists():
    return True

  try:
    last_check = datetime.fromisoformat(UPDATE_CHECK.read_text().strip())
    return (datetime.now() - last_check).days >= 1
  except Exception as e:
    logger.warning(f"failed to read last check time: {e}")
    return True

def get_remote_commit_hash():
  """Get the latest commit hash from FIBO GitHub repo."""
  try:
    result = subprocess.run(
      ["git", "ls-remote", "https://github.com/edmcouncil/fibo.git", "HEAD"],
      capture_output=True,
      text=True,
      check=True,
      timeout=10
    )
    return result.stdout.split()[0]
  except Exception as e:
    logger.warning(f"failed to get remote commit hash: {e}")
    return None

def get_local_commit_hash():
  """Get the commit hash of local FIBO repo."""
  if not FIBO_DIR.exists() or not (FIBO_DIR / ".git").exists():
    return None

  try:
    result = subprocess.run(
      ["git", "-C", str(FIBO_DIR), "rev-parse", "HEAD"],
      capture_output=True,
      text=True,
      check=True
    )
    return result.stdout.strip()
  except Exception as e:
    logger.warning(f"failed to get local commit hash: {e}")
    return None

def needs_update():
  """Check if FIBO needs to be updated."""
  if not STORE_PATH.exists():
    logger.info("no cache found, need to download")
    return True

  remote_hash = get_remote_commit_hash()
  if remote_hash is None:
    logger.info("cannot check remote, using existing cache")
    return False

  local_hash = get_local_commit_hash()
  if local_hash is None:
    logger.info("no local repo, checking if cache is recent")
    # If cache exists but no local repo, assume it's from cleanup - don't re-download unless forced
    return False

  if remote_hash != local_hash:
    logger.info(f"update available: local {local_hash[:8]} -> remote {remote_hash[:8]}")
    return True

  logger.info("fibo is up to date")
  return False

def download_fibo(force=False):
  """Download FIBO ontology from GitHub."""
  # Check if we need to update
  if not force and not should_check_updates():
    if FIBO_DIR.exists() and (FIBO_DIR / "FND").exists():
      logger.info("fibo exists, skipping update check (checked recently)")
      return True

  # Mark that we checked
  DATA_DIR.mkdir(parents=True, exist_ok=True)
  UPDATE_CHECK.write_text(datetime.now().isoformat())

  # Check if update is needed
  if not force and not needs_update():
    if FIBO_DIR.exists() and (FIBO_DIR / "FND").exists():
      return True

  # Download or update
  if FIBO_DIR.exists():
    logger.info(f"removing old fibo at {FIBO_DIR}")
    import shutil
    shutil.rmtree(FIBO_DIR)

  logger.info("downloading fibo ontology from github")
  try:
    subprocess.run(["git", "clone", "--depth=1", "https://github.com/edmcouncil/fibo.git", str(FIBO_DIR)], check=True)
    logger.info("fibo downloaded successfully")
    return True
  except Exception as e:
    logger.error(f"failed to download fibo: {e}")
    return False

def load_fibo(cleanup=True):
  logger.info("loading fibo into rdflib")
  g = Graph()

  files = list(FIBO_DIR.rglob("*.rdf")) + list(FIBO_DIR.rglob("*.owl"))

  if not files:
    logger.error("no rdf/owl files found")
    return False

  logger.info(f"found {len(files)} files, loading all")
  for i, f in enumerate(files, 1):
    try:
      g.parse(f, format="xml")
      if i % 10 == 0:
        logger.info(f"loaded {i}/{len(files)} files, {len(g)} triples")
    except Exception as e:
      logger.warning(f"failed to load {f.name}: {e}")

  logger.info(f"total triples: {len(g)}")

  logger.info(f"saving to cache: {STORE_PATH}")
  DATA_DIR.mkdir(parents=True, exist_ok=True)
  g.serialize(destination=str(STORE_PATH), format="turtle")
  logger.info("cache saved successfully")

  if cleanup:
    import shutil
    logger.info("cleaning up fibo source directory")
    shutil.rmtree(FIBO_DIR)
    logger.info(f"removed {FIBO_DIR}")

  return True

def setup(force=False):
  logger.info("starting fibo ontology setup")

  if not download_fibo(force=force):
    sys.exit(1)

  if not load_fibo():
    sys.exit(1)

  logger.info("setup completed successfully")

def run_stdio():
  init_graph()
  logger.info(f"starting fibo mcp in stdio mode")
  logger.info(f"graph loaded with {len(g)} triples")
  mcp.run()

def run_http(port, host):
  from starlette.applications import Starlette
  from starlette.routing import Route
  from starlette.responses import JSONResponse
  import uvicorn

  init_graph()

  async def health(request):
    return JSONResponse({"status": "ok", "triples": len(g)})

  logger.info(f"starting fibo mcp in http mode")
  logger.info(f"host: {host}:{port}")
  logger.info(f"graph loaded with {len(g)} triples")

  mcp_app = mcp.http_app(path="/mcp")
  app = Starlette(routes=[Route("/health", health)], lifespan=mcp_app.lifespan)
  app.routes.extend(mcp_app.routes)

  logger.info(f"server ready at http://{host}:{port}/mcp")
  uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="FIBO MCP")
  parser.add_argument("--setup", action="store_true", help="download and load fibo")
  parser.add_argument("--force-update", action="store_true", help="force re-download fibo (ignore cache)")
  parser.add_argument("--http", action="store_true", help="run in http mode")
  parser.add_argument("--port", type=int, default=8000, help="http port")
  parser.add_argument("--host", default="0.0.0.0", help="http host")
  parser.add_argument("--verbose", "-v", action="store_true", help="enable debug logging")
  args = parser.parse_args()

  if args.verbose:
    logger.setLevel(logging.DEBUG)

  if args.setup:
    setup(force=args.force_update)
  elif args.http:
    run_http(args.port, args.host)
  else:
    run_stdio()
