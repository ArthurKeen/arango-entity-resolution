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
from typing import Any, Dict, List, Mapping, Optional, Sequence

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


@dataclass
class CategoricalEMResult:
    """Outcome of a multi-level (categorical) EM run.

    ``m``/``u`` map each field to a probability vector over its ordered levels,
    each summing to 1. The binary model is the two-level special case, where
    ``m[field][-1]`` is the familiar P(agree | match).
    """

    fields: List[str]
    level_names: Dict[str, List[str]]
    m: Dict[str, List[float]]
    u: Dict[str, List[float]]
    lambda_: float
    iterations: int
    converged: bool
    n_pairs: int
    log_likelihood: float
    #: Per field, how many pairs actually supplied a level (not NaN).
    observed_counts: Dict[str, int]

    def to_dict(self) -> Dict[str, object]:
        return {
            "fields": list(self.fields),
            "level_names": {f: list(v) for f, v in self.level_names.items()},
            "m": {f: list(v) for f, v in self.m.items()},
            "u": {f: list(v) for f, v in self.u.items()},
            "lambda": self.lambda_,
            "iterations": self.iterations,
            "converged": self.converged,
            "n_pairs": self.n_pairs,
            "log_likelihood": self.log_likelihood,
            "observed_counts": dict(self.observed_counts),
        }

    def to_comparison_levels(
        self, thresholds: Mapping[str, Sequence[Optional[float]]]
    ) -> Dict[str, List[Dict[str, object]]]:
        """Emit learned probabilities in the scorer's ``comparison_levels`` shape.

        This is the join between learning and scoring:
        :class:`~entity_resolution.learning.fellegi_sunter_scorer.FellegiSunterScorer`
        consumes ``{field: [{name, min_similarity, m, u}, ...]}``, and returning
        exactly that keeps the two from drifting apart. ``thresholds`` supplies
        the ``min_similarity`` per level in the same order the levels were
        defined, with ``None`` for the final fallback.
        """
        out: Dict[str, List[Dict[str, object]]] = {}
        for field in self.fields:
            names = self.level_names[field]
            field_thresholds = list(thresholds.get(field, []))
            if len(field_thresholds) != len(names):
                raise ValueError(
                    f"thresholds for {field!r} must have one entry per level "
                    f"({len(names)}), got {len(field_thresholds)}"
                )
            out[field] = [
                {
                    "name": names[i],
                    "min_similarity": field_thresholds[i],
                    "m": self.m[field][i],
                    "u": self.u[field][i],
                }
                for i in range(len(names))
            ]
        return out


def assign_level(similarity: Optional[float], thresholds: Sequence[Optional[float]]) -> Optional[int]:
    """Index of the first level whose ``min_similarity`` the score reaches.

    ``thresholds`` is ordered most-selective first with ``None`` last (the
    fallback), matching the scorer. Returns ``None`` for an unobserved value —
    the null level, which carries no evidence and must not be conflated with the
    lowest level. Sharing this function between training and scoring is what
    keeps the two binarisations identical.
    """
    if similarity is None:
        return None
    for index, threshold in enumerate(thresholds):
        if threshold is None or similarity >= threshold:
            return index
    return len(thresholds) - 1


