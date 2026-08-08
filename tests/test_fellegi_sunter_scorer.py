"""Unit tests for the runtime FellegiSunterScorer (plan 1.1B)."""

from __future__ import annotations

import math

import pytest

from entity_resolution.learning.fellegi_sunter_scorer import FellegiSunterScorer


def _scorer(**kw):
    return FellegiSunterScorer(
        m={"name": 0.9, "city": 0.8},
        u={"name": 0.05, "city": 0.2},
        default_threshold=0.85,
        **kw,
    )


def test_full_agreement_scores_higher_than_full_disagreement():
    s = _scorer()
    agree = s.score({"name": 0.99, "city": 0.95})
    disagree = s.score({"name": 0.1, "city": 0.2})
    assert agree > 0.5 > disagree
    assert 0.0 <= disagree < agree <= 1.0


def test_posterior_matches_sigmoid_of_llr_plus_prior_logit():
    s = _scorer(match_prior=0.3)
    fs = {"name": 0.99, "city": 0.10}  # name agrees, city disagrees
    llr = math.log(0.9 / 0.05) + math.log((1 - 0.8) / (1 - 0.2))
    prior_logit = math.log(0.3 / 0.7)
    expected = 1.0 / (1.0 + math.exp(-(llr + prior_logit)))
    assert s.score(fs) == pytest.approx(expected)


def test_more_agreeing_fields_increase_posterior():
    s = _scorer()
    one = s.score({"name": 0.99, "city": 0.1})
    two = s.score({"name": 0.99, "city": 0.99})
    assert two > one


def test_missing_field_is_null_level_not_disagreement():
    """An unobserved field carries no evidence; an observed mismatch does.

    This previously asserted the opposite (missing == explicit 0.0). That was a
    statistical defect, not a contract: charging the disagreement LLR for data a
    record simply does not have pushes sparse-but-identical records below
    threshold so they never merge.
    """
    s = _scorer()
    explicit_disagreement = s.score({"name": 0.99, "city": 0.0})
    missing = s.score({"name": 0.99})  # city absent -> null level

    assert missing > explicit_disagreement, (
        "a missing field must not be penalised as heavily as an observed mismatch"
    )
    # Exactly zero contribution: the pair scores as if the model had only
    # 'name'. Same m/u as _scorer() so the only difference is city's absence.
    name_only = FellegiSunterScorer(
        m={"name": 0.9}, u={"name": 0.05}, default_threshold=0.85
    )
    assert s.total_llr({"name": 0.99}) == pytest.approx(
        name_only.total_llr({"name": 0.99})
    )


def test_explicit_zero_still_counts_as_disagreement():
    """0.0 means 'compared, completely different' and must keep its penalty.

    Guards the distinction the null level depends on: if a caller coerces
    missing values to 0.0, this is the behaviour they get.
    """
    s = _scorer()
    assert s.total_llr({"name": 0.99, "city": 0.0}) < s.total_llr({"name": 0.99})


def test_observed_fields_counts_only_supplied_evidence():
    s = _scorer()
    assert s.observed_fields({"name": 0.9, "city": 0.1}) == 2
    assert s.observed_fields({"name": 0.9}) == 1
    assert s.observed_fields({"name": 0.9, "city": None}) == 1
    assert s.observed_fields({}) == 0


def test_from_model_doc_uses_stored_thresholds_and_lambda():
    doc = {
        "m": {"name": 0.9}, "u": {"name": 0.1},
        "agreement_thresholds": {"name": 0.6}, "lambda": 0.2,
    }
    s = FellegiSunterScorer.from_model_doc(doc)
    # sim 0.7 >= stored threshold 0.6 -> agreement, even though < default 0.85.
    assert s.score({"name": 0.7}) > s.score({"name": 0.5})
    assert s.match_prior == pytest.approx(0.2)


