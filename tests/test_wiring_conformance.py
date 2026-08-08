"""Wiring conformance tests — the anti-drift layer.

These tests exist because a class of defects in this repo shared one root cause:
something was *built* but never *wired* into anything that would exercise it, and
the tests that should have caught it mocked the very seam that was broken.

The rules this file enforces:

1. Every public entry point is CONSTRUCTED FOR REAL, with the arguments its own
   signature declares. No ``MagicMock`` stands in for a class we own. The only
   thing faked is the database wire (``FakeDatabase`` below), because that is a
   genuine external boundary.
2. Cross-module call contracts are asserted directly: if module A calls
   ``B(x=...)`` or ``b.foo()``, a test here asserts that ``B`` accepts ``x`` and
   that ``foo`` exists. Signature drift then fails at test time, not at runtime
   in a user's pipeline.
3. Behavioural invariants that must hold for EVERY implementation of an interface
   are parametrized over all implementations, so a new backend or strategy
   inherits the checks automatically.

Known-broken paths are marked ``xfail(strict=True)`` — a defect ledger. When
someone fixes the underlying bug the test XPASSes, strict mode turns that into a
failure, and the marker must be removed. Nothing silently stays broken, and
nothing silently gets fixed without the ledger being updated.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any, Dict, List

import pytest

from entity_resolution.strategies.base_strategy import BlockingStrategy


# ---------------------------------------------------------------------------
# Database wire fake — the ONLY thing we are allowed to fake.
# ---------------------------------------------------------------------------


class FakeCursor(list):
    """AQL cursor stand-in; python-arango cursors are list-iterable."""


class FakeAQL:
    """Records executed AQL so tests can assert on the query text itself."""

    def __init__(self, results: List[Any] | None = None):
        self.results = results if results is not None else []
        self.executed: List[Dict[str, Any]] = []

    def execute(self, query, bind_vars=None, **kwargs):
        self.executed.append({"query": query, "bind_vars": bind_vars or {}})
        return FakeCursor(self.results)


class FakeCollection:
    def __init__(self, name: str):
        self.name = name

    def count(self):
        return 0

    def all(self, *args, **kwargs):
        return FakeCursor([])

    def insert_many(self, docs, **kwargs):
        return []

    def update_many(self, docs, **kwargs):
        return []


class FakeDatabase:
    """Minimal python-arango StandardDatabase stand-in.

    Deliberately NOT a MagicMock: attribute typos and calls to methods that do
    not exist must raise, rather than silently returning a Mock that makes a
    broken code path look like it worked.
    """

    def __init__(self, results: List[Any] | None = None):
        self.aql = FakeAQL(results)
        self.name = "conformance_test_db"

    def collection(self, name):
        return FakeCollection(name)

    def has_collection(self, name):
        return True

    def create_collection(self, name, **kwargs):
        return FakeCollection(name)

    def collections(self):
        return []

    def graphs(self):
        return []

    def has_graph(self, name):
        return False

    def properties(self):
        return {"name": self.name}


@pytest.fixture
def fake_db():
    return FakeDatabase()


# ---------------------------------------------------------------------------
# 1. Construction smoke: every blocking strategy builds for real.
# ---------------------------------------------------------------------------


def _discover_strategies():
    """Find every concrete BlockingStrategy subclass in the strategies package."""
    import entity_resolution.strategies as strategies_pkg

    found = {}
    for mod_info in pkgutil.iter_modules(strategies_pkg.__path__):
        module = importlib.import_module(
            f"entity_resolution.strategies.{mod_info.name}"
        )
        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, BlockingStrategy)
                and obj is not BlockingStrategy
                and obj.__module__ == module.__name__
            ):
                found[name] = obj
    return found


STRATEGY_CLASSES = _discover_strategies()

# Representative valid arguments per strategy. A strategy added without an entry
# here fails test_every_strategy_has_construction_coverage — so new code cannot
# quietly skip this layer.
STRATEGY_ARGS: Dict[str, Dict[str, Any]] = {
    "BM25BlockingStrategy": {
        "collection": "companies",
        "search_view": "companies_view",
        "search_field": "name",
    },
    "CollectBlockingStrategy": {
        "collection": "companies",
        "blocking_fields": ["state", "city"],
    },
    "GeographicBlockingStrategy": {
        "collection": "companies",
        # blocking_type defaults to "state", which requires a state field mapping
        "geographic_fields": {"state": "state"},
    },
    "GraphEmbeddingBlockingStrategy": {
        "collection": "companies",
        "edge_collection": "company_links",
    },
    "GraphTraversalBlockingStrategy": {
        "collection": "companies",
        "edge_collection": "has_phone",
        "intermediate_collection": "phones",
    },
    "HybridBlockingStrategy": {
        "collection": "companies",
        "search_view": "companies_view",
        # search_fields is a field -> weight mapping, not a list
        "search_fields": {"name": 1.0},
    },
    "LSHBlockingStrategy": {"collection": "companies"},
    "ShardParallelBlockingStrategy": {
        "collection": "companies",
        "blocking_fields": ["state"],
    },
    "VectorBlockingStrategy": {"collection": "companies"},
}


def test_every_strategy_has_construction_coverage():
    """A new strategy must be added to STRATEGY_ARGS, not silently untested."""
    missing = sorted(set(STRATEGY_CLASSES) - set(STRATEGY_ARGS))
    assert not missing, (
        f"Blocking strategies with no construction-smoke coverage: {missing}. "
        "Add valid constructor arguments to STRATEGY_ARGS in this file."
    )


@pytest.mark.parametrize("strategy_name", sorted(STRATEGY_ARGS))
def test_strategy_constructs_with_declared_signature(strategy_name, fake_db):
    """Construct each strategy for real and verify its declared interface.

    Catches constructor drift (renamed/removed kwargs) and missing interface
    methods — the failure mode behind the dead ``async_pipeline`` and
    ``orchestrator.from_config`` code paths.
    """
    cls = STRATEGY_CLASSES[strategy_name]
    instance = cls(db=fake_db, **STRATEGY_ARGS[strategy_name])

    assert isinstance(instance, BlockingStrategy)
    assert hasattr(instance, "generate_candidates"), (
        f"{strategy_name} must expose generate_candidates()"
    )
    assert callable(instance.generate_candidates)


@pytest.mark.parametrize("strategy_name", sorted(STRATEGY_ARGS))
def test_strategy_args_match_real_required_params(strategy_name):
    """Our test args must satisfy exactly the params the class truly requires.

    This keeps the ledger honest: if a constructor gains a required parameter,
    this fails rather than the strategy quietly becoming unconstructible.
    """
    cls = STRATEGY_CLASSES[strategy_name]
    sig = inspect.signature(cls.__init__)
    required = {
        p.name
        for p in sig.parameters.values()
        if p.name not in ("self", "db")
        and p.default is inspect.Parameter.empty
        and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    }
    provided = set(STRATEGY_ARGS[strategy_name])
    assert required <= provided, (
        f"{strategy_name} requires {sorted(required - provided)} "
        "which STRATEGY_ARGS does not supply"
    )
    unknown = provided - set(sig.parameters)
    assert not unknown, (
        f"{strategy_name} does not accept {sorted(unknown)} — signature drift"
    )


# ---------------------------------------------------------------------------
# 2. Cross-module call contracts (the seams mocks used to hide).
# ---------------------------------------------------------------------------


def test_batch_similarity_service_accepts_documented_kwargs():
    """BatchSimilarityService's real kwargs, asserted so callers can't drift.

    ``async_pipeline.py`` calls this with ``fields=``/``threshold=``, which do
    not exist; the correct parameter is ``field_weights``.
    """
    from entity_resolution.services.batch_similarity_service import (
        BatchSimilarityService,
    )

    params = inspect.signature(BatchSimilarityService.__init__).parameters
    assert "field_weights" in params
    assert "fields" not in params, (
        "BatchSimilarityService has no 'fields' param; callers passing fields= "
        "are broken (see async_pipeline.py)"
    )
    assert hasattr(BatchSimilarityService, "compute_similarities"), (
        "compute_similarities() is the real entry point (not compute_similarity)"
    )
    assert not hasattr(BatchSimilarityService, "compute_similarity")


def test_wcc_clustering_service_entry_point_is_cluster():
    """``async_pipeline`` calls ``find_clusters()``, which does not exist."""
    from entity_resolution.services.wcc_clustering_service import (
        WCCClusteringService,
    )

    assert hasattr(WCCClusteringService, "cluster")
    assert not hasattr(WCCClusteringService, "find_clusters"), (
        "find_clusters() does not exist; the entry point is cluster()"
    )


def test_similarity_config_has_no_edge_collection_attr():
    """Pins the attribute error behind the async pipeline's clustering stage."""
    from entity_resolution.config.er_config import SimilarityConfig

    cfg = SimilarityConfig()
    assert not hasattr(cfg, "edge_collection"), (
        "SimilarityConfig gained edge_collection — update async_pipeline.py "
        "and delete this assertion"
    )


