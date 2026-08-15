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

#: Minimum gap between two comparison-band cuts, as a fraction of the histogram.
#: Cuts closer than this describe the same thinning rather than two separations.
_MIN_BAND_SEPARATION_FRACTION = 0.2

#: A cut must leave at least this share of the scores on each side. Troughs in
#: the sparse TAILS of a unimodal distribution score maximum depth — a single
#: empty bin between two one-count bins looks like a perfect valley — so depth
#: alone accepts noise. A band boundary should divide the data, not shave a tail.
_MIN_BAND_MASS_FRACTION = 0.05

__all__ = [
    "BandSelection",
    "ThresholdSelection",
    "select_comparison_bands",
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


@dataclass
class BandSelection:
    """Comparison-level band thresholds inferred from a score distribution."""

    #: Descending thresholds, most selective first. Empty when selection failed.
    thresholds: List[float]
    method: str
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    warning: Optional[str] = None

    def to_comparison_levels(
        self, names: Optional[Sequence[str]] = None
    ) -> List[Dict[str, Any]]:
        """Shape the thresholds as the level structure a config/scorer accepts.

        Appends the fallback level whose ``min_similarity`` is ``None``.
        """
        default_names = ("exact", "close", "near", "weak")
        chosen = list(names) if names else list(default_names[: len(self.thresholds)])
        if len(chosen) != len(self.thresholds):
            raise ValueError(
                f"need one name per threshold ({len(self.thresholds)}), got {len(chosen)}"
            )
        levels = [
            {"name": chosen[i], "min_similarity": t}
            for i, t in enumerate(self.thresholds)
        ]
        levels.append({"name": "else", "min_similarity": None})
        return levels

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thresholds": list(self.thresholds),
            "method": self.method,
            "diagnostics": self.diagnostics,
            "warning": self.warning,
        }