def test_multi_level_comparisons_preserve_fuzzy_evidence():
    scorer = FellegiSunterScorer(
        m={"name": 0.8},
        u={"name": 0.01},
        comparison_levels={
            "name": [
                {"name": "exact", "min_similarity": 1.0, "m": 0.80, "u": 0.01},
                {"name": "fuzzy", "min_similarity": 0.85, "m": 0.15, "u": 0.09},
                {"name": "else", "m": 0.05, "u": 0.90},
            ]
        },
    )

    exact = scorer.total_llr({"name": 1.0})
    fuzzy = scorer.total_llr({"name": 0.9})
    disagree = scorer.total_llr({"name": 0.2})

    assert exact > fuzzy > 0.0 > disagree
    assert scorer.total_llr({"name": None}) == 0.0


def test_multi_level_model_document_loads_and_explains_selected_level():
    doc = {
        "m": {"name": 0.8},
        "u": {"name": 0.01},
        "lambda": 0.2,
        "comparison_levels": {
            "name": [
                {"name": "exact", "min_similarity": 1.0, "m": 0.80, "u": 0.01},
                {"name": "fuzzy", "min_similarity": 0.85, "m": 0.15, "u": 0.09},
                {"name": "else", "m": 0.05, "u": 0.90},
            ]
        },
    }

    scorer = FellegiSunterScorer.from_model_doc(doc)
    entry = scorer.explain({"name": 0.9})["fields"][0]

    assert entry["state"] == "fuzzy"
    assert entry["comparison_level"] == "fuzzy"
    assert entry["llr"] == pytest.approx(math.log(0.15 / 0.09))
    assert scorer.match_prior == pytest.approx(0.2)


def test_multi_level_probabilities_must_sum_to_one():
    with pytest.raises(ValueError, match="must sum to 1"):
        FellegiSunterScorer(
            m={"name": 0.8},
            u={"name": 0.01},
            comparison_levels={
                "name": [
                    {"name": "exact", "min_similarity": 1.0, "m": 0.8, "u": 0.01},
                    {"name": "else", "m": 0.1, "u": 0.9},
                ]
            },
        )


def test_rejects_empty_params():
    with pytest.raises(ValueError):
        FellegiSunterScorer(m={}, u={})


# ---------------------------------------------------------------------------
# Term-frequency adjustment (Splink's second pillar)
# ---------------------------------------------------------------------------

from entity_resolution.learning.fellegi_sunter_scorer import (  # noqa: E402
    term_frequency_tables_from_docs,
)

# 'Smith' is common, 'Xanthopoulos' is rare.
_TF = {"name": {"Smith": 0.20, "Xanthopoulos": 0.0005}}


def _tf_scorer(**kw):
    return FellegiSunterScorer(
        m={"name": 0.9, "city": 0.8},
        u={"name": 0.05, "city": 0.2},
        default_threshold=0.85,
        term_frequencies=_TF,
        **kw,
    )


def test_rare_value_agreement_outweighs_common_value_agreement():
    """The whole point of TF adjustment.

    Both pairs agree perfectly on name. Agreeing on a rare surname is far
    stronger evidence of identity than agreeing on a common one; without TF
    adjustment the two are scored identically.
    """
    s = _tf_scorer()
    common = s.total_llr({"name": 1.0}, {"name": "Smith"})
    rare = s.total_llr({"name": 1.0}, {"name": "Xanthopoulos"})

    assert rare > common
    # Rarity spans ~400x here, so the weight gap should be substantial.
    assert rare - common > 2.0


def test_common_value_scores_below_the_unadjusted_average():
    """A very common value must be WEAKER evidence than the average."""
    s = _tf_scorer()
    unadjusted = s.total_llr({"name": 1.0})
    common = s.total_llr({"name": 1.0}, {"name": "Smith"})

    assert common < unadjusted, (
        "agreeing on a value 4x more common than the average chance rate should "
        "carry less weight than the average"
    )


def test_tf_adjustment_only_applies_on_exact_agreement():
    """A fuzzy match between two different values has no frequency to look up."""
    s = _tf_scorer()
    fuzzy = s.total_llr({"name": 0.93})  # agrees, but values differ
    assert fuzzy == pytest.approx(s.total_llr({"name": 0.93}, {}))


def test_unknown_value_falls_back_to_base_weight():
    """A value outside the persisted top-N table uses the average, not a guess."""
    s = _tf_scorer()
    assert s.total_llr({"name": 1.0}, {"name": "NotInTable"}) == pytest.approx(
        s.total_llr({"name": 1.0})
    )