def test_orchestrator_from_config_builds_bm25_strategy(fake_db):
    """``from_config`` must build the config shape its docstring documents."""
    from entity_resolution.core.orchestrator import MultiStrategyOrchestrator

    orchestrator = MultiStrategyOrchestrator.from_config(
        db=fake_db,
        config={
            "strategies": [
                {
                    "type": "bm25",
                    "collection": "companies",
                    "search_view": "companies_view",
                    "search_field": "name",
                    "bm25_threshold": 2.5,
                    "limit_per_entity": 15,
                }
            ]
        },
    )
    assert len(orchestrator.strategies) == 1
    strategy = orchestrator.strategies[0]
    assert strategy.search_view == "companies_view"
    assert strategy.bm25_threshold == 2.5
    assert strategy.limit_per_entity == 15


def test_orchestrator_from_config_accepts_legacy_bm25_aliases(fake_db):
    """Legacy view_name/top_n/score_threshold keys still build a strategy."""
    from entity_resolution.core.orchestrator import MultiStrategyOrchestrator

    orchestrator = MultiStrategyOrchestrator.from_config(
        db=fake_db,
        config={
            "strategies": [
                {
                    "type": "bm25",
                    "collection": "companies",
                    "search_field": "name",
                    "view_name": "companies_view",
                    "top_n": 10,
                    "score_threshold": 1.5,
                }
            ]
        },
    )
    strategy = orchestrator.strategies[0]
    assert strategy.search_view == "companies_view"
    assert strategy.limit_per_entity == 10
    assert strategy.bm25_threshold == 1.5


