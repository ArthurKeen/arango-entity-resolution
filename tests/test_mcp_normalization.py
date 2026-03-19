"""Unit tests for MCP request normalization contracts."""

from __future__ import annotations

import pytest

from entity_resolution.mcp.normalization import (
    normalize_advisor_context,
    normalize_find_duplicates_args,
    normalize_resolve_entity_args,
)


def test_normalize_find_duplicates_legacy_only():
    req = normalize_find_duplicates_args(
        collection="companies",
        fields=["name", "city"],
        strategy="bm25",
        confidence_threshold=0.9,
        max_block_size=120,
        store_clusters=False,
    )

    assert req.collection == "companies"
    assert req.fields == ["name", "city"]
    assert req.strategy == "bm25"
    assert req.confidence_threshold == 0.9
    assert req.max_block_size == 120
    assert req.store_clusters is False
    assert req.deprecation_warnings == []


def test_normalize_find_duplicates_options_override_legacy_with_warning():
    req = normalize_find_duplicates_args(
        collection="companies",
        fields=["name"],
        strategy="exact",
        confidence_threshold=0.8,
        max_block_size=200,
        options={
            "blocking": {"strategy": "bm25", "max_block_size": 80, "fields": ["name", "postal_code"]},
            "similarity": {"confidence_threshold": 0.91},
            "active_learning": {"enabled": True, "refresh_every": 7},
        },
    )

    assert req.strategy == "bm25"
    assert req.max_block_size == 80
    assert req.fields == ["name", "postal_code"]
    assert req.confidence_threshold == 0.91
    assert req.enable_active_learning is True
    assert req.active_learning_refresh_every == 7
    assert len(req.deprecation_warnings) >= 1


def test_normalize_resolve_entity_options_override():
    req = normalize_resolve_entity_args(
        collection="companies",
        record={"name": "Acme"},
        fields=["name"],
        confidence_threshold=0.75,
        top_k=5,
        options={
            "retrieval": {"fields": ["name", "aliases"], "top_k": 3},
            "similarity": {"confidence_threshold": 0.85},
        },
    )

    assert req.fields == ["name", "aliases"]
    assert req.top_k == 3
    assert req.confidence_threshold == 0.85
    assert len(req.deprecation_warnings) >= 1


def test_normalize_advisor_context_preserves_request_id_and_options():
    ctx = normalize_advisor_context(
        request_id="req-123",
        options={"diagnostics": {"include_warnings": True}},
    )
    assert ctx.request_id == "req-123"
    assert ctx.options.diagnostics["include_warnings"] is True
    assert ctx.deprecation_warnings == []


def test_normalize_options_rejects_non_dict():
    with pytest.raises(ValueError, match="options must be an object/dict"):
        normalize_find_duplicates_args(
            collection="companies",
            fields=["name"],
            options="bad",  # type: ignore[arg-type]
        )


def test_normalize_options_rejects_non_dict_blocks():
    with pytest.raises(ValueError, match="options\\.blocking must be an object/dict"):
        normalize_find_duplicates_args(
            collection="companies",
            fields=["name"],
            options={"blocking": ["bad"]},
        )
