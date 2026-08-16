"""Chunked BM25 blocking must bound query duration without changing results.

The strategy issued ONE query containing a per-document subquery over the whole
collection and materialised every pair before returning. Measured on the
DBLP-Scholar benchmark (66,879 documents) that took 19.3 minutes against 7.1
seconds for 4,910 — ~13x the records for ~164x the time — and the single request
exceeded python-arango's default 60-second read timeout, so any caller above
~10k records hit that before anything else.

The correctness property that makes chunking safe is that each source document
searches the entire view independently, so partitioning the OUTER loop changes
the number of requests and nothing else. These tests pin that equivalence,
because a chunking bug loses pairs silently — blocking reports a pair count, not
a completeness figure, so nothing downstream would notice.
"""

from __future__ import annotations

import time
import uuid

import pytest

from entity_resolution.strategies.bm25_blocking import BM25BlockingStrategy

WORDS = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"]


@pytest.fixture
def searchable(db_connection):
    """A collection of overlapping text plus an indexed ArangoSearch view."""
    suffix = uuid.uuid4().hex[:8]
    collection = f"chunk_{suffix}"
    view = f"chunk_view_{suffix}"
    db = db_connection

    db.create_collection(collection)
    db.collection(collection).insert_many([
        {"_key": f"d{i}", "text": f"{WORDS[i % 8]} {WORDS[(i * 3) % 8]} widget {i % 17}"}
        for i in range(200)
    ])
    db.create_view(view, view_type="arangosearch", properties={
        "links": {collection: {"fields": {"text": {"analyzers": ["text_en"]}}}}
    })

    # ArangoSearch indexes asynchronously; wait for the view to see every doc,
    # or the first assertions race the indexer and under-report pairs.
    deadline = time.time() + 60
    while time.time() < deadline:
        seen = next(iter(db.aql.execute(
            "FOR d IN @@view SEARCH d.text != null COLLECT WITH COUNT INTO n RETURN n",
            bind_vars={"@view": view},
        )), 0)
        if seen >= 200:
            break
        time.sleep(0.5)

    yield db, collection, view

    if any(v["name"] == view for v in db.views()):
        db.delete_view(view)
    if db.has_collection(collection):
        db.delete_collection(collection)


def _strategy(db, collection, view, chunk_size):
    return BM25BlockingStrategy(
        db=db, collection=collection, search_view=view, search_field="text",
        bm25_threshold=1.0, limit_per_entity=10, chunk_size=chunk_size,
    )


def _pair_set(strategy):
    return {(p["doc1_key"], p["doc2_key"]) for p in strategy.generate_candidates()}


@pytest.mark.parametrize("chunk_size", [7, 50, 199, 200, 201, 5000])
def test_chunking_produces_identical_pairs(searchable, chunk_size):
    """The property everything else rests on, across boundary-adjacent sizes."""
    db, collection, view = searchable

    unchunked = _pair_set(_strategy(db, collection, view, 0))
    chunked = _pair_set(_strategy(db, collection, view, chunk_size))

    assert chunked == unchunked, (
        f"chunk_size={chunk_size} changed the candidate set: "
        f"{len(chunked)} pairs vs {len(unchunked)} unchunked"
    )
    assert unchunked, "fixture produced no pairs; the test would be vacuous"


def test_multiple_chunks_are_actually_executed(searchable):
    """Guards against the parametrised test passing because chunking no-ops."""
    db, collection, view = searchable
    strategy = _strategy(db, collection, view, 25)
    strategy.generate_candidates()

    stats = strategy.get_statistics()
    assert stats["chunks_executed"] > 1, (
        f"expected several chunks over 200 docs at size 25, got {stats}"
    )
    assert stats["chunk_sizes"][0] == 25, "first chunk uses the configured size"


def test_chunk_size_adapts_to_measured_duration(searchable):
    """Chunk size is a starting point, not a fixed quantum.

    A fixed size cannot suit every workload: per-document cost scales with the
    size of the view being searched and the length of the text, so a size that
    is comfortable on 5k documents exceeded the 60s client timeout on 67k
    (~17ms/doc, ~87s for a 5,000-document chunk). Sizes therefore track a
    wall-clock budget. On this small fixture every chunk is fast, so sizes grow.
    """
    db, collection, view = searchable
    strategy = _strategy(db, collection, view, 25)
    strategy.generate_candidates()

    sizes = strategy.get_statistics()["chunk_sizes"]
    assert sizes[0] == 25
    assert max(sizes) > sizes[0], (
        f"fast chunks should grow toward the time budget, got {sizes}"
    )


def test_adaptive_growth_does_not_change_results(searchable):
    """Adapting the size must not alter the candidate set."""
    db, collection, view = searchable
    adaptive = _pair_set(_strategy(db, collection, view, 25))
    unchunked = _pair_set(_strategy(db, collection, view, 0))
    assert adaptive == unchunked


def test_invalid_time_budget_is_rejected(db_connection):
    with pytest.raises(ValueError, match="chunk_target_seconds"):
        BM25BlockingStrategy(
            db=db_connection, collection="c", search_view="v",
            search_field="text", chunk_target_seconds=0,
        )


def test_iter_candidates_streams_without_materialising(searchable):
    """A caller must be able to consume pairs without holding them all."""
    db, collection, view = searchable
    strategy = _strategy(db, collection, view, 25)

    iterator = strategy.iter_candidates()
    first = next(iterator)

    assert set(first) >= {"doc1_key", "doc2_key", "bm25_score"}
    assert sum(1 for _ in iterator) > 0


def test_chunk_size_zero_issues_a_single_request(searchable):
    """The pre-chunking behaviour stays reachable for callers that want it."""
    db, collection, view = searchable
    strategy = _strategy(db, collection, view, 0)
    pairs = strategy.generate_candidates()

    assert pairs
    assert "chunks_executed" not in strategy.get_statistics()


def test_chunk_larger_than_collection_still_returns_everything(searchable):
    db, collection, view = searchable
    assert _pair_set(_strategy(db, collection, view, 10_000)) == _pair_set(
        _strategy(db, collection, view, 0)
    )


def test_negative_chunk_size_is_rejected(db_connection):
    with pytest.raises(ValueError, match="chunk_size"):
        BM25BlockingStrategy(
            db=db_connection, collection="c", search_view="v",
            search_field="text", chunk_size=-1,
        )


def test_pairs_remain_normalised_across_chunks(searchable):
    """Symmetric dedup must survive partitioning.

    A pair can be discovered from either endpoint, and those endpoints may fall
    in different chunks — so normalisation has to happen after all chunks are
    collected, not within one.
    """
    db, collection, view = searchable
    pairs = _strategy(db, collection, view, 25).generate_candidates()

    keys = [(p["doc1_key"], p["doc2_key"]) for p in pairs]
    assert all(a < b for a, b in keys), "pairs are not canonically ordered"
    assert len(keys) == len(set(keys)), "duplicate pairs survived chunking"
