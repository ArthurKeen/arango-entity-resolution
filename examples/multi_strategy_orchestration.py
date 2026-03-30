"""
Example: Multi-Strategy Blocking Orchestration

Demonstrates running multiple blocking strategies and merging their
candidate pairs with the MultiStrategyOrchestrator.

Requires: ArangoDB running locally with test data.

    python examples/multi_strategy_orchestration.py
"""

from arango import ArangoClient
from entity_resolution.core.orchestrator import MultiStrategyOrchestrator
from entity_resolution.strategies.collect_blocking import CollectBlockingStrategy


def seed_test_data(db, collection="test_orchestrator_companies"):
    """Seed sample company data for blocking."""
    if db.has_collection(collection):
        db.delete_collection(collection)

    col = db.create_collection(collection)
    companies = [
        {"_key": "c1", "name": "Acme Corporation", "phone": "2125551234", "state": "NY", "city": "New York"},
        {"_key": "c2", "name": "ACME Corp", "phone": "2125551234", "state": "NY", "city": "New York"},
        {"_key": "c3", "name": "Acme Inc", "phone": "3105559999", "state": "CA", "city": "Los Angeles"},
        {"_key": "c4", "name": "Globex Industries", "phone": "3125550001", "state": "IL", "city": "Chicago"},
        {"_key": "c5", "name": "Globex Ind.", "phone": "3125550001", "state": "IL", "city": "Chicago"},
        {"_key": "c6", "name": "Wayne Enterprises", "phone": "2025551111", "state": "DC", "city": "Washington"},
        {"_key": "c7", "name": "Wayne Corp", "phone": "2025551111", "state": "DC", "city": "Washington"},
    ]
    for c in companies:
        col.insert(c)
    print(f"Seeded {len(companies)} companies")
    return collection


def main():
    client = ArangoClient(hosts="http://localhost:8529")
    db = client.db("_system", username="root", password="rootpassword")

    collection = seed_test_data(db)

    # Strategy 1: Block by phone + state (exact match)
    phone_state = CollectBlockingStrategy(
        db=db,
        collection=collection,
        blocking_fields=["phone", "state"],
    )

    # Strategy 2: Block by city + state (broader)
    city_state = CollectBlockingStrategy(
        db=db,
        collection=collection,
        blocking_fields=["city", "state"],
    )

    # --- Union mode: maximum recall ---
    print("\n=== Union Mode (all unique pairs from any strategy) ===")
    union_orch = MultiStrategyOrchestrator(
        strategies=[phone_state, city_state],
        merge_mode="union",
    )
    union_candidates = union_orch.run()
    stats = union_orch.get_statistics()

    print(f"Total candidates: {stats['total_candidates']}")
    for c in union_candidates:
        print(f"  {c['doc1_key']} <-> {c['doc2_key']}  sources={c['sources']}")

    # --- Intersection mode: maximum precision ---
    print("\n=== Intersection Mode (only pairs found by BOTH strategies) ===")
    inter_orch = MultiStrategyOrchestrator(
        strategies=[phone_state, city_state],
        merge_mode="intersection",
    )
    inter_candidates = inter_orch.run()
    stats = inter_orch.get_statistics()

    print(f"Total candidates: {stats['total_candidates']}")
    for c in inter_candidates:
        print(f"  {c['doc1_key']} <-> {c['doc2_key']}  sources={c['sources']}")

    # --- From YAML config ---
    print("\n=== Building from Config Dict ===")
    config_dict = {
        "merge_mode": "union",
        "deduplicate": True,
        "strategies": [
            {
                "type": "collect",
                "collection": collection,
                "blocking_fields": ["phone", "state"],
            },
            {
                "type": "collect",
                "collection": collection,
                "blocking_fields": ["city", "state"],
                "max_block_size": 50,
            },
        ],
    }
    config_orch = MultiStrategyOrchestrator.from_config(db, config_dict)
    config_candidates = config_orch.run()
    print(f"Config-driven orchestrator: {len(config_candidates)} candidates")

    # Cleanup
    db.delete_collection(collection)
    print("\nDone. Test collection cleaned up.")


if __name__ == "__main__":
    main()
