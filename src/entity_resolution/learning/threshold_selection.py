"""Choose a decision threshold from data instead of hard-coding one.

Benchmarking established that a fixed default is unsafe. Running the shipped
``0.8`` against the public Leipzig benchmarks:

============== ================ ================== =========
dataset        F1 at 0.8        F1 at best         best thr
============== ================ ================== =========
DBLP-ACM       0.935            0.937              0.77
DBLP-Scholar   0.661            0.840              0.50
Abt-Buy        0.067            0.541              0.35
Amazon-Google  0.037            0.488              0.34
============== ================ ================== =========

On the two noisy product datasets a user following the documented default got
roughly a **tenth** of the achievable F1, and the best threshold ranges from 0.34
to 0.77 — a spread no single constant can cover. Threshold choice dominates
matcher sophistication: no scoring improvement rescues a run operating at the
wrong cutoff.

Two regimes are supported, because the information available differs:

:func:`select_threshold_supervised`
    Labelled pairs exist (a truth file, or analyst verdicts accumulated in the
    review queue). Sweep and take the operating point that maximises the chosen
    objective. This is the accurate path — use it whenever labels exist, even a
    few hundred.

:func:`select_threshold_unsupervised`
    No labels, which is the normal state on a new dataset. Match scores are
    characteristically **bimodal** — a large mass of low-scoring non-matches and
    a smaller high-scoring mass of matches — so the task is finding the valley
    between the two modes. Otsu's method does exactly that by maximising
    between-class variance, and it needs no labels, no distribution assumption
    beyond bimodality, and no extra dependencies.

Both return a :class:`ThresholdSelection` recording the value, the method, and
enough diagnostics to audit the choice. The threshold is never silently applied:
callers log or persist the selection so the operating point travels with the
scores it produced.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

#: Fallback when a distribution is too degenerate to infer anything from.
_FALLBACK_THRESHOLD = 0.5

__all__ = [
    "ThresholdSelection",
    "select_threshold_supervised",
    "select_threshold_unsupervised",
    "otsu_threshold",
    "score_distribution_diagnostics",
]


@dataclass
class ThresholdSelection:
    """A chosen threshold plus the evidence for choosing it."""

    threshold: float
    method: str
    #: "supervised" when labels drove the choice, else "unsupervised".
    regime: str
    #: Objective maximised, for supervised selection.
    objective: Optional[str] = None
    #: Metrics at the chosen point (supervised only).
    metrics: Dict[str, float] = field(default_factory=dict)
    #: Method-specific diagnostics — separability, mode positions, sample size.
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    #: Set when the input was too degenerate and a fallback was used.
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "threshold": self.threshold,
            "method": self.method,
            "regime": self.regime,
            "objective": self.objective,
            "metrics": self.metrics,
            "diagnostics": self.diagnostics,
            "warning": self.warning,
        }


# ---------------------------------------------------------------------------
# Supervised
# ---------------------------------------------------------------------------


def select_threshold_supervised(
    scored_pairs: Iterable[Tuple[str, str, float]],
    truth_pairs: Set[Tuple[str, str]],
    *,
    objective: str = "f1",
    min_precision: Optional[float] = None,
    min_recall: Optional[float] = None,
    steps: int = 99,
) -> ThresholdSelection:
    """Pick the threshold maximising ``objective`` over labelled pairs.

    Args:
        scored_pairs: ``(key_a, key_b, score)`` triples. Order within a pair does
            not matter; pairs are canonicalised before comparison.
        truth_pairs: known-matching pairs, canonically ordered.
        objective: ``"f1"`` (default), ``"precision"``, or ``"recall"``.
            Precision and recall are only meaningful with the corresponding
            ``min_recall`` / ``min_precision`` constraint, since each is
            trivially maximised at an extreme threshold.
        min_precision: reject operating points below this precision.
        min_recall: reject operating points below this recall.
        steps: number of thresholds evaluated across (0, 1).

    A constraint that excludes every point is reported in ``warning`` and the
    best unconstrained point is returned, rather than failing — a threshold is
    always needed, but the caller must be able to see the constraint was unmet.
    """
    if objective not in ("f1", "precision", "recall"):
        raise ValueError(
            f"objective must be 'f1', 'precision' or 'recall', got {objective!r}"
        )

    pairs = [(_canon(a, b), float(s)) for a, b, s in scored_pairs]
    if not pairs:
        return ThresholdSelection(
            threshold=_FALLBACK_THRESHOLD,
            method="fallback",
            regime="supervised",
            objective=objective,
            warning="no scored pairs supplied; using fallback threshold",
        )
    if not truth_pairs:
        return ThresholdSelection(
            threshold=_FALLBACK_THRESHOLD,
            method="fallback",
            regime="supervised",
            objective=objective,
            warning="no truth pairs supplied; cannot evaluate — using fallback",
        )

    curve: List[Dict[str, float]] = []
    for i in range(1, steps + 1):
        threshold = i / (steps + 1)
        predicted = {p for p, s in pairs if s >= threshold}
        point = _prf(predicted, truth_pairs)
        point["threshold"] = threshold
        curve.append(point)

    feasible = [
        p for p in curve
        if (min_precision is None or p["precision"] >= min_precision)
        and (min_recall is None or p["recall"] >= min_recall)
    ]
    warning = None
    if not feasible:
        feasible = curve
        warning = (
            "no threshold satisfied the precision/recall constraints; "
            "returning the best unconstrained operating point"
        )

    best = max(feasible, key=lambda p: (p[objective], p["f1"]))
    return ThresholdSelection(
        threshold=round(best["threshold"], 4),
        method="supervised_sweep",
        regime="supervised",
        objective=objective,
        metrics={
            "precision": round(best["precision"], 4),
            "recall": round(best["recall"], 4),
            "f1": round(best["f1"], 4),
        },
        diagnostics={
            "labelled_pairs": len(truth_pairs),
            "scored_pairs": len(pairs),
            "steps": steps,
            "constraints": {
                "min_precision": min_precision,
                "min_recall": min_recall,
            },
        },
        warning=warning,
    )


def _canon(a: str, b: str) -> Tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _prf(predicted: Set[Tuple[str, str]], truth: Set[Tuple[str, str]]) -> Dict[str, float]:
    tp = len(predicted & truth)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(truth) if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


# ---------------------------------------------------------------------------
# Unsupervised
# ---------------------------------------------------------------------------


def otsu_threshold(
    scores: Sequence[float], *, bins: int = 256
) -> Tuple[float, Dict[str, Any]]:
    """Otsu's method: the cut maximising between-class variance.

    Treats the score histogram as a two-class problem and returns the cut that
    best separates them. Where match scores are bimodal — a broad low-scoring
    non-match mass and a tighter high-scoring match mass — this lands in the
    valley between the modes without needing any labels.

    Returns ``(threshold, diagnostics)`` containing two quality measures. Only
    one of them is a usable guard:

    ``valley_depth``
        How deep the trough at the cut is relative to the smaller of the two
        surrounding peaks, in [0, 1]. **This is the bimodality evidence.**
        Measured: ~0.71 for a clearly bimodal distribution, ~0.47 for a
        separated-but-unbalanced one (the usual ER shape), 0.10 for a tight
        unimodal blob, 0.00 for a plain Gaussian.

    ``separability``
        Between-class variance over total variance. Informational only — it does
        **not** indicate bimodality, which is easy to get wrong. Splitting any
        single Gaussian at its mean yields 2/pi ~= 0.637, so a unimodal
        distribution scores ~0.64 here and real bimodal benchmark data scored
        0.63-0.86. Gating on it would reject good cuts and accept meaningless
        ones; ``valley_depth`` is the discriminating statistic.
    """
    values = [float(s) for s in scores if s is not None and math.isfinite(s)]
    if not values:
        return _FALLBACK_THRESHOLD, {"reason": "no finite scores"}

    low, high = min(values), max(values)
    if high - low < 1e-9:
        return _FALLBACK_THRESHOLD, {
            "reason": "all scores identical",
            "score_min": low,
            "score_max": high,
        }

    # Adapt resolution to sample size. A fixed large bin count over a narrow
    # score range leaves ~2 samples per bin, and that sparsity reads as deep
    # troughs between noise spikes — enough to make a tight unimodal blob look
    # bimodal. ~sqrt(n) buckets (the usual histogram heuristic) keeps bins
    # populated enough for valley depth to mean something.
    bins = max(16, min(bins, int(math.sqrt(len(values))) * 2))

    counts = [0] * bins
    width = (high - low) / bins
    for value in values:
        index = int((value - low) / width)
        counts[min(index, bins - 1)] += 1

    total = len(values)
    # Bin midpoints as the representative score for each bucket.
    centres = [low + (i + 0.5) * width for i in range(bins)]
    global_mean = sum(c * n for c, n in zip(centres, counts)) / total

    best_variance = -1.0
    best_index = bins // 2
    weight_below = 0
    sum_below = 0.0
    for i in range(bins - 1):
        weight_below += counts[i]
        sum_below += centres[i] * counts[i]
        if weight_below == 0:
            continue
        weight_above = total - weight_below
        if weight_above == 0:
            break
        mean_below = sum_below / weight_below
        mean_above = (global_mean * total - sum_below) / weight_above
        # Between-class variance for this cut.
        variance = (
            (weight_below / total) * (weight_above / total)
            * (mean_below - mean_above) ** 2
        )
        if variance > best_variance:
            best_variance = variance
            best_index = i

    threshold = low + (best_index + 1) * width
    total_variance = (
        sum(counts[i] * (centres[i] - global_mean) ** 2 for i in range(bins)) / total
    )
    separability = (best_variance / total_variance) if total_variance > 0 else 0.0

    return round(threshold, 4), {
        "valley_depth": _valley_depth(counts, best_index),
        "separability": round(separability, 4),
        "between_class_variance": round(best_variance, 6),
        "total_variance": round(total_variance, 6),
        "score_min": round(low, 4),
        "score_max": round(high, 4),
        "sample_size": total,
        "bins": bins,
    }


def _valley_depth(counts: Sequence[int], cut_index: int, window: int = 3) -> float:
    """How pronounced the trough at ``cut_index`` is, in [0, 1].

    ``1 - density(cut) / min(peak_below, peak_above)`` over a lightly smoothed
    histogram. A real valley between two modes scores high; a cut through the
    middle of one mode scores ~0 because the "valley" is as tall as the peaks.

    Smoothing matters: on a raw histogram a single empty bin next to a mode looks
    like a deep valley, which would wave through exactly the unimodal cases this
    is meant to reject.
    """
    if not counts or cut_index <= 0 or cut_index >= len(counts) - 1:
        return 0.0

    smoothed = [
        sum(counts[max(0, i - window): i + window + 1])
        / len(counts[max(0, i - window): i + window + 1])
        for i in range(len(counts))
    ]
    peak_below = max(smoothed[:cut_index], default=0.0)
    peak_above = max(smoothed[cut_index + 1:], default=0.0)
    smaller_peak = min(peak_below, peak_above)
    if smaller_peak <= 0:
        return 0.0
    return round(max(0.0, 1.0 - smoothed[cut_index] / smaller_peak), 4)


def score_distribution_diagnostics(scores: Sequence[float]) -> Dict[str, Any]:
    """Summary statistics used to judge whether a threshold is well determined."""
    values = sorted(float(s) for s in scores if s is not None and math.isfinite(s))
    if not values:
        return {"sample_size": 0}

    def quantile(q: float) -> float:
        if len(values) == 1:
            return values[0]
        position = q * (len(values) - 1)
        lower = int(math.floor(position))
        upper = min(lower + 1, len(values) - 1)
        frac = position - lower
        return values[lower] * (1 - frac) + values[upper] * frac

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return {
        "sample_size": len(values),
        "min": round(values[0], 4),
        "p25": round(quantile(0.25), 4),
        "median": round(quantile(0.5), 4),
        "p75": round(quantile(0.75), 4),
        "max": round(values[-1], 4),
        "mean": round(mean, 4),
        "stdev": round(math.sqrt(variance), 4),
    }


def select_threshold_unsupervised(
    scores: Sequence[float],
    *,
    method: str = "otsu",
    min_valley_depth: float = 0.15,
    fallback: float = _FALLBACK_THRESHOLD,
    bins: int = 256,
) -> ThresholdSelection:
    """Infer a threshold from the score distribution alone.

    Args:
        scores: candidate-pair scores from a full scoring run.
        method: currently ``"otsu"``.
        min_valley_depth: below this the distribution is treated as too close to
            unimodal for a cut to mean anything, and ``fallback`` is returned
            with a warning. Guards the case where blocking produced only
            near-duplicates so every pair scores similarly — Otsu would still
            return a precise-looking number with no support behind it. Measured
            reference points are in :func:`otsu_threshold`; 0.15 sits above the
            0.00-0.10 unimodal range and below the ~0.47 seen on real
            separated-but-unbalanced benchmark data.
        fallback: threshold used when selection is not trustworthy.
        bins: histogram resolution.
    """
    if method != "otsu":
        raise ValueError(f"unknown method {method!r}; supported: 'otsu'")

    threshold, diagnostics = otsu_threshold(scores, bins=bins)
    diagnostics.update(score_distribution_diagnostics(scores))

    valley_depth = diagnostics.get("valley_depth")
    warning = None
    if valley_depth is None:
        warning = diagnostics.get("reason", "threshold could not be inferred")
        threshold = fallback
    elif valley_depth < min_valley_depth:
        warning = (
            f"score distribution is not meaningfully bimodal (valley depth "
            f"{valley_depth:.3f} < {min_valley_depth}); the inferred threshold is "
            f"unreliable, so the fallback {fallback} was used. Supply labelled "
            f"pairs and use select_threshold_supervised for an accurate cutoff."
        )
        threshold = fallback

    if warning:
        logger.warning("Unsupervised threshold selection: %s", warning)
    else:
        logger.info(
            "Selected threshold %.4f by Otsu (valley depth %.3f over %d pairs)",
            threshold, valley_depth, diagnostics.get("sample_size", 0),
        )

    return ThresholdSelection(
        threshold=threshold,
        method="otsu" if not warning else "fallback",
        regime="unsupervised",
        diagnostics=diagnostics,
        warning=warning,
    )
