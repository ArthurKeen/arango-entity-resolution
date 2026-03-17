# Entity Resolution Advisor MCP Spec (Neutral)

Status: Draft  
Audience: Client applications integrating general-purpose entity resolution planning and analysis  
Namespace: `entity_resolution_advisor.*`

---

## 1) Scope

This spec defines a neutral MCP interface for helping client applications decide:

- which ER technique family to use
- which blocking candidates to prioritize
- which match features and weights to apply
- how to compare strategy variants before production rollout

The design is dataset- and domain-agnostic. It does not assume any specific project, schema, or vendor.

---

## 2) Protocol Conventions

### 2.1 JSON Schema Dialect

All schemas use JSON Schema Draft 2020-12.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema"
}
```

### 2.2 Request Envelope

MCP tool calls are logically treated as:

```json
{
  "tool": "entity_resolution_advisor.<name>",
  "arguments": {
    "...": "..."
  }
}
```

### 2.3 Standard Success Response Contract

All tools return:

```json
{
  "status": "ok",
  "tool_version": "1.0.0",
  "advisor_policy_version": "2026-03-01",
  "request_id": "uuid-or-client-id",
  "result": {}
}
```

### 2.4 Standard Error Response Contract

All tools return errors in this shape:

```json
{
  "status": "error",
  "tool_version": "1.0.0",
  "request_id": "uuid-or-client-id",
  "error": {
    "code": "INVALID_ARGUMENT | DATA_ACCESS_ERROR | NOT_ENOUGH_DATA | INTERNAL_ERROR",
    "message": "Human-readable message",
    "details": {}
  }
}
```

---

## 3) Shared Component Schemas

### 3.1 Objective Profile

```json
{
  "$id": "https://entity-resolution.dev/schemas/objective-profile.json",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "priority": {
      "type": "string",
      "enum": ["balanced", "precision_first", "recall_first", "throughput_first", "cost_first", "explainability_first"],
      "default": "balanced"
    },
    "latency_budget_ms": { "type": "number", "minimum": 0 },
    "throughput_target_rps": { "type": "number", "minimum": 0 },
    "max_memory_mb": { "type": "number", "minimum": 0 },
    "max_candidate_pairs": { "type": "integer", "minimum": 0 },
    "max_edge_count": { "type": "integer", "minimum": 0 }
  }
}
```

### 3.2 Data Source Reference

```json
{
  "$id": "https://entity-resolution.dev/schemas/data-source-ref.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["source_type", "dataset_id"],
  "properties": {
    "source_type": {
      "type": "string",
      "enum": ["collection", "table", "file", "view", "query"]
    },
    "dataset_id": { "type": "string", "minLength": 1 },
    "connection_ref": { "type": "string" },
    "query": { "type": "string" },
    "sample_limit": { "type": "integer", "minimum": 100, "default": 10000 }
  }
}
```

### 3.3 Confidence Object

```json
{
  "$id": "https://entity-resolution.dev/schemas/confidence.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["score"],
  "properties": {
    "score": { "type": "number", "minimum": 0, "maximum": 1 },
    "factors": { "type": "array", "items": { "type": "string" } }
  }
}
```

---

## 4) Tool Specifications

## 4.1 `entity_resolution_advisor.profile_dataset`

Profiles a dataset and returns field-level statistics useful for ER design.

### Request Schema

```json
{
  "$id": "https://entity-resolution.dev/schemas/tools/profile-dataset.request.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["data_source"],
  "properties": {
    "request_id": { "type": "string" },
    "data_source": { "$ref": "https://entity-resolution.dev/schemas/data-source-ref.json" },
    "include_fields": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    },
    "exclude_fields": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    },
    "compute_pairwise_signals": { "type": "boolean", "default": true }
  }
}
```

### Response `result` Schema

```json
{
  "profile_id": "profile_20260317_001",
  "row_count_estimate": 1200000,
  "field_profiles": [
    {
      "field": "name",
      "data_type": "string",
      "null_rate": 0.01,
      "distinct_count_estimate": 1100000,
      "entropy_estimate": 0.83,
      "heavy_hitters": [
        { "value": "unknown", "fraction": 0.02 }
      ],
      "token_stats": {
        "avg_token_count": 4.1,
        "avg_char_length": 23.8
      }
    }
  ],
  "pairwise_signals": {
    "near_duplicate_rate_estimate": 0.07,
    "hub_risk_score": 0.31
  }
}
```

---

## 4.2 `entity_resolution_advisor.recommend_resolution_strategy`

Recommends ranked ER strategy families based on profile and constraints.

### Request Schema

```json
{
  "$id": "https://entity-resolution.dev/schemas/tools/recommend-resolution-strategy.request.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["profile", "objective_profile"],
  "properties": {
    "request_id": { "type": "string" },
    "profile": { "type": "object" },
    "objective_profile": { "$ref": "https://entity-resolution.dev/schemas/objective-profile.json" },
    "allow_embedding_models": { "type": "boolean", "default": true },
    "allow_graph_clustering": { "type": "boolean", "default": true }
  }
}
```

### Response `result` Schema

```json
{
  "recommendations": [
    {
      "strategy_id": "pre_ingest_canonicalize_then_match",
      "rank": 1,
      "fit_score": 0.89,
      "expected_tradeoffs": {
        "precision": "high",
        "recall": "medium",
        "throughput": "high",
        "implementation_complexity": "medium"
      },
      "rationale": [
        "High duplication concentration indicates edge explosion risk",
        "Objective prioritizes throughput and bounded graph size"
      ],
      "confidence": {
        "score": 0.84,
        "factors": ["sample_size_sufficient", "field_entropy_strong"]
      }
    }
  ]
}
```

---

## 4.3 `entity_resolution_advisor.recommend_blocking_candidates`

Ranks blocking fields and composites with estimated candidate volume.

### Request Schema

```json
{
  "$id": "https://entity-resolution.dev/schemas/tools/recommend-blocking-candidates.request.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["profile"],
  "properties": {
    "request_id": { "type": "string" },
    "profile": { "type": "object" },
    "max_composite_size": { "type": "integer", "minimum": 1, "maximum": 5, "default": 3 },
    "max_results": { "type": "integer", "minimum": 1, "maximum": 100, "default": 20 },
    "must_include_fields": {
      "type": "array",
      "items": { "type": "string" }
    },
    "must_exclude_fields": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

### Response `result` Schema

```json
{
  "blocking_candidates": [
    {
      "candidate_id": "name_city_postal",
      "fields": ["name", "city", "postal_code"],
      "estimated_candidate_pairs": 4200000,
      "estimated_recall_proxy": 0.91,
      "estimated_precision_proxy": 0.63,
      "hub_risk_score": 0.22,
      "notes": ["Good entropy balance", "Low heavy-hitter concentration"]
    }
  ]
}
```

---

## 4.4 `entity_resolution_advisor.evaluate_blocking_plan`

Evaluates a user-proposed blocking plan before execution.

### Request Schema

```json
{
  "$id": "https://entity-resolution.dev/schemas/tools/evaluate-blocking-plan.request.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["profile", "blocking_plan"],
  "properties": {
    "request_id": { "type": "string" },
    "profile": { "type": "object" },
    "blocking_plan": {
      "type": "object",
      "additionalProperties": false,
      "required": ["fields"],
      "properties": {
        "fields": { "type": "array", "items": { "type": "string" }, "minItems": 1 },
        "min_block_size": { "type": "integer", "minimum": 1, "default": 2 },
        "max_block_size": { "type": "integer", "minimum": 2, "default": 1000 }
      }
    }
  }
}
```

### Response `result` Schema

```json
{
  "estimated_block_count": 180000,
  "estimated_candidate_pairs": 3900000,
  "estimated_block_size_distribution": {
    "p50": 3,
    "p90": 28,
    "p99": 410,
    "max_estimate": 22000
  },
  "risk_flags": [
    "heavy_hitter_blocks_detected",
    "edge_explosion_risk_high"
  ],
  "recommended_guardrails": {
    "suggested_max_block_size": 100,
    "suggested_min_block_size": 2
  }
}
```

---

## 4.5 `entity_resolution_advisor.recommend_match_features`

Recommends feature families and initial thresholds for matching.

### Request Schema

```json
{
  "$id": "https://entity-resolution.dev/schemas/tools/recommend-match-features.request.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["profile"],
  "properties": {
    "request_id": { "type": "string" },
    "profile": { "type": "object" },
    "feature_families_available": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["string_similarity", "phonetic", "geospatial", "embedding", "temporal", "graph"]
      }
    }
  }
}
```

### Response `result` Schema

```json
{
  "recommended_features": [
    {
      "feature_name": "name_jaro_winkler",
      "family": "string_similarity",
      "priority": 1,
      "default_weight": 0.35,
      "default_threshold_hint": 0.9
    }
  ],
  "fallback_features": [
    {
      "feature_name": "name_embedding_cosine",
      "family": "embedding",
      "priority": 3
    }
  ]
}
```

---

## 4.6 `entity_resolution_advisor.estimate_feature_weights`

Estimates field/feature weights from labels or weak supervision.

### Request Schema

```json
{
  "$id": "https://entity-resolution.dev/schemas/tools/estimate-feature-weights.request.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["feature_matrix_ref"],
  "properties": {
    "request_id": { "type": "string" },
    "feature_matrix_ref": {
      "type": "object",
      "required": ["dataset_id"],
      "properties": {
        "dataset_id": { "type": "string" },
        "label_mode": { "type": "string", "enum": ["gold_labels", "weak_labels", "pseudo_labels"] }
      }
    },
    "target_metric": { "type": "string", "enum": ["f1", "precision_at_recall", "recall_at_precision"], "default": "f1" },
    "min_samples": { "type": "integer", "minimum": 100, "default": 1000 }
  }
}
```

### Response `result` Schema

```json
{
  "weights": {
    "name_jaro_winkler": 0.42,
    "address_cosine": 0.31,
    "postal_exact": 0.27
  },
  "threshold_recommendation": {
    "match_threshold": 0.82,
    "review_band": [0.68, 0.82]
  },
  "diagnostics": {
    "samples_used": 12500,
    "target_metric_estimate": 0.87
  },
  "confidence": {
    "score": 0.79,
    "factors": ["label_coverage_good", "class_balance_moderate"]
  }
}
```

---

## 4.7 `entity_resolution_advisor.simulate_pipeline_variants`

Evaluates multiple candidate configurations and returns ranked outcomes.

### Request Schema

```json
{
  "$id": "https://entity-resolution.dev/schemas/tools/simulate-pipeline-variants.request.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["variants"],
  "properties": {
    "request_id": { "type": "string" },
    "variants": {
      "type": "array",
      "minItems": 2,
      "items": {
        "type": "object",
        "required": ["variant_id", "config"],
        "properties": {
          "variant_id": { "type": "string" },
          "config": { "type": "object" }
        }
      }
    },
    "objective_profile": { "$ref": "https://entity-resolution.dev/schemas/objective-profile.json" }
  }
}
```

### Response `result` Schema

```json
{
  "variant_results": [
    {
      "variant_id": "v1",
      "estimated_runtime_sec": 142.5,
      "estimated_peak_memory_mb": 980,
      "estimated_precision": 0.93,
      "estimated_recall": 0.88,
      "estimated_storage_mb": 540
    }
  ],
  "ranking": [
    { "variant_id": "v1", "rank": 1, "fit_score": 0.91 }
  ],
  "winner": {
    "variant_id": "v1",
    "reason": "Best objective fit under memory and edge-count constraints"
  }
}
```

---

## 4.8 `entity_resolution_advisor.export_recommended_config`

Exports a normalized config artifact for downstream execution.

### Request Schema

```json
{
  "$id": "https://entity-resolution.dev/schemas/tools/export-recommended-config.request.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["recommendation", "format"],
  "properties": {
    "request_id": { "type": "string" },
    "recommendation": { "type": "object" },
    "format": { "type": "string", "enum": ["json", "yaml"] },
    "include_rationale": { "type": "boolean", "default": true }
  }
}
```

### Response `result` Schema

```json
{
  "format": "yaml",
  "config_text": "entity_resolution:\\n  blocking:\\n    ...",
  "config_hash": "sha256:...",
  "policy_version": "2026-03-01"
}
```

---

## 5) Non-Functional Requirements

- Deterministic output for identical inputs when random seeds are fixed.
- Explicit confidence and uncertainty surfaced in recommendations.
- Stable `advisor_policy_version` returned on every tool call.
- No hidden writes unless a tool explicitly declares persistence side effects.

---

## 6) Backward Compatibility Rules

- Additive fields are allowed in responses.
- Existing fields must not change type.
- Breaking changes require:
  - new `tool_version`
  - migration note in release documentation.

---

## 7) Minimal Tool Set (MVP)

For first release, implement:

1. `profile_dataset`
2. `recommend_resolution_strategy`
3. `recommend_blocking_candidates`
4. `estimate_feature_weights`
5. `simulate_pipeline_variants`

Then add the rest incrementally.