@pytest.mark.parametrize(
    "entry,missing",
    [
        ({"type": "bm25", "search_field": "name", "search_view": "v"}, "collection"),
        ({"type": "bm25", "collection": "c", "search_field": "name"}, "search_view"),
        ({"type": "collect", "collection": "c"}, "blocking_fields"),
    ],
)
def test_orchestrator_from_config_reports_missing_keys(fake_db, entry, missing):
    """A missing required key must name itself, not fail deep inside a builder."""
    from entity_resolution.core.orchestrator import MultiStrategyOrchestrator

    with pytest.raises(ValueError, match=missing):
        MultiStrategyOrchestrator.from_config(db=fake_db, config={"strategies": [entry]})


def test_orchestrator_from_config_builds_collect_strategy(fake_db):
    """The collect path must work with the documented config shape."""
    from entity_resolution.core.orchestrator import MultiStrategyOrchestrator

    orchestrator = MultiStrategyOrchestrator.from_config(
        db=fake_db,
        config={
            "strategies": [
                {
                    "type": "collect",
                    "collection": "companies",
                    "blocking_fields": ["state"],
                }
            ]
        },
    )
    assert len(orchestrator.strategies) == 1


# ---------------------------------------------------------------------------
# 3. Interface-wide behavioural invariants (parametrized over all impls).
# ---------------------------------------------------------------------------

