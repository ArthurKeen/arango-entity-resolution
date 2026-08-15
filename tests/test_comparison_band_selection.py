"""Automatic comparison-band placement from the score distribution.

Benchmarking established that band PLACEMENT dominates band count: the same
model scored F1 0.388 with bands copied from another dataset versus 0.505 with
bands matched to its own distribution, because word-based Jaccard over long text
rarely exceeds ~0.6 so a 0.9 band sits empty. Placing bands by hand means either
inspecting the distribution or — as two of the published benchmark figures did —
tuning against labels a deployment does not have. This removes that dependency.

Three design decisions are load-bearing and each is pinned below:

* **Troughs, not variance.** Multi-level Otsu is the obvious generalisation and
  the wrong objective: variance is maximised by splitting where mass is
  concentrated, so when one mode dominates it subdivides that mode instead of
  separating it. Measured, it returned cuts at 0.29 and 0.11 on a distribution
  whose visible valley was near 0.45.
* **Separation between cuts.** Across an empty gap every bin is a local minimum
  of equal depth, so taking the top-n outright returns adjacent cuts and a
  middle band holding nothing.
* **Mass on both sides.** A single empty bin between two one-count bins in a
  Gaussian's tail scores maximum depth. Depth alone therefore accepts noise, and
  a unimodal distribution intermittently produced "bands".
"""

from __future__ import annotations

import random

import pytest

from entity_resolution.learning.threshold_selection import (
    BandSelection,
    select_comparison_bands,
)


def _bimodal(n_low=3000, n_high=600, seed=0):
    """The usual ER shape: many low-scoring non-matches, fewer high matches."""
    rng = random.Random(seed)
    return (
        [rng.gauss(0.10, 0.05) for _ in range(n_low)]
        + [rng.gauss(0.80, 0.06) for _ in range(n_high)]
    )


def _unimodal(n=3000, seed=0):
    rng = random.Random(seed)
    return [rng.gauss(0.4, 0.12) for _ in range(n)]


def _trimodal(seed=0):
    rng = random.Random(seed)
    return (
        [rng.gauss(0.1, 0.03) for _ in range(2000)]
        + [rng.gauss(0.5, 0.03) for _ in range(800)]
        + [rng.gauss(0.9, 0.03) for _ in range(500)]
    )


class TestPlacement:
    def test_cut_lands_between_the_modes_not_inside_one(self):
        """The defect that ruled out the variance criterion."""
        selection = select_comparison_bands(_bimodal(), n_thresholds=1)

        assert len(selection.thresholds) == 1
        cut = selection.thresholds[0]
        assert 0.2 < cut < 0.75, (
            f"cut at {cut} is inside a mode; it must fall in the gap between "
            "the non-match mass near 0.10 and the match mass near 0.80"
        )

    def test_two_cuts_are_not_adjacent(self):
        """Without suppression both cuts land in the same empty gap."""
        selection = select_comparison_bands(_bimodal(), n_thresholds=2)

        assert len(selection.thresholds) == 2
        assert selection.thresholds[0] - selection.thresholds[1] > 0.05, (
            f"cuts {selection.thresholds} are adjacent, leaving an empty band"
        )

    def test_thresholds_are_returned_descending(self):
        """Most selective first, matching the level structure consumers expect."""
        selection = select_comparison_bands(_trimodal(), n_thresholds=2)
        assert selection.thresholds == sorted(selection.thresholds, reverse=True)

    def test_separate_gaps_are_found_in_a_trimodal_distribution(self):
        selection = select_comparison_bands(_trimodal(), n_thresholds=2)

        assert len(selection.thresholds) == 2
        high, low = selection.thresholds
        assert high > 0.6, f"expected a cut in the 0.5-0.9 gap, got {high}"
        assert low < 0.45, f"expected a cut in the 0.1-0.5 gap, got {low}"

    def test_reports_the_evidence_for_its_choice(self):
        selection = select_comparison_bands(_bimodal(), n_thresholds=2)
        assert selection.method == "valley_detection"
        assert selection.diagnostics["sample_size"] == 3600
        assert len(selection.diagnostics["valley_depths"]) == 2
        assert selection.warning is None


