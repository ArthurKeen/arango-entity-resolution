"""Matching-quality regression gate.

Unit tests verify that each function is locally correct. They cannot see
*statistical* regressions — a change to null handling, weight renormalization,
or threshold defaults can leave every unit test green while quietly destroying
end-to-end matching quality. That class of bug is precisely what this file
catches.

A small labeled dataset is scored through the real matching code and the
resulting clusters are measured with both pairwise and B-cubed metrics
(:mod:`entity_resolution.services.cluster_metrics`). Quality must stay above an
explicit floor.

The floors are deliberately set BELOW current measured performance: this gate is
a ratchet against regression, not a brittle exact-match assertion. When a genuine
improvement lands, raise the floor in the same commit.

NOTE ON THE FILENAME: this file must not contain the word "benchmark".
``conftest.pytest_collection_modifyitems`` auto-marks any test whose nodeid
contains "benchmark" as ``performance``, which would deselect this gate from the
``-m unit`` run that CI enforces — the gate would exist but never execute. That
is the exact "built but never wired" failure mode this suite guards against.

The dataset encodes the classic ER failure modes on purpose:

* records that match strongly on every populated field (must merge)
* SPARSE records — identical but with most fields missing (must still merge;
  treating a missing field as disagreement breaks this)
* records sharing exactly ONE low-information field (must NOT merge; weight
  renormalization without a minimum-evidence floor breaks this)
* same-name decoys with conflicting strong identifiers (must NOT merge)
"""

from __future__ import annotations

from typing import Dict, List, Sequence

import pytest

from entity_resolution.services.cluster_metrics import (
    b_cubed,
    evaluate_clustering,
    pairwise_closure_metrics,
)
from entity_resolution.similarity.weighted_field_similarity import (
    WeightedFieldSimilarity,
)

# ---------------------------------------------------------------------------
# Labeled fixture. Keys encode the truth cluster for readability: e1a/e1b are
# the same entity; the trailing letter distinguishes source records.
# ---------------------------------------------------------------------------

RECORDS: Dict[str, Dict[str, object]] = {
    # Entity 1 — strong full-field match, formatting noise only.
    "e1a": {
        "name": "Acme Corporation",
        "address": "123 Main Street",
        "city": "Boston",
        "email": "info@acme.com",
        "phone": "555-0100",
    },
    "e1b": {
        "name": "ACME Corp.",
        "address": "123 Main St",
        "city": "Boston",
        "email": "info@acme.com",
        "phone": "5550100",
    },
    # Entity 2 — SPARSE pair. Same entity, but one record has almost no data.
    # Correct behaviour: the fields that ARE present agree strongly, so these
    # merge. Treating absent fields as disagreement would split them.
    "e2a": {
        "name": "Globex Industries",
        "address": "500 Oak Avenue",
        "city": "Chicago",
        "email": "contact@globex.com",
        "phone": "555-0200",
    },
    "e2b": {
        "name": "Globex Industries",
        "email": "contact@globex.com",
    },
    # Entity 3 — singleton that shares ONLY a city with several others.
    # Must not merge: one low-information field is not evidence of identity.
    "e3a": {
        "name": "Initech Systems",
        "city": "Boston",
    },
    # Entity 4 — same-name decoy of entity 1, different everything else.
    # Must not merge with e1a/e1b.
    "e4a": {
        "name": "Acme Corporation",
        "address": "77 Industrial Way",
        "city": "Portland",
        "email": "hello@acme-pdx.com",
        "phone": "555-0400",
    },
    # Entity 5 — clean unrelated singleton.
    "e5a": {
        "name": "Umbrella Health",
        "address": "9 Willow Lane",
        "city": "Seattle",
        "email": "info@umbrella.example",
        "phone": "555-0500",
    },
}

TRUTH_CLUSTERS: List[List[str]] = [
    ["e1a", "e1b"],
    ["e2a", "e2b"],
    ["e3a"],
    ["e4a"],
    ["e5a"],
]

FIELD_WEIGHTS = {
    "name": 0.40,
    "address": 0.25,
    "email": 0.20,
    "phone": 0.10,
    "city": 0.05,
}