def estimate_categorical_mu(
    gamma: np.ndarray,
    field_levels: Mapping[str, Sequence[str]],
    *,
    max_iterations: int = 50,
    tol: float = 1e-5,
    init_lambda: float = 0.1,
    weights: Optional[np.ndarray] = None,
    fixed_u: Optional[Mapping[str, Sequence[float]]] = None,
) -> CategoricalEMResult:
    """Estimate per-level m/u and lambda by EM over categorical comparisons.

    The binary model collapses every similarity to agree/disagree at one cutoff,
    which discards the gradation continuous comparators produce. Measured cost of
    that on the public benchmarks: Fellegi-Sunter scored F1 0.117 against
    weighted similarity's 0.541 on Abt-Buy, because word-based Jaccard over long
    text almost never clears a single agreement threshold, so ``m`` for the body
    field was learned as 0.0 and recall collapsed to 0.062. Multiple ordered
    levels keep that gradation.

    Args:
        gamma: ``(n_pairs, n_fields)`` array whose cells hold a LEVEL INDEX for
            the field, or ``NaN`` where the field was not observed on that pair.
            Column order follows ``field_levels`` iteration order.
        field_levels: ordered level names per field, most selective first. The
            number of levels may differ per field.
        max_iterations, tol: stop when the largest parameter change falls below
            ``tol``, or after ``max_iterations``.
        init_lambda: initial match prior.
        weights: optional ``(n_pairs,)`` weights, e.g. counts when identical
            comparison patterns are collapsed.
        fixed_u: optional per-field level probabilities for ``u``, held constant.
            Supply this when ``u`` has been measured on random record pairs,
            which is the only unbiased source for it — candidate pairs have all
            cleared a similarity gate and cannot furnish a representative
            non-match sample. Label switching is not resolved when ``u`` is
            given, since the measured values already anchor which class is which.

    Unobserved cells contribute nothing to either class likelihood, and each
    field's M-step denominator is its own observed weight rather than the global
    class weight — so a frequently-empty field is not mistaken for a
    frequently-disagreeing one.
    """
    gamma = np.asarray(gamma, dtype=np.float64)
    if gamma.ndim != 2:
        raise ValueError("gamma must be a 2D (n_pairs, n_fields) array")

    fields = list(field_levels)
    n_pairs, n_fields = gamma.shape
    if n_fields != len(fields):
        raise ValueError(
            f"field_levels has {len(fields)} entries but gamma has {n_fields} columns"
        )
    if n_pairs == 0:
        raise ValueError("need at least one comparison vector")
    for field in fields:
        if len(field_levels[field]) < 2:
            raise ValueError(
                f"field {field!r} needs at least two levels; a single level "
                "carries no discriminating information"
            )

    if weights is None:
        weights = np.ones(n_pairs, dtype=np.float64)
    else:
        weights = np.asarray(weights, dtype=np.float64)
        if weights.shape != (n_pairs,):
            raise ValueError("weights must have shape (n_pairs,)")
    total_w = weights.sum()

    # One-hot encode each field's observed level. An unobserved cell yields an
    # all-zero row, so it drops out of every dot product below — the categorical
    # equivalent of the binary path's present-mask.
    onehots: List[np.ndarray] = []
    present: List[np.ndarray] = []
    for column, field in enumerate(fields):
        n_levels = len(field_levels[field])
        col = gamma[:, column]
        observed = np.isfinite(col)
        indices = np.where(observed, np.nan_to_num(col, nan=0.0), 0).astype(np.int64)
        if observed.any() and (
            indices[observed].min() < 0 or indices[observed].max() >= n_levels
        ):
            raise ValueError(
                f"gamma contains a level index outside 0..{n_levels - 1} for "
                f"field {field!r}"
            )
        encoded = np.zeros((n_pairs, n_levels), dtype=np.float64)
        encoded[np.arange(n_pairs), indices] = 1.0
        encoded[~observed] = 0.0
        onehots.append(encoded)
        present.append(observed.astype(np.float64))

    # Initialise m biased toward the most selective level and u toward the
    # least, so the match class starts as the high-agreement one.
    m_probs: List[np.ndarray] = []
    u_probs: List[np.ndarray] = []
    for field in fields:
        n_levels = len(field_levels[field])
        m_init = np.full(n_levels, (1.0 - 0.8) / max(n_levels - 1, 1))
        m_init[0] = 0.8
        u_init = np.full(n_levels, (1.0 - 0.8) / max(n_levels - 1, 1))
        u_init[-1] = 0.8
        m_probs.append(_normalise(m_init))
        u_probs.append(_normalise(u_init))

    if fixed_u is not None:
        for column, field in enumerate(fields):
            if field not in fixed_u:
                continue
            supplied = np.asarray(fixed_u[field], dtype=np.float64)
            if supplied.shape != (len(field_levels[field]),):
                raise ValueError(
                    f"fixed_u[{field!r}] must have one probability per level "
                    f"({len(field_levels[field])}), got {supplied.shape}"
                )
            u_probs[column] = _normalise(supplied)

    lam = float(init_lambda)
    converged = False
    iterations = 0

    for iterations in range(1, max_iterations + 1):
        log_m = np.zeros(n_pairs, dtype=np.float64)
        log_u = np.zeros(n_pairs, dtype=np.float64)
        for column in range(n_fields):
            log_m += onehots[column] @ np.log(m_probs[column])
            log_u += onehots[column] @ np.log(u_probs[column])

        log_pm = np.log(max(lam, _EPS)) + log_m
        log_pu = np.log(max(1 - lam, _EPS)) + log_u
        max_log = np.maximum(log_pm, log_pu)
        denom = max_log + np.log(np.exp(log_pm - max_log) + np.exp(log_pu - max_log))
        resp = np.exp(log_pm - denom)

        wr = weights * resp
        w_non = weights * (1 - resp)
        sum_match = wr.sum()
        new_lambda = sum_match / total_w

        delta = abs(new_lambda - lam)
        for column in range(n_fields):
            observed_match = wr @ present[column]
            if observed_match > _EPS:
                candidate = _normalise((wr @ onehots[column]) / observed_match)
                delta = max(delta, float(np.max(np.abs(candidate - m_probs[column]))))
                m_probs[column] = candidate
            if fixed_u is None or fields[column] not in fixed_u:
                observed_non = w_non @ present[column]
                if observed_non > _EPS:
                    candidate = _normalise((w_non @ onehots[column]) / observed_non)
                    delta = max(delta, float(np.max(np.abs(candidate - u_probs[column]))))
                    u_probs[column] = candidate

        lam = new_lambda
        if delta < tol:
            converged = True
            break

    log_m = np.zeros(n_pairs, dtype=np.float64)
    log_u = np.zeros(n_pairs, dtype=np.float64)
    for column in range(n_fields):
        log_m += onehots[column] @ np.log(m_probs[column])
        log_u += onehots[column] @ np.log(u_probs[column])
    log_pm = np.log(max(lam, _EPS)) + log_m
    log_pu = np.log(max(1 - lam, _EPS)) + log_u
    max_log = np.maximum(log_pm, log_pu)
    ll = float(
        (weights * (max_log + np.log(np.exp(log_pm - max_log) + np.exp(log_pu - max_log)))).sum()
    )

    # Resolve label switching by which class concentrates on the most selective
    # level. Skipped when u was measured externally — swapping would discard
    # those values and return an m that was never estimated as one.
    if fixed_u is None:
        m_top = float(np.mean([p[0] for p in m_probs]))
        u_top = float(np.mean([p[0] for p in u_probs]))
        if m_top < u_top:
            m_probs, u_probs = u_probs, m_probs
            lam = 1 - lam

    return CategoricalEMResult(
        fields=fields,
        level_names={f: list(field_levels[f]) for f in fields},
        m={f: [float(x) for x in m_probs[i]] for i, f in enumerate(fields)},
        u={f: [float(x) for x in u_probs[i]] for i, f in enumerate(fields)},
        lambda_=float(lam),
        iterations=iterations,
        converged=converged,
        n_pairs=int(n_pairs),
        log_likelihood=ll,
        observed_counts={f: int(present[i].sum()) for i, f in enumerate(fields)},
    )


