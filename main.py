import sys
import json
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP
from rdflib import Graph, URIRef
from rank_bm25 import BM25Okapi

DATA_DIR = Path("./data")
STORE_PATH = DATA_DIR / "fibo.db"

mcp = FastMCP("FIBO")
g: Optional[Graph] = None
bm25: Optional[BM25Okapi] = None
docs: Optional[list] = None

def init():
    """Load FIBO graph and build search index"""
    global g, bm25, docs
    
    if g is not None:
        return g
    
    if not STORE_PATH.exists():
        download_fibo()
    
    g = Graph()
    g.parse(STORE_PATH, format="turtle")
    
    # Build BM25 index
    corpus = []
    docs = []
    
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    
    SELECT ?uri ?label ?definition WHERE {
        ?uri a owl:Class ;
             rdfs:label ?label .
        OPTIONAL { ?uri skos:definition ?definition }
        FILTER(STRSTARTS(STR(?uri), "https://spec.edmcouncil.org/fibo/"))
    }
    """
    
    for row in g.query(query):
        text = str(row.label)
        if row.definition:
            text += " " + str(row.definition)
        
        corpus.append(text.lower().split())
        docs.append({
            "uri": str(row.uri),
            "label": str(row.label),
            "definition": str(row.definition) if row.definition else None
        })
    
    bm25 = BM25Okapi(corpus)
    return g

@mcp.tool()
def traverse(query: str, top_k: int = 5, n_hops: int = 1) -> str:
    """Search and traverse FIBO (Financial Industry Business Ontology) knowledge graph.
    
    Args:
        query: search terms or direct URI
        top_k: number of search results to return (default 5)
        n_hops: depth of graph traversal from concept (default 1)
    
    Returns both search results and full exploration of the top match.
    """
    graph = init()
    
    # Check if query is a URI
    if query.startswith("http"):
        # Direct exploration of URI
        uri_ref = URIRef(query)
        
        outgoing = []
        incoming = []
        
        for p, o in graph.predicate_objects(uri_ref):
            outgoing.append({
                "predicate": str(p).split("/")[-1].split("#")[-1],
                "object": str(o)
            })
        
        for s, p in graph.subject_predicates(uri_ref):
            incoming.append({
                "subject": str(s).split("/")[-1].split("#")[-1],
                "predicate": str(p).split("/")[-1].split("#")[-1]
            })
        
        return json.dumps({
            "uri": query,
            "edges": {
                "outgoing": outgoing,
                "incoming": incoming,
                "total": len(outgoing) + len(incoming)
            }
        }, indent=2)
    
    # Search for concepts
    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)
    
    # Get top results
    top_n = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
    
    search_results = []
    for idx, score in top_n:
        if score > 0:
            search_results.append({
                **docs[idx],
                "score": round(score, 3)
            })
    
    if not search_results:
        return json.dumps({
            "query": query,
            "error": "No matching concepts found"
        }, indent=2)
    
    result = {
        "query": query,
        "search_results": search_results
    }
    
    # Always explore the top result if available
    if search_results:
        top_uri = search_results[0]["uri"]
        uri_ref = URIRef(top_uri)
        
        outgoing = []
        incoming = []
        
        for p, o in graph.predicate_objects(uri_ref):
            outgoing.append({
                "predicate": str(p).split("/")[-1].split("#")[-1],
                "object": str(o)
            })
        
        for s, p in graph.subject_predicates(uri_ref):
            incoming.append({
                "subject": str(s).split("/")[-1].split("#")[-1],
                "predicate": str(p).split("/")[-1].split("#")[-1]  
            })
        
        result["explored"] = {
            "concept": search_results[0]["label"],
            "uri": top_uri,
            "definition": search_results[0]["definition"],
            "edges": {
                "outgoing": outgoing,
                "incoming": incoming,
                "total": len(outgoing) + len(incoming)
            }
        }
    
    return json.dumps(result, indent=2)

@mcp.tool()
def sparql(query: str) -> str:
    """Run SPARQL query on FIBO.
    
    query: SPARQL query string
    
    Returns query results.
    """
    graph = init()
    
    try:
        results = graph.query(query)
        
        output = []
        for row in results:
            output.append({
                str(var): str(row[var]) 
                for var in results.vars 
                if row[var] is not None
            })
        
        return json.dumps({
            "results": output,
            "count": len(output)
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})

def download_fibo():
    """Download FIBO"""
    import subprocess
    import shutil
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    FIBO_DIR = DATA_DIR / "fibo"
    
    if FIBO_DIR.exists():
        shutil.rmtree(FIBO_DIR)
    
    subprocess.run(
        ["git", "clone", "--depth=1", 
         "https://github.com/edmcouncil/fibo.git", str(FIBO_DIR)],
        check=True, capture_output=True
    )
    
    # Load all RDF files
    g = Graph()
    for f in list(FIBO_DIR.rglob("*.rdf")) + list(FIBO_DIR.rglob("*.owl")):
        try:
            g.parse(f, format="xml")
        except:
            pass
    
    g.serialize(STORE_PATH, format="turtle")
    shutil.rmtree(FIBO_DIR)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-download", action="store_true", help="Force re-download FIBO data")
    parser.add_argument("--http", action="store_true", help="Run as HTTP server")
    parser.add_argument("--port", type=int, default=8000, help="HTTP server port")
    args = parser.parse_args()
    
    if args.force_download:
        print("Force downloading FIBO...")
        STORE_PATH.unlink(missing_ok=True)
        download_fibo()
        print("FIBO download complete")
        sys.exit(0)
    
    init()
    
    if args.http:
        mcp.run(transport="http", port=args.port)
    else:
        mcp.run()