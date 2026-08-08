"""Tests for data-driven decision-threshold selection.

Threshold choice dominates matcher sophistication: on the public benchmarks the
shipped 0.8 default reached F1 0.067 where 0.35 reached 0.541. These tests pin
the behaviour that replaces that constant, including the guards that stop it
returning a confident-looking number from a distribution that cannot support one.
"""

from __future__ import annotations

import random

import pytest

from entity_resolution.learning.threshold_selection import (
    ThresholdSelection,
    otsu_threshold,
    score_distribution_diagnostics,
    select_threshold_supervised,
    select_threshold_unsupervised,
)


# ---------------------------------------------------------------------------
# Unsupervised (Otsu)
# ---------------------------------------------------------------------------


def _bimodal(n_low=800, n_high=200, low_centre=0.15, high_centre=0.85, spread=0.05):
    """Scores shaped like a real ER run: many non-matches, fewer matches."""
    rng = random.Random(7)
    low = [max(0.0, min(1.0, rng.gauss(low_centre, spread))) for _ in range(n_low)]
    high = [max(0.0, min(1.0, rng.gauss(high_centre, spread))) for _ in range(n_high)]
    return low + high


class TestOtsu:
    def test_finds_the_valley_between_two_modes(self):
        threshold, diagnostics = otsu_threshold(_bimodal())

        # The cut must land between the modes, not inside either one.
        assert 0.15 < threshold < 0.85
        assert diagnostics["valley_depth"] > 0.3, (
            "two clearly separated populations must show a real trough"
        )

    def test_separates_the_populations_it_was_derived_from(self):
        scores = _bimodal()
        threshold, _ = otsu_threshold(scores)
        below = [s for s in scores if s < threshold]
        above = [s for s in scores if s >= threshold]

        assert len(below) == pytest.approx(800, abs=60)
        assert len(above) == pytest.approx(200, abs=60)

    def test_reports_no_valley_for_a_unimodal_distribution(self):
        """One blob of similar scores cannot support a meaningful cut.

        Note this asserts valley_depth, NOT separability. Splitting any single
        Gaussian at its mean gives separability 2/pi ~= 0.637, so separability
        cannot distinguish unimodal from bimodal — an early version of this
        guard used it and waved unimodal input straight through.
        """
        rng = random.Random(3)
        scores = [rng.gauss(0.5, 0.05) for _ in range(1000)]

        _threshold, diagnostics = otsu_threshold(scores)

        assert diagnostics["valley_depth"] < 0.15
        assert diagnostics["separability"] > 0.5, (
            "separability stays high for unimodal input — that is exactly why it "
            "is not the guard"
        )

    def test_identical_scores_fall_back(self):
        threshold, diagnostics = otsu_threshold([0.7] * 100)
        assert threshold == 0.5
        assert "identical" in diagnostics["reason"]

    def test_empty_input_falls_back(self):
        threshold, diagnostics = otsu_threshold([])
        assert threshold == 0.5
        assert diagnostics["reason"] == "no finite scores"

    def test_ignores_none_and_non_finite_values(self):
        scores = _bimodal() + [None, float("nan"), float("inf")]  # type: ignore[list-item]
        threshold, diagnostics = otsu_threshold(scores)
        assert 0.15 < threshold < 0.85
        assert diagnostics["sample_size"] == 1000


class TestSelectThresholdUnsupervised:
    def test_selects_a_threshold_for_a_bimodal_run(self):
        result = select_threshold_unsupervised(_bimodal())

        assert isinstance(result, ThresholdSelection)
        assert result.method == "otsu"
        assert result.regime == "unsupervised"
        assert result.warning is None
        assert 0.15 < result.threshold < 0.85

    def test_weakly_bimodal_input_falls_back_with_a_warning(self):
        """The important guard: do not hand back a confident-looking number.

        If blocking produced only near-duplicates, every pair scores similarly
        and Otsu would still return a precise-looking cut with no meaning.
        """
        rng = random.Random(11)
        scores = [rng.gauss(0.8, 0.02) for _ in range(500)]

        result = select_threshold_unsupervised(scores)

        assert result.threshold == 0.5, "must use the fallback, not the Otsu cut"
        assert result.method == "fallback"
        assert result.warning is not None
        assert "valley depth" in result.warning
        assert "select_threshold_supervised" in result.warning, (
            "the warning should point at the accurate alternative"
        )

    def test_min_valley_depth_is_configurable(self):
        rng = random.Random(5)
        scores = [rng.gauss(0.8, 0.02) for _ in range(500)]

        permissive = select_threshold_unsupervised(scores, min_valley_depth=0.0)

        assert permissive.warning is None
        assert permissive.method == "otsu"

    def test_custom_fallback_is_honoured(self):
        result = select_threshold_unsupervised([0.5] * 50, fallback=0.42)
        assert result.threshold == 0.42

    def test_rejects_unknown_method(self):
        with pytest.raises(ValueError, match="unknown method"):
            select_threshold_unsupervised([0.1, 0.9], method="kmeans")

    def test_diagnostics_are_auditable(self):
        result = select_threshold_unsupervised(_bimodal())
        d = result.diagnostics
        for key in ("valley_depth", "separability", "sample_size", "median", "p25", "p75", "stdev"):
            assert key in d, f"missing diagnostic {key}"


