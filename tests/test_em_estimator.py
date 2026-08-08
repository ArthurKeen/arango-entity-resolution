"""Unit tests for Fellegi-Sunter EM estimation (plan 1.1)."""

from __future__ import annotations

import numpy as np
import pytest

from entity_resolution.learning.em_estimator import EMEstimator, estimate_mu


def _synthesize(rng, n, lam, m, u):
    """Generate (gamma, is_match) from known parameters."""
    m = np.asarray(m)
    u = np.asarray(u)
    is_match = rng.random(n) < lam
    probs = np.where(is_match[:, None], m[None, :], u[None, :])
    gamma = (rng.random((n, len(m))) < probs).astype(float)
    return gamma, is_match


def test_recovers_known_parameters():
    """Acceptance: EM recovers synthetic m/u/lambda within tolerance."""
    rng = np.random.default_rng(42)
    true_lambda = 0.2
    true_m = [0.95, 0.90, 0.85]
    true_u = [0.05, 0.10, 0.20]
    gamma, _ = _synthesize(rng, 40000, true_lambda, true_m, true_u)

    res = estimate_mu(gamma, ["f0", "f1", "f2"])

    assert res.converged
    assert res.lambda_ == pytest.approx(true_lambda, abs=0.03)
    for i, f in enumerate(["f0", "f1", "f2"]):
        assert res.m[f] == pytest.approx(true_m[i], abs=0.05)
        assert res.u[f] == pytest.approx(true_u[i], abs=0.05)


def test_resolves_label_switching_from_inverted_init():
    """Even initialized 'backwards', the match class ends up high-agreement."""
    rng = np.random.default_rng(7)
    gamma, _ = _synthesize(rng, 20000, 0.25, [0.92, 0.88], [0.08, 0.15])

    res = estimate_mu(gamma, ["a", "b"], init_m=0.1, init_u=0.9, init_lambda=0.9)

    # m must dominate u regardless of initialization.
    assert res.m["a"] > res.u["a"]
    assert res.m["b"] > res.u["b"]
    assert res.lambda_ < 0.5


def test_weights_collapse_equivalent_to_expanded():
    """Weighted unique patterns == expanding them into repeated rows."""
    patterns = np.array([[1.0, 1.0], [1.0, 0.0], [0.0, 0.0]])
    counts = np.array([500.0, 300.0, 200.0])
    weighted = estimate_mu(patterns, ["a", "b"], weights=counts, init_lambda=0.4)

    expanded = np.repeat(patterns, counts.astype(int), axis=0)
    full = estimate_mu(expanded, ["a", "b"], init_lambda=0.4)

    assert weighted.lambda_ == pytest.approx(full.lambda_, abs=1e-6)
    assert weighted.m["a"] == pytest.approx(full.m["a"], abs=1e-6)
    assert weighted.u["b"] == pytest.approx(full.u["b"], abs=1e-6)


def test_empty_input_raises():
    with pytest.raises(ValueError, match="at least one"):
        estimate_mu(np.empty((0, 2)), ["a", "b"])


def test_field_count_mismatch_raises():
    with pytest.raises(ValueError, match="columns"):
        estimate_mu(np.ones((3, 2)), ["only_one"])


def test_result_to_dict_roundtrips_fields():
    rng = np.random.default_rng(1)
    gamma, _ = _synthesize(rng, 5000, 0.3, [0.9, 0.8], [0.1, 0.2])
    d = estimate_mu(gamma, ["x", "y"]).to_dict()
    assert set(d["m"]) == {"x", "y"}
    assert 0.0 <= d["lambda"] <= 1.0
    assert d["n_pairs"] == 5000


