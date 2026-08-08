"""Integration test: ModelParameterEstimator end-to-end on real ArangoDB (plan 1.1A)."""

from __future__ import annotations

import uuid

import pytest

from entity_resolution.config.er_config import (
    BlockingConfig,
    ERPipelineConfig,
    SimilarityConfig,
)
from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline
from entity_resolution.learning import ModelParameterEstimator
from entity_resolution.services.batch_similarity_service import BatchSimilarityService


@pytest.fixture
def estimation_fixture(db_connection):
    suffix = uuid.uuid4().hex[:8]
    vcol = f"itm_person_{suffix}"
    ecol = f"itm_similar_{suffix}"
    db = db_connection
    db.create_collection(vcol)
    db.create_collection(ecol, edge=True)

    def vid(k):
        return f"{vcol}/{k}"

    # 10 near-duplicate (match-like) pairs and 10 clearly-different pairs.
    records = []
    edges = []
    for i in range(10):
        records += [
            # Match pairs: near-identical names (one-char variation), same city.
            {"_key": f"m{i}a", "name": "Jonathon Smith", "city": "Boston"},
            {"_key": f"m{i}b", "name": "Jonathan Smith", "city": "Boston"},
            # Non-match pairs: clearly different names and cities.
            {"_key": f"x{i}a", "name": "Alice Walker", "city": "Seattle"},
            {"_key": f"x{i}b", "name": "Bob Martinez", "city": "Miami"},
        ]
        edges += [
            {"_from": vid(f"m{i}a"), "_to": vid(f"m{i}b"), "similarity": 0.9},
            {"_from": vid(f"x{i}a"), "_to": vid(f"x{i}b"), "similarity": 0.3},
        ]
    db.collection(vcol).insert_many(records)
    db.collection(ecol).insert_many(edges)

    yield db, vcol, ecol
    for n in (vcol, ecol, "er_model_params", "er_term_frequencies"):
        if db.has_collection(n):
            db.delete_collection(n)


def test_estimate_persist_and_term_frequencies(estimation_fixture):
    db, vcol, ecol = estimation_fixture
    sim = BatchSimilarityService(
        db=db, collection=vcol,
        field_weights={"name": 0.6, "city": 0.4},
        similarity_algorithm="jaro_winkler",
    )
    estimator = ModelParameterEstimator(
        db=db, similarity_service=sim, edge_collection=ecol,
        field_names=["name", "city"], default_threshold=0.7,
    )

    out = estimator.run(source_collection=vcol, sample_size=100)

    # m should exceed u for both fields (matches agree far more often).
    model = out["model"]
    assert model["m"]["name"] > model["u"]["name"]
    assert model["m"]["city"] > model["u"]["city"]
    assert out["version"] == 1

    # Params persisted and reloadable.
    latest = estimator.load_latest()
    assert latest["version"] == 1
    assert latest["fields"] == ["name", "city"]

    # Term-frequency table: 'Boston' is the most common city.
    tf = db.collection("er_term_frequencies").get("city")
    assert tf is not None
    assert tf["top_values"][0]["value"] == "Boston"


def test_sparse_fields_remain_unobserved_through_training_samples(estimation_fixture):
    """Real DB fetches must not turn missing fields into FS disagreements."""
    db, vcol, ecol = estimation_fixture
    db.collection(vcol).insert_many([
        {"_key": "sparse_a", "name": "Sparse Person"},
        {"_key": "sparse_b", "name": "Sparse Person"},
    ])
    db.collection(ecol).insert({
        "_from": f"{vcol}/sparse_a",
        "_to": f"{vcol}/sparse_b",
        "similarity": 1.0,
    })

    sim = BatchSimilarityService(
        db=db, collection=vcol,
        field_weights={"name": 0.6, "city": 0.4},
        similarity_algorithm="jaro_winkler",
    )

    # Keep the public method's legacy float-only behavior unless explicitly
    # requested, but preserve the null level for probabilistic training.
    legacy = sim.compute_similarities_detailed(
        [("sparse_a", "sparse_b")], threshold=0.0
    )
    preserved = sim.compute_similarities_detailed(
        [("sparse_a", "sparse_b")], threshold=0.0, preserve_missing=True
    )
    assert legacy[0]["field_scores"]["city"] == 0.0
    assert preserved[0]["field_scores"]["city"] is None

    estimator = ModelParameterEstimator(
        db=db, similarity_service=sim, edge_collection=ecol,
        field_names=["name", "city"], default_threshold=0.7,
    )
    candidate_samples = estimator.sample_comparisons(100)
    random_samples = estimator.sample_random_pair_comparisons(100, vcol)

    assert any(row.get("city") is None for row in candidate_samples)
    assert any(row.get("city") is None for row in random_samples)