IN_PROCESS_BACKENDS = [
    "python_union_find",
    "python_dfs",
    "python_sparse",
    "aql_graph",
]


def _build_backend(name: str, db):
    from entity_resolution.services.clustering_backends.aql_graph import (
        AQLGraphBackend,
    )
    from entity_resolution.services.clustering_backends.python_dfs import (
        PythonDFSBackend,
    )
    from entity_resolution.services.clustering_backends.python_sparse import (
        PythonSparseBackend,
    )
    from entity_resolution.services.clustering_backends.python_union_find import (
        PythonUnionFindBackend,
    )

    mapping = {
        "python_union_find": PythonUnionFindBackend,
        "python_dfs": PythonDFSBackend,
        "python_sparse": PythonSparseBackend,
        "aql_graph": AQLGraphBackend,
    }
    return mapping[name](db=db, edge_collection_name="similarTo")


@pytest.mark.parametrize("backend_name", IN_PROCESS_BACKENDS)
def test_backend_declares_its_name(backend_name, fake_db):
    backend = _build_backend(backend_name, fake_db)
    assert backend.backend_name() == backend_name


@pytest.mark.parametrize("backend_name", IN_PROCESS_BACKENDS)
def test_backend_excludes_suppressed_edges(backend_name, fake_db):
    """EVERY backend must honour analyst 'not a match' verdicts.

    A suppressed edge is a human decision. A backend that ignores it silently
    re-merges rejected pairs. Asserted on the AQL text because that is where
    the filter must live for the work to happen server-side.
    """
    backend = _build_backend(backend_name, fake_db)
    backend.cluster()

    assert fake_db.aql.executed, f"{backend_name} issued no query"
    queries = " ".join(call["query"] for call in fake_db.aql.executed)
    assert "suppressed" in queries, (
        f"{backend_name} does not filter suppressed edges — analyst "
        "'no_match' verdicts would be silently ignored"
    )


class _SuppressionAwareFakeDatabase(FakeDatabase):
    """FakeDatabase that reports a configurable suppressed-edge count.

    Lets the GAE tests drive both branches of ``_prepare_edge_source`` without a
    live engine: the count query decides whether a projection is materialised.
    """

    def __init__(self, suppressed_count: int):
        super().__init__()
        self.suppressed_count = suppressed_count
        self.created_collections: List[str] = []
        self.deleted_collections: List[str] = []
        self._existing = {"similarTo"}
        self.aql = self._make_aql()

    def _make_aql(self):
        outer = self

        class _AQL(FakeAQL):
            def execute(self, query, bind_vars=None, **kwargs):
                self.executed.append({"query": query, "bind_vars": bind_vars or {}})
                if "COLLECT WITH COUNT" in query:
                    return FakeCursor([outer.suppressed_count])
                return FakeCursor([])

        return _AQL()

    def has_collection(self, name):
        return name in self._existing

    def create_collection(self, name, **kwargs):
        self.created_collections.append(name)
        self._existing.add(name)
        return FakeCollection(name)

    def delete_collection(self, name):
        self.deleted_collections.append(name)
        self._existing.discard(name)
        return True


def _gae_backend(db):
    from entity_resolution.services.clustering_backends.gae_wcc import GAEWCCBackend

    return GAEWCCBackend(db=db, edge_collection_name="similarTo")


def test_gae_backend_excludes_suppressed_edges():
    """GAE must honour suppression like every in-process backend does.

    ``loaddata`` takes collection names, not queries, so the backend has to load
    an active-only projection. Asserted behaviourally: the projection is created
    and populated by a query that filters suppressed edges.
    """
    db = _SuppressionAwareFakeDatabase(suppressed_count=3)
    backend = _gae_backend(db)

    edge_source = backend._prepare_edge_source()

    assert edge_source != "similarTo", (
        "with suppressed edges present, GAE must not load the raw collection"
    )
    assert edge_source in db.created_collections
    copy_queries = [
        c["query"] for c in db.aql.executed if "INSERT" in c["query"].upper()
    ]
    assert copy_queries, "no projection-populating query was issued"
    assert any("suppressed" in q for q in copy_queries), (
        "the projection is populated without filtering suppressed edges, so "
        "analyst 'no_match' verdicts would still reach the engine"
    )


