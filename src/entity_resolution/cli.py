"""
Command Line Interface for ArangoDB Entity Resolution.
"""

from __future__ import annotations

import click
import json
import sys
from typing import Any, Callable, Dict

from arango import ArangoClient

from .core.configurable_pipeline import ConfigurableERPipeline
from .mcp.tools.cluster import run_get_clusters
from .mcp.tools.pipeline import run_pipeline_status
from .services.ab_evaluation_runner import run_blocking_benchmark
from .services.cluster_export_service import ClusterExportService
from .utils.config import DatabaseConfig
from .utils.constants import get_version_string
from .utils.database import get_connection_args, get_database

@click.group()
@click.version_option(version=get_version_string())
def main():
    """ArangoDB Entity Resolution CLI."""
    pass


def connection_options(func: Callable[..., Any]) -> Callable[..., Any]:
    """Shared database connection options for CLI commands."""
    options = [
        click.option("--password", "-p", help="Password."),
        click.option("--username", "-u", help="Username."),
        click.option("--port", type=int, help="ArangoDB port."),
        click.option("--host", help="ArangoDB host."),
        click.option("--database", "-d", help="Database name (overrides config)."),
    ]
    for option in options:
        func = option(func)
    return func


def _resolve_connection_args(
    database: str | None,
    host: str | None,
    port: int | None,
    username: str | None,
    password: str | None,
) -> Dict[str, Any]:
    """Merge CLI overrides onto configured connection defaults."""
    try:
        args = get_connection_args()
    except Exception:
        defaults = DatabaseConfig()
        args = {
            "host": defaults.host,
            "port": defaults.port,
            "username": defaults.username,
            "password": defaults.password,
            "database": defaults.database,
        }
    if database is not None:
        args["database"] = database
    if host is not None:
        args["host"] = host
    if port is not None:
        args["port"] = port
    if username is not None:
        args["username"] = username
    if password is not None:
        args["password"] = password
    return args


def _get_db_from_options(
    database: str | None,
    host: str | None,
    port: int | None,
    username: str | None,
    password: str | None,
):
    """Connect using config defaults unless CLI overrides require a direct client."""
    args = _resolve_connection_args(database, host, port, username, password)
    if host is None and port is None and username is None and password is None:
        return get_database(args["database"])

    client = ArangoClient(hosts=f"http://{args['host']}:{args['port']}")
    db = client.db(args["database"], username=args["username"], password=args["password"])
    db.properties()
    return db


def _emit_json(payload: Any) -> None:
    """Write JSON to stdout with stable formatting."""
    click.echo(json.dumps(payload, indent=2))


@main.command()
@click.option('--config', '-c', type=click.Path(exists=True), required=True, help='Path to YAML/JSON configuration file.')
@connection_options
def run(config, database, host, port, username, password):
    """Run an entity resolution pipeline from a configuration file."""
    try:
        db = _get_db_from_options(database, host, port, username, password)
        # Initialize and run pipeline
        pipeline = ConfigurableERPipeline(db=db, config_path=config)
        results = pipeline.run()
        
        click.echo(click.style("\nPipeline execution successful!", fg="green", bold=True))
        _emit_json(results)
        
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


@main.command()
@click.option("--collection", required=True, help="Source collection name.")
@click.option("--edge-collection", help="Similarity edge collection override.")
@connection_options
def status(collection, edge_collection, database, host, port, username, password):
    """Show pipeline status for a collection."""
    try:
        conn = _resolve_connection_args(database, host, port, username, password)
        result = run_pipeline_status(
            **conn,
            collection=collection,
            edge_collection=edge_collection,
        )
        _emit_json(result)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


@main.command()
@click.option("--collection", required=True, help="Source collection name.")
@click.option("--limit", type=int, default=50, show_default=True, help="Maximum clusters to return.")
@click.option("--min-size", type=int, default=2, show_default=True, help="Minimum cluster size.")
@connection_options
def clusters(collection, limit, min_size, database, host, port, username, password):
    """List stored clusters and quality signals."""
    try:
        conn = _resolve_connection_args(database, host, port, username, password)
        result = run_get_clusters(
            **conn,
            collection=collection,
            limit=limit,
            min_size=min_size,
        )
        _emit_json(result)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


