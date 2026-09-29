"""Binary ``u`` counted from random pairs must stay inside the sample's resolution.

The rate was clamped away from 0 but not from 1, so a near-constant field reached
``u = 1.0``. Downstream clipping kept the log finite, but at ``1 - 1e-6``: one
disagreement on such a field then scored about +9 nats of match evidence at
``m = 0.99``, a number chosen by an epsilon rather than by the data.
"""

from __future__ import annotations

import math

import pytest

from entity_resolution.learning.fellegi_sunter_scorer import FellegiSunterScorer
from entity_resolution.learning.model_parameter_estimator import binary_u_from_comparisons

FIELDS = ["country", "name"]
THRESHOLDS = {"country": 0.9, "name": 0.8}


def _u(comparisons):
    return binary_u_from_comparisons(comparisons, FIELDS, THRESHOLDS, 0.8)


def test_constant_field_is_clamped_below_one() -> None:
    n = 99
    u = _u([{"country": 1.0, "name": 0.1}] * n)
    assert u["country"] == pytest.approx(n / (n + 1))


def test_never_agreeing_field_is_clamped_above_zero() -> None:
    n = 99
    u = _u([{"country": 1.0, "name": 0.1}] * n)
    assert u["name"] == pytest.approx(1 / (n + 1))


def test_interior_rate_is_the_plain_count() -> None:
    comps = [{"country": 1.0, "name": 0.9}] * 3 + [{"country": 0.0, "name": 0.1}] * 7
    assert _u(comps) == {"country": pytest.approx(0.3), "name": pytest.approx(0.3)}


def test_unobserved_values_are_not_counted_and_unseen_fields_are_omitted() -> None:
    comps = [{"country": 1.0}, {"country": 0.0, "name": None}]
    u = _u(comps)
    assert u == {"country": pytest.approx(0.5)}


def test_disagreement_weight_on_a_constant_field_is_bounded_by_the_sample() -> None:
    # The end-to-end consequence, through the real scorer.
    n = 10_000
    u = _u([{"country": 1.0, "name": 0.5}] * n)
    scorer = FellegiSunterScorer(
        m={"country": 0.99, "name": 0.9}, u=u, agreement_thresholds=THRESHOLDS
    )
    disagree = scorer._llr_disagree["country"]
    assert disagree == pytest.approx(math.log(0.01 / (1 / (n + 1))), rel=1e-6)
    assert disagree < 5.0  # was +9.21 with u clipped at 1 - 1e-6
