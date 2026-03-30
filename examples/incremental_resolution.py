"""
Example: Incremental Entity Resolution

Demonstrates how to use the IncrementalResolver to match new incoming
records against an existing collection — without re-processing the full
dataset.  This is the pattern used by the `resolve_entity` MCP tool for
real-time / streaming entity resolution.

The example walks through three stages:
  1. Seed a collection of companies (the "existing" dataset)
  2. Resolve individual new records against the collection, showing
     per-field similarity breakdowns
  3. Simulate a streaming batch: insert each new record, resolve it,
     and show how the cluster membership evolves

Prerequisites:
  - ArangoDB running locally (default: http://localhost:8529)
  - pip install entity-resolution  (with jellyfish, python-arango)

Usage:
    python examples/incremental_resolution.py
"""

from arango import ArangoClient
from entity_resolution.core.incremental_resolver import IncrementalResolver


COLLECTION = "test_incremental_companies"

EXISTING_COMPANIES = [
    {"_key": "c1", "name": "Acme Corporation", "city": "New York",   "state": "NY"},
    {"_key": "c2", "name": "Globex Industries", "city": "Chicago",    "state": "IL"},
    {"_key": "c3", "name": "Wayne Enterprises", "city": "Washington", "state": "DC"},
    {"_key": "c4", "name": "Stark Industries",  "city": "Los Angeles","state": "CA"},
    {"_key": "c5", "name": "Umbrella Corp",     "city": "Denver",     "state": "CO"},
]

INCOMING_RECORDS = [
    {"name": "ACME Corp",            "city": "New York",    "state": "NY"},
    {"name": "Globex Ind.",          "city": "Chicago",     "state": "IL"},
    {"name": "Wonka Chocolate Inc.", "city": "Portland",    "state": "OR"},
    {"name": "Wayne Corp",           "city": "Washington",  "state": "DC"},
    {"name": "Stark Ind.",           "city": "Los Angeles",  "state": "CA"},
]


def seed_collection(db):
    """Create and populate the test collection."""
    if db.has_collection(COLLECTION):
        db.delete_collection(COLLECTION)

    col = db.create_collection(COLLECTION)
    for doc in EXISTING_COMPANIES:
        col.insert(doc)
    print(f"Seeded {len(EXISTING_COMPANIES)} companies into '{COLLECTION}'")
    return col


def stage_resolve_new_records(db):
    """Resolve individual records without inserting them."""
    resolver = IncrementalResolver(
        db=db,
        collection=COLLECTION,
        fields=["name", "city", "state"],
        confidence_threshold=0.70,
        blocking_strategy="prefix",
        prefix_length=3,
    )

    for record in INCOMING_RECORDS:
        label = f"{record['name']} ({record['city']}, {record['state']})"
        matches = resolver.resolve(record, top_k=3)

        if matches:
            print(f"\n  {label}")
            for m in matches:
                print(f"    -> {m['_key']}  score={m['score']:.4f}  match={m['match']}")
                for field, fs in m["field_scores"].items():
                    print(f"         {field}: {fs['score']:.4f} ({fs['method']})")
        else:
            print(f"\n  {label}")
            print("    -> No matches above threshold")


def stage_streaming_batch(db, col):
    """Simulate streaming: insert each new record and resolve it."""
    resolver = IncrementalResolver(
        db=db,
        collection=COLLECTION,
        fields=["name", "city", "state"],
        confidence_threshold=0.70,
        blocking_strategy="prefix",
        prefix_length=3,
    )

    for i, record in enumerate(INCOMING_RECORDS):
        key = f"new_{i}"
        label = f"{record['name']} ({record['city']}, {record['state']})"

        matches = resolver.resolve(record, top_k=3, exclude_key=key)
        best = matches[0] if matches else None

        doc = {**record, "_key": key}
        col.insert(doc)

        if best:
            print(f"  Inserted '{key}' — matched {best['_key']} (score={best['score']:.4f})")
        else:
            print(f"  Inserted '{key}' — new entity (no match)")

    total = col.count()
    print(f"\n  Collection now has {total} documents")


def cleanup(db):
    """Remove test collection."""
    if db.has_collection(COLLECTION):
        db.delete_collection(COLLECTION)
    print("\nTest collection cleaned up.")


def main():
    client = ArangoClient(hosts="http://localhost:8529")
    db = client.db("_system", username="root", password="rootpassword")

    col = seed_collection(db)

    try:
        # Stage 1: Resolve without inserting
        print("\n" + "=" * 60)
        print("Stage 1: Resolve new records against existing data")
        print("=" * 60)
        stage_resolve_new_records(db)

        # Stage 2: Streaming insert + resolve
        print("\n" + "=" * 60)
        print("Stage 2: Simulate streaming batch (insert + resolve)")
        print("=" * 60)
        stage_streaming_batch(db, col)

    finally:
        cleanup(db)

    print("\nDone.")


if __name__ == "__main__":
    main()