def test_field_without_a_tf_table_is_unaffected():
    s = _tf_scorer()
    assert s.total_llr({"city": 1.0}, {"city": "Boston"}) == pytest.approx(
        s.total_llr({"city": 1.0})
    )


def test_tf_adjustment_does_not_affect_disagreement():
    """Disagreement weight comes from (1-m)/(1-u); rarity is irrelevant there."""
    s = _tf_scorer()
    assert s.total_llr({"name": 0.1}, {"name": "Xanthopoulos"}) == pytest.approx(
        s.total_llr({"name": 0.1})
    )


def test_scorer_without_tf_tables_is_unchanged():
    """TF is opt-in: omitting the tables preserves the previous behaviour."""
    plain = _scorer()
    assert plain.total_llr({"name": 1.0}, {"name": "Smith"}) == pytest.approx(
        plain.total_llr({"name": 1.0})
    )


class TestExplain:
    """Match-weight waterfall — the glass-box counterpart to an LLM rationale."""

    def test_field_contributions_sum_to_total(self):
        s = _tf_scorer()
        scores = {"name": 1.0, "city": 0.2}
        report = s.explain(scores, {"name": "Xanthopoulos"})

        assert report["total_llr"] == pytest.approx(
            sum(e["llr"] for e in report["fields"])
        )
        assert report["total_llr"] == pytest.approx(
            s.total_llr(scores, {"name": "Xanthopoulos"})
        )
        assert report["posterior"] == pytest.approx(
            s.score(scores, {"name": "Xanthopoulos"})
        )

    def test_states_are_labelled(self):
        s = _tf_scorer()
        report = s.explain({"name": 1.0, "city": None})
        states = {e["field"]: e["state"] for e in report["fields"]}
        assert states == {"name": "agree", "city": "not_observed"}

    def test_unobserved_field_contributes_zero(self):
        s = _tf_scorer()
        report = s.explain({"name": 1.0})
        city = next(e for e in report["fields"] if e["field"] == "city")
        assert city["llr"] == 0.0

    def test_reports_tf_delta_and_direction(self):
        s = _tf_scorer()
        rare = s.explain({"name": 1.0}, {"name": "Xanthopoulos"})
        common = s.explain({"name": 1.0}, {"name": "Smith"})

        rare_entry = next(e for e in rare["fields"] if e["field"] == "name")
        common_entry = next(e for e in common["fields"] if e["field"] == "name")

        assert rare_entry["tf_adjusted"] and common_entry["tf_adjusted"]
        assert rare_entry["tf_delta"] > 0, "a rare value must add weight"
        assert common_entry["tf_delta"] < 0, "a common value must remove weight"
        assert rare_entry["value_frequency"] == 0.0005


class TestTermFrequencyTableLoading:
    def test_from_persisted_documents(self):
        docs = [
            {
                "_key": "name", "field": "name", "total": 1000,
                "top_values": [
                    {"value": "Smith", "count": 200, "relative_frequency": 0.2},
                    {"value": "Jones", "count": 50, "relative_frequency": 0.05},
                ],
            }
        ]
        tables = term_frequency_tables_from_docs(docs)
        assert tables == {"name": {"Smith": 0.2, "Jones": 0.05}}

    def test_recomputes_missing_relative_frequency(self):
        """Tables written before relative_frequency existed still load."""
        docs = [{
            "field": "city", "total": 400,
            "top_values": [{"value": "Boston", "count": 100}],
        }]
        assert term_frequency_tables_from_docs(docs) == {"city": {"Boston": 0.25}}

    def test_accepts_in_memory_compute_output(self):
        computed = {
            "name": {"total": 10, "top_values": [
                {"value": "Smith", "count": 5, "relative_frequency": 0.5}
            ]}
        }
        assert term_frequency_tables_from_docs(computed) == {"name": {"Smith": 0.5}}

    def test_ignores_empty_and_zero_frequency_entries(self):
        docs = [{"field": "x", "total": 0, "top_values": [{"value": "a", "count": 0}]}]
        assert term_frequency_tables_from_docs(docs) == {}
