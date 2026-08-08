"""
Security regression tests for AQL injection prevention (PR1).

These tests assert that user/config-controlled identifiers and expressions are
either validated (rejected) or passed as bind variables before reaching AQL,
covering the entry points hardened in the comprehensive-review remediation
plan (Workstream 1A).
"""

import logging

import pytest

from entity_resolution.utils.validation import (
    validate_computed_field_expression,
)
from entity_resolution.core.incremental_resolver import IncrementalResolver
from entity_resolution.config.er_config import BlockingConfig
from entity_resolution.services.evaluation_service import EvaluationService
from entity_resolution.services.blocking_service import BlockingService
from entity_resolution.services.similarity_edge_service import SimilarityEdgeService
from entity_resolution.services.cross_collection_matching_service import (
    CrossCollectionMatchingService,
)
from entity_resolution.strategies.bm25_blocking import BM25BlockingStrategy
from entity_resolution.strategies.collect_blocking import CollectBlockingStrategy
from entity_resolution.strategies.geographic_blocking import GeographicBlockingStrategy
from entity_resolution.strategies.hybrid_blocking import HybridBlockingStrategy
from entity_resolution.strategies.shard_parallel_blocking import (
    ShardParallelBlockingStrategy,
)


class _RecordingAQL:
    """Captures the last AQL query + bind_vars and returns an empty result."""

    def __init__(self):
        self.last_query = None
        self.last_bind_vars = None

    def execute(self, query, bind_vars=None, **kwargs):
        self.last_query = query
        self.last_bind_vars = bind_vars or {}
        return iter([])


class _FakeDB:
    def __init__(self):
        self.aql = _RecordingAQL()

    def collection(self, name):
        return object()

    def has_collection(self, name):
        return True


# ---------------------------------------------------------------------------
# validate_computed_field_expression
# ---------------------------------------------------------------------------

SAFE_EXPRESSIONS = [
    "CONCAT(d.first_name, d.last_name)",
    "LOWER(d.name)",
    "SUBSTRING(d.code, 0, 3)",
    "d.first_name",
]


@pytest.mark.parametrize("expr", SAFE_EXPRESSIONS)
def test_safe_computed_expressions_pass(expr):
    assert validate_computed_field_expression(expr) == expr.strip()


MALICIOUS_EXPRESSIONS = [
    "d.x) REMOVE d IN companies //",
    "d.x) INSERT {evil: 1} INTO companies RETURN (",
    "(FOR v IN secrets RETURN v)",
    "d.x UPDATE d WITH {a: 1} IN companies",
    "d.name /* comment */",
    "d.name ; DROP",
]


@pytest.mark.parametrize("expr", MALICIOUS_EXPRESSIONS)
def test_malicious_computed_expressions_rejected(expr):
    with pytest.raises(ValueError):
        validate_computed_field_expression(expr)


def test_empty_computed_expression_rejected():
    with pytest.raises(ValueError):
        validate_computed_field_expression("   ")


# ---------------------------------------------------------------------------
# IncrementalResolver identifier validation
# ---------------------------------------------------------------------------

def test_incremental_resolver_rejects_malicious_collection():
    with pytest.raises(ValueError):
        IncrementalResolver(db=_FakeDB(), collection="x RETURN doc; //", fields=["name"])


def test_incremental_resolver_rejects_malicious_field():
    with pytest.raises(ValueError):
        IncrementalResolver(db=_FakeDB(), collection="companies", fields=["name) REMOVE doc IN companies //"])


def test_incremental_resolver_accepts_valid_identifiers():
    resolver = IncrementalResolver(db=_FakeDB(), collection="companies", fields=["name", "address.city"])
    assert resolver.collection == "companies"
    assert resolver.fields == ["name", "address.city"]


def test_incremental_resolver_rejects_malicious_prefix_length():
    with pytest.raises(ValueError, match="prefix_length"):
        IncrementalResolver(
            db=_FakeDB(),
            collection="companies",
            fields=["name"],
            prefix_length="3) REMOVE doc IN companies //",
        )


# ---------------------------------------------------------------------------
# Config-controlled AQL fragments
# ---------------------------------------------------------------------------

def test_geographic_zip_ranges_use_bind_variables():
    malicious = '577") REMOVE d IN companies //'
    strategy = GeographicBlockingStrategy(
        db=_FakeDB(),
        collection="companies",
        blocking_type="zip_range",
        geographic_fields={"zip": "postal_code"},
        zip_ranges=[("570", malicious)],
    )

    query = strategy._build_geographic_query()
    bind_vars = strategy._build_bind_vars()

    assert malicious not in query
    assert "@zip_min_0" in query and "@zip_max_0" in query
    assert bind_vars["zip_max_0"] == malicious


def test_collect_exclude_values_reject_malicious_field():
    with pytest.raises(ValueError):
        CollectBlockingStrategy(
            db=_FakeDB(),
            collection="companies",
            blocking_fields=["name"],
            exclude_values={"name) REMOVE d IN companies //": {"bad"}},
        )


def test_collect_strategy_rejects_malicious_computed_expression_directly():
    with pytest.raises(ValueError):
        CollectBlockingStrategy(
            db=_FakeDB(),
            collection="companies",
            blocking_fields=["evil"],
            computed_fields={"evil": "d.x) REMOVE d IN companies //"},
        )


def test_collect_block_sizes_reject_aql_fragments():
    with pytest.raises(ValueError, match="block sizes"):
        CollectBlockingStrategy(
            db=_FakeDB(),
            collection="companies",
            blocking_fields=["name"],
            max_block_size="100) REMOVE d IN companies //",
        )