def select_comparison_bands(
    scores: Sequence[float],
    *,
    n_thresholds: int = 2,
    min_valley_depth: float = 0.15,
    bins: int = 128,
) -> BandSelection:
    """Place comparison-level bands where the score distribution separates.

    Benchmarking showed band PLACEMENT dominates band count: the same model
    scored F1 0.388 with bands copied from another dataset versus 0.505 with
    bands matched to its own distribution, because word-based Jaccard over long
    text rarely exceeds ~0.6 so a 0.9 band sits empty. Hand-placing bands means
    either inspecting the distribution or — as the published benchmark figures
    did for two datasets — tuning against labels a deployment does not have.
    This removes that dependency.

    Places cuts at the deepest TROUGHS in the score histogram, not at the cuts
    that maximise between-class variance. Multi-level Otsu is the obvious
    generalisation and it is the wrong objective here: variance is maximised by
    splitting wherever mass is concentrated, so when one mode dominates — the
    normal ER shape, where non-matches vastly outnumber matches — it subdivides
    that mode instead of separating it from the other. Measured on a clearly
    bimodal sample (3000 non-matches near 0.10, 600 matches near 0.80), the
    variance criterion returned cuts at 0.29 and 0.11, both inside the non-match
    peak, while the visible valley sat near 0.45. Trough depth asks the question
    band placement actually poses: where does the distribution thin out?

    Refuses, rather than guessing, when the distribution carries no evidence of
    separation — using ``valley_depth`` at the strongest cut, the same guard as
    :func:`select_threshold_unsupervised`. Between-class variance cannot detect
    bimodality (splitting a single Gaussian at its mean already yields ~0.64),
    so gating on it would return confident-looking bands from a distribution
    that supports none. A refusal is information: it says the matcher is not
    separating classes on this data, and bands will not fix that.

    Returns a :class:`BandSelection`; ``thresholds`` is empty when it declines.
    """
    if n_thresholds < 1:
        raise ValueError("n_thresholds must be at least 1")
    if n_thresholds > 3:
        # Exhaustive search is O(bins**n_thresholds); beyond 3 cuts it stops
        # being cheap, and the benchmark found more bands is not better anyway
        # (a four-level split was the worst of four settings tried).
        raise ValueError("n_thresholds above 3 is not supported")

    values = [float(s) for s in scores if s is not None and math.isfinite(s)]
    if len(values) < 2:
        return BandSelection([], "fallback", {"sample_size": len(values)},
                             "too few scores to infer bands")

    low, high = min(values), max(values)
    if high - low < 1e-9:
        return BandSelection(
            [], "fallback",
            {"score_min": low, "score_max": high, "sample_size": len(values)},
            "all scores identical; no band structure to infer",
        )

    # Same sqrt(n) resolution heuristic as the single-cut path: a fixed large
    # bin count over few samples leaves noise spikes that read as real troughs.
    bins = max(16, min(bins, int(math.sqrt(len(values))) * 2))
    width = (high - low) / bins
    counts = [0] * bins
    for value in values:
        counts[min(int((value - low) / width), bins - 1)] += 1

    total = len(values)

    # Smooth before looking for troughs: an unsmoothed histogram of real scores
    # is spiky, and every downward blip between two spikes reads as a valley.
    smoothed = [
        sum(counts[max(0, i - 1): min(bins, i + 2)]) / len(
            counts[max(0, i - 1): min(bins, i + 2)]
        )
        for i in range(bins)
    ]

    # Candidate cuts are interior local minima of the smoothed histogram, each
    # scored by how deep its trough is relative to the surrounding peaks.
    cumulative = 0
    min_side_mass = total * _MIN_BAND_MASS_FRACTION
    candidates = []
    for i in range(bins):
        cumulative += counts[i]
        if i == 0 or i == bins - 1:
            continue
        if not (smoothed[i] <= smoothed[i - 1] and smoothed[i] <= smoothed[i + 1]):
            continue
        # Both sides must carry real mass, or this is a tail artefact rather
        # than a separation between populations.
        if min(cumulative, total - cumulative) < min_side_mass:
            continue
        depth = _valley_depth(counts, i)
        if depth >= min_valley_depth:
            candidates.append((depth, i))

    diagnostics: Dict[str, Any] = {
        "score_min": round(low, 4),
        "score_max": round(high, 4),
        "sample_size": total,
        "bins": bins,
        "candidate_valleys": len(candidates),
    }

    if not candidates:
        message = (
            "score distribution shows no separation (no trough reached depth "
            f"{min_valley_depth}); bands would subdivide a single mode. Improve "
            "features or scoring rather than banding."
        )
        logger.warning("Comparison-band selection declined: %s", message)
        return BandSelection([], "fallback", diagnostics, message)

    # Deepest troughs first, but suppress neighbours: across an empty gap every
    # bin is a local minimum of equal depth, so taking the top-n outright
    # returns adjacent cuts and a middle band holding almost nothing. Requiring
    # separation makes each cut mark a DISTINCT thinning of the distribution.
    min_separation = max(2, int(bins * _MIN_BAND_SEPARATION_FRACTION))
    chosen: List[Tuple[float, int]] = []
    for depth, index in sorted(candidates, reverse=True):
        if all(abs(index - taken) >= min_separation for _, taken in chosen):
            chosen.append((depth, index))
        if len(chosen) == n_thresholds:
            break

    # Returning fewer bands than requested is deliberate: forcing extra cuts
    # into a distribution that supports only one real separation manufactures
    # structure, and the benchmark already showed more bands is not better.
    thresholds = sorted(
        (round(low + (index + 1) * width, 4) for _, index in chosen), reverse=True
    )
    diagnostics["valley_depths"] = [round(d, 4) for d, _ in chosen]
    diagnostics["strongest_valley_depth"] = round(max(d for d, _ in chosen), 4)
    if len(thresholds) < n_thresholds:
        diagnostics["requested_thresholds"] = n_thresholds

    logger.info(
        "Selected comparison bands %s (valley depths %s over %d scores)",
        thresholds, diagnostics["valley_depths"], total,
    )
    return BandSelection(thresholds, "valley_detection", diagnostics)


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
