"""
Example: YAML-Configured Entity Resolution Pipeline

Demonstrates how to define a complete ER pipeline via YAML configuration,
load it as an ERPipelineConfig, validate it, and run the pipeline against
a self-contained seed dataset.

The YAML config is embedded as a string so this example is fully
self-contained — no external config file is needed.

Prerequisites:
  - ArangoDB running locally (default: http://localhost:8529)
  - pip install entity-resolution  (with jellyfish, pyyaml, python-arango)

Usage:
    python examples/yaml_config_pipeline.py
"""

import tempfile
import time
from pathlib import Path

import yaml
from arango import ArangoClient

# ── Inline YAML configuration ────────────────────────────────────────────
PIPELINE_YAML = """\
entity_resolution:
  entity_type: "company"
  collection_name: "test_yaml_companies"
  edge_collection: "test_yaml_similarity"
  cluster_collection: "test_yaml_clusters"

  blocking:
    strategy: "exact"
    max_block_size: 50
    min_block_size: 2
    fields:
      - name: "state"
      - name: "city"

  similarity:
    algorithm: "jaro_winkler"
    threshold: 0.78
    batch_size: 1000
    field_weights:
      name: 0.6
      city: 0.2
      state: 0.1
      phone: 0.1

  clustering:
    algorithm: "wcc"
    min_cluster_size: 2
    store_results: true
    backend: "python_union_find"
"""


SEED_COMPANIES = [
    {"_key": "c01", "name": "Acme Corporation",    "city": "New York",    "state": "NY", "phone": "2125551234"},
    {"_key": "c02", "name": "ACME Corp",           "city": "New York",    "state": "NY", "phone": "2125551234"},
    {"_key": "c03", "name": "Acme Inc.",           "city": "New York",    "state": "NY", "phone": "2125551235"},
    {"_key": "c04", "name": "Globex Industries",   "city": "Chicago",     "state": "IL", "phone": "3125550001"},
    {"_key": "c05", "name": "Globex Ind.",         "city": "Chicago",     "state": "IL", "phone": "3125550001"},
    {"_key": "c06", "name": "Wayne Enterprises",   "city": "Washington",  "state": "DC", "phone": "2025551111"},
    {"_key": "c07", "name": "Wayne Corp",          "city": "Washington",  "state": "DC", "phone": "2025551111"},
    {"_key": "c08", "name": "Stark Industries",    "city": "Los Angeles", "state": "CA", "phone": "3105559876"},
    {"_key": "c09", "name": "Umbrella Corp",       "city": "Denver",      "state": "CO", "phone": "7205550000"},
]


def seed_data(db, collection_name: str):
    """Create and populate the test collection."""
    if db.has_collection(collection_name):
        db.delete_collection(collection_name)
    col = db.create_collection(collection_name)
    for doc in SEED_COMPANIES:
        col.insert(doc)
    print(f"Seeded {len(SEED_COMPANIES)} companies into '{collection_name}'")


def load_and_validate_config(yaml_str: str):
    """Parse the inline YAML and build an ERPipelineConfig."""
    from entity_resolution.config.er_config import ERPipelineConfig

    config_dict = yaml.safe_load(yaml_str)
    config = ERPipelineConfig.from_dict(config_dict)

    errors = config.validate()
    if errors:
        print("Config validation errors:")
        for err in errors:
            print(f"  - {err}")
        raise ValueError("Invalid configuration")

    print("\nConfiguration loaded and validated:")
    print(f"  Entity type       : {config.entity_type}")
    print(f"  Collection        : {config.collection_name}")
    print(f"  Blocking strategy : {config.blocking.strategy}")
    print(f"  Blocking fields   : {[f if isinstance(f, str) else f.get('name') for f in config.blocking.fields]}")
    print(f"  Similarity algo   : {config.similarity.algorithm}")
    print(f"  Similarity thresh : {config.similarity.threshold}")
    print(f"  Clustering backend: {config.clustering.backend}")
    return config


def run_pipeline(db, config):
    """Run the ConfigurableERPipeline with the loaded config."""
    from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline

    print("\nRunning ER pipeline...")
    print("=" * 60)

    pipeline = ConfigurableERPipeline(db=db, config=config)
    results = pipeline.run()

    print("\n--- Pipeline Results ---")
    for phase in ("blocking", "similarity", "edges", "clustering"):
        phase_data = results.get(phase, {})
        if not phase_data:
            continue
        print(f"\n  {phase.upper()}:")
        for key, val in phase_data.items():
            print(f"    {key}: {val}")

    print(f"\n  Total runtime: {results.get('total_runtime_seconds', 0):.2f}s")
    return results


def show_yaml_roundtrip(config):
    """Demonstrate converting the config back to YAML."""
    print("\n--- Config round-trip (back to YAML) ---")
    regenerated = config.to_yaml()
    print(regenerated)


def show_config_from_file(yaml_str: str):
    """Demonstrate loading from a temporary file (the file-based workflow)."""
    from entity_resolution.config.er_config import ERPipelineConfig

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_str)
        tmp_path = f.name

    config = ERPipelineConfig.from_yaml(tmp_path)
    Path(tmp_path).unlink()
    print(f"\nLoaded config from temp file: {config}")
    return config


def cleanup(db, config):
    """Remove test collections."""
    for col_name in (config.collection_name, config.edge_collection, config.cluster_collection):
        if db.has_collection(col_name):
            db.delete_collection(col_name)
    print("\nTest collections cleaned up.")


def main():
    client = ArangoClient(hosts="http://localhost:8529")
    db = client.db("_system", username="root", password="rootpassword")

    config = load_and_validate_config(PIPELINE_YAML)
    seed_data(db, config.collection_name)

    try:
        results = run_pipeline(db, config)
        show_yaml_roundtrip(config)
        show_config_from_file(PIPELINE_YAML)
    finally:
        cleanup(db, config)

    print("\nDone.")


if __name__ == "__main__":
    main()