class TestEMEstimatorWrapper:
    def test_build_gamma_binarizes_at_threshold(self):
        est = EMEstimator(field_names=["name", "city"], default_threshold=0.85)
        comparisons = [
            {"name": 0.95, "city": 0.40},
            {"name": 0.20, "city": 0.90},
        ]
        gamma = est.build_gamma(comparisons)
        assert gamma.tolist() == [[1.0, 0.0], [0.0, 1.0]]

    def test_build_gamma_marks_unobserved_fields_nan_not_zero(self):
        """Missing != disagreement.

        This previously asserted ``[1.0, 0.0]`` for a row with city absent,
        which conflated "not compared" with "compared and different" and biased
        every sparse field's m downward. NaN lets estimate_mu mask the cell.
        """
        est = EMEstimator(field_names=["name", "city"], default_threshold=0.85)
        gamma = est.build_gamma([{"name": 0.86}, {"name": 0.9, "city": None}])

        assert gamma[0][0] == 1.0
        assert np.isnan(gamma[0][1]), "absent field must be NaN, not 0.0"
        assert np.isnan(gamma[1][1]), "explicit None must be NaN, not 0.0"

    def test_estimate_mu_masks_unobserved_cells(self):
        """A field's m/u is estimated only where it was observed.

        Two datasets are identical except that in the second, the 'city' column
        is unobserved (NaN) on the rows where it disagreed. If NaN were treated
        as disagreement the two runs would produce the same m; masking means the
        second run estimates city's m only from the rows that actually compared
        it, so m_city must come out strictly higher.
        """
        as_disagreement = np.array(
            [[1.0, 1.0], [1.0, 0.0], [1.0, 0.0], [0.0, 0.0]]
        )
        as_unobserved = np.array(
            [[1.0, 1.0], [1.0, np.nan], [1.0, np.nan], [0.0, 0.0]]
        )

        res_dis = estimate_mu(as_disagreement, ["name", "city"])
        res_unobs = estimate_mu(as_unobserved, ["name", "city"])

        assert res_unobs.m["city"] > res_dis.m["city"], (
            "masking unobserved cells must stop them dragging m_city down"
        )
        # The 'name' column is untouched, so its estimate should be unaffected.
        assert res_unobs.m["name"] == pytest.approx(res_dis.m["name"], abs=1e-6)

    def test_estimate_mu_tolerates_a_wholly_unobserved_field(self):
        """A field never observed must not produce NaN or crash the run.

        Its m/u simply stay at the initialisation values — there is no evidence
        to move them — and every other field still estimates normally.
        """
        gamma = np.array(
            [[1.0, np.nan], [1.0, np.nan], [0.0, np.nan], [0.0, np.nan]]
        )
        res = estimate_mu(gamma, ["name", "never_seen"], init_m=0.9, init_u=0.1)

        assert np.isfinite(res.m["never_seen"])
        assert np.isfinite(res.u["never_seen"])
        assert np.isfinite(res.m["name"])
        assert np.isfinite(res.log_likelihood)

    def test_estimate_mu_all_nan_row_contributes_no_evidence(self):
        """A pair with nothing observed must not skew the parameters."""
        base = np.array([[1.0, 1.0], [1.0, 1.0], [0.0, 0.0], [0.0, 0.0]])
        with_blank = np.vstack([base, [[np.nan, np.nan]]])

        res_base = estimate_mu(base, ["a", "b"])
        res_blank = estimate_mu(with_blank, ["a", "b"])

        assert res_blank.m["a"] == pytest.approx(res_base.m["a"], abs=1e-4)
        assert res_blank.u["a"] == pytest.approx(res_base.u["a"], abs=1e-4)

    def test_per_field_thresholds(self):
        est = EMEstimator(
            field_names=["name", "zip"],
            agreement_thresholds={"name": 0.7, "zip": 0.99},
        )
        gamma = est.build_gamma([{"name": 0.75, "zip": 0.95}])
        assert gamma.tolist() == [[1.0, 0.0]]  # zip 0.95 < 0.99 -> disagree

    def test_estimate_end_to_end(self):
        rng = np.random.default_rng(3)
        # High-similarity matches vs low-similarity non-matches.
        comps = []
        for _ in range(8000):
            if rng.random() < 0.3:
                comps.append({"a": rng.uniform(0.85, 1.0), "b": rng.uniform(0.8, 1.0)})
            else:
                comps.append({"a": rng.uniform(0.0, 0.5), "b": rng.uniform(0.0, 0.6)})
        est = EMEstimator(field_names=["a", "b"], default_threshold=0.7)
        res = est.estimate(comps)
        assert res.m["a"] > res.u["a"]
        assert res.lambda_ == pytest.approx(0.3, abs=0.06)


