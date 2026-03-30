"""
arango-er-mcp --demo quickstart mode.

Spins up a local ArangoDB Docker container (if needed), loads a sample
company/person dataset, and prints ready-to-use Claude Desktop config.

Run::

    arango-er-mcp --demo

What it does:
  1. Check for a running ArangoDB (localhost:8529 or labeled Docker container)
  2. If none found, start a temporary arangodb:3.12 Docker container
  3. Load ~200 sample company records with intentional duplicates
  4. Run the full ER pipeline on the sample data
  5. Print a summary + Claude Desktop JSON config snippet
  6. Start the MCP server in stdio mode ready for Claude
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from typing import Any, Dict, Optional

from ..utils.constants import DEFAULT_HOST, DEFAULT_PORT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sample data — realistic company duplicates for demo purposes
# ---------------------------------------------------------------------------

SAMPLE_COMPANIES = [
    # Cluster 1: Acme Corp variants
    {"name": "Acme Corporation", "city": "Boston", "state": "MA", "industry": "Software"},
    {"name": "Acme Corp", "city": "Boston", "state": "Massachusetts", "industry": "Software"},
    {"name": "ACME Corp.", "city": "Boston", "state": "MA", "industry": "Tech"},
    # Cluster 2: TechFlow variants
    {"name": "TechFlow Inc", "city": "Austin", "state": "TX", "industry": "SaaS"},
    {"name": "Tech Flow Incorporated", "city": "Austin", "state": "Texas", "industry": "SaaS"},
    {"name": "Techflow Inc.", "city": "Austin", "state": "TX", "industry": "Software"},
    # Cluster 3: Global Dynamics variants
    {"name": "Global Dynamics LLC", "city": "Chicago", "state": "IL", "industry": "Consulting"},
    {"name": "Global Dynamics", "city": "Chicago", "state": "Illinois", "industry": "Consulting"},
    {"name": "GlobalDynamics LLC", "city": "Chicago", "state": "IL", "industry": "Management"},
    # Cluster 4: Pinnacle variants
    {"name": "Pinnacle Solutions", "city": "Seattle", "state": "WA", "industry": "Cloud"},
    {"name": "Pinnacle Solutions Inc", "city": "Seattle", "state": "Washington", "industry": "Cloud"},
    # Cluster 5: NexGen variants
    {"name": "NexGen Systems", "city": "Denver", "state": "CO", "industry": "AI"},
    {"name": "Nexgen Systems Inc", "city": "Denver", "state": "Colorado", "industry": "Artificial Intelligence"},
    {"name": "Next Gen Systems", "city": "Denver", "state": "CO", "industry": "AI"},
    # Distinct companies (true negatives)
    {"name": "BlueSky Analytics", "city": "Miami", "state": "FL", "industry": "Analytics"},
    {"name": "RedRock Ventures", "city": "Phoenix", "state": "AZ", "industry": "Finance"},
    {"name": "Ironclad Security", "city": "New York", "state": "NY", "industry": "Cybersecurity"},
    {"name": "Cloudbase Infrastructure", "city": "Portland", "state": "OR", "industry": "Cloud"},
    {"name": "DataStream Partners", "city": "Atlanta", "state": "GA", "industry": "Data"},
    {"name": "Meridian Health Systems", "city": "Dallas", "state": "TX", "industry": "Healthcare"},
]


# ---------------------------------------------------------------------------
# Docker / ArangoDB helpers
# ---------------------------------------------------------------------------

def _find_running_arango() -> Optional[Dict[str, Any]]:
    """Try localhost, then labeled Docker container."""
    # Try localhost first
    default_url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    try:
        from arango import ArangoClient
        client = ArangoClient(hosts=default_url)
        db = client.db("_system", username="root", password="")
        db.collections()
        return {"host": DEFAULT_HOST, "port": DEFAULT_PORT, "password": ""}
    except Exception as e:
        logger.debug("No ArangoDB on %s:%s with empty password: %s", DEFAULT_HOST, DEFAULT_PORT, e)

    # Try env password
    pw = os.getenv("ARANGO_ROOT_PASSWORD", "")
    if pw:
        try:
            from arango import ArangoClient
            client = ArangoClient(hosts=default_url)
            db = client.db("_system", username="root", password=pw)
            db.collections()
            return {"host": DEFAULT_HOST, "port": DEFAULT_PORT, "password": pw}
        except Exception as e:
            logger.debug("No ArangoDB on %s:%s with env password: %s", DEFAULT_HOST, DEFAULT_PORT, e)

    return None


def _start_demo_container() -> Dict[str, Any]:
    """Start a temporary ArangoDB 3.12 Docker container for the demo."""
    import random
    port = random.randint(28529, 38529)
    password = "demo-password"
    container_name = "arango-er-demo"

    # Kill any previous demo container
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
    )

    print(f"  Starting ArangoDB 3.12 Docker container on port {port}...")
    proc = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{port}:8529",
            "-e", f"ARANGO_ROOT_PASSWORD={password}",
            "--label", "arango-er-demo=true",
            "arangodb:3.12",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Docker failed: {proc.stderr}")

    # Wait for it to be ready — suppress urllib3 retry warnings during
    # startup: ConnectionResetError is expected while ArangoDB initialises
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    import logging as _logging
    _urllib3_logger = _logging.getLogger("urllib3.connectionpool")
    _prev_level = _urllib3_logger.level
    _urllib3_logger.setLevel(_logging.ERROR)

    print("  Waiting for ArangoDB to be ready", end="", flush=True)
    for _ in range(30):
        time.sleep(2)
        try:
            from arango import ArangoClient
            client = ArangoClient(hosts=f"http://localhost:{port}")
            db = client.db("_system", username="root", password=password)
            db.collections()
            _urllib3_logger.setLevel(_prev_level)
            print(" ready!")
            return {"host": "localhost", "port": port, "password": password, "container": container_name}
        except Exception:
            print(".", end="", flush=True)

    _urllib3_logger.setLevel(_prev_level)
    raise RuntimeError("ArangoDB did not become ready within 60 seconds")


# ---------------------------------------------------------------------------
# Demo runner
# ---------------------------------------------------------------------------

def run_demo() -> None:
    """Full demo quickstart: spin up DB, load data, run pipeline, print config."""
    _banner()

    # Step 1: Find or start ArangoDB
    print("\n[1/4] Connecting to ArangoDB...")
    conn = _find_running_arango()
    container_started = False
    if conn:
        print(f"  Found running ArangoDB at {conn['host']}:{conn['port']}")
    else:
        try:
            conn = _start_demo_container()
            container_started = True
        except Exception as exc:
            print(f"\n  ERROR: Could not start Docker container: {exc}")
            print("  Make sure Docker is running, or set ARANGO_ROOT_PASSWORD to connect")
            print(f"  to an existing ArangoDB instance on {DEFAULT_HOST}:{DEFAULT_PORT}.")
            sys.exit(1)

    from arango import ArangoClient
    client = ArangoClient(hosts=f"http://{conn['host']}:{conn['port']}")
    sys_db = client.db("_system", username="root", password=conn["password"])

    # Create demo database
    db_name = "er_demo"
    if sys_db.has_database(db_name):
        sys_db.delete_database(db_name)
    sys_db.create_database(db_name)
    db = client.db(db_name, username="root", password=conn["password"])

    # Step 2: Load sample data
    print("\n[2/4] Loading sample company data...")
    coll = db.create_collection("companies")
    meta = coll.insert_many(SAMPLE_COMPANIES)
    print(f"  Inserted {len(meta)} company records ({len(SAMPLE_COMPANIES)} total, with intentional duplicates)")

    # Step 3: Run ER pipeline
    print("\n[3/4] Running entity resolution pipeline...")
    try:
        from entity_resolution.config.er_config import (
            BlockingConfig, ClusteringConfig, ERPipelineConfig, SimilarityConfig,
        )
        from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline

        cfg = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            edge_collection="companies_similarity_edges",
            cluster_collection="companies_clusters",
            blocking=BlockingConfig(strategy="exact", fields=["name"], max_block_size=500),
            similarity=SimilarityConfig(threshold=0.70),
            clustering=ClusteringConfig(store_results=True),
        )
        pipeline = ConfigurableERPipeline(db=db, config=cfg)
        results = pipeline.run()

        blocking = results.get("blocking", {})
        similarity = results.get("similarity", {})
        clustering = results.get("clustering", {})

        print(f"  Blocking:   {blocking.get('blocks_found', blocking.get('total_unique_pairs', '?'))} candidate pairs")
        print(f"  Similarity: {similarity.get('matches_found', '?')} matches above threshold")
        print(f"  Clusters:   {clustering.get('clusters_found', '?')} entity clusters")
    except Exception as exc:
        print(f"  Pipeline warning: {exc}")
        print("  (Sample data is loaded — MCP tools will still work)")

    # Step 4: Print Claude Desktop config
    print("\n[4/4] Setup complete!")
    _print_claude_config(conn)

    if container_started:
        print("\n  NOTE: Demo ArangoDB container 'arango-er-demo' is still running.")
        print("  Stop it when done with:  docker rm -f arango-er-demo\n")

    DEMO_PORT = 8080
    DEMO_HOST = "127.0.0.1"

    print(f"\nStarting MCP server (SSE / HTTP) on http://{DEMO_HOST}:{DEMO_PORT}/sse")
    print("Use the SSE config above only with clients that support remote HTTP MCP connections.")
    print("For Claude Desktop production use, prefer the stdio config shown above.")
    print("Press Ctrl+C to stop.\n")

    os.environ["ARANGO_HOST"] = conn["host"]
    os.environ["ARANGO_PORT"] = str(conn["port"])
    os.environ["ARANGO_PASSWORD"] = conn["password"]
    os.environ["ARANGO_DATABASE"] = db_name

    from entity_resolution.mcp.server import run_sse_server

    run_sse_server(host=DEMO_HOST, port=DEMO_PORT)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _banner() -> None:
    print("""
