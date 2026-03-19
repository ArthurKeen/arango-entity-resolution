"""Unit tests for MCP request normalization contracts."""

from __future__ import annotations

import pytest

from entity_resolution.mcp.normalization import (
    normalize_advisor_context,
    normalize_cross_collection_args,
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


# ---------------------------------------------------------------------------
# normalize_cross_collection_args
# ---------------------------------------------------------------------------


def test_normalize_cross_collection_positional_fields():
    req = normalize_cross_collection_args(
        source_collection="registrations",
        target_collection="companies",
        source_fields=["company_name", "city"],
        target_fields=["legal_name", "location_city"],
    )

    assert req.source_collection == "registrations"
    assert req.target_collection == "companies"
    assert req.source_fields == {"company_name": "company_name", "city": "city"}
    assert req.target_fields == {"company_name": "legal_name", "city": "location_city"}
    assert req.confidence_threshold == 0.85
    assert req.candidate_limit == 1000
    assert req.batch_size == 100
    assert req.max_runtime_ms == 300000
    assert req.deterministic_tiebreak is True
    assert req.blocking_fields == ["company_name"]
    assert req.edge_collection == "registrations_companies_resolved_edges"
    assert req.deprecation_warnings == []
    assert abs(sum(req.field_weights.values()) - 1.0) < 0.01


def test_normalize_cross_collection_field_mapping_overrides_positional():
    req = normalize_cross_collection_args(
        source_collection="regs",
        target_collection="duns",
        source_fields=["name"],
        target_fields=["legal_name"],
        options={
            "retrieval": {
                "field_mapping": {
                    "company": {"source": "BR_Name", "target": "DUNS_NAME"},
                    "address": {"source": "ADDRESS", "target": "ADDR_STREET"},
                },
                "candidate_limit": 500,
            },
            "similarity": {"confidence_threshold": 0.92},
            "blocking": {"fields": ["company"], "strategy": "exact"},
            "execution": {"batch_size": 25, "max_runtime_ms": 60000},
            "clustering": {"edge_collection": "custom_edges"},
        },
    )

    assert req.source_fields == {"company": "BR_Name", "address": "ADDRESS"}
    assert req.target_fields == {"company": "DUNS_NAME", "address": "ADDR_STREET"}
    assert req.confidence_threshold == 0.92
    assert req.candidate_limit == 500
    assert req.batch_size == 25
    assert req.max_runtime_ms == 60000
    assert req.blocking_fields == ["company"]
    assert req.edge_collection == "custom_edges"
    assert len(req.deprecation_warnings) >= 1
    assert any("field_mapping" in w for w in req.deprecation_warnings)


def test_normalize_cross_collection_rejects_length_mismatch():
    with pytest.raises(ValueError, match="same length"):
        normalize_cross_collection_args(
            source_collection="a",
            target_collection="b",
            source_fields=["x"],
            target_fields=["y", "z"],
        )


def test_normalize_cross_collection_rejects_empty_mapping_value():
    with pytest.raises(ValueError, match="non-empty source and target"):
        normalize_cross_collection_args(
            source_collection="a",
            target_collection="b",
            source_fields=[],
            target_fields=[],
            options={
                "retrieval": {
                    "field_mapping": {
                        "name": {"source": "x", "target": ""},
                    }
                }
            },
        )


def test_normalize_cross_collection_filters():
    req = normalize_cross_collection_args(
        source_collection="regs",
        target_collection="companies",
        source_fields=["name"],
        target_fields=["name"],
        options={
            "retrieval": {
                "target_filter": {"status": {"equals": "active"}},
                "source_skip_values": {"name": ["UNKNOWN", "N/A"]},
            }
        },
    )

    assert req.target_filter == {"status": {"equals": "active"}}
    assert req.source_skip_values == {"name": ["UNKNOWN", "N/A"]}
