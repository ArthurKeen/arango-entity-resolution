"""Precision-first, read-only canonical-hub resolution for the data fabric.

This module is intentionally dependency-light. Embedding, candidate retrieval,
and optional uncertain-band verification are injectable, so the safety contract
can be tested without a model or a live ArangoDB deployment.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from types import MappingProxyType
from typing import Any, Literal, Protocol

ResolveStatus = Literal["resolved", "abstained", "refused"]

_ORACLE_KEYS = frozenset(
    {
        "canonical_id",
        "expected_canonical_id",
        "gold_id",
        "ground_truth_id",
        "match_id",
        "oracle_id",
        "resolved_to",
    }
)


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True)
class ResolveProfile:
    """Immutable precision and observable-field policy."""

    name: str
    observable_fields: tuple[str, ...]
    field_weights: tuple[tuple[str, float], ...]
    resolve_threshold: float
    minimum_margin: float
    vector_weight: float
    top_k: int
    uncertainty_low: float
    uncertainty_high: float

    def __post_init__(self) -> None:
        if not self.name or not self.observable_fields:
            raise ValueError("profile name and observable_fields are required")
        if len(set(self.observable_fields)) != len(self.observable_fields):
            raise ValueError("observable_fields must be unique")
        weights = dict(self.field_weights)
        if set(weights) != set(self.observable_fields):
            raise ValueError("field_weights must cover exactly the observable fields")
        if any(not math.isfinite(weight) or weight <= 0 for weight in weights.values()):
            raise ValueError("field weights must be finite and positive")
        if not 0 <= self.vector_weight <= 1:
            raise ValueError("vector_weight must be between zero and one")
        if not 0 <= self.resolve_threshold <= 1:
            raise ValueError("resolve_threshold must be between zero and one")
        if self.vector_weight >= self.resolve_threshold:
            raise ValueError(
                "resolve_threshold must exceed vector_weight so vector evidence "
                "cannot resolve without field evidence"
            )
        if not 0 <= self.minimum_margin <= 1:
            raise ValueError("minimum_margin must be between zero and one")
        if self.top_k < 2 or self.top_k > 100:
            raise ValueError("top_k must be between 2 and 100")
        if not 0 <= self.uncertainty_low <= self.uncertainty_high <= 1:
            raise ValueError("uncertainty band must be ordered within [0, 1]")

    @property
    def weights(self) -> Mapping[str, float]:
        return MappingProxyType(dict(self.field_weights))


@dataclass(frozen=True)
class ResolveRequest:
    """One scoped entity observation and its absolute monotonic deadline."""

    account_scope: str
    attributes: Mapping[str, Any]
    deadline_at: float
    request_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))


@dataclass(frozen=True)
class FieldEvidence:
    """Similarity evidence for one allowlisted observable field."""

    field: str
    similarity: float
    weight: float


@dataclass(frozen=True)
class ResolveEvidence:
    """Explainable evidence for the selected candidate."""

    profile: str
    candidate_count: int
    field_scores: tuple[FieldEvidence, ...]
    vector_score: float
    verifier_used: bool = False
    verifier_decision: str | None = None


@dataclass(frozen=True)
class ResolveResult:
    """Stable service result; this service never creates or changes linkages."""

    status: ResolveStatus
    canonical_id: str | None
    reason: str
    score: float | None
    margin: float | None
    evidence: ResolveEvidence | None
    candidate_account_scope: str | None
    deadline_at: float
    elapsed_ms: float


@dataclass(frozen=True)
class CanonicalCandidate:
    """Candidate payload returned by a scoped provider."""

    canonical_id: str | None
    account_scope: str
    fields: Mapping[str, Any]
    vector_score: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", _freeze_mapping(self.fields))


@dataclass(frozen=True)
class CandidateSearchResult:
    """Structured candidate retrieval, including unavailable-vector abstention."""

    candidates: tuple[CanonicalCandidate, ...] = ()
    available: bool = True
    reason: str | None = None

    @classmethod
    def unavailable(cls, reason: str) -> CandidateSearchResult:
        return cls(available=False, reason=reason)


@dataclass(frozen=True)
class VerifierDecision:
    """Optional uncertain-band adjudication."""

    decision: Literal["match", "no_match", "abstain"]
    reason: str


class Embedder(Protocol):
    def embed(self, text: str, *, deadline_at: float) -> Sequence[float]: ...


class VectorCandidateProvider(Protocol):
    def search(
        self,
        vector: Sequence[float],
        *,
        account_scope: str,
        top_k: int,
        deadline_at: float,
    ) -> CandidateSearchResult: ...


class UncertaintyVerifier(Protocol):
    def verify(
        self,
        query_fields: Mapping[str, Any],
        candidate_fields: Mapping[str, Any],
        *,
        score: float,
        deadline_at: float,
    ) -> VerifierDecision: ...


@dataclass(frozen=True)
class _ScoredCandidate:
    candidate: CanonicalCandidate
    score: float
    fields: tuple[FieldEvidence, ...]


class SemanticCanonicalHubResolver:
    """Resolve an observation to an existing canonical ID without any writes."""

    def __init__(
        self,
        profile: ResolveProfile,
        embedder: Embedder,
        candidates: VectorCandidateProvider,
        *,
        verifier: UncertaintyVerifier | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.profile = profile
        self.embedder = embedder
        self.candidates = candidates
        self.verifier = verifier
        self._clock = clock

    def resolve(self, request: ResolveRequest) -> ResolveResult:
        started = self._clock()

        def result(
            status: ResolveStatus,
            reason: str,
            *,
            canonical_id: str | None = None,
            score: float | None = None,
            margin: float | None = None,
            evidence: ResolveEvidence | None = None,
            candidate_account_scope: str | None = None,
        ) -> ResolveResult:
            return ResolveResult(
                status=status,
                canonical_id=canonical_id,
                reason=reason,
                score=score,
                margin=margin,
                evidence=evidence,
                candidate_account_scope=candidate_account_scope,
                deadline_at=request.deadline_at,
                elapsed_ms=max(0.0, (self._clock() - started) * 1000),
            )

        scope = request.account_scope.strip()
        if not scope:
            return result("refused", "account_scope_required")
        if not math.isfinite(request.deadline_at) or request.deadline_at <= started:
            return result("abstained", "deadline_exceeded")

        input_keys = {_normalized_key(key) for key in request.attributes}
        if input_keys & _ORACLE_KEYS or any("oracle" in key or "canonical" in key for key in input_keys):
            return result("refused", "oracle_identifier_in_input")
        unknown = set(request.attributes) - set(self.profile.observable_fields)
        if unknown:
            return result("refused", "non_observable_field")

        query_fields = {
            field: _observable_value(request.attributes[field])
            for field in self.profile.observable_fields
            if field in request.attributes and _observable_value(request.attributes[field]) is not None
        }
        if not query_fields:
            return result("abstained", "no_observable_fields")
        if self._expired(request.deadline_at):
            return result("abstained", "deadline_exceeded")

        similarity_text = "\n".join(
            f"{field}: {query_fields[field]}" for field in self.profile.observable_fields
            if field in query_fields
        )
        try:
            vector = tuple(float(value) for value in self.embedder.embed(
                similarity_text,
                deadline_at=request.deadline_at,
            ))
        except Exception:
            return result("abstained", "embedding_unavailable")
        if not vector or any(not math.isfinite(value) for value in vector):
            return result("abstained", "embedding_invalid")
        if self._expired(request.deadline_at):
            return result("abstained", "deadline_exceeded")

        try:
            search = self.candidates.search(
                vector,
                account_scope=scope,
                top_k=self.profile.top_k,
                deadline_at=request.deadline_at,
            )
        except Exception:
            return result("abstained", "candidate_search_unavailable")
        if not search.available:
            return result("abstained", search.reason or "vector_search_unavailable")
        if self._expired(request.deadline_at):
            return result("abstained", "deadline_exceeded")
        if not search.candidates:
            return result("abstained", "no_candidate")

        # This post-check is intentionally independent of provider query scoping.
        for candidate in search.candidates:
            if candidate.account_scope != scope:
                return result("refused", "cross_account_candidate")
            if not candidate.canonical_id or not candidate.canonical_id.strip():
                return result("refused", "candidate_canonical_id_required")

        scored: list[_ScoredCandidate] = []
        for candidate in search.candidates:
            if not math.isfinite(candidate.vector_score) or not 0 <= candidate.vector_score <= 1:
                return result("abstained", "candidate_score_invalid")
            field_evidence, field_score = self._field_score(query_fields, candidate.fields)
            combined = (
                self.profile.vector_weight * candidate.vector_score
                + (1 - self.profile.vector_weight) * field_score
            )
            scored.append(
                _ScoredCandidate(
                    candidate=candidate,
                    score=combined,
                    fields=field_evidence,
                )
            )
        scored.sort(key=lambda item: (-item.score, item.candidate.canonical_id or ""))
        top = scored[0]
        margin = top.score - scored[1].score if len(scored) > 1 else 1.0
        evidence = ResolveEvidence(
            profile=self.profile.name,
            candidate_count=len(scored),
            field_scores=top.fields,
            vector_score=top.candidate.vector_score,
        )

        if top.score < self.profile.resolve_threshold:
            return result(
                "abstained",
                "below_threshold",
                score=top.score,
                margin=margin,
                evidence=evidence,
            )
        if margin < self.profile.minimum_margin:
            return result(
                "abstained",
                "ambiguous_margin",
                score=top.score,
                margin=margin,
                evidence=evidence,
            )

        if (
            self.verifier is not None
            and self.profile.uncertainty_low <= top.score <= self.profile.uncertainty_high
        ):
            if self._expired(request.deadline_at):
                return result(
                    "abstained",
                    "deadline_exceeded",
                    score=top.score,
                    margin=margin,
                    evidence=evidence,
                )
            try:
                verdict = self.verifier.verify(
                    query_fields,
                    {
                        field: top.candidate.fields[field]
                        for field in self.profile.observable_fields
                        if field in top.candidate.fields
                    },
                    score=top.score,
                    deadline_at=request.deadline_at,
                )
            except Exception:
                verdict = VerifierDecision("abstain", "verifier_unavailable")
            evidence = ResolveEvidence(
                profile=evidence.profile,
                candidate_count=evidence.candidate_count,
                field_scores=evidence.field_scores,
                vector_score=evidence.vector_score,
                verifier_used=True,
                verifier_decision=verdict.decision,
            )
            if verdict.decision != "match":
                return result(
                    "abstained",
                    f"verifier_{verdict.decision}",
                    score=top.score,
                    margin=margin,
                    evidence=evidence,
                )

        if self._expired(request.deadline_at):
            return result(
                "abstained",
                "deadline_exceeded",
                score=top.score,
                margin=margin,
                evidence=evidence,
            )
        return result(
            "resolved",
            "threshold_and_margin_satisfied",
            canonical_id=top.candidate.canonical_id,
            score=top.score,
            margin=margin,
            evidence=evidence,
            candidate_account_scope=top.candidate.account_scope,
        )

    def _expired(self, deadline_at: float) -> bool:
        return self._clock() >= deadline_at

    def _field_score(
        self,
        query: Mapping[str, Any],
        candidate: Mapping[str, Any],
    ) -> tuple[tuple[FieldEvidence, ...], float]:
        evidence: list[FieldEvidence] = []
        weighted_total = 0.0
        total_weight = 0.0
        for field, weight in self.profile.field_weights:
            left = _observable_value(query.get(field))
            right = _observable_value(candidate.get(field))
            if left is None or right is None:
                continue
            similarity = SequenceMatcher(None, str(left).casefold(), str(right).casefold()).ratio()
            evidence.append(FieldEvidence(field=field, similarity=similarity, weight=weight))
            weighted_total += similarity * weight
            total_weight += weight
        return tuple(evidence), weighted_total / total_weight if total_weight else 0.0


def _normalized_key(key: Any) -> str:
    return str(key).strip().casefold().replace("-", "_").replace(".", "_")


def _observable_value(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (dict, list, tuple, set, bytes)):
        return None
    if isinstance(value, str):
        normalized = " ".join(value.split())
        return normalized or None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return value
    return None
