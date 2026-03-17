# Entity Resolution Advisor MCP Examples

Companion to: `docs/development/ENTITY_RESOLUTION_ADVISOR_MCP_SPEC.md`

This document provides concrete example calls and responses for each
`entity_resolution_advisor.*` tool.

---

## 1) Conventions

All calls are shown in logical envelope form:

```json
{
  "tool": "entity_resolution_advisor.<name>",
  "arguments": {}
}
```

Successful responses:

```json
{
  "status": "ok",
  "tool_version": "1.0.0",
  "advisor_policy_version": "2026-03-01",
  "request_id": "req-123",
  "result": {}
}
```

Error responses:

```json
{
  "status": "error",
  "tool_version": "1.0.0",
  "request_id": "req-123",
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "Human-readable message",
    "details": {}
  }
}
```

---

## 2) `profile_dataset`

### Example Request

```json
{
  "tool": "entity_resolution_advisor.profile_dataset",
  "arguments": {
    "request_id": "req-profile-001",
    "data_source": {
      "source_type": "collection",
      "dataset_id": "customers_v1",
      "connection_ref": "prod_warehouse",
      "sample_limit": 50000
    },
    "exclude_fields": ["raw_blob"],
    "compute_pairwise_signals": true
  }
}
```

### Example Response

```json
{
  "status": "ok",
  "tool_version": "1.0.0",
  "advisor_policy_version": "2026-03-01",
  "request_id": "req-profile-001",
  "result": {
    "profile_id": "profile_customers_v1_20260317",
    "row_count_estimate": 1245023,
    "field_profiles": [
      {
        "field": "full_name",
        "data_type": "string",
        "null_rate": 0.002,
        "distinct_count_estimate": 1204112,
        "entropy_estimate": 0.92,
        "heavy_hitters": [{"value": "unknown", "fraction": 0.004}],
        "token_stats": {"avg_token_count": 3.4, "avg_char_length": 19.2}
      },
      {
        "field": "postal_code",
        "data_type": "string",
        "null_rate": 0.015,
        "distinct_count_estimate": 32211,
        "entropy_estimate": 0.63,
        "heavy_hitters": [{"value": "00000", "fraction": 0.009}],
        "token_stats": {"avg_token_count": 1.0, "avg_char_length": 5.0}
      }
    ],
    "pairwise_signals": {
      "near_duplicate_rate_estimate": 0.083,
      "hub_risk_score": 0.29
    }
  }
}
```

---

## 3) `recommend_resolution_strategy`

### Example Request

```json
{
  "tool": "entity_resolution_advisor.recommend_resolution_strategy",
  "arguments": {
    "request_id": "req-strategy-001",
    "profile": {
      "profile_id": "profile_customers_v1_20260317",
      "pairwise_signals": {
        "near_duplicate_rate_estimate": 0.083,
        "hub_risk_score": 0.29
      }
    },
    "objective_profile": {
      "priority": "balanced",
      "latency_budget_ms": 250,
      "max_edge_count": 4000000
    },
    "allow_embedding_models": true,
    "allow_graph_clustering": true
  }
}
```

### Example Response

```json
{
  "status": "ok",
  "tool_version": "1.0.0",
  "advisor_policy_version": "2026-03-01",
  "request_id": "req-strategy-001",
  "result": {
    "recommendations": [
      {
        "strategy_id": "hybrid_block_then_weighted_match",
        "rank": 1,
        "fit_score": 0.9,
        "expected_tradeoffs": {
          "precision": "high",
          "recall": "medium_high",
          "throughput": "high",
          "implementation_complexity": "medium"
        },
        "rationale": [
          "High duplicate signal supports aggressive candidate pruning",
          "Edge budget indicates bounded graph output is important"
        ],
        "confidence": {
          "score": 0.84,
          "factors": ["sample_size_sufficient", "field_entropy_strong"]
        }
      },
      {
        "strategy_id": "embedding_first_nearest_neighbor",
        "rank": 2,
        "fit_score": 0.73,
        "expected_tradeoffs": {
          "precision": "medium_high",
          "recall": "high",
          "throughput": "medium",
          "implementation_complexity": "medium_high"
        },
        "rationale": [
          "Better semantic recall for noisy strings",
          "May exceed latency budget at current scale"
        ],
        "confidence": {
          "score": 0.66,
          "factors": ["insufficient_embedding_baseline_history"]
        }
      }
    ]
  }
}
```

---