class TestRefusal:
    """Declining is information, not a failure: it says the matcher is not
    separating classes on this data, and bands will not fix that."""

    @pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
    def test_unimodal_scores_are_refused_across_samples(self, seed):
        """Tail troughs score maximum depth, so this must hold on every draw."""
        selection = select_comparison_bands(_unimodal(seed=seed), n_thresholds=2)

        assert selection.thresholds == []
        assert selection.method == "fallback"
        assert "no separation" in (selection.warning or "")

    def test_identical_scores_are_refused(self):
        selection = select_comparison_bands([0.5] * 500, n_thresholds=1)
        assert selection.thresholds == []
        assert "identical" in (selection.warning or "")

    def test_too_few_scores_are_refused(self):
        assert select_comparison_bands([0.5], n_thresholds=1).thresholds == []

    def test_empty_input_is_refused(self):
        assert select_comparison_bands([], n_thresholds=1).thresholds == []

    def test_returns_fewer_bands_rather_than_manufacturing_them(self):
        """A distribution with one separation must not be forced into three.

        Forcing extra cuts invents structure, and the benchmark already showed
        more bands is not better.
        """
        selection = select_comparison_bands(_bimodal(), n_thresholds=3)
        assert len(selection.thresholds) < 3


class TestValidation:
    def test_rejects_zero_thresholds(self):
        with pytest.raises(ValueError, match="at least 1"):
            select_comparison_bands(_bimodal(), n_thresholds=0)

    def test_rejects_more_than_three_thresholds(self):
        with pytest.raises(ValueError, match="above 3"):
            select_comparison_bands(_bimodal(), n_thresholds=4)

    def test_non_finite_scores_are_ignored(self):
        scores = _bimodal() + [float("nan"), float("inf"), None]
        selection = select_comparison_bands(scores, n_thresholds=1)
        assert selection.diagnostics["sample_size"] == 3600


class TestLevelStructure:
    """Output must drop straight into the config/scorer level shape."""

    def test_converts_to_comparison_levels_with_a_fallback(self):
        selection = select_comparison_bands(_bimodal(), n_thresholds=2)
        levels = selection.to_comparison_levels()

        assert [lvl["name"] for lvl in levels] == ["exact", "close", "else"]
        assert levels[-1]["min_similarity"] is None
        assert levels[0]["min_similarity"] > levels[1]["min_similarity"]

    def test_accepts_custom_level_names(self):
        selection = select_comparison_bands(_bimodal(), n_thresholds=1)
        levels = selection.to_comparison_levels(names=["strong"])
        assert [lvl["name"] for lvl in levels] == ["strong", "else"]

    def test_rejects_a_name_count_mismatch(self):
        selection = select_comparison_bands(_bimodal(), n_thresholds=2)
        with pytest.raises(ValueError, match="one name per threshold"):
            selection.to_comparison_levels(names=["only-one"])

    def test_output_is_accepted_by_the_config_validator(self):
        """The join: inferred bands must satisfy the same rules a hand-written
        table does, or automatic placement cannot actually be used."""
        from entity_resolution.config.er_config import SimilarityConfig

        selection = select_comparison_bands(_bimodal(), n_thresholds=2)
        config = SimilarityConfig(
            comparison_levels={"title": selection.to_comparison_levels()}
        )
        assert len(config.comparison_levels["title"]) == 3

    def test_output_is_accepted_by_the_scorer(self):
        """And by the runtime, once EM has filled in the probabilities."""
        from entity_resolution.learning.em_estimator import EMEstimator

        selection = select_comparison_bands(_bimodal(), n_thresholds=2)
        specs = selection.to_comparison_levels()
        comparisons = [{"title": s} for s in _bimodal(n_low=400, n_high=100)]

        result = EMEstimator(field_names=["title"]).estimate_categorical(
            comparisons, {"title": specs}
        )
        assert result.level_names["title"] == ["exact", "close", "else"]

    def test_serialises_for_persistence(self):
        payload = select_comparison_bands(_bimodal(), n_thresholds=2).to_dict()
        assert set(payload) == {"thresholds", "method", "diagnostics", "warning"}
        assert isinstance(payload["thresholds"], list)


def test_selection_is_deterministic_for_identical_input():
    """Same scores must yield the same bands; a model's identity depends on it."""
    scores = _bimodal()
    first = select_comparison_bands(scores, n_thresholds=2)
    second = select_comparison_bands(scores, n_thresholds=2)
    assert first.thresholds == second.thresholds
    assert isinstance(first, BandSelection)