╔══════════════════════════════════════════════════════════╗
║     ArangoDB Entity Resolution — MCP Demo Quickstart     ║
║                     v3.2.3                               ║
╚══════════════════════════════════════════════════════════╝

This demo will:
  • Start ArangoDB (or use an existing instance)
  • Load 20 sample company records with intentional duplicates
  • Run the full ER pipeline to find clusters
  • Start the MCP server so Claude/Cursor can explore the results
""")


def _print_claude_config(conn: Dict[str, Any]) -> None:
    # Demo uses SSE transport — Claude Desktop connects via HTTP URL,
    # no subprocess launch needed.
    sse_config = {
        "mcpServers": {
            "entity-resolution-demo": {
                "url": "http://localhost:8080/sse",
            }
        }
    }

    # Also show the stdio config for production use
    stdio_config = {
        "mcpServers": {
            "entity-resolution": {
                "command": "arango-er-mcp",
                "env": {
                    "ARANGO_HOST": conn["host"],
                    "ARANGO_PORT": str(conn["port"]),
                    "ARANGO_PASSWORD": conn["password"],
                    "ARANGO_DATABASE": "er_demo",
                },
            }
        }
    }

    claude_config_path = os.path.expanduser(
        "~/Library/Application Support/Claude/claude_desktop_config.json"
    )

    print("  Demo server (SSE) — add to Claude Desktop config:")
    print(f"  ({claude_config_path})")
    print()
    print(json.dumps(sse_config, indent=2))
    print()
    print("  For production (stdio, Claude Desktop launches the process):")
    print(json.dumps(stdio_config, indent=2))
    print()
    print("  Then tell Claude:  'List the entity clusters in my companies collection'")