def test_production_pipeline_loads_and_applies_term_frequencies(estimation_fixture):
    """The configured FS service must use TF tables persisted during training.

    Trains through ``pipeline.build_model_parameter_estimator`` because that is
    exactly what ``arango-er estimate`` does. Models are looked up by
    configuration hash (fields, agreement thresholds, algorithm), so training
    through the pipeline is what makes a train-then-run cycle match by
    construction. Constructing the estimator by hand with different thresholds
    produces a different hash, no match, and a silent fallback to
    weighted_heuristic — which is the real trap this test now exercises the
    happy path of.
    """
    db, vcol, ecol = estimation_fixture

    config = ERPipelineConfig(
        entity_type="person",
        collection_name=vcol,
        edge_collection=ecol,
        blocking=BlockingConfig(strategy="exact", fields=["name"]),
        similarity=SimilarityConfig(
            algorithm="jaro_winkler",
            field_weights={"name": 0.6, "city": 0.4},
            scoring_method="fellegi_sunter",
            match_prior=0.5,
        ),
    )
    pipeline = ConfigurableERPipeline(db=db, config=config)

    sim = BatchSimilarityService(
        db=db, collection=vcol,
        field_weights={"name": 0.6, "city": 0.4},
        similarity_algorithm="jaro_winkler",
    )
    pipeline.build_model_parameter_estimator(sim).run(
        source_collection=vcol, sample_size=100
    )

    service = pipeline.build_similarity_service()

    assert service.scoring_method == "fellegi_sunter"
    assert service.fs_scorer.term_frequencies["city"]["Boston"] == pytest.approx(0.5)
    # Seattle occurs half as often as Boston. Exact agreement on it must
    # therefore carry more evidence in the actual production scoring path.
    common_score = service._score_pair(
        {"name": None, "city": "Boston"},
        {"name": None, "city": "Boston"},
    )
    rarer_score = service._score_pair(
        {"name": None, "city": "Seattle"},
        {"name": None, "city": "Seattle"},
    )
    assert rarer_score > common_score


