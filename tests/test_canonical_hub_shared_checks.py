"""Shared checks for consumers that guard the resolver independently.

contextual-data-fabric wraps the resolver in its own guard and had copied the
request-side checks, the oracle-key set and the reason codes line for line.
One copied helper had already been rewritten differently, and the copy refused
a request with an unusable field where the resolver quietly ignored the field
(arango-solutions-org/arango-entity-resolution#4).

These tests hold the shared surface: check_request applies exactly the checks
resolve() applies, the stricter rule is a profile setting rather than a code
fork, and RESOLVE_REASONS names every reason the package can emit.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from entity_resolution.canonical_hub import (
    ORACLE_KEYS,
    RESOLVE_REASONS,
    CandidateSearchResult,
    ResolveProfile,
    ResolveRequest,
    SemanticCanonicalHubResolver,
    check_request,
)

NOW = 100.0
DEADLINE = 200.0


def _profile(**overrides) -> ResolveProfile:
    base = dict(
        name="shared_checks",
        observable_fields=("name", "country"),
        field_weights=(("name", 0.6), ("country", 0.4)),
        vector_weight=0.7,
        resolve_threshold=0.88,
        minimum_margin=0.08,
        top_k=10,
        uncertainty_low=0.88,
        uncertainty_high=0.93,
    )
    base.update(overrides)
    return ResolveProfile(**base)


def _request(attributes, scope="acct-1", deadline=DEADLINE) -> ResolveRequest:
    return ResolveRequest(account_scope=scope, attributes=attributes, deadline_at=deadline)


# (case id, request kwargs, profile overrides, expected status, expected reason)
CASES = [
    ("blank scope", dict(attributes={"name": "Acme"}, scope="  "), {}, "refused", "account_scope_required"),
    ("deadline passed", dict(attributes={"name": "Acme"}, deadline=NOW), {}, "abstained", "deadline_exceeded"),
    ("deadline not finite", dict(attributes={"name": "Acme"}, deadline=float("nan")), {}, "abstained", "deadline_exceeded"),
    ("oracle key", dict(attributes={"name": "Acme", "gold_id": "x"}), {}, "refused", "oracle_identifier_in_input"),
    ("oracle-like key", dict(attributes={"name": "Acme", "My-Canonical.Ref": "x"}), {}, "refused", "oracle_identifier_in_input"),
    ("unknown field", dict(attributes={"name": "Acme", "phone": "1"}), {}, "refused", "non_observable_field"),
    ("nothing usable", dict(attributes={"name": "   ", "country": None}), {}, "abstained", "no_observable_fields"),
    ("unusable, refuse", dict(attributes={"name": "Acme", "country": ["US"]}),
     {"on_unusable_value": "refuse"}, "refused", "non_scalar_observable_value"),
    ("blank, refuse", dict(attributes={"name": "Acme", "country": ""}),
     {"on_unusable_value": "refuse"}, "refused", "non_scalar_observable_value"),
]


@pytest.mark.parametrize("case_id, kwargs, profile, status, reason", CASES, ids=[c[0] for c in CASES])
def test_check_request_verdicts(case_id, kwargs, profile, status, reason) -> None:
    check = check_request(_request(**kwargs), _profile(**profile), now=NOW)
    assert (check.status, check.reason) == (status, reason)
    assert not check.passed
    assert check.reason in RESOLVE_REASONS[check.status]


def test_passing_request_returns_normalised_attributes_in_profile_order() -> None:
    check = check_request(_request({"country": "  US ", "name": "Acme   Corp"}, scope=" acct-1 "), _profile(), now=NOW)
    assert check.passed and check.status is None and check.reason is None
    assert check.account_scope == "acct-1"
    assert list(check.observable_attributes.items()) == [("name", "Acme Corp"), ("country", "US")]


def test_ignore_is_the_default_and_drops_only_the_unusable_field() -> None:
    check = check_request(_request({"name": "Acme", "country": ["US"]}), _profile(), now=NOW)
    assert check.passed
    assert dict(check.observable_attributes) == {"name": "Acme"}


def test_profile_rejects_an_unknown_policy() -> None:
    with pytest.raises(ValueError, match="on_unusable_value"):
        _profile(on_unusable_value="warn")


class _Embedder:
    def __init__(self) -> None:
        self.calls = 0

    def embed(self, text, *, deadline_at):
        self.calls += 1
        return (0.1, 0.2, 0.3)


class _NoCandidates:
    def search(self, vector, *, account_scope, top_k, deadline_at):
        return CandidateSearchResult(candidates=())


def _resolve(request, profile):
    embedder = _Embedder()
    resolver = SemanticCanonicalHubResolver(profile, embedder, _NoCandidates(), clock=lambda: NOW)
    return resolver.resolve(request), embedder


@pytest.mark.parametrize("case_id, kwargs, profile, status, reason", CASES, ids=[c[0] for c in CASES])
def test_resolve_applies_the_same_checks_before_any_backend_call(case_id, kwargs, profile, status, reason) -> None:
    # One implementation: resolve() returns check_request's verdict, and the
    # backend is never touched when the request fails.
    result, embedder = _resolve(_request(**kwargs), _profile(**profile))
    assert (result.status, result.reason) == (status, reason)
    assert embedder.calls == 0


def test_a_passing_request_reaches_the_backend() -> None:
    # Positive control for the test above.
    result, embedder = _resolve(_request({"name": "Acme"}), _profile())
    assert embedder.calls == 1
    assert (result.status, result.reason) == ("abstained", "no_candidate")


def test_oracle_keys_are_the_documented_set() -> None:
    assert isinstance(ORACLE_KEYS, frozenset)
    assert {"canonical_id", "gold_id", "ground_truth_id", "oracle_id", "resolved_to"} <= ORACLE_KEYS


def test_every_emitted_reason_is_in_the_vocabulary() -> None:
    # Closed over the package source, so a reason added to the resolver or the
    # provider without being added to RESOLVE_REASONS fails here.
    package = Path(__file__).resolve().parents[1] / "src" / "entity_resolution" / "canonical_hub"
    resolver_src = (package / "resolver.py").read_text(encoding="utf-8")
    provider_src = (package / "arango_vector_provider.py").read_text(encoding="utf-8")

    emitted = set(re.findall(r'(?:result|stop)\(\s*"(refused|abstained|resolved)",\s*"([a-z_]+)"', resolver_src))
    assert len(emitted) >= 15, "the scan found too few reasons; the pattern no longer matches the source"
    for status, reason in emitted:
        assert reason in RESOLVE_REASONS[status], (status, reason)

    for decision in ("no_match", "abstain"):  # f"verifier_{decision}"; "match" resolves
        assert f"verifier_{decision}" in RESOLVE_REASONS["abstained"]
    assert "vector_search_unavailable" in RESOLVE_REASONS["abstained"]  # the resolver's default

    provider_reasons = set(re.findall(r'\.unavailable\(\s*"([a-z_]+)"', provider_src))
    assert len(provider_reasons) >= 5, "the scan found too few provider reasons"
    for reason in provider_reasons:
        assert reason in RESOLVE_REASONS["abstained"], reason


def test_resolve_profile_policy_field_is_last_and_defaulted() -> None:
    # Existing callers construct ResolveProfile positionally or by keyword
    # without the new field; it must stay optional.
    fields = dataclasses.fields(ResolveProfile)
    assert fields[-1].name == "on_unusable_value"
    assert fields[-1].default == "ignore"