def test_shard_parallel_rejects_malicious_blocking_field():
    with pytest.raises(ValueError):
        ShardParallelBlockingStrategy(
            db=_FakeDB(),
            collection="companies",
            blocking_fields=["name`) REMOVE d IN companies //"],
        )


def test_hybrid_blocking_rejects_malicious_analyzer():
    with pytest.raises(ValueError):
        HybridBlockingStrategy(
            db=_FakeDB(),
            collection="companies",
            search_view="company_search",
            search_fields={"name": 1.0},
            analyzer='text_en") REMOVE d IN companies //',
        )


def test_bm25_blocking_rejects_malicious_min_length():
    strategy = BM25BlockingStrategy(
        db=_FakeDB(),
        collection="companies",
        search_view="company_search",
        search_field="name",
        filters={"name": {"min_length": "5) OR true //"}},
    )
    with pytest.raises(ValueError, match="min_length"):
        strategy._build_bm25_query()


def test_hybrid_blocking_rejects_malicious_min_length():
    strategy = HybridBlockingStrategy(
        db=_FakeDB(),
        collection="companies",
        search_view="company_search",
        search_fields={"name": 1.0},
        filters={"name": {"min_length": "5) OR true //"}},
    )
    with pytest.raises(ValueError, match="min_length"):
        strategy._build_hybrid_query()


def test_evaluation_service_rejects_malicious_score_field():
    with pytest.raises(ValueError):
        EvaluationService(
            db=_FakeDB(),
            edge_collection="similarTo",
            score_field="similarity) REMOVE e IN similarTo //",
        )


def test_cross_collection_filter_values_use_bind_variables():
    malicious = 'CA") REMOVE s IN source //'
    service = CrossCollectionMatchingService(
        db=_FakeDB(),
        source_collection="source",
        target_collection="target",
        edge_collection="edges",
    )
    service.configure_matching(
        source_fields={"name": "name"},
        target_fields={"name": "name"},
        field_weights={"name": 1.0},
        custom_filters={"source": {"state": {"equals": malicious}}},
    )

    query = service._build_count_query()
    bind_vars = service._collection_bind_vars()

    assert malicious not in query
    assert "s.state == @_filter_s_0_eq" in query
    assert bind_vars["_filter_s_0_eq"] == malicious


def test_legacy_blocking_limit_uses_bind_variable():
    malicious = "10 REMOVE doc IN companies"
    service = BlockingService.__new__(BlockingService)
    service.logger = logging.getLogger("test")
    db = _FakeDB()

    service._exact_blocking(
        db,
        "companies",
        {"_id": "companies/1", "email": "a@example.com"},
        malicious,
    )

    assert malicious not in db.aql.last_query
    assert "LIMIT @limit" in db.aql.last_query
    assert db.aql.last_bind_vars["limit"] == malicious


# ---------------------------------------------------------------------------
# BlockingConfig computed-field validation wiring
# ---------------------------------------------------------------------------

def test_blocking_config_rejects_malicious_expression_by_default():
    cfg = BlockingConfig(
        strategy="collect",
        fields=[{"name": "evil", "expression": "d.x) REMOVE d IN companies //"}],
    )
    with pytest.raises(ValueError):
        cfg.parse_fields()


def test_blocking_config_allows_safe_expression():
    cfg = BlockingConfig(
        strategy="collect",
        fields=[{"name": "full", "expression": "CONCAT(d.first_name, d.last_name)"}],
    )
    names, computed = cfg.parse_fields()
    assert names == ["full"]
    assert computed["full"] == "CONCAT(d.first_name, d.last_name)"


def test_blocking_config_opt_in_bypasses_validation():
    cfg = BlockingConfig(
        strategy="collect",
        fields=[{"name": "raw", "expression": "(FOR v IN x RETURN v)"}],
        allow_unsafe_expressions=True,
    )
    names, computed = cfg.parse_fields()
    assert computed["raw"] == "(FOR v IN x RETURN v)"


# ---------------------------------------------------------------------------
# Edge-clear paths use bind variables (no value interpolation)
# ---------------------------------------------------------------------------

def test_similarity_edge_clear_uses_bind_vars():
    svc = SimilarityEdgeService.__new__(SimilarityEdgeService)
    svc.db = _FakeDB()
    svc.edge_collection_name = "similarTo"

    svc.clear_edges(method="phone_blocking", older_than="2025-01-01T00:00:00")

    query = svc.db.aql.last_query
    bind_vars = svc.db.aql.last_bind_vars
    assert "@method" in query and "@older_than" in query
    assert "phone_blocking" not in query
    assert "2025-01-01T00:00:00" not in query
    assert bind_vars.get("method") == "phone_blocking"
    assert bind_vars.get("older_than") == "2025-01-01T00:00:00"


def test_cross_collection_clear_inferred_uses_bind_vars():
    svc = CrossCollectionMatchingService.__new__(CrossCollectionMatchingService)
    svc.db = _FakeDB()
    svc.edge_collection_name = "inferredEdges"
    svc.logger = logging.getLogger("test")

    svc.clear_inferred_edges(older_than="2025-01-01T00:00:00")

    query = svc.db.aql.last_query
    bind_vars = svc.db.aql.last_bind_vars
    assert "@older_than" in query
    assert "2025-01-01T00:00:00" not in query
    assert bind_vars.get("older_than") == "2025-01-01T00:00:00"