## 4) `recommend_blocking_candidates`

### Example Request

```json
{
  "tool": "entity_resolution_advisor.recommend_blocking_candidates",
  "arguments": {
    "request_id": "req-blocking-001",
    "profile": {
      "profile_id": "profile_customers_v1_20260317"
    },
    "max_composite_size": 3,
    "max_results": 5,
    "must_exclude_fields": ["notes", "description"]
  }
}
```

### Example Response

```json
{
  "status": "ok",
  "tool_version": "1.0.0",
  "advisor_policy_version": "2026-03-01",
  "request_id": "req-blocking-001",
  "result": {
    "blocking_candidates": [
      {
        "candidate_id": "full_name_postal",
        "fields": ["full_name", "postal_code"],
        "estimated_candidate_pairs": 5100000,
        "estimated_recall_proxy": 0.9,
        "estimated_precision_proxy": 0.57,
        "hub_risk_score": 0.21,
        "notes": ["Good balance", "Watch heavy-hitter postal values"]
      },
      {
        "candidate_id": "email_domain_phone_prefix",
        "fields": ["email_domain", "phone_prefix"],
        "estimated_candidate_pairs": 2200000,
        "estimated_recall_proxy": 0.78,
        "estimated_precision_proxy": 0.73,
        "hub_risk_score": 0.14,
        "notes": ["Lower pair volume", "Potential recall loss for missing phone"]
      }
    ]
  }
}
```

---

## 5) `evaluate_blocking_plan`

### Example Request

```json
{
  "tool": "entity_resolution_advisor.evaluate_blocking_plan",
  "arguments": {
    "request_id": "req-eval-blocking-001",
    "profile": {
      "profile_id": "profile_customers_v1_20260317"
    },
    "blocking_plan": {
      "fields": ["full_name", "postal_code"],
      "min_block_size": 2,
      "max_block_size": 100
    }
  }
}
```

### Example Response

```json
{
  "status": "ok",
  "tool_version": "1.0.0",
  "advisor_policy_version": "2026-03-01",
  "request_id": "req-eval-blocking-001",
  "result": {
    "estimated_block_count": 205331,
    "estimated_candidate_pairs": 3880142,
    "estimated_block_size_distribution": {
      "p50": 3,
      "p90": 24,
      "p99": 161,
      "max_estimate": 2440
    },
    "risk_flags": ["heavy_hitter_blocks_detected"],
    "recommended_guardrails": {
      "suggested_max_block_size": 80,
      "suggested_min_block_size": 2
    }
  }
}
```

---

## 6) `recommend_match_features`

### Example Request

```json
{
  "tool": "entity_resolution_advisor.recommend_match_features",
  "arguments": {
    "request_id": "req-features-001",
    "profile": {
      "profile_id": "profile_customers_v1_20260317"
    },
    "feature_families_available": [
      "string_similarity",
      "embedding",
      "geospatial"
    ]
  }
}
```

### Example Response

```json
{
  "status": "ok",
  "tool_version": "1.0.0",
  "advisor_policy_version": "2026-03-01",
  "request_id": "req-features-001",
  "result": {
    "recommended_features": [
      {
        "feature_name": "full_name_jaro_winkler",
        "family": "string_similarity",
        "priority": 1,
        "default_weight": 0.34,
        "default_threshold_hint": 0.9
      },
      {
        "feature_name": "street_cosine_embedding",
        "family": "embedding",
        "priority": 2,
        "default_weight": 0.27,
        "default_threshold_hint": 0.82
      }
    ],
    "fallback_features": [
      {
        "feature_name": "geo_distance_km",
        "family": "geospatial",
        "priority": 4
      }
    ]
  }
}
```

---

## 7) `estimate_feature_weights`

### Example Request

```json
{
  "tool": "entity_resolution_advisor.estimate_feature_weights",
  "arguments": {
    "request_id": "req-weights-001",
    "feature_matrix_ref": {
      "dataset_id": "pair_features_20260317",
      "label_mode": "gold_labels"
    },
    "target_metric": "f1",
    "min_samples": 5000
  }
}
```

### Example Response