def _normalise(probs: np.ndarray) -> np.ndarray:
    """Clip away from 0/1 and renormalise so the vector sums to exactly 1.

    Clipping alone leaves the sum slightly off, and the scorer validates that
    level probabilities sum to 1; a level never seen in training would otherwise
    be 0 and make log(m/u) infinite.
    """
    clipped = np.clip(np.asarray(probs, dtype=np.float64), _EPS, 1.0)
    return clipped / clipped.sum()


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

    def build_categorical_gamma(
        self,
        comparisons: Sequence[Dict[str, float]],
        level_thresholds: Mapping[str, Sequence[Optional[float]]],
    ) -> np.ndarray:
        """Assign each comparison to a level index per field.

        Cells hold the index of the matched level, or ``NaN`` where the field was
        not observed — the null level, which carries no evidence and must stay
        distinct from the lowest level. Level assignment goes through
        :func:`assign_level`, the same function the scorer uses, so training and
        scoring cannot bin a similarity differently.

        Fields absent from ``level_thresholds`` are skipped entirely rather than
        silently binarised, so a partially-configured model fails visibly at
        :func:`estimate_categorical_mu` instead of mixing two comparison models.
        """
        fields = [f for f in self.field_names if f in level_thresholds]
        if not fields:
            raise ValueError(
                "level_thresholds covers none of the estimator's fields; "
                f"expected some of {self.field_names}"
            )
        rows = []
        for comp in comparisons:
            row = []
            for f in fields:
                index = assign_level(comp.get(f), list(level_thresholds[f]))
                row.append(np.nan if index is None else float(index))
            rows.append(row)
        if not rows:
            return np.empty((0, len(fields)), dtype=np.float64)
        return np.asarray(rows, dtype=np.float64)

    def estimate_categorical(
        self,
        comparisons: Sequence[Dict[str, float]],
        level_specs: Mapping[str, Sequence[Mapping[str, Any]]],
        *,
        fixed_u: Optional[Mapping[str, Sequence[float]]] = None,
        init_lambda: float = 0.1,
        weights: Optional[np.ndarray] = None,
    ) -> "CategoricalEMResult":
        """Learn per-level m/u from comparisons and level definitions.

        ``level_specs`` maps each field to its ordered levels, most selective
        first, each ``{"name": str, "min_similarity": float | None}`` with the
        final level's threshold ``None`` (the fallback). That is the same shape
        :class:`~entity_resolution.learning.fellegi_sunter_scorer.FellegiSunterScorer`
        accepts, minus the ``m``/``u`` this fills in — so
        :meth:`CategoricalEMResult.to_comparison_levels` round-trips straight
        into the scorer.
        """
        ordered = [f for f in self.field_names if f in level_specs]
        thresholds = {
            f: [lvl.get("min_similarity") for lvl in level_specs[f]] for f in ordered
        }
        names = {f: [str(lvl["name"]) for lvl in level_specs[f]] for f in ordered}

        for f in ordered:
            spec_thresholds = thresholds[f]
            if spec_thresholds and spec_thresholds[-1] is not None:
                raise ValueError(
                    f"level_specs[{f!r}] must end with a fallback level whose "
                    "min_similarity is None"
                )

        gamma = self.build_categorical_gamma(comparisons, thresholds)
        return estimate_categorical_mu(
            gamma,
            names,
            max_iterations=self.max_iterations,
            tol=self.tol,
            init_lambda=init_lambda,
            weights=weights,
            fixed_u=fixed_u,
        )

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