MATCH_THRESHOLD = 0.80

# Floors: set below currently measured values so this ratchets against
# regression. Raise them (in the same commit) when quality genuinely improves.
MIN_PAIRWISE_F1 = 0.80
MIN_B_CUBED_F1 = 0.85


def _cluster_records(threshold: float = MATCH_THRESHOLD) -> List[List[str]]:
    """Score every pair with the real matcher and union-find the matches."""
    scorer = WeightedFieldSimilarity(
        field_weights=FIELD_WEIGHTS,
        algorithm="jaro_winkler",
        handle_nulls="skip",
    )

    keys = sorted(RECORDS)
    parent = {k: k for k in keys}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            if scorer.compute(RECORDS[a], RECORDS[b]) >= threshold:
                union(a, b)

    groups: Dict[str, List[str]] = {}
    for key in keys:
        groups.setdefault(find(key), []).append(key)
    return [sorted(members) for members in groups.values()]


@pytest.fixture(scope="module")
def predicted_clusters() -> List[List[str]]:
    return _cluster_records()


def test_pairwise_f1_above_floor(predicted_clusters):
    """End-to-end pairwise F1 over the transitive closure must not regress."""
    metrics = pairwise_closure_metrics(predicted_clusters, TRUTH_CLUSTERS)
    assert metrics["f1"] >= MIN_PAIRWISE_F1, (
        f"pairwise F1 {metrics['f1']:.3f} fell below floor {MIN_PAIRWISE_F1}. "
        f"Full metrics: {metrics}. Clusters: {predicted_clusters}"
    )


def test_b_cubed_f1_above_floor(predicted_clusters):
    """Entity-level (B-cubed) F1 must not regress."""
    metrics = b_cubed(predicted_clusters, TRUTH_CLUSTERS, all_records=RECORDS)
    assert metrics["f1"] >= MIN_B_CUBED_F1, (
        f"B-cubed F1 {metrics['f1']:.3f} fell below floor {MIN_B_CUBED_F1}. "
        f"Full metrics: {metrics}. Clusters: {predicted_clusters}"
    )


def test_strong_full_field_match_merges(predicted_clusters):
    """The easy case must work: high agreement on every populated field."""
    same = [c for c in predicted_clusters if "e1a" in c]
    assert same and "e1b" in same[0], (
        f"e1a/e1b failed to merge despite agreeing on all fields: {predicted_clusters}"
    )


def test_same_name_decoy_does_not_merge(predicted_clusters):
    """Matching names must not outvote disagreement on every other field."""
    cluster = next(c for c in predicted_clusters if "e1a" in c)
    assert "e4a" not in cluster, (
        "same-name decoy e4a merged into the Acme cluster — name similarity is "
        f"overwhelming contradicting evidence: {predicted_clusters}"
    )


def test_single_shared_low_information_field_does_not_merge(predicted_clusters):
    """Sharing only 'city' is not identity evidence.

    Guards the renormalization hazard: with handle_nulls='skip', a pair whose
    only mutually-present field is city renormalizes to a perfect score unless a
    minimum-evidence floor is enforced.
    """
    cluster = next(c for c in predicted_clusters if "e3a" in c)
    assert cluster == ["e3a"], (
        "e3a merged with another record on the strength of a shared city alone: "
        f"{predicted_clusters}"
    )


def test_sparse_record_still_merges(predicted_clusters):
    """A record missing most fields must still match on the fields it has.

    The weighted-heuristic path handles this correctly by renormalizing over
    mutually-present fields. The Fellegi-Sunter path does NOT — see
    ``test_fellegi_sunter_does_not_penalise_missing_fields`` below.
    """
    cluster = next(c for c in predicted_clusters if "e2a" in c)
    assert "e2b" in cluster, (
        "sparse record e2b failed to merge with e2a despite exact agreement on "
        f"name and email: {predicted_clusters}"
    )