```json
{
  "status": "ok",
  "tool_version": "1.0.0",
  "advisor_policy_version": "2026-03-01",
  "request_id": "req-weights-001",
  "result": {
    "weights": {
      "full_name_jaro_winkler": 0.4,
      "street_cosine_embedding": 0.26,
      "postal_exact": 0.2,
      "city_jaccard": 0.14
    },
    "threshold_recommendation": {
      "match_threshold": 0.81,
      "review_band": [0.69, 0.81]
    },
    "diagnostics": {
      "samples_used": 18422,
      "target_metric_estimate": 0.886
    },
    "confidence": {
      "score": 0.8,
      "factors": ["sample_size_good", "label_noise_low"]
    }
  }
}
```

---

## 8) `simulate_pipeline_variants`

### Example Request

```json
{
  "tool": "entity_resolution_advisor.simulate_pipeline_variants",
  "arguments": {
    "request_id": "req-sim-001",
    "objective_profile": {
      "priority": "throughput_first",
      "max_memory_mb": 2048,
      "max_edge_count": 5000000
    },
    "variants": [
      {
        "variant_id": "v_blocking_strict",
        "config": {
          "blocking": {"fields": ["full_name", "postal_code"], "max_block_size": 80},
          "matching": {"threshold": 0.84}
        }
      },
      {
        "variant_id": "v_blocking_relaxed",
        "config": {
          "blocking": {"fields": ["full_name", "city"], "max_block_size": 200},
          "matching": {"threshold": 0.8}
        }
      }
    ]
  }
}
```

### Example Response

```json
{
  "status": "ok",
  "tool_version": "1.0.0",
  "advisor_policy_version": "2026-03-01",
  "request_id": "req-sim-001",
  "result": {
    "variant_results": [
      {
        "variant_id": "v_blocking_strict",
        "estimated_runtime_sec": 141.2,
        "estimated_peak_memory_mb": 1120,
        "estimated_precision": 0.94,
        "estimated_recall": 0.83,
        "estimated_storage_mb": 420
      },
      {
        "variant_id": "v_blocking_relaxed",
        "estimated_runtime_sec": 248.9,
        "estimated_peak_memory_mb": 1784,
        "estimated_precision": 0.9,
        "estimated_recall": 0.89,
        "estimated_storage_mb": 760
      }
    ],
    "ranking": [
      {"variant_id": "v_blocking_strict", "rank": 1, "fit_score": 0.91},
      {"variant_id": "v_blocking_relaxed", "rank": 2, "fit_score": 0.73}
    ],
    "winner": {
      "variant_id": "v_blocking_strict",
      "reason": "Meets throughput and memory constraints with higher fit score"
    }
  }
}
```

---

## 9) `export_recommended_config`

### Example Request

```json
{
  "tool": "entity_resolution_advisor.export_recommended_config",
  "arguments": {
    "request_id": "req-export-001",
    "format": "yaml",
    "include_rationale": true,
    "recommendation": {
      "strategy_id": "hybrid_block_then_weighted_match",
      "blocking": {"fields": ["full_name", "postal_code"], "max_block_size": 80},
      "matching": {"weights": {"full_name_jaro_winkler": 0.4, "postal_exact": 0.2}}
    }
  }
}
```

### Example Response

```json
{
  "status": "ok",
  "tool_version": "1.0.0",
  "advisor_policy_version": "2026-03-01",
  "request_id": "req-export-001",
  "result": {
    "format": "yaml",
    "config_text": "entity_resolution:\\n  strategy: hybrid_block_then_weighted_match\\n  ...",
    "config_hash": "sha256:de6f6cb2...",
    "policy_version": "2026-03-01"
  }
}
```

---

## 10) Example Error Cases

### 10.1 Invalid Field in Blocking Plan

```json
{
  "status": "error",
  "tool_version": "1.0.0",
  "request_id": "req-eval-blocking-002",
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "Unknown field 'postalcode' in blocking_plan.fields",
    "details": {
      "unknown_fields": ["postalcode"],
      "suggestions": ["postal_code"]
    }
  }
}
```

### 10.2 Insufficient Labels for Weight Estimation

```json
{
  "status": "error",
  "tool_version": "1.0.0",
  "request_id": "req-weights-003",
  "error": {
    "code": "NOT_ENOUGH_DATA",
    "message": "Minimum sample requirement not met",
    "details": {
      "samples_found": 640,
      "min_samples": 5000
    }
  }
}
```

---

## 11) Client Integration Checklist

- Persist `request_id` and `advisor_policy_version` for auditability.
- Store full recommendation payloads, not just winner IDs.
- Re-run `profile_dataset` after material schema/data shifts.
- Keep objective constraints explicit in each advisory request.
- Re-baseline recommendation outputs on major tool version changes.

