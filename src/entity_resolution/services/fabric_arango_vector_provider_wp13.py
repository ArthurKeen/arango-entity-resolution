"""Read-only ArangoDB vector candidates for the fabric canonical hub."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from entity_resolution.utils.validation import (
    validate_collection_name,
    validate_field_name,
)

from .fabric_canonical_hub_resolver_wp13 import (
    CandidateSearchResult,
    CanonicalCandidate,
)


class ArangoCanonicalHubVectorProvider:
    """Native-vector-only candidate provider with query and result scoping.

    Missing vector capability is represented as an unavailable search result.
    There is deliberately no exact, collection-scan, or Python cosine fallback.
    """

    def __init__(
        self,
        database: Any,
        *,
        collection: str,
        vector_field: str,
        vector_index: str,
        canonical_id_field: str,
        account_scope_field: str,
        observable_fields: Sequence[str],
        maximum_top_k: int = 50,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.database = database
        self.collection = validate_collection_name(collection)
        self.vector_field = validate_field_name(vector_field, allow_nested=False)
        self.vector_index = validate_field_name(vector_index, allow_nested=False)
        self.canonical_id_field = validate_field_name(
            canonical_id_field,
            allow_nested=False,
        )
        self.account_scope_field = validate_field_name(
            account_scope_field,
            allow_nested=False,
        )
        self.observable_fields = tuple(
            validate_field_name(field, allow_nested=False) for field in observable_fields
        )
        if not self.observable_fields or len(set(self.observable_fields)) != len(
            self.observable_fields
        ):
            raise ValueError("observable_fields must be non-empty and unique")
        if maximum_top_k < 2 or maximum_top_k > 100:
            raise ValueError("maximum_top_k must be between 2 and 100")
        self.maximum_top_k = maximum_top_k
        self._clock = clock

    def search(
        self,
        vector: Sequence[float],
        *,
        account_scope: str,
        top_k: int,
        deadline_at: float,
    ) -> CandidateSearchResult:
        if not account_scope.strip():
            return CandidateSearchResult.unavailable("account_scope_required")
        if self._clock() >= deadline_at:
            return CandidateSearchResult.unavailable("deadline_exceeded")
        if not vector or any(not math.isfinite(float(value)) for value in vector):
            return CandidateSearchResult.unavailable("query_vector_invalid")
        bounded_top_k = min(max(int(top_k), 2), self.maximum_top_k)

        try:
            indexes = self.database.collection(self.collection).indexes()
        except Exception:
            return CandidateSearchResult.unavailable("vector_capability_check_failed")
        if not any(self._matches_configured_index(index) for index in indexes):
            return CandidateSearchResult.unavailable("configured_vector_index_unavailable")

        query = f"""
        FOR candidate IN @@collection
            FILTER candidate.{self.account_scope_field} == @account_scope
            LET vector_score = APPROX_NEAR_COSINE(
                candidate.{self.vector_field},
                @query_vector
            )
            SORT vector_score DESC
            LIMIT @top_k
            RETURN {{
                canonical_id: candidate.{self.canonical_id_field},
                account_scope: candidate.{self.account_scope_field},
                fields: KEEP(candidate, @observable_fields),
                vector_score: vector_score
            }}
        """
        bind_vars = {
            "@collection": self.collection,
            "account_scope": account_scope,
            "query_vector": [float(value) for value in vector],
            "top_k": bounded_top_k,
            "observable_fields": list(self.observable_fields),
        }
        remaining = deadline_at - self._clock()
        if remaining <= 0:
            return CandidateSearchResult.unavailable("deadline_exceeded")
        try:
            rows = list(
                self.database.aql.execute(
                    query,
                    bind_vars=bind_vars,
                    max_runtime=max(0.001, remaining),
                )
            )
        except Exception as exc:
            return CandidateSearchResult.unavailable(
                f"vector_search_unavailable:{type(exc).__name__}"
            )
        if self._clock() >= deadline_at:
            return CandidateSearchResult.unavailable("deadline_exceeded")

        candidates: list[CanonicalCandidate] = []
        for row in rows[:bounded_top_k]:
            if not isinstance(row, Mapping):
                return CandidateSearchResult.unavailable("candidate_payload_invalid")
            fields = row.get("fields")
            if not isinstance(fields, Mapping):
                return CandidateSearchResult.unavailable("candidate_payload_invalid")
            candidates.append(
                CanonicalCandidate(
                    canonical_id=(
                        str(row["canonical_id"]) if row.get("canonical_id") is not None else None
                    ),
                    account_scope=str(row.get("account_scope", "")),
                    fields=fields,
                    vector_score=float(row.get("vector_score", math.nan)),
                )
            )
        return CandidateSearchResult(candidates=tuple(candidates))

    def _matches_configured_index(self, index: Mapping[str, Any]) -> bool:
        index_id = str(index.get("id", "")).rsplit("/", 1)[-1]
        index_name = str(index.get("name", ""))
        return (
            index.get("type") == "vector"
            and self.vector_field in (index.get("fields") or ())
            and self.vector_index in {index_id, index_name}
        )
