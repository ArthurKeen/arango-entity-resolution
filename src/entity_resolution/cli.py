"""
Command Line Interface for ArangoDB Entity Resolution.
"""

import click
import json
import sys
from pathlib import Path
from typing import Optional

from .utils.database import get_database
from .core.configurable_pipeline import ConfigurableERPipeline
from .utils.constants import get_version_string

@click.group()
@click.version_option(version=get_version_string())
def main():
    """ArangoDB Entity Resolution CLI."""
    pass

@main.command()
@click.option('--config', '-c', type=click.Path(exists=True), required=True, help='Path to YAML/JSON configuration file.')
@click.option('--database', '-d', help='Database name (overrides config).')
@click.option('--host', help='ArangoDB host.')
@click.option('--port', type=int, help='ArangoDB port.')
@click.option('--username', '-u', help='Username.')
@click.option('--password', '-p', help='Password.')
def run(config, database, host, port, username, password):
    """Run an entity resolution pipeline from a configuration file."""
    try:
        # Connect to database
        db = get_database(
            database=database,
            host=host,
            port=port,
            username=username,
            password=password
        )
        
        # Initialize and run pipeline
        pipeline = ConfigurableERPipeline(db=db, config_path=config)
        results = pipeline.run()
        
        click.echo(click.style("\nPipeline execution successful!", fg="green", bold=True))
        click.echo(json.dumps(results, indent=2))
        
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
