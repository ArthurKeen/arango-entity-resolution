"""Cluster-level entity-resolution metrics.

Pairwise precision/recall (see :mod:`evaluation_service`) measures the quality of
*scoring decisions*. It does not measure the quality of the *entities* the
pipeline finally produces, and it is well known to be optimistic: large clusters
dominate the pair count, so a single chain merge can look cheap while badly
corrupting the output.

This module provides the entity-centric metrics the record-linkage literature
uses for that job:

* **B-cubed** (Bagga & Baldwin) — computed per *record* rather than per pair, so
  it penalises over-merging and under-merging symmetrically and is not dominated
  by big clusters. This is the standard rigour bar for ER evaluation.
* **Pairwise metrics over the transitive closure** of the final clusters — the
  honest measure of what clustering actually asserted, including pairs the
  scorer never saw but transitivity implied.

Both take the same inputs: a predicted clustering and a ground-truth clustering,
each expressed as an iterable of clusters of record keys. Records may be absent
from either side; singletons may be omitted (they are inferred) as long as
``all_records`` is supplied.
"""

from __future__ import annotations

from itertools import combinations
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

__all__ = [
    "b_cubed",
    "pairwise_closure_metrics",
    "evaluate_clustering",
]


def _to_membership(
    clusters: Iterable[Sequence[str]],
    all_records: Optional[Iterable[str]] = None,
) -> Dict[str, frozenset]:
    """Map each record to the set of records sharing its cluster (including itself).

    Records listed in ``all_records`` but absent from ``clusters`` are treated as
    singletons, which is what an ER pipeline means when it emits only clusters of
    size >= 2.
    """
    membership: Dict[str, frozenset] = {}
    for cluster in clusters:
        members = frozenset(cluster)
        if not members:
            continue
        for record in members:
            # A record appearing in two predicted clusters is a bug upstream; the
            # union keeps this function total rather than silently picking one.
            existing = membership.get(record)
            membership[record] = members if existing is None else (existing | members)

    if all_records is not None:
        for record in all_records:
            membership.setdefault(record, frozenset({record}))

    return membership


def b_cubed(
    predicted: Iterable[Sequence[str]],
    truth: Iterable[Sequence[str]],
    all_records: Optional[Iterable[str]] = None,
) -> Dict[str, float]:
    """B-cubed precision / recall / F1 over records.

    For each record ``e`` with predicted cluster ``C(e)`` and true cluster
    ``T(e)``::

        precision(e) = |C(e) & T(e)| / |C(e)|
        recall(e)    = |C(e) & T(e)| / |T(e)|

    The reported values average over every record evaluated. Only records present
    in the ground truth are scored, since a record with no truth assignment has
    no defined correct answer.

    Returns a dict with ``precision``, ``recall``, ``f1`` and ``records_evaluated``.
    """
    truth_membership = _to_membership(truth, all_records)
    predicted_membership = _to_membership(predicted, all_records)

    scored = [r for r in truth_membership if r in predicted_membership]
    if not scored:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "records_evaluated": 0,
        }

    precision_total = 0.0
    recall_total = 0.0
    for record in scored:
        pred_cluster = predicted_membership[record]
        true_cluster = truth_membership[record]
        overlap = len(pred_cluster & true_cluster)
        precision_total += overlap / len(pred_cluster)
        recall_total += overlap / len(true_cluster)

    precision = precision_total / len(scored)
    recall = recall_total / len(scored)
    f1 = (
        (2 * precision * recall / (precision + recall))
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "records_evaluated": len(scored),
    }


def _within_cluster_pairs(clusters: Iterable[Sequence[str]]) -> Set[Tuple[str, str]]:
    """All unordered intra-cluster pairs, canonically ordered."""
    pairs: Set[Tuple[str, str]] = set()
    for cluster in clusters:
        unique = sorted(set(cluster))
        for a, b in combinations(unique, 2):
            pairs.add((a, b))
    return pairs


def pairwise_closure_metrics(
    predicted: Iterable[Sequence[str]],
    truth: Iterable[Sequence[str]],
) -> Dict[str, float]:
    """Pairwise precision / recall / F1 over the transitive closure of clusters.

    Unlike scoring-stage pairwise metrics, this counts every pair the final
    clustering *implies* — so the precision cost of chain merges (A-B, B-C
    silently asserting A-C) is actually measured.
    """
    predicted_pairs = _within_cluster_pairs(predicted)
    truth_pairs = _within_cluster_pairs(truth)

    true_positives = len(predicted_pairs & truth_pairs)
    precision = (
        true_positives / len(predicted_pairs) if predicted_pairs else 0.0
    )
    recall = true_positives / len(truth_pairs) if truth_pairs else 0.0
    f1 = (
        (2 * precision * recall / (precision + recall))
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positives": true_positives,
        "predicted_pairs": len(predicted_pairs),
        "truth_pairs": len(truth_pairs),
    }


def evaluate_clustering(
    predicted: Iterable[Sequence[str]],
    truth: Iterable[Sequence[str]],
    all_records: Optional[Iterable[str]] = None,
) -> Dict[str, object]:
    """Full cluster-quality report: B-cubed plus pairwise-closure metrics.

    Both families are reported together deliberately — pairwise numbers are
    comparable with published benchmark results, while B-cubed is the metric that
    reflects entity-level correctness.
    """
    predicted_list: List[Sequence[str]] = [list(c) for c in predicted]
    truth_list: List[Sequence[str]] = [list(c) for c in truth]

    return {
        "b_cubed": b_cubed(predicted_list, truth_list, all_records),
        "pairwise": pairwise_closure_metrics(predicted_list, truth_list),
        "predicted_clusters": len(predicted_list),
        "truth_clusters": len(truth_list),
    }
