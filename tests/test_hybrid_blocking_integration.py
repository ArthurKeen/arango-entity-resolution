"""Hybrid blocking against a real ArangoSearch view.

The query-string unit tests cannot show *recall*: that a record with a typo
actually receives candidates. PHRASE retrieval required the whole source value
as an exact stemmed token sequence, so "Northwind Tradrs" (k3) matched nothing
and was left with no candidates at all.

The companion ``d1._key < d2._key`` fix is covered by the query-shape unit test
rather than here: its recall loss needs a lower-key record whose LIMIT is
filled by a third record unlike the pair, which this small fixture does not
construct.
"""

from __future__ import annotations

import time

import pytest

from entity_resolution.strategies.hybrid_blocking import HybridBlockingStrategy

pytestmark = pytest.mark.integration

COLLECTION = "hybrid_it_companies"
VIEW = "hybrid_it_companies_v"
DOCS = [
    ("k1", "Northwind Traders"),
    ("k2", "Northwind Trader"),
    ("k3", "Northwind Tradrs"),
    ("k4", "Contoso Pharmaceuticals"),
    ("k5", "Contoso Pharmaceutical"),
]


@pytest.fixture
def companies(db_connection):
    db = db_connection
    if any(v["name"] == VIEW for v in db.views()):
        db.delete_view(VIEW)
    if db.has_collection(COLLECTION):
        db.delete_collection(COLLECTION)
    db.create_collection(COLLECTION).insert_many(
        [{"_key": k, "name": n} for k, n in DOCS]
    )
    db.create_view(
        VIEW, "arangosearch",
        {"links": {COLLECTION: {"fields": {"name": {"analyzers": ["text_en"]}}}}},
    )
    # Wait for the view to index everything (it is eventually consistent).
    for _ in range(50):
        if len(list(db.aql.execute(f"FOR d IN {VIEW} OPTIONS {{waitForSync: true}} RETURN 1"))) == len(DOCS):
            break
        time.sleep(0.1)
    yield db
    db.delete_view(VIEW)
    db.delete_collection(COLLECTION)


def _pairs(db, **overrides):
    kwargs = dict(
        db=db, collection=COLLECTION, search_view=VIEW, search_fields={"name": 1.0},
        levenshtein_threshold=0.5, bm25_threshold=0.001, limit_per_entity=1,
    )
    kwargs.update(overrides)
    return {(p["doc1_key"], p["doc2_key"]) for p in HybridBlockingStrategy(**kwargs).generate_candidates()}


def test_every_record_with_a_near_duplicate_receives_a_candidate(companies) -> None:
    covered = {key for pair in _pairs(companies) for key in pair}
    assert covered == {k for k, _ in DOCS}


def test_phrase_mode_is_the_near_exact_legacy_behaviour(companies) -> None:
    covered = {key for pair in _pairs(companies, match_mode="phrase") for key in pair}
    assert "k3" not in covered
