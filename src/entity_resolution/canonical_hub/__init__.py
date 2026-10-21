"""Precision-first, read-only canonical-hub resolution.

Resolves one incoming record to an existing canonical entity, or abstains or
refuses with a stated reason, under an explicit precision and scope policy.
Embedding, candidate retrieval and uncertain-band verification are injected, so
the safety contract can be tested without a model or a database.

Public API
----------
Everything named in ``__all__`` is public and follows semantic versioning:
a removal or incompatible change happens only in a major release, with a
deprecation warning first.

* Resolver: :class:`SemanticCanonicalHubResolver`
* Contract types: :class:`ResolveRequest`, :class:`ResolveResult`,
  :class:`ResolveEvidence`, :class:`FieldEvidence`, :class:`ResolveProfile`,
  and the :data:`ResolveStatus` literal (``"resolved"``, ``"abstained"``,
  ``"refused"``)
* Extension points, for supplying your own backends:
  :class:`Embedder`, :class:`VectorCandidateProvider`,
  :class:`UncertaintyVerifier`, and the values they exchange,
  :class:`CanonicalCandidate`, :class:`CandidateSearchResult` and
  :class:`VerifierDecision`
* An ArangoDB backend: :class:`ArangoCanonicalHubVectorProvider`, native
  vector index only, with no exact or Python fallback

Anything else, including the submodules' underscore-prefixed names, is
internal and may change in any release.

Until 3.9.0 this lived in ``entity_resolution.services.fabric_canonical_hub_resolver_wp13``
and ``entity_resolution.services.fabric_arango_vector_provider_wp13``. Those
paths still work in 3.9.x, with a ``DeprecationWarning``, and are removed in
3.10.0.
"""

from .arango_vector_provider import ArangoCanonicalHubVectorProvider
from .resolver import (
    CandidateSearchResult,
    CanonicalCandidate,
    Embedder,
    FieldEvidence,
    ResolveEvidence,
    ResolveProfile,
    ResolveRequest,
    ResolveResult,
    ResolveStatus,
    SemanticCanonicalHubResolver,
    UncertaintyVerifier,
    VectorCandidateProvider,
    VerifierDecision,
)

__all__ = [
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
]