# ---------------------------------------------------------------------------
# Supervised
# ---------------------------------------------------------------------------


def _labelled():
    """Scored pairs with known truth: matches score high, non-matches low."""
    scored = []
    truth = set()
    for i in range(50):
        a, b = f"a{i}", f"b{i}"
        scored.append((a, b, 0.9))
        truth.add((a, b))
    for i in range(200):
        scored.append((f"x{i}", f"y{i}", 0.2))
    return scored, truth


class TestSelectThresholdSupervised:
    def test_finds_the_separating_threshold(self):
        scored, truth = _labelled()

        result = select_threshold_supervised(scored, truth)

        assert result.regime == "supervised"
        assert result.method == "supervised_sweep"
        assert 0.2 < result.threshold <= 0.9
        assert result.metrics["f1"] == pytest.approx(1.0), (
            "perfectly separable data must yield F1 1.0 at the right cut"
        )

    def test_pair_order_does_not_matter(self):
        """Pairs are canonicalised, so (b,a) still matches truth (a,b)."""
        scored = [("b0", "a0", 0.9), ("y1", "x1", 0.1)]
        truth = {("a0", "b0")}

        result = select_threshold_supervised(scored, truth)

        assert result.metrics["recall"] == pytest.approx(1.0)

    def test_min_precision_constraint_is_respected(self):
        scored, truth = _labelled()
        # Add noise that scores as high as the matches, capping precision.
        scored += [(f"n{i}", f"m{i}", 0.9) for i in range(50)]

        result = select_threshold_supervised(scored, truth, min_precision=0.9)

        assert result.warning is not None, (
            "precision 0.9 is unreachable here, so the caller must be told"
        )

    def test_min_recall_constraint_selects_a_lower_threshold(self):
        scored, truth = _labelled()
        strict = select_threshold_supervised(scored, truth, min_recall=1.0)
        assert strict.metrics["recall"] == pytest.approx(1.0)

    def test_objective_recall_prefers_higher_recall(self):
        scored, truth = _labelled()
        by_recall = select_threshold_supervised(scored, truth, objective="recall")
        assert by_recall.objective == "recall"
        assert by_recall.metrics["recall"] == pytest.approx(1.0)

    def test_rejects_unknown_objective(self):
        scored, truth = _labelled()
        with pytest.raises(ValueError, match="objective must be"):
            select_threshold_supervised(scored, truth, objective="accuracy")

    def test_no_scored_pairs_falls_back(self):
        result = select_threshold_supervised([], {("a", "b")})
        assert result.threshold == 0.5
        assert result.method == "fallback"
        assert "no scored pairs" in result.warning

    def test_no_truth_pairs_falls_back(self):
        result = select_threshold_supervised([("a", "b", 0.9)], set())
        assert result.threshold == 0.5
        assert "no truth pairs" in result.warning

    def test_supervised_beats_unsupervised_on_the_same_data(self):
        """Labels are worth having: the sweep should match or beat Otsu."""
        scored, truth = _labelled()
        scores = [s for _a, _b, s in scored]

        sup = select_threshold_supervised(scored, truth)
        unsup = select_threshold_unsupervised(scores)

        def f1_at(threshold):
            predicted = {tuple(sorted((a, b))) for a, b, s in scored if s >= threshold}
            tp = len(predicted & truth)
            p = tp / len(predicted) if predicted else 0.0
            r = tp / len(truth)
            return 2 * p * r / (p + r) if (p + r) else 0.0

        assert f1_at(sup.threshold) >= f1_at(unsup.threshold)


class TestDiagnostics:
    def test_quantiles_are_ordered(self):
        d = score_distribution_diagnostics(_bimodal())
        assert d["min"] <= d["p25"] <= d["median"] <= d["p75"] <= d["max"]
        assert d["sample_size"] == 1000

    def test_empty_input(self):
        assert score_distribution_diagnostics([]) == {"sample_size": 0}

    def test_single_value(self):
        d = score_distribution_diagnostics([0.6])
        assert d["median"] == pytest.approx(0.6)
        assert d["stdev"] == pytest.approx(0.0)


def test_selection_serialises_for_persistence():
    """The chosen operating point must be persistable alongside the scores."""
    result = select_threshold_unsupervised(_bimodal())
    payload = result.to_dict()
    assert set(payload) >= {"threshold", "method", "regime", "diagnostics"}
    assert isinstance(payload["threshold"], float)