def test_learned_params_drive_fs_scoring_and_separate_classes(estimation_fixture):
    """End-to-end: estimate m/u, score with FS, and verify it separates the classes."""
    db, vcol, ecol = estimation_fixture
    sim = BatchSimilarityService(
        db=db, collection=vcol,
        field_weights={"name": 0.6, "city": 0.4},
        similarity_algorithm="jaro_winkler",
    )
    estimator = ModelParameterEstimator(
        db=db, similarity_service=sim, edge_collection=ecol,
        field_names=["name", "city"], default_threshold=0.7,
    )
    estimator.run(source_collection=vcol, sample_size=100)

    # Build an FS-scoring similarity service from the learned params.
    from entity_resolution.learning.fellegi_sunter_scorer import FellegiSunterScorer

    doc = estimator.load_latest()
    fs_scorer = FellegiSunterScorer.from_model_doc(doc)
    fs_sim = BatchSimilarityService(
        db=db, collection=vcol,
        field_weights={"name": 0.6, "city": 0.4},
        similarity_algorithm="jaro_winkler",
        scoring_method="fellegi_sunter",
        fs_scorer=fs_scorer,
    )

    match_scores = fs_sim.compute_similarities([("m0a", "m0b")], threshold=0.0, return_all=True)
    non_scores = fs_sim.compute_similarities([("x0a", "x0b")], threshold=0.0, return_all=True)

    # FS posterior should be clearly high for the match pair, low for the
    # non-match. The absolute floor is loose on purpose. u is measured from a
    # RANDOM sample of record pairs, and this fixture holds only four distinct
    # value patterns, so chance agreement legitimately lands anywhere around
    # 0.4-0.5 between runs — which moves the match posterior between roughly
    # 0.67 and 0.81. A tight floor here makes the test flaky rather than strict;
    # a bigger or more varied fixture is the real fix if precision is wanted.
    # (The earlier >0.9 was only reachable with the inflated discrimination of a
    # u inferred from candidate pairs alone.)
    assert match_scores[0][2] > 0.6
    assert non_scores[0][2] < 0.1
    # Separation is the property that actually matters and is stable across
    # sampling variation.
    assert match_scores[0][2] - non_scores[0][2] > 0.5
    # And the posteriors are valid probabilities.
    assert 0.0 <= non_scores[0][2] < match_scores[0][2] <= 1.0


def test_u_is_measured_from_random_pairs_not_candidate_edges(estimation_fixture):
    """u must come from a random-pair sample, not the biased candidate set.

    The candidate edge collection is deliberately half match-like pairs, so EM
    run over it alone has to explain a large agreeing population and lands on an
    inflated u. Random pairs drawn from the source collection are almost all
    non-matches, so their agreement rate is the honest u.
    """
    db, vcol, ecol = estimation_fixture
    # The base fixture intentionally repeats only four value patterns, which is
    # useful for class-separation tests but too small for a stable random-pair
    # frequency assertion. Add unique non-candidate records so the source
    # population represents unrelated entities regardless of RAND() ordering.
    db.collection(vcol).insert_many([
        {
            "_key": f"random_{i}",
            "name": f"unique-name-{i}",
            "city": f"unique-city-{i}",
        }
        for i in range(200)
    ])
    sim = BatchSimilarityService(
        db=db, collection=vcol,
        field_weights={"name": 0.6, "city": 0.4},
        similarity_algorithm="jaro_winkler",
    )
    estimator = ModelParameterEstimator(
        db=db, similarity_service=sim, edge_collection=ecol,
        field_names=["name", "city"], default_threshold=1.0,
    )

    u_random = estimator.estimate_u_from_random_pairs(200, vcol)

    assert set(u_random) == {"name", "city"}
    for field, value in u_random.items():
        assert 0.0 < value <= 1.0, f"u[{field}] out of range: {value}"
    # Most random name pairs are unrelated people, so chance agreement is low.
    assert u_random["name"] < 0.5, (
        f"u[name]={u_random['name']:.3f} — random pairs should rarely agree on name"
    )


def test_run_records_u_provenance_and_anchors_u(estimation_fixture):
    """run() threads source_collection through, and the model records how."""
    db, vcol, ecol = estimation_fixture
    sim = BatchSimilarityService(
        db=db, collection=vcol,
        field_weights={"name": 0.6, "city": 0.4},
        similarity_algorithm="jaro_winkler",
    )
    estimator = ModelParameterEstimator(
        db=db, similarity_service=sim, edge_collection=ecol,
        field_names=["name", "city"], default_threshold=0.7,
    )

    out = estimator.run(source_collection=vcol, sample_size=100, u_sample_size=200)

    assert out["u_estimation"] == "random_pairs"
    persisted = estimator.load_latest()
    assert persisted["u_estimation"] == "random_pairs", (
        "provenance must survive persistence — weights learned under a biased u "
        "are not comparable with weights learned under a measured one"
    )
    # Deliberately NOT comparing against a second call to
    # estimate_u_from_random_pairs: that draws an INDEPENDENT random sample, so
    # comparing the two is comparing two random variables. On this small fixture
    # they legitimately differ by more than any tolerance worth asserting (0.25
    # vs 0.55 observed), which made this test flaky twice. Assert instead what is
    # deterministic: every field got a persisted u that is a valid probability.
    assert set(persisted["u"]) == {"name", "city"}
    for field, value in persisted["u"].items():
        assert 0.0 < value <= 1.0, f"u[{field}] is not a probability: {value}"


