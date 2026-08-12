"""Categorical (multi-level) Fellegi-Sunter EM estimation.

The binary model collapses every similarity to agree/disagree at one cutoff,
discarding the gradation continuous comparators produce. Measured cost on the
public benchmarks: FS scored F1 0.117 against weighted similarity's 0.541 on
Abt-Buy, because word-based Jaccard over long text almost never clears a single
agreement threshold — ``m`` for the body field was learned as 0.0 and recall
collapsed to 0.062.

The scorer could already *consume* per-field comparison levels, but nothing
could learn, configure or persist them, so the capability was unreachable. These
tests cover the learning half and, critically, that its output round-trips into
the scorer — the join is where "built but never wired" defects live in this
repository.
"""

from __future__ import annotations

import numpy as np
import pytest

from entity_resolution.learning.em_estimator import (
    EMEstimator,
    assign_level,
    estimate_categorical_mu,
    estimate_mu,
)
from entity_resolution.learning.fellegi_sunter_scorer import FellegiSunterScorer

THREE_LEVELS = ["exact", "close", "else"]
THREE_THRESHOLDS = [0.9, 0.5, None]
THREE_SPEC = [
    {"name": "exact", "min_similarity": 0.9},
    {"name": "close", "min_similarity": 0.5},
    {"name": "else", "min_similarity": None},
]