def test_gae_backend_skips_projection_when_nothing_suppressed():
    """No suppressed edges means no copy — the raw collection loads directly."""
    db = _SuppressionAwareFakeDatabase(suppressed_count=0)
    backend = _gae_backend(db)

    assert backend._prepare_edge_source() == "similarTo"
    assert db.created_collections == [], (
        "duplicating a possibly-huge edge collection is wasteful when there is "
        "nothing to filter out"
    )


def test_gae_backend_drops_its_projection():
    """The temporary projection must not be left behind."""
    db = _SuppressionAwareFakeDatabase(suppressed_count=1)
    backend = _gae_backend(db)

    target = backend._prepare_edge_source()
    backend._drop_temp_edge_collection()

    assert target in db.deleted_collections
    assert backend._temp_edge_collection is None


def test_gae_backend_recreates_a_stale_projection():
    """A leftover projection is dropped first, never silently reused.

    Reusing it would resurrect edges suppressed since the previous run.
    """
    db = _SuppressionAwareFakeDatabase(suppressed_count=1)
    stale = f"similarTo{'_gae_active'}"
    db._existing.add(stale)
    backend = _gae_backend(db)

    backend._prepare_edge_source()

    assert stale in db.deleted_collections
    assert stale in db.created_collections


@pytest.mark.parametrize("strategy_name", sorted(STRATEGY_ARGS))
def test_normalized_pairs_are_symmetric_and_ordered(strategy_name, fake_db):
    """Pair normalization must be canonical: (a,b) and (b,a) collapse to one."""
    cls = STRATEGY_CLASSES[strategy_name]
    strategy = cls(db=fake_db, **STRATEGY_ARGS[strategy_name])

    pairs = [
        {"doc1_key": "b", "doc2_key": "a"},
        {"doc1_key": "a", "doc2_key": "b"},
    ]
    normalized = strategy._normalize_pairs(pairs)

    assert len(normalized) == 1, "(a,b) and (b,a) must deduplicate to one pair"
    assert normalized[0]["doc1_key"] == "a"
    assert normalized[0]["doc2_key"] == "b"


@pytest.mark.parametrize("strategy_name", sorted(STRATEGY_ARGS))
def test_normalized_pairs_reject_self_pairs(strategy_name, fake_db):
    """A record must never be paired with itself, under any strategy.

    Self-pairs score 1.0, create self-loop edges and inflate cluster quality
    metrics. graph_traversal_blocking generates them from parallel edges, so
    this is enforced centrally in the base class and checked for every strategy.
    """
    cls = STRATEGY_CLASSES[strategy_name]
    strategy = cls(db=fake_db, **STRATEGY_ARGS[strategy_name])

    normalized = strategy._normalize_pairs([
        {"doc1_key": "a", "doc2_key": "a"},
        {"doc1_key": "a", "doc2_key": "b"},
    ])

    assert normalized == [{"doc1_key": "a", "doc2_key": "b"}], (
        f"{strategy_name} let a self-pair through: {normalized}"
    )


# ---------------------------------------------------------------------------
# 4. Config flags must reach a call site (the "built but never wired" check).
# ---------------------------------------------------------------------------


def test_collective_enabled_flag_is_reachable_from_run():
    """A config flag users can set must be consumed by the documented entry point."""
    import inspect as _inspect

    from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline

    run_source = _inspect.getsource(ConfigurableERPipeline.run)
    assert "run_collective" in run_source, (
        "ConfigurableERPipeline.run() never calls run_collective(), so "
        "collective.enabled cannot take effect"
    )
