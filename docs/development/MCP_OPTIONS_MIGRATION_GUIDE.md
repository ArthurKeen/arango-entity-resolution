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

---

## FAQ

### Is this a breaking change?

No. Both legacy and `options` styles are currently accepted.

### What if both legacy and `options` are sent?

`options` wins for overlapping fields.

### Will legacy fields be removed?

Not in this phase. Removal, if any, will be announced with a versioned migration window.