class TestPipelineWiring:
    """auto_threshold must be reachable from config, not just importable.

    A config flag users can set that no entry point consumes is the recurring
    defect class in this repo, so the wiring is asserted directly.
    """

    def test_config_accepts_and_round_trips_the_flag(self):
        from entity_resolution.config.er_config import SimilarityConfig

        cfg = SimilarityConfig.from_dict(
            {"threshold": 0.8, "auto_threshold": True,
             "auto_threshold_min_valley_depth": 0.25}
        )
        assert cfg.auto_threshold is True
        assert cfg.auto_threshold_min_valley_depth == 0.25

        # to_dict/from_dict must not silently drop it.
        again = SimilarityConfig.from_dict(cfg.to_dict())
        assert again.auto_threshold is True
        assert again.auto_threshold_min_valley_depth == 0.25

    def test_default_is_off_so_existing_runs_are_unchanged(self):
        from entity_resolution.config.er_config import SimilarityConfig

        assert SimilarityConfig().auto_threshold is False

    def test_pipeline_consumes_the_flag(self):
        """run_similarity must branch on auto_threshold and call the selector."""
        import inspect

        from entity_resolution.core.configurable_pipeline import (
            ConfigurableERPipeline,
        )

        run_sim = inspect.getsource(ConfigurableERPipeline.run_similarity)
        assert "auto_threshold" in run_sim, (
            "run_similarity never checks auto_threshold, so setting it would be "
            "silently ignored"
        )
        auto = inspect.getsource(
            ConfigurableERPipeline._run_similarity_with_auto_threshold
        )
        assert "select_threshold_unsupervised" in auto
        # Scoring must happen at 0.0 first, or there is no distribution to
        # infer a threshold from.
        assert "threshold=0.0" in auto
        assert "return_all=True" in auto

    def test_selection_is_reported_in_results(self):
        """The operating point must travel with the results it produced."""
        import inspect

        from entity_resolution.core.configurable_pipeline import (
            ConfigurableERPipeline,
        )

        run = inspect.getsource(ConfigurableERPipeline.run)
        assert "'auto_threshold': self._auto_threshold_selection" in run


class TestLoadLatestDisambiguation:
    """load_latest() must not return a model from a different configuration.

    Each config hash starts its own version sequence at 1, so sorting by version
    alone leaves several models tied and the winner is whatever the storage
    engine returns. That silently scores with parameters trained for a different
    field set or agreement threshold — and it produced a real order-dependent
    test failure plus a benchmark run where every threshold setting appeared to
    give identical results.
    """

    def _estimator(self, docs):
        from unittest.mock import MagicMock

        from entity_resolution.learning import ModelParameterEstimator

        db = MagicMock()
        db.has_collection.return_value = True
        captured = {}

        def execute(query, bind_vars=None, **_kw):
            captured["query"] = query
            captured["bind_vars"] = bind_vars or {}
            if bind_vars and "h" in bind_vars:
                return [d for d in docs if d["config_hash"] == bind_vars["h"]]
            # Emulate the server honouring the ORDER BY in the query.
            if "created_at DESC" in query:
                return sorted(docs, key=lambda d: d["created_at"], reverse=True)[:1]
            return sorted(docs, key=lambda d: d["version"], reverse=True)[:1]

        db.aql.execute.side_effect = execute
        est = ModelParameterEstimator(
            db=db, similarity_service=MagicMock(), edge_collection="e",
            field_names=["name"],
        )
        return est, captured

    def _docs(self):
        return [
            {"config_hash": "aaa", "version": 1, "created_at": "2026-01-01T00:00:00",
             "m": {"name": 0.1}},
            {"config_hash": "bbb", "version": 1, "created_at": "2026-06-01T00:00:00",
             "m": {"name": 0.9}},
        ]

    def test_without_hash_returns_most_recently_created(self):
        est, captured = self._estimator(self._docs())

        latest = est.load_latest()

        assert latest["config_hash"] == "bbb", (
            "two models tied at version 1 — the newer one must win, not an "
            "arbitrary pick"
        )
        assert "created_at DESC" in captured["query"]

    def test_with_hash_selects_that_configuration(self):
        est, _captured = self._estimator(self._docs())
        assert est.load_latest("aaa")["config_hash"] == "aaa"

    def test_missing_collection_returns_none(self):
        from unittest.mock import MagicMock

        from entity_resolution.learning import ModelParameterEstimator

        db = MagicMock()
        db.has_collection.return_value = False
        est = ModelParameterEstimator(
            db=db, similarity_service=MagicMock(), edge_collection="e",
            field_names=["name"],
        )
        assert est.load_latest() is None
