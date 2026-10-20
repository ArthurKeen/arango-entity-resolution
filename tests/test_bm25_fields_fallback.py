"""BM25 blocking must read `blocking.fields` safely (arango-solutions-org/arango-entity-resolution#3).

`blocking.fields` means "block on these together" under the exact strategy.
BM25 searches one field and may filter on one more, and the pipeline used to
map the list onto that silently: `fields[1]` became an exact-equality filter,
a computed field's expression was dropped so BM25 searched an attribute that
does not exist, and the resulting zero candidates looked like success.

Real config, real pipeline, real BM25BlockingStrategy. Only the database wire
is faked; it records the AQL the strategy sends.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pytest

from entity_resolution.config.er_config import ERPipelineConfig
from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline


class _RecordingDB:
    """The database wire: records AQL, returns no rows. Not a MagicMock."""

    name = "bm25_fallback_test_db"

    def __init__(self, records: int = 100) -> None:
        self.queries: List[Dict[str, Any]] = []
        self.records = records
        self.aql = self

    def execute(self, query, bind_vars=None, **kwargs):
        self.queries.append({"query": query, "bind_vars": dict(bind_vars or {})})
        return iter([])

    def has_collection(self, name):
        return True

    def collection(self, name):
        records = self.records

        class _Collection:
            def count(self):
                return records

        return _Collection()


def _pipeline(blocking: Dict[str, Any], records: int = 100):
    db = _RecordingDB(records)
    config = ERPipelineConfig.from_dict({
        "entity_resolution": {"collection_name": "companies", "blocking": {"strategy": "bm25", **blocking}}
    })
    return ConfigurableERPipeline(db=db, config=config), db


def _search_queries(db) -> List[str]:
    return [q["query"] for q in db.queries if "SEARCH" in q["query"]]


def test_second_field_is_not_turned_into_an_equality_filter(caplog) -> None:
    pipeline, db = _pipeline({"fields": ["company_name", "state"]})
    with caplog.at_level(logging.WARNING):
        pipeline.run_blocking()
    queries = _search_queries(db)
    assert queries, "the strategy never searched"
    assert all("d2.state == d1.state" not in q for q in queries)
    assert all("d2.company_name IN TOKENS(d1.company_name" in q for q in queries)
    # Both silent decisions are now said out loud.
    assert "searching 'company_name'" in caplog.text
    assert "ignores blocking.fields entries ['state']" in caplog.text


def test_explicit_blocking_field_still_filters() -> None:
    pipeline, db = _pipeline({"search_field": "company_name", "blocking_field": "state"})
    pipeline.run_blocking()
    assert all("d2.state == d1.state" in q for q in _search_queries(db))


@pytest.mark.parametrize("role", ["search_field", "blocking_field"])
def test_computed_field_cannot_be_searched_or_filtered(role: str) -> None:
    computed = {"name": "name_norm", "expression": "LOWER(d.company_name)"}
    blocking = {"fields": [computed]} if role == "search_field" else {
        "search_field": "company_name", "blocking_field": "name_norm", "fields": [computed]}
    pipeline, db = _pipeline(blocking)
    with pytest.raises(ValueError, match="computed field 'name_norm'"):
        pipeline.run_blocking()
    assert not _search_queries(db), "must refuse before querying"


def test_zero_candidates_on_a_populated_collection_warns(caplog) -> None:
    pipeline, _ = _pipeline({"search_field": "company_name"}, records=250)
    with caplog.at_level(logging.WARNING):
        assert pipeline.run_blocking() == []
    assert "zero candidate pairs from 250 records" in caplog.text
    assert "'companies_search'" in caplog.text


def test_zero_candidates_on_an_empty_collection_is_quiet(caplog) -> None:
    pipeline, _ = _pipeline({"search_field": "company_name"}, records=0)
    with caplog.at_level(logging.WARNING):
        pipeline.run_blocking()
    assert "zero candidate pairs" not in caplog.text