def test_fellegi_sunter_does_not_penalise_missing_fields():
    """A missing field must contribute no evidence — neither for nor against.

    Two records that agree perfectly on the fields they share should not be
    scored lower simply because one of them has fewer fields populated.
    """
    from entity_resolution.learning.fellegi_sunter_scorer import (
        FellegiSunterScorer,
    )

    scorer = FellegiSunterScorer(
        m={"name": 0.9, "address": 0.9, "email": 0.9, "phone": 0.9},
        u={"name": 0.05, "address": 0.05, "email": 0.05, "phone": 0.05},
        default_threshold=0.85,
    )

    sparse_but_agreeing = {"name": 1.0, "email": 1.0}  # address/phone absent
    llr_sparse = scorer.total_llr(sparse_but_agreeing)

    # A neutral missing field contributes exactly zero, so the sparse pair's
    # evidence must equal the agreement evidence of just the present fields.
    # Comparing against a model containing ONLY those fields expresses that
    # exactly; a weaker "is it still positive?" check would miss the bug
    # whenever agreements happen to outweigh the spurious penalties.
    present_only = FellegiSunterScorer(
        m={"name": 0.9, "email": 0.9},
        u={"name": 0.05, "email": 0.05},
        default_threshold=0.85,
    )
    expected = present_only.total_llr({"name": 1.0, "email": 1.0})

    assert llr_sparse == pytest.approx(expected), (
        f"absent fields changed the score (got {llr_sparse:.4f}, expected "
        f"{expected:.4f}); they are being charged as disagreement instead of "
        "contributing no evidence"
    )


def test_evaluate_clustering_reports_both_metric_families(predicted_clusters):
    """The reporting entry point returns both metric families together."""
    report = evaluate_clustering(
        predicted_clusters, TRUTH_CLUSTERS, all_records=RECORDS
    )
    assert set(report) >= {"b_cubed", "pairwise", "predicted_clusters"}
    assert 0.0 <= report["b_cubed"]["f1"] <= 1.0
    assert 0.0 <= report["pairwise"]["f1"] <= 1.0


# ---------------------------------------------------------------------------
# Metric-implementation self-checks: a broken metric would silently disarm the
# gate above, so the metrics themselves are verified against hand-computed cases.
# ---------------------------------------------------------------------------


def test_b_cubed_perfect_clustering_scores_one():
    metrics = b_cubed(TRUTH_CLUSTERS, TRUTH_CLUSTERS, all_records=RECORDS)
    assert metrics["precision"] == pytest.approx(1.0)
    assert metrics["recall"] == pytest.approx(1.0)
    assert metrics["f1"] == pytest.approx(1.0)


def test_b_cubed_penalises_over_merging():
    """One giant cluster: perfect recall, poor precision."""
    everything = [sorted(RECORDS)]
    metrics = b_cubed(everything, TRUTH_CLUSTERS, all_records=RECORDS)
    assert metrics["recall"] == pytest.approx(1.0)
    assert metrics["precision"] < 0.5
    assert metrics["f1"] < 1.0


def test_b_cubed_penalises_under_merging():
    """All singletons: perfect precision, poor recall."""
    singletons: List[Sequence[str]] = [[k] for k in RECORDS]
    metrics = b_cubed(singletons, TRUTH_CLUSTERS, all_records=RECORDS)
    assert metrics["precision"] == pytest.approx(1.0)
    assert metrics["recall"] < 1.0


def test_pairwise_closure_counts_implied_pairs():
    """A 3-chain asserts 3 pairs, including the one never scored directly."""
    metrics = pairwise_closure_metrics([["a", "b", "c"]], [["a", "b", "c"]])
    assert metrics["predicted_pairs"] == 3
    assert metrics["true_positives"] == 3
    assert metrics["f1"] == pytest.approx(1.0)


def test_pairwise_closure_detects_chain_merge_precision_loss():
    """Chain-merging two distinct entities is caught as a precision loss."""
    metrics = pairwise_closure_metrics([["a", "b", "c"]], [["a", "b"], ["c"]])
    assert metrics["recall"] == pytest.approx(1.0)
    assert metrics["precision"] < 0.5