def _synth_categorical(n=4000, lam=0.3, seed=0):
    """Two fields, three levels; matches concentrate high, non-matches low."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        if rng.random() < lam:
            rows.append([
                rng.choice([0, 1], p=[0.7, 0.3]),
                rng.choice([0, 1, 2], p=[0.6, 0.3, 0.1]),
            ])
        else:
            rows.append([
                rng.choice([1, 2], p=[0.1, 0.9]),
                rng.choice([1, 2], p=[0.05, 0.95]),
            ])
    return np.array(rows, dtype=float)


class TestLevelAssignment:
    """Training and scoring must bin a similarity identically."""

    @pytest.mark.parametrize(
        "similarity,expected",
        [
            (1.0, 0), (0.9, 0),            # boundary is inclusive
            (0.89, 1), (0.5, 1),
            (0.49, 2), (0.0, 2),
        ],
    )
    def test_thresholds_are_inclusive_and_ordered(self, similarity, expected):
        assert assign_level(similarity, THREE_THRESHOLDS) == expected

    def test_unobserved_is_the_null_level_not_the_lowest(self):
        """None must not collapse into the fallback level.

        Conflating them is the null-level bug in categorical form: a record
        lacking a field would be treated as maximally disagreeing on it.
        """
        assert assign_level(None, THREE_THRESHOLDS) is None
        assert assign_level(0.0, THREE_THRESHOLDS) == 2


class TestParameterRecovery:
    def test_recovers_known_level_probabilities(self):
        gamma = _synth_categorical()
        res = estimate_categorical_mu(
            gamma, {"title": THREE_LEVELS, "body": THREE_LEVELS}
        )

        assert res.converged
        assert res.lambda_ == pytest.approx(0.3, abs=0.06)
        # title's true m was [0.7, 0.3, 0.0].
        assert res.m["title"][0] == pytest.approx(0.7, abs=0.08)
        assert res.m["title"][1] == pytest.approx(0.3, abs=0.08)
        # The match class must favour the selective level over the fallback.
        assert res.m["title"][0] > res.u["title"][0]
        assert res.u["title"][2] > res.m["title"][2]

    def test_level_probabilities_sum_to_one(self):
        """The scorer validates this; a drifting sum makes learned models unusable."""
        res = estimate_categorical_mu(
            _synth_categorical(), {"title": THREE_LEVELS, "body": THREE_LEVELS}
        )
        for field in res.fields:
            assert sum(res.m[field]) == pytest.approx(1.0, abs=1e-9)
            assert sum(res.u[field]) == pytest.approx(1.0, abs=1e-9)

    def test_unseen_level_is_clipped_not_zero(self):
        """A level absent from training must not make log(m/u) infinite."""
        # Level 1 never occurs.
        gamma = np.array([[0.0], [0.0], [2.0], [2.0]])
        res = estimate_categorical_mu(gamma, {"f": THREE_LEVELS})

        assert res.m["f"][1] > 0.0
        assert res.u["f"][1] > 0.0
        assert all(np.isfinite(np.log(np.array(res.m["f"]) / np.array(res.u["f"]))))

    def test_two_levels_track_the_binary_estimator(self):
        """The binary model is the two-level special case.

        Tolerance is 0.025 against a measured delta of ~0.012 for m and ~0.004
        for u — tight enough to catch a genuine divergence rather than passing on
        slack. The residual difference is initialisation, not disagreement: the
        binary path starts at m=0.9/u=0.1 while the categorical one biases the
        most selective level to 0.8, so they settle in slightly different local
        optima of the same likelihood.
        """
        rng = np.random.default_rng(7)
        agree = (rng.random((3000, 2)) < np.where(
            (rng.random((3000, 1)) < 0.3), [0.9, 0.85], [0.1, 0.15]
        )).astype(float)

        binary = estimate_mu(agree, ["a", "b"])
        # Level 0 = agree, level 1 = disagree, so index = 1 - agreement.
        categorical = estimate_categorical_mu(
            1.0 - agree, {"a": ["agree", "disagree"], "b": ["agree", "disagree"]}
        )

        assert categorical.m["a"][0] == pytest.approx(binary.m["a"], abs=0.025)
        assert categorical.u["a"][0] == pytest.approx(binary.u["a"], abs=0.025)
        assert categorical.lambda_ == pytest.approx(binary.lambda_, abs=0.025)


class TestNullLevel:
    def test_unobserved_cells_do_not_count_toward_any_level(self):
        gamma = np.array([[0.0], [0.0], [np.nan], [np.nan], [2.0]])
        res = estimate_categorical_mu(gamma, {"f": THREE_LEVELS})
        assert res.observed_counts["f"] == 3

    def test_a_sparse_field_is_not_penalised_like_a_disagreeing_one(self):
        """Per-field denominators are what make this true.

        Field 'sparse' agrees whenever observed but is missing on most pairs;
        field 'dense' agrees exactly as often but is always observed. Their
        learned m must be comparable — using a global class denominator would
        drag the sparse field's m down in proportion to its emptiness.
        """
        rows = []
        for i in range(400):
            level = 0.0 if i % 2 == 0 else 2.0
            sparse = level if i % 10 == 0 else np.nan
            rows.append([level, sparse])
        gamma = np.array(rows)

        res = estimate_categorical_mu(
            gamma, {"dense": THREE_LEVELS, "sparse": THREE_LEVELS}
        )
        assert res.observed_counts["sparse"] < res.observed_counts["dense"]
        assert res.m["sparse"][0] == pytest.approx(res.m["dense"][0], abs=0.15)

    def test_all_unobserved_field_stays_finite(self):
        gamma = np.array([[0.0, np.nan], [2.0, np.nan], [0.0, np.nan]])
        res = estimate_categorical_mu(
            gamma, {"seen": THREE_LEVELS, "never": THREE_LEVELS}
        )
        assert res.observed_counts["never"] == 0
        assert all(np.isfinite(res.m["never"]))
        assert np.isfinite(res.log_likelihood)


class TestFixedU:
    def test_supplied_u_is_returned_unchanged(self):
        supplied = [0.02, 0.08, 0.90]
        res = estimate_categorical_mu(
            _synth_categorical(), {"title": THREE_LEVELS, "body": THREE_LEVELS},
            fixed_u={"title": supplied},
        )
        assert res.u["title"] == pytest.approx(supplied, abs=1e-6)

    def test_unlisted_fields_still_estimate_u(self):
        res = estimate_categorical_mu(
            _synth_categorical(), {"title": THREE_LEVELS, "body": THREE_LEVELS},
            fixed_u={"title": [0.02, 0.08, 0.90]},
        )
        assert res.u["body"][2] > res.u["body"][0], "body's u was still learned"

    def test_label_switching_is_skipped_when_u_is_measured(self):
        """Swapping would discard measured values and return an unestimated m."""
        supplied = [0.90, 0.08, 0.02]  # deliberately match-shaped
        res = estimate_categorical_mu(
            _synth_categorical(), {"title": THREE_LEVELS, "body": THREE_LEVELS},
            fixed_u={"title": supplied, "body": supplied},
        )
        assert res.u["title"] == pytest.approx(supplied, abs=1e-6)

    def test_wrong_length_is_rejected(self):
        with pytest.raises(ValueError, match="one probability per level"):
            estimate_categorical_mu(
                _synth_categorical(), {"title": THREE_LEVELS, "body": THREE_LEVELS},
                fixed_u={"title": [0.5, 0.5]},
            )


class TestValidation:
    def test_single_level_is_rejected(self):
        with pytest.raises(ValueError, match="at least two levels"):
            estimate_categorical_mu(np.zeros((3, 1)), {"f": ["only"]})

    def test_out_of_range_level_index_is_rejected(self):
        with pytest.raises(ValueError, match="outside 0"):
            estimate_categorical_mu(np.array([[5.0]]), {"f": THREE_LEVELS})

    def test_column_count_must_match(self):
        with pytest.raises(ValueError, match="columns"):
            estimate_categorical_mu(np.zeros((3, 2)), {"f": THREE_LEVELS})

    def test_empty_input_is_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            estimate_categorical_mu(np.empty((0, 1)), {"f": THREE_LEVELS})


class TestEstimatorIntegration:
    def _comparisons(self, n=3000, seed=1):
        rng = np.random.default_rng(seed)
        out = []
        for _ in range(n):
            if rng.random() < 0.3:
                out.append({"title": rng.uniform(0.85, 1.0), "body": rng.uniform(0.4, 1.0)})
            else:
                out.append({"title": rng.uniform(0.0, 0.45), "body": rng.uniform(0.0, 0.3)})
        return out

    def test_estimate_categorical_from_similarity_records(self):
        est = EMEstimator(field_names=["title", "body"])
        res = est.estimate_categorical(
            self._comparisons(), {"title": THREE_SPEC, "body": THREE_SPEC}
        )
        assert res.converged
        assert res.level_names["title"] == THREE_LEVELS
        assert res.m["title"][0] > res.u["title"][0]

    def test_missing_similarity_becomes_the_null_level(self):
        est = EMEstimator(field_names=["title", "body"])
        comparisons = self._comparisons()
        comparisons.append({"title": 0.95})  # body absent

        res = est.estimate_categorical(
            comparisons, {"title": THREE_SPEC, "body": THREE_SPEC}
        )
        assert res.observed_counts["title"] == res.observed_counts["body"] + 1

    def test_spec_without_a_fallback_level_is_rejected(self):
        est = EMEstimator(field_names=["title"])
        with pytest.raises(ValueError, match="fallback level"):
            est.estimate_categorical(
                self._comparisons(),
                {"title": [{"name": "exact", "min_similarity": 0.9}]},
            )

    def test_fields_with_no_levels_configured_are_skipped(self):
        """A partially configured model must not silently mix comparison models."""
        est = EMEstimator(field_names=["title", "body"])
        res = est.estimate_categorical(self._comparisons(), {"title": THREE_SPEC})
        assert res.fields == ["title"]

    def test_no_configured_fields_is_rejected(self):
        est = EMEstimator(field_names=["title"])
        with pytest.raises(ValueError, match="covers none"):
            est.estimate_categorical(self._comparisons(), {"other": THREE_SPEC})


class TestScorerRoundTrip:
    """The join: what EM learns must be what the scorer accepts.

    This is where this repository's recurring defect lives — a capability built
    on one side of a seam and never connected to the other.
    """

    def _trained(self):
        rng = np.random.default_rng(3)
        comparisons = []
        for _ in range(3000):
            if rng.random() < 0.3:
                comparisons.append({"title": rng.uniform(0.9, 1.0)})
            else:
                comparisons.append({"title": rng.uniform(0.0, 0.4)})
        est = EMEstimator(field_names=["title"])
        return est.estimate_categorical(comparisons, {"title": THREE_SPEC})

    def test_learned_levels_construct_a_scorer(self):
        levels = self._trained().to_comparison_levels({"title": THREE_THRESHOLDS})
        scorer = FellegiSunterScorer(
            m={"title": 0.9}, u={"title": 0.1}, comparison_levels=levels
        )
        assert scorer.comparison_levels["title"][0]["name"] == "exact"

    def test_learned_model_ranks_levels_monotonically(self):
        levels = self._trained().to_comparison_levels({"title": THREE_THRESHOLDS})
        scorer = FellegiSunterScorer(
            m={"title": 0.9}, u={"title": 0.1}, comparison_levels=levels
        )
        exact = scorer.total_llr({"title": 0.95})
        close = scorer.total_llr({"title": 0.6})
        worst = scorer.total_llr({"title": 0.1})
        assert exact > close > worst, (
            f"levels must be ordered by evidence: {exact} > {close} > {worst}"
        )

    def test_unobserved_field_contributes_nothing_through_levels(self):
        levels = self._trained().to_comparison_levels({"title": THREE_THRESHOLDS})
        scorer = FellegiSunterScorer(
            m={"title": 0.9}, u={"title": 0.1}, comparison_levels=levels
        )
        assert scorer.total_llr({}) == pytest.approx(0.0)
        assert scorer.total_llr({"title": None}) == pytest.approx(0.0)

    def test_threshold_count_mismatch_is_rejected(self):
        with pytest.raises(ValueError, match="one entry per level"):
            self._trained().to_comparison_levels({"title": [0.9, None]})

    def test_result_serialises_for_persistence(self):
        payload = self._trained().to_dict()
        assert set(payload) >= {
            "fields", "level_names", "m", "u", "lambda", "observed_counts",
        }
        assert payload["level_names"]["title"] == THREE_LEVELS


# ---------------------------------------------------------------------------
# Config schema and model identity
# ---------------------------------------------------------------------------


class TestComparisonLevelConfig:
    """Only STRUCTURE is configurable; m/u are learned.

    A hand-written level table that also asserted probabilities could contradict
    the data, so the config deliberately cannot express them.
    """

    def _config(self, levels):
        from entity_resolution.config.er_config import SimilarityConfig

        return SimilarityConfig(comparison_levels=levels)

    def test_shorthand_thresholds_expand_to_named_levels(self):
        cfg = self._config({"title": [0.95, 0.7]})
        assert cfg.comparison_levels["title"] == [
            {"name": "exact", "min_similarity": 0.95},
            {"name": "close", "min_similarity": 0.7},
            {"name": "else", "min_similarity": None},
        ]

    def test_explicit_levels_are_preserved(self):
        cfg = self._config({
            "title": [
                {"name": "identical", "min_similarity": 0.99},
                {"name": "other"},
            ]
        })
        assert [lvl["name"] for lvl in cfg.comparison_levels["title"]] == [
            "identical", "other",
        ]
        assert cfg.comparison_levels["title"][-1]["min_similarity"] is None

    def test_round_trips_through_to_dict(self):
        """A config flag dropped by to_dict is silently lost on save/reload.

        Levels change what every learned weight means, so losing them would make
        a persisted model unreproducible.
        """
        from entity_resolution.config.er_config import SimilarityConfig

        original = self._config({"title": [0.95, 0.7], "body": [0.8]})
        restored = SimilarityConfig.from_dict(original.to_dict())
        assert restored.comparison_levels == original.comparison_levels

    def test_absent_levels_keep_the_binary_model(self):
        assert self._config(None).comparison_levels == {}

    @pytest.mark.parametrize(
        "levels,message",
        [
            ({"t": [0.5, 0.9]}, "descend"),
            ({"t": [{"name": "x", "min_similarity": 0.5}]}, "fallback"),
            ({"t": []}, "non-empty"),
            ({"t": [1.5]}, r"\[0, 1\]"),
            ({"t": [{"name": "a", "min_similarity": 0.9}, {"name": "a"}]}, "duplicate"),
            ({"t": [{"min_similarity": 0.9}, {"name": "z"}]}, "needs a name"),
            ({"t": [0.9, 0.8, 0.7, 0.6, 0.5]}, "at most"),
        ],
    )
    def test_invalid_structures_are_rejected_by_field(self, levels, message):
        with pytest.raises(ValueError, match=message):
            self._config(levels)

    def test_error_names_the_offending_field(self):
        with pytest.raises(ValueError, match="comparison_levels\\['body'\\]"):
            self._config({"title": [0.9], "body": [0.1, 0.9]})


class TestModelIdentity:
    """Levels are part of a model's identity, not decoration."""

    def _hash(self, levels=None):
        from entity_resolution.learning.model_parameter_estimator import config_hash

        return config_hash(
            ["a", "b"], {"a": 0.85}, "jaccard", comparison_levels=levels
        )

    def test_changing_a_threshold_changes_the_hash(self):
        """Otherwise the loader hands back parameters learned under other bins."""
        at_95 = self._hash({"a": [{"name": "e", "min_similarity": 0.95},
                                  {"name": "x", "min_similarity": None}]})
        at_90 = self._hash({"a": [{"name": "e", "min_similarity": 0.90},
                                  {"name": "x", "min_similarity": None}]})
        assert at_95 != at_90

    def test_adding_levels_changes_the_hash(self):
        assert self._hash() != self._hash(
            {"a": [{"name": "e", "min_similarity": 0.9},
                   {"name": "x", "min_similarity": None}]}
        )

    def test_hash_is_stable_across_calls(self):
        levels = {"a": [{"name": "e", "min_similarity": 0.9},
                        {"name": "x", "min_similarity": None}]}
        assert self._hash(levels) == self._hash(levels)

    def test_binary_models_keep_their_existing_hash(self):
        """Backward compatibility: models trained before levels existed must load.

        Reproduces the pre-levels formula exactly; a drift here would orphan every
        previously trained model.
        """
        import hashlib
        import json

        payload = json.dumps(
            {"fields": ["a", "b"], "thresholds": {"a": 0.85}, "algorithm": "jaccard"},
            sort_keys=True,
        )
        legacy = hashlib.md5(payload.encode("utf-8")).hexdigest()[:16]
        assert self._hash() == legacy
