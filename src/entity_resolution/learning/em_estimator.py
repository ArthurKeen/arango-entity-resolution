"""Fellegi-Sunter EM estimation of per-field m/u probabilities.

Classic two-class Fellegi-Sunter expectation-maximization over binary
field-agreement vectors. Given comparison vectors from sampled candidate pairs
(no labels), it estimates, per field:

- ``m`` = P(field agrees | the pair is a true match)
- ``u`` = P(field agrees | the pair is a non-match)

and the match prior ``lambda`` = P(match) over the candidate set. These feed the
honest Fellegi-Sunter scorer (plan 0.2) so weights are learned from data rather
than hand-set, the defining unsupervised capability of Splink/Zingg.

The core (:func:`estimate_mu`) is pure numpy and dependency-free so it is unit
testable on synthetic data with known parameters. Higher layers build the
comparison vectors from real records and persist results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

_EPS = 1e-6


@dataclass
class EMResult:
    """Outcome of an EM run.

    ``m``/``u`` are per-field dicts keyed by field name; ``lambda_`` is the
    estimated match prior; ``converged``/``iterations`` describe the run.
    """

    fields: List[str]
    m: Dict[str, float]
    u: Dict[str, float]
    lambda_: float
    iterations: int
    converged: bool
    n_pairs: int
    log_likelihood: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "fields": list(self.fields),
            "m": dict(self.m),
            "u": dict(self.u),
            "lambda": self.lambda_,
            "iterations": self.iterations,
            "converged": self.converged,
            "n_pairs": self.n_pairs,
            "log_likelihood": self.log_likelihood,
        }


def estimate_mu(
    gamma: np.ndarray,
    field_names: Sequence[str],
    *,
    max_iterations: int = 50,
    tol: float = 1e-5,
    init_m: float = 0.9,
    init_u: float = 0.1,
    init_lambda: float = 0.1,
    weights: Optional[np.ndarray] = None,
    fixed_u: Optional[Sequence[float]] = None,
) -> EMResult:
    """Estimate m/u/lambda from a binary agreement matrix via Fellegi-Sunter EM.

    Parameters
    ----------
    gamma:
        ``(n_pairs, n_fields)`` array of agreement indicators: ``1`` agrees,
        ``0`` observed-and-disagrees, ``NaN`` **not observed** on that pair.
        NaN cells are masked out, so each field's m/u is estimated only over the
        pairs where that field was actually compared, and an unobserved field
        contributes nothing to the pair's likelihood. This matches the scorer's
        null comparison level; without the mask, a frequently-empty field would
        look like a frequently-disagreeing one and its ``m`` would be biased
        downward.
    field_names:
        Names for the ``n_fields`` columns, in order.
    max_iterations, tol:
        Stop when the max parameter change between iterations is below ``tol``
        or after ``max_iterations``.
    init_m, init_u, init_lambda:
        Initial guesses. ``init_m > init_u`` biases the "match" class to be the
        high-agreement one, resolving the label-switching ambiguity.
    weights:
        Optional ``(n_pairs,)`` non-negative weights (e.g. counts when identical
        rows are collapsed). Defaults to all ones.
    fixed_u:
        Optional per-field ``u`` values held CONSTANT throughout (only ``m`` and
        ``lambda`` are then estimated). Supply this when ``u`` has been measured
        directly from random record pairs, which is the statistically sound way
        to obtain it: ``u`` is defined as the agreement rate among *non-matches*,
        and running EM over blocked candidate pairs cannot see a representative
        non-match population — every pair already passed a similarity gate, so
        the "non-match" class is drawn from near-matches and ``u`` comes out
        inflated, compressing every ``log(m/u)`` weight. See
        :meth:`~entity_resolution.learning.model_parameter_estimator.ModelParameterEstimator.estimate_u_from_random_pairs`.
        When ``fixed_u`` is given, label switching is not resolved by comparing
        mean(m) to mean(u) — the fixed ``u`` already anchors which class is which.

    Returns
    -------
    EMResult
    """
    gamma = np.asarray(gamma, dtype=np.float64)
    if gamma.ndim != 2:
        raise ValueError("gamma must be a 2D (n_pairs, n_fields) array")
    n_pairs, n_fields = gamma.shape
    if n_fields != len(field_names):
        raise ValueError(
            f"field_names has {len(field_names)} entries but gamma has {n_fields} columns"
        )
    if n_pairs == 0:
        raise ValueError("need at least one comparison vector")

    if weights is None:
        weights = np.ones(n_pairs, dtype=np.float64)
    else:
        weights = np.asarray(weights, dtype=np.float64)
        if weights.shape != (n_pairs,):
            raise ValueError("weights must have shape (n_pairs,)")
    total_w = weights.sum()

    # Split gamma into an observation mask and a NaN-free agreement matrix.
    # ``present`` zeroes every unobserved cell's contribution in the dot
    # products below, which is what makes NaN mean "no evidence" rather than
    # "disagrees". ``g`` must be NaN-free or the matrix products poison every
    # row total with NaN.
    present = np.isfinite(gamma).astype(np.float64)
    g = np.nan_to_num(gamma, nan=0.0)
    g_agree = g * present            # 1 where observed & agrees
    g_disagree = (1.0 - g) * present  # 1 where observed & disagrees

    m = np.full(n_fields, float(init_m))
    if fixed_u is None:
        u = np.full(n_fields, float(init_u))
    else:
        u = np.asarray(fixed_u, dtype=np.float64)
        if u.shape != (n_fields,):
            raise ValueError(
                f"fixed_u must have one value per field ({n_fields}), got {u.shape}"
            )
        u = np.clip(u, _EPS, 1 - _EPS)
    lam = float(init_lambda)

    converged = False
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        m_c = np.clip(m, _EPS, 1 - _EPS)
        u_c = np.clip(u, _EPS, 1 - _EPS)

        # E-step in log space (avoids underflow with many fields). Only observed
        # cells contribute: sum_f present*[ g*log m + (1-g)*log(1-m) ].
        log_m = g_agree @ np.log(m_c) + g_disagree @ np.log(1 - m_c)
        log_u = g_agree @ np.log(u_c) + g_disagree @ np.log(1 - u_c)
        log_pm = np.log(max(lam, _EPS)) + log_m
        log_pu = np.log(max(1 - lam, _EPS)) + log_u
        # Responsibility g_i = P(M | gamma_i) via stable log-sum-exp.
        max_log = np.maximum(log_pm, log_pu)
        denom = max_log + np.log(np.exp(log_pm - max_log) + np.exp(log_pu - max_log))
        resp = np.exp(log_pm - denom)  # (n_pairs,)

        # M-step (weighted). Denominators are PER FIELD — the observed weight for
        # that field — not the global class weight, so a field missing on half
        # the pairs is estimated from the half where it was compared instead of
        # being diluted toward 0.
        wr = weights * resp
        sum_match = wr.sum()
        new_lambda = sum_match / total_w
        obs_match = wr @ present          # (n_fields,)
        new_m = np.divide(
            wr @ g_agree, obs_match,
            out=m.copy(), where=obs_match > _EPS,
        )
        if fixed_u is None:
            w_non = weights * (1 - resp)
            obs_non = w_non @ present
            new_u = np.divide(
                w_non @ g_agree, obs_non,
                out=u.copy(), where=obs_non > _EPS,
            )
        else:
            new_u = u  # measured externally from random pairs; never re-estimated

        delta = max(
            float(np.max(np.abs(new_m - m))),
            float(np.max(np.abs(new_u - u))),
            abs(new_lambda - lam),
        )
        m, u, lam = new_m, new_u, new_lambda
        if delta < tol:
            converged = True
            break

    # Final log-likelihood (weighted) for diagnostics.
    m_c = np.clip(m, _EPS, 1 - _EPS)
    u_c = np.clip(u, _EPS, 1 - _EPS)
    log_m = g_agree @ np.log(m_c) + g_disagree @ np.log(1 - m_c)
    log_u = g_agree @ np.log(u_c) + g_disagree @ np.log(1 - u_c)
    log_pm = np.log(max(lam, _EPS)) + log_m
    log_pu = np.log(max(1 - lam, _EPS)) + log_u
    max_log = np.maximum(log_pm, log_pu)
    ll = float((weights * (max_log + np.log(np.exp(log_pm - max_log) + np.exp(log_pu - max_log)))).sum())

    # Resolve label switching: the match class must be the higher-agreement one.
    # Skipped when u was supplied — swapping would discard the measured values
    # and hand back an m that was never estimated as one.
    if fixed_u is None and float(np.mean(m)) < float(np.mean(u)):
        m, u = u, m
        lam = 1 - lam

    return EMResult(
        fields=list(field_names),
        m={f: float(v) for f, v in zip(field_names, m)},
        u={f: float(v) for f, v in zip(field_names, u)},
        lambda_=float(lam),
        iterations=iterations,
        converged=converged,
        n_pairs=int(n_pairs),
        log_likelihood=ll,
    )


@dataclass
class EMEstimator:
    """Builds agreement vectors from comparison records and runs :func:`estimate_mu`.

    A comparison record is a mapping of field name -> per-field similarity in
    [0, 1] (as produced by the similarity comparators). Agreement is binarized
    per field at ``agreement_thresholds[field]`` (default ``default_threshold``).
    """

    field_names: List[str]
    agreement_thresholds: Dict[str, float] = field(default_factory=dict)
    default_threshold: float = 0.85
    max_iterations: int = 50
    tol: float = 1e-5

    def build_gamma(self, comparisons: Sequence[Dict[str, float]]) -> np.ndarray:
        """Binarize similarity comparisons into an agreement matrix.

        Cell values are ``1.0`` (agrees), ``0.0`` (observed and disagrees), or
        ``NaN`` (**not observed** on this pair — the field was absent or
        ``None``).

        NaN is not the same as 0.0. Treating unobserved fields as disagreement
        biases each field's ``m`` downward in proportion to how often that field
        is empty, and it contradicts the scorer, which gives unobserved fields
        zero weight (see
        :class:`~entity_resolution.learning.fellegi_sunter_scorer.FellegiSunterScorer`).
        :func:`estimate_mu` masks these cells so each field's m/u is estimated
        only over the pairs where it was actually compared.
        """
        rows = []
        for comp in comparisons:
            row = []
            for f in self.field_names:
                val = comp.get(f)
                if val is None:
                    row.append(np.nan)  # null level — carries no evidence
                    continue
                thr = self.agreement_thresholds.get(f, self.default_threshold)
                row.append(1.0 if val >= thr else 0.0)
            rows.append(row)
        if not rows:
            return np.empty((0, len(self.field_names)), dtype=np.float64)
        return np.asarray(rows, dtype=np.float64)

    def estimate(
        self,
        comparisons: Sequence[Dict[str, float]],
        *,
        fixed_u: Optional[Dict[str, float]] = None,
        **kwargs,
    ) -> EMResult:
        """Run EM over comparison records.

        ``fixed_u`` maps field name -> u probability measured independently (see
        :func:`estimate_mu`). Fields absent from the mapping fall back to
        ``init_u``, so a partially-measured model still runs.
        """
        gamma = self.build_gamma(comparisons)
        if fixed_u is not None:
            default_u = kwargs.get("init_u", 0.1)
            kwargs["fixed_u"] = [
                float(fixed_u.get(f, default_u)) for f in self.field_names
            ]
        return estimate_mu(
            gamma,
            self.field_names,
            max_iterations=self.max_iterations,
            tol=self.tol,
            **kwargs,
        )