class TestFixedU:
    """u supplied from an unbiased source is honoured, not re-estimated.

    u is defined as the agreement rate among NON-matches. EM run over blocked
    candidate pairs cannot see a representative non-match population (every pair
    already cleared a similarity gate), so u must be measurable externally and
    held fixed while EM estimates only m and lambda.
    """

    def test_fixed_u_is_returned_unchanged(self):
        gamma = np.array([[1.0, 1.0], [1.0, 0.0], [0.0, 0.0], [1.0, 1.0]])
        supplied = [0.02, 0.30]

        res = estimate_mu(gamma, ["a", "b"], fixed_u=supplied)

        assert res.u["a"] == pytest.approx(0.02)
        assert res.u["b"] == pytest.approx(0.30)

    def test_fixed_u_still_estimates_m_and_lambda(self):
        gamma = np.array([[1.0, 1.0], [1.0, 1.0], [0.0, 0.0], [0.0, 0.0]])

        res = estimate_mu(gamma, ["a", "b"], fixed_u=[0.05, 0.05])

        assert 0.0 <= res.lambda_ <= 1.0
        assert res.m["a"] > res.u["a"], "m must exceed the chance agreement rate"
        assert np.isfinite(res.log_likelihood)

    def test_fixed_u_lowers_u_versus_joint_em_on_biased_sample(self):
        """The whole point: a candidate-only sample inflates u.

        This gamma mimics blocked candidates — mostly agreeing, because they all
        passed a similarity gate. Joint EM has to explain the few disagreements
        as the non-match class and lands on a high u. Supplying u measured from
        random pairs keeps the match weight log(m/u) from being compressed.
        """
        biased = np.array(
            [[1.0, 1.0]] * 8 + [[1.0, 0.0]] * 2, dtype=np.float64
        )

        joint = estimate_mu(biased, ["a", "b"])
        anchored = estimate_mu(biased, ["a", "b"], fixed_u=[0.01, 0.01])

        assert anchored.u["a"] < joint.u["a"]
        joint_weight = np.log(joint.m["a"] / joint.u["a"])
        anchored_weight = np.log(anchored.m["a"] / anchored.u["a"])
        assert anchored_weight > joint_weight, (
            "anchoring u on an unbiased sample must restore discriminating power"
        )

    def test_fixed_u_rejects_wrong_length(self):
        with pytest.raises(ValueError, match="one value per field"):
            estimate_mu(np.ones((2, 2)), ["a", "b"], fixed_u=[0.1])

    def test_estimator_wrapper_maps_fixed_u_by_field_name(self):
        est = EMEstimator(field_names=["name", "city"], default_threshold=0.85)
        comparisons = [
            {"name": 0.95, "city": 0.95},
            {"name": 0.95, "city": 0.10},
            {"name": 0.10, "city": 0.10},
        ]

        res = est.estimate(comparisons, fixed_u={"name": 0.03, "city": 0.25})

        assert res.u["name"] == pytest.approx(0.03)
        assert res.u["city"] == pytest.approx(0.25)

    def test_estimator_wrapper_defaults_unlisted_fields(self):
        """A partially-measured model still runs; unmeasured fields use init_u."""
        est = EMEstimator(field_names=["name", "city"])
        res = est.estimate(
            [{"name": 0.95, "city": 0.95}, {"name": 0.1, "city": 0.1}],
            fixed_u={"name": 0.03},
            init_u=0.2,
        )
        assert res.u["name"] == pytest.approx(0.03)
        assert res.u["city"] == pytest.approx(0.2)
