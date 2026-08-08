"""Focused WP-13 safety and precision gate for newly added AER modules."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from entity_resolution.services.fabric_arango_vector_provider_wp13 import (
    ArangoCanonicalHubVectorProvider,
)
from entity_resolution.services.fabric_canonical_hub_resolver_wp13 import (
    CandidateSearchResult,
    CanonicalCandidate,
    ResolveProfile,
    ResolveRequest,
    SemanticCanonicalHubResolver,
    VerifierDecision,
)

FIXTURE = Path(__file__).with_name("fabric_canonical_hub_precision_wp13.json")


def _profile() -> ResolveProfile:
    return ResolveProfile(
        name="fabric_canonical_hub",
        observable_fields=("name", "email_domain", "phone_country", "postal_code", "country"),
        field_weights=(
            ("name", 0.30),
            ("email_domain", 0.30),
            ("phone_country", 0.10),
            ("postal_code", 0.20),
            ("country", 0.10),
        ),
        vector_weight=0.70,
        resolve_threshold=0.88,
        minimum_margin=0.08,
        top_k=10,
        uncertainty_low=0.88,
        uncertainty_high=0.93,
    )


class _Embedder:
    def __init__(self) -> None:
        self.inputs: list[str] = []

    def embed(self, text, *, deadline_at):
        self.inputs.append(text)
        return (0.1, 0.2, 0.3)


class _Provider:
    def __init__(self, candidates) -> None:
        self.candidates = tuple(candidates)
        self.calls = []

    def search(self, vector, *, account_scope, top_k, deadline_at):
        self.calls.append(
            {
                "vector": vector,
                "account_scope": account_scope,
                "top_k": top_k,
                "deadline_at": deadline_at,
            }
        )
        return CandidateSearchResult(candidates=self.candidates)


def _candidate(raw) -> CanonicalCandidate:
    return CanonicalCandidate(
        canonical_id=raw["canonical_id"],
        account_scope=raw["account_scope"],
        fields=raw["fields"],
        vector_score=raw["vector_score"],
    )


def test_labeled_precision_corpus_gates_false_positives_and_scope() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    results = []
    for case in document["cases"]:
        embedder = _Embedder()
        provider = _Provider(_candidate(raw) for raw in case["candidates"])
        resolver = SemanticCanonicalHubResolver(
            _profile(),
            embedder,
            provider,
            clock=lambda: 100.0,
        )
        result = resolver.resolve(
            ResolveRequest(
                account_scope=case["account_scope"],
                attributes=case["attributes"],
                deadline_at=101.0,
                request_id=case["id"],
            )
        )
        assert result.status == case["expected_status"], case["id"]
        results.append((case, result))

        # Oracle fields are refused before embedding or candidate search.
        if case["id"] == "oracle-input-refused":
            assert not embedder.inputs
            assert not provider.calls
        for text in embedder.inputs:
            assert "canonical/" not in text
            assert "canonical_id" not in text

    true_positives = sum(
        result.status == "resolved"
        and result.canonical_id == case["truth_canonical_id"]
        and case["truth_canonical_id"] is not None
        for case, result in results
    )
    false_positives = sum(
        result.status == "resolved"
        and result.canonical_id != case["truth_canonical_id"]
        for case, result in results
    )
    positives = sum(case["truth_canonical_id"] is not None for case, _ in results)
    abstentions = sum(result.status == "abstained" for _, result in results)
    cross_scope_violations = sum(
        result.status == "resolved"
        and any(
            candidate["canonical_id"] == result.canonical_id
            and candidate["account_scope"] != case["account_scope"]
            for candidate in case["candidates"]
        )
        for case, result in results
    )

    precision = true_positives / (true_positives + false_positives)
    recall = true_positives / positives
    abstention_rate = abstentions / len(results)
    assert precision == 1.0
    assert recall == pytest.approx(2 / 3)
    assert abstention_rate == pytest.approx(3 / 8)
    assert cross_scope_violations == 0


def test_deadline_and_required_scope_fail_closed() -> None:
    resolver = SemanticCanonicalHubResolver(
        _profile(),
        _Embedder(),
        _Provider(()),
        clock=lambda: 100.0,
    )
    deadline = resolver.resolve(
        ResolveRequest("acct-a", {"name": "Late"}, deadline_at=100.0)
    )
    missing_scope = resolver.resolve(
        ResolveRequest(" ", {"name": "Unscoped"}, deadline_at=101.0)
    )
    assert (deadline.status, deadline.reason) == ("abstained", "deadline_exceeded")
    assert (missing_scope.status, missing_scope.reason) == (
        "refused",
        "account_scope_required",
    )


def test_frozen_contracts_and_json_safe_scalar_evidence() -> None:
    request = ResolveRequest("acct-a", {"name": "Northstar"}, deadline_at=101.0)
    with pytest.raises(FrozenInstanceError):
        request.account_scope = "acct-b"
    with pytest.raises(TypeError):
        request.attributes["name"] = "Changed"

    result = SemanticCanonicalHubResolver(
        _profile(),
        _Embedder(),
        _Provider(
            (
                CanonicalCandidate(
                    "canonical/northstar",
                    "acct-a",
                    {"name": "Northstar"},
                    0.99,
                ),
            )
        ),
        clock=lambda: 100.0,
    ).resolve(request)
    assert result.status == "resolved"
    assert result.evidence is not None
    assert result.evidence.field_scores[0].field == "name"


class _Verifier:
    def __init__(self, decision="no_match") -> None:
        self.decision = decision
        self.calls = 0

    def verify(self, query_fields, candidate_fields, *, score, deadline_at):
        self.calls += 1
        return VerifierDecision(self.decision, "fixture verdict")


def test_optional_verifier_only_adjudicates_band_and_never_scope() -> None:
    verifier = _Verifier()
    in_band = CanonicalCandidate(
        "canonical/in-band",
        "acct-a",
        {"name": "In Band"},
        0.85,
    )
    result = SemanticCanonicalHubResolver(
        _profile(),
        _Embedder(),
        _Provider((in_band,)),
        verifier=verifier,
        clock=lambda: 100.0,
    ).resolve(ResolveRequest("acct-a", {"name": "In Band"}, deadline_at=101.0))
    assert result.status == "abstained"
    assert result.reason == "verifier_no_match"
    assert verifier.calls == 1

    cross_scope = CanonicalCandidate(
        "canonical/cross-scope",
        "acct-b",
        {"name": "In Band"},
        0.85,
    )
    refused = SemanticCanonicalHubResolver(
        _profile(),
        _Embedder(),
        _Provider((cross_scope,)),
        verifier=verifier,
        clock=lambda: 100.0,
    ).resolve(ResolveRequest("acct-a", {"name": "In Band"}, deadline_at=101.0))
    assert refused.reason == "cross_account_candidate"
    assert verifier.calls == 1


class _Collection:
    def __init__(self, indexes):
        self._indexes = indexes

    def indexes(self):
        return self._indexes


class _Aql:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return iter(self.rows)


class _Database:
    def __init__(self, indexes, rows=()):
        self._collection = _Collection(indexes)
        self.aql = _Aql(rows)

    def collection(self, name):
        assert name == "canonical_entities"
        return self._collection


def _arango_provider(database) -> ArangoCanonicalHubVectorProvider:
    return ArangoCanonicalHubVectorProvider(
        database,
        collection="canonical_entities",
        vector_field="fabric_embedding",
        vector_index="fabric_canonical_hub_vector_idx",
        canonical_id_field="canonical_id",
        account_scope_field="account_scope",
        observable_fields=("name", "country"),
        maximum_top_k=20,
        clock=lambda: 100.0,
    )


def test_arango_provider_uses_scoped_bind_vars_and_bounded_native_query() -> None:
    database = _Database(
        [
            {
                "type": "vector",
                "name": "fabric_canonical_hub_vector_idx",
                "fields": ["fabric_embedding"],
            }
        ],
        [
            {
                "canonical_id": "canonical/northstar",
                "account_scope": "acct-a",
                "fields": {"name": "Northstar", "country": "US"},
                "vector_score": 0.98,
            }
        ],
    )
    result = _arango_provider(database).search(
        (0.1, 0.2),
        account_scope="acct-a",
        top_k=999,
        deadline_at=101.0,
    )
    assert result.available
    assert result.candidates[0].canonical_id == "canonical/northstar"
    query, kwargs = database.aql.calls[0]
    assert "FILTER candidate.account_scope == @account_scope" in query
    assert "APPROX_NEAR_COSINE" in query
    assert kwargs["bind_vars"]["account_scope"] == "acct-a"
    assert kwargs["bind_vars"]["top_k"] == 20
    assert kwargs["bind_vars"]["observable_fields"] == ["name", "country"]


def test_arango_provider_abstains_without_configured_index_and_never_scans() -> None:
    database = _Database([])
    result = _arango_provider(database).search(
        (0.1, 0.2),
        account_scope="acct-a",
        top_k=10,
        deadline_at=101.0,
    )
    assert not result.available
    assert result.reason == "configured_vector_index_unavailable"
    assert not database.aql.calls


def test_arango_provider_rejects_interpolated_identifier_injection() -> None:
    with pytest.raises(ValueError, match="Invalid field name"):
        ArangoCanonicalHubVectorProvider(
            _Database([]),
            collection="canonical_entities",
            vector_field="embedding) REMOVE candidate",
            vector_index="safe_index",
            canonical_id_field="canonical_id",
            account_scope_field="account_scope",
            observable_fields=("name",),
        )