def test_falls_back_to_joint_em_without_source_collection(estimation_fixture):
    """Backward compatibility: no source collection -> old joint estimation."""
    db, vcol, ecol = estimation_fixture
    sim = BatchSimilarityService(
        db=db, collection=vcol,
        field_weights={"name": 0.6, "city": 0.4},
        similarity_algorithm="jaro_winkler",
    )
    estimator = ModelParameterEstimator(
        db=db, similarity_service=sim, edge_collection=ecol,
        field_names=["name", "city"], default_threshold=0.7,
    )

    estimator.estimate(sample_size=100)  # no source_collection

    assert estimator._last_u_estimation == "joint_em_candidates_only"


def test_explain_match_includes_probabilistic_waterfall(estimation_fixture, monkeypatch):
    """explain_match surfaces the calibrated decomposition once a model exists.

    The heuristic mean says "these look similar"; the waterfall says which
    evidence moved the decision and by how much, in additive log-odds. That is
    the auditable artifact a data steward can defend a merge with.
    """
    db, vcol, ecol = estimation_fixture
    sim = BatchSimilarityService(
        db=db, collection=vcol,
        field_weights={"name": 0.6, "city": 0.4},
        similarity_algorithm="jaro_winkler",
    )
    ModelParameterEstimator(
        db=db, similarity_service=sim, edge_collection=ecol,
        field_names=["name", "city"], default_threshold=0.7,
    ).run(source_collection=vcol, sample_size=100)

    from entity_resolution.mcp.tools import entity as entity_tools

    # run_explain_match opens its own client; point it at this test database.
    monkeypatch.setattr(entity_tools, "ArangoClient", lambda hosts: _StubClient(db))

    result = entity_tools.run_explain_match(
        host="localhost", port=8529, username="root", password="x",
        database=db.name, collection=vcol,
        key_a="m0a", key_b="m0b", fields=["name", "city"],
    )

    report = result["probabilistic"]
    assert report is not None, "a trained model exists, so a waterfall is expected"
    assert report["model_version"] == 1
    assert report["u_estimation"] == "random_pairs"
    # Additive in log-odds: the parts must sum to the whole.
    assert report["total_llr"] == pytest.approx(
        sum(f["llr"] for f in report["fields"])
    )
    assert 0.0 <= report["posterior"] <= 1.0
    states = {f["field"]: f["state"] for f in report["fields"]}
    assert states["name"] == "agree"


def test_explain_match_without_a_trained_model_returns_none(estimation_fixture, monkeypatch):
    """An untrained deployment must still get a working explain_match."""
    db, vcol, _ecol = estimation_fixture
    for name in ("er_model_params", "er_term_frequencies"):
        if db.has_collection(name):
            db.delete_collection(name)

    from entity_resolution.mcp.tools import entity as entity_tools

    monkeypatch.setattr(entity_tools, "ArangoClient", lambda hosts: _StubClient(db))
    result = entity_tools.run_explain_match(
        host="localhost", port=8529, username="root", password="x",
        database=db.name, collection=vcol,
        key_a="m0a", key_b="m0b", fields=["name"],
    )

    assert result["probabilistic"] is None
    # The heuristic breakdown is unaffected.
    assert result["overall_score"] > 0
    assert "name" in result["field_breakdown"]


class _StubClient:
    """Returns the already-connected test database, ignoring credentials."""

    def __init__(self, db):
        self._db = db

    def db(self, *_args, **_kwargs):
        return self._db


