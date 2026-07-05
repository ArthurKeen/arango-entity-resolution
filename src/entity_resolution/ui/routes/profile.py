"""Data-profiling endpoint (plan 2.4).

Exposes ``FieldProfiler`` over HTTP: per-field detected type, completeness,
cardinality, and sample values, plus an optional emitted similarity config to
pre-fill the config builder.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _db(request: Request):
    return request.app.state.db


@router.get("/{collection}")
async def profile_collection(
    request: Request,
    collection: str,
    sample_size: int = Query(1000, ge=1, le=100000),
    emit_config: bool = False,
) -> Dict[str, Any]:
    """Profile a collection's fields; with ``emit_config`` also return a
    recommended similarity config (weights/transformers/priors)."""
    from entity_resolution.learning.field_profiler import FieldProfiler
    from entity_resolution.utils.validation import validate_collection_name

    try:
        validate_collection_name(collection)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db = _db(request)
    if not db.has_collection(collection):
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection}")

    profiler = FieldProfiler(db=db, collection=collection, sample_size=sample_size)
    result = profiler.profile()
    if emit_config:
        result["config"] = profiler.emit_similarity_config(result)
    return result
