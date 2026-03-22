# MCP Options Migration Guide

Status: active  
Audience: callers of `arango-er-mcp` tools migrating from legacy top-level args

---

## Why this migration exists

MCP tool signatures grew over time with many top-level parameters. The `options`
model keeps signatures stable while allowing additive feature growth.

During migration, both styles are supported:

- legacy top-level args (existing behavior)
- `options` blocks (new canonical shape)

When both are present for the same concern, `options` wins.

---

## Compatibility Policy

- Backward compatibility is preserved in this phase.
- Legacy fields continue to work.
- Conflicting values may produce `deprecation_warnings` in tool responses where
  the tool already returns an object (`dict`) payload.
- For tools returning arrays (e.g. `resolve_entity`), warnings are logged server-side.

---

## Canonical `options` blocks

Supported blocks:

- `blocking`
- `similarity`
- `clustering`
- `active_learning`
- `retrieval`
- `gating`
- `aliasing`
- `diagnostics`
- `execution`

Unknown blocks are retained in passthrough for forward compatibility.

---

## Migration Examples

### `find_duplicates`: legacy -> options

Legacy:

```json
{
  "collection": "companies",
  "fields": ["name", "city"],
  "strategy": "bm25",
  "confidence_threshold": 0.9,
  "max_block_size": 120,
  "store_clusters": false
}
```

Options style:

```json
{
  "collection": "companies",
  "fields": ["name", "city"],
  "options": {
    "blocking": {
      "strategy": "bm25",
      "fields": ["name", "city"],
      "max_block_size": 120
    },
    "similarity": {
      "confidence_threshold": 0.9
    },
    "clustering": {
      "store_clusters": false
    }
  }
}
```

### `resolve_entity`: legacy -> options

Legacy:

```json
{
  "collection": "companies",
  "record": {"name": "Acme"},
  "fields": ["name"],
  "confidence_threshold": 0.8,
  "top_k": 5
}
```

Options style:

```json
{
  "collection": "companies",
  "record": {"name": "Acme"},
  "fields": ["name"],
  "options": {
    "retrieval": {
      "fields": ["name"],
      "top_k": 5
    },
    "similarity": {
      "confidence_threshold": 0.8
    }
  }
}
```

---

## Field Mapping Reference

### `find_duplicates`

- `strategy` -> `options.blocking.strategy`
- `fields` -> `options.blocking.fields`
- `max_block_size` -> `options.blocking.max_block_size`
- `confidence_threshold` -> `options.similarity.confidence_threshold`
- `store_clusters` -> `options.clustering.store_clusters`
- `edge_collection` -> `options.clustering.edge_collection`
- `enable_active_learning` -> `options.active_learning.enabled`
- `feedback_collection` -> `options.active_learning.feedback_collection`
- `active_learning_refresh_every` -> `options.active_learning.refresh_every`
- `active_learning_model` -> `options.active_learning.model`
- `active_learning_low_threshold` -> `options.active_learning.low_threshold`
- `active_learning_high_threshold` -> `options.active_learning.high_threshold`
- `gating.mode` -> `options.gating.mode` (`enforce` | `report_only` | `shadow`)
- `similarity.type` -> `options.similarity.type` (e.g. `token_jaccard`)
- `similarity.token_jaccard_fields` -> `options.similarity.token_jaccard_fields`
- `similarity.token_jaccard_min_score` -> `options.similarity.token_jaccard_min_score`
- `aliasing.sources[].type=managed_ref` with dictionary payload in `options.aliasing.managed_refs`

### `resolve_entity`

- `fields` -> `options.retrieval.fields`
- `top_k` -> `options.retrieval.top_k`
- `confidence_threshold` -> `options.similarity.confidence_threshold`

---

## Recommended Client Strategy

1. Continue sending current payloads if needed.
2. Move new feature flags/config to `options` first.
3. Migrate all mapped legacy fields to `options`.
4. Treat `deprecation_warnings` as migration TODOs.
5. Persist `er_options_schema_version` from dict/envelope responses and reject unexpected versions.

---

## New Rollout + Aliasing Controls

### Gating Rollout Modes

`find_duplicates` supports a rollout-safe gate mode:

```json
{
  "options": {
    "gating": {
      "mode": "report_only"
    }
  }
}
```

Allowed values:

- `enforce` - gate failures reject candidates
- `report_only` - gate failures are counted in diagnostics only
- `shadow` - alias of report-only semantics for phased rollout

In `report_only`/`shadow`, diagnostics include `would_reject_*` counters.

### Managed Alias References

To use server-managed alias dictionaries:

```json
{
  "options": {
    "aliasing": {
      "sources": [
        { "type": "managed_ref", "ref": "entity_aliases_v1" }
      ],
      "managed_refs": {
        "entity_aliases_v1": {
          "ibm": ["international", "business", "machines"]
        }
      }
    }
  }
}
```

`managed_refs` are applied in token-expansion paths for `find_duplicates` gates and `explain_match` diagnostics.
Gate diagnostics now also surface:

- `similarity.gates.aliasing.managed_ref_requested`: all refs requested by `aliasing.sources`
- `similarity.gates.aliasing.managed_ref_applied`: configured refs successfully resolved
- `similarity.gates.aliasing.managed_ref_missing`: configured refs with no backing dictionary

Equivalent aliasing diagnostics are included in `explain_match` under
`gates.aliasing.{managed_ref_requested,managed_ref_applied,managed_ref_missing}`.

---

## Response Versioning

Dict/envelope responses now include:

```json
{
  "er_options_schema_version": "1.0"
}
```

Use this field for compatibility checks as option contracts evolve.

---

## FAQ

### Is this a breaking change?

No. Both legacy and `options` styles are currently accepted.

### What if both legacy and `options` are sent?

`options` wins for overlapping fields.

### Will legacy fields be removed?

Not in this phase. Removal, if any, will be announced with a versioned migration window.
