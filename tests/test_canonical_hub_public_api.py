"""The canonical-hub resolver has one stable, public import path.

It used to be importable only as ``services.fabric_canonical_hub_resolver_wp13``,
a work-package name that reads as internal, and it was in no release, so a
consumer could neither import it with confidence nor pin a version
(arango-solutions-org/arango-entity-resolution#1). These tests pin the public
surface: removing a name, or breaking the deprecated alias before 3.10.0, fails
here first.
"""

from __future__ import annotations

import importlib
import inspect
import sys
import warnings

import pytest

import entity_resolution.canonical_hub as canonical_hub

PUBLIC = {
    # Shared checks, added for issue #4.
    "ORACLE_KEYS",
    "RESOLVE_REASONS",
    "RequestCheck",
    "check_request",
    "ArangoCanonicalHubVectorProvider",
    "CandidateSearchResult",
    "CanonicalCandidate",
    "Embedder",
    "FieldEvidence",
    "ResolveEvidence",
    "ResolveProfile",
    "ResolveRequest",
    "ResolveResult",
    "ResolveStatus",
    "SemanticCanonicalHubResolver",
    "UncertaintyVerifier",
    "VectorCandidateProvider",
    "VerifierDecision",
}


def test_public_names_are_exactly_the_documented_set() -> None:
    assert set(canonical_hub.__all__) == PUBLIC
    for name in PUBLIC:
        assert getattr(canonical_hub, name) is not None
        assert f"`{name}`" in canonical_hub.__doc__ or f":class:`{name}`" in canonical_hub.__doc__ \
            or f":data:`{name}`" in canonical_hub.__doc__, f"{name} is public but undocumented"


def test_the_consumer_contract_from_issue_1() -> None:
    # The exact import the consumer will switch to, and the request fields its
    # adapter passes.
    from entity_resolution.canonical_hub import ResolveRequest, SemanticCanonicalHubResolver

    params = set(inspect.signature(ResolveRequest).parameters)
    assert {"account_scope", "attributes", "deadline_at", "request_id"} <= params
    assert callable(SemanticCanonicalHubResolver.resolve)


@pytest.mark.parametrize(
    "old_module, name",
    [
        ("entity_resolution.services.fabric_canonical_hub_resolver_wp13", "SemanticCanonicalHubResolver"),
        ("entity_resolution.services.fabric_canonical_hub_resolver_wp13", "ResolveRequest"),
        ("entity_resolution.services.fabric_arango_vector_provider_wp13", "ArangoCanonicalHubVectorProvider"),
    ],
)
def test_deprecated_paths_still_work_and_say_so(old_module: str, name: str) -> None:
    sys.modules.pop(old_module, None)  # the warning fires on first import
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        module = importlib.import_module(old_module)
    assert getattr(module, name) is getattr(canonical_hub, name)
    messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
    assert any("entity_resolution.canonical_hub" in m and "3.10.0" in m for m in messages)


def test_the_new_path_does_not_warn() -> None:
    # In a fresh interpreter: evicting the package from this process's
    # sys.modules would give later tests a second copy of every class.
    import subprocess

    result = subprocess.run(
        # A -W module field must equal the module name exactly; filterwarnings
        # takes a regex, so it covers every entity_resolution submodule.
        [sys.executable, "-c",
         "import warnings; "
         "warnings.filterwarnings('error', category=DeprecationWarning, module=r'entity_resolution(\\.|$)'); "
         "import entity_resolution.canonical_hub"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr[-800:]