@main.command()
@click.option("--collection", required=True, help="Source collection name.")
@click.option("--cluster-collection", help="Stored cluster collection override.")
@click.option("--edge-collection", help="Similarity edge collection override.")
@click.option("--output-dir", required=True, type=click.Path(file_okay=False), help="Directory for JSON/CSV export artifacts.")
@click.option("--filename-prefix", default="cluster_export", show_default=True, help="Filename prefix for exported artifacts.")
@click.option("--limit", type=int, help="Optional maximum number of clusters to export.")
@connection_options
def export(
    collection,
    cluster_collection,
    edge_collection,
    output_dir,
    filename_prefix,
    limit,
    database,
    host,
    port,
    username,
    password,
):
    """Export cluster results to JSON and CSV."""
    try:
        db = _get_db_from_options(database, host, port, username, password)
        service = ClusterExportService(
            db=db,
            source_collection=collection,
            edge_collection=edge_collection,
            cluster_collection=cluster_collection,
        )
        exported = service.export(
            output_dir=output_dir,
            filename_prefix=filename_prefix,
            limit=limit,
        )
        click.echo(click.style("\nExport complete!", fg="green", bold=True))
        _emit_json(
            {
                "collection": collection,
                "cluster_collection": service.cluster_collection,
                "output_files": {
                    "json": exported["json"],
                    "csv": exported["csv"],
                },
                "clusters_exported": exported["clusters_exported"],
            }
        )
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


@main.command()
@click.option("--collection", required=True, help="Source collection name.")
@click.option("--ground-truth", "ground_truth", required=True, type=click.Path(exists=True), help="Ground-truth pairs file (.json or .csv).")
@click.option("--baseline-field", "baseline_fields", multiple=True, required=True, help="Exact blocking field(s) for the baseline strategy.")
@click.option("--search-view", required=True, help="ArangoSearch view name for BM25 comparison.")
@click.option("--search-field", required=True, help="Field searched by the BM25 strategy.")
@click.option("--blocking-field", help="Optional field used to constrain BM25 comparisons.")
@click.option("--output-dir", required=True, type=click.Path(file_okay=False), help="Directory for benchmark artifacts.")
@click.option("--filename-prefix", default="blocking_benchmark", show_default=True, help="Filename prefix for benchmark artifacts.")
@click.option("--baseline-max-block-size", type=int, default=100, show_default=True, help="Maximum exact-block size.")
@click.option("--hybrid-bm25-threshold", type=float, default=2.0, show_default=True, help="Minimum BM25 score for the comparison strategy.")
@click.option("--hybrid-limit-per-entity", type=int, default=20, show_default=True, help="Maximum BM25 candidates per source record.")
@connection_options
def benchmark(
    collection,
    ground_truth,
    baseline_fields,
    search_view,
    search_field,
    blocking_field,
    output_dir,
    filename_prefix,
    baseline_max_block_size,
    hybrid_bm25_threshold,
    hybrid_limit_per_entity,
    database,
    host,
    port,
    username,
    password,
):
    """Run the supported exact-vs-BM25 blocking benchmark workflow."""
    try:
        db = _get_db_from_options(database, host, port, username, password)
        results = run_blocking_benchmark(
            db=db,
            collection_name=collection,
            ground_truth_path=ground_truth,
            baseline_fields=baseline_fields,
            search_view=search_view,
            search_field=search_field,
            blocking_field=blocking_field,
            output_dir=output_dir,
            filename_prefix=filename_prefix,
            baseline_max_block_size=baseline_max_block_size,
            hybrid_bm25_threshold=hybrid_bm25_threshold,
            hybrid_limit_per_entity=hybrid_limit_per_entity,
        )
        click.echo(click.style("\nBenchmark complete!", fg="green", bold=True))
        _emit_json(results)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