def test_config_mismatch_reports_the_mismatch_not_missing_model(
    estimation_fixture, caplog
):
    """A model trained under other settings must not look like "never trained".

    Parameters are only valid for the comparison settings they were estimated
    under, so a config-hash miss correctly refuses to reuse them. But the two
    causes need different fixes, and telling a user who just ran
    `arango-er estimate` to run it again sends them in a circle.
    """
    import logging

    db, vcol, ecol = estimation_fixture

    trained_config = ERPipelineConfig(
        entity_type="person", collection_name=vcol, edge_collection=ecol,
        blocking=BlockingConfig(strategy="exact", fields=["name"]),
        similarity=SimilarityConfig(
            algorithm="jaro_winkler",
            field_weights={"name": 0.6, "city": 0.4},
            scoring_method="fellegi_sunter",
        ),
    )
    sim = BatchSimilarityService(
        db=db, collection=vcol,
        field_weights={"name": 0.6, "city": 0.4},
        similarity_algorithm="jaro_winkler",
    )
    ConfigurableERPipeline(
        db=db, config=trained_config
    ).build_model_parameter_estimator(sim).run(
        source_collection=vcol, sample_size=100
    )

    # Same data, different agreement thresholds => different configuration.
    changed_config = ERPipelineConfig(
        entity_type="person", collection_name=vcol, edge_collection=ecol,
        blocking=BlockingConfig(strategy="exact", fields=["name"]),
        similarity=SimilarityConfig(
            algorithm="jaro_winkler",
            field_weights={"name": 0.6, "city": 0.4},
            scoring_method="fellegi_sunter",
            agreement_thresholds={"name": 0.5, "city": 0.5},
        ),
    )

    with caplog.at_level(logging.WARNING):
        service = ConfigurableERPipeline(
            db=db, config=changed_config
        ).build_similarity_service()

    # Refusing to reuse mismatched parameters is the correct behaviour.
    assert service.scoring_method == "weighted_heuristic"

    message = " ".join(r.getMessage() for r in caplog.records)
    assert "no model matches this configuration" in message
    assert "different configurations" in message, (
        "the warning must say a model EXISTS under other settings, not imply "
        "nothing was ever trained"
    )


def test_list_model_configurations_reports_each_trained_config(estimation_fixture):
    """Diagnostics need one row per configuration, not per model version."""
    db, vcol, ecol = estimation_fixture
    sim = BatchSimilarityService(
        db=db, collection=vcol,
        field_weights={"name": 0.6, "city": 0.4},
        similarity_algorithm="jaro_winkler",
    )
    estimator = ModelParameterEstimator(
        db=db, similarity_service=sim, edge_collection=ecol,
        field_names=["name", "city"], default_threshold=0.7,
    )
    estimator.run(source_collection=vcol, sample_size=100)
    estimator.run(source_collection=vcol, sample_size=100)  # v2, same config

    configs = estimator.list_model_configurations()
    assert len(configs) == 1, "two versions of one config must collapse to one row"
    assert configs[0]["config_hash"] == estimator.configuration_hash()
    assert configs[0]["version"] == 2


def test_no_models_at_all_says_so(estimation_fixture, caplog):
    """The genuinely-untrained case keeps its own, actionable message."""
    import logging

    db, vcol, ecol = estimation_fixture
    for name in ("er_model_params", "er_term_frequencies"):
        if db.has_collection(name):
            db.delete_collection(name)

    config = ERPipelineConfig(
        entity_type="person", collection_name=vcol, edge_collection=ecol,
        blocking=BlockingConfig(strategy="exact", fields=["name"]),
        similarity=SimilarityConfig(
            algorithm="jaro_winkler",
            field_weights={"name": 0.6, "city": 0.4},
            scoring_method="fellegi_sunter",
        ),
    )
    with caplog.at_level(logging.WARNING):
        service = ConfigurableERPipeline(db=db, config=config).build_similarity_service()

    assert service.scoring_method == "weighted_heuristic"
    message = " ".join(r.getMessage() for r in caplog.records)
    assert "no model parameters exist" in message
    assert "no model matches this configuration" not in message
