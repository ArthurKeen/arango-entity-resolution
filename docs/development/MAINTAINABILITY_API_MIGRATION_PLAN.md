# MCP API Maintainability Migration Plan

Status: proposed  
Owner: entity-resolution maintainability pass  
Scope: `src/entity_resolution/mcp/**`, bridge to pipeline/entity tools

---

## Goal

Reduce API drift and parameter sprawl by introducing a canonical `options`-based
request shape for MCP tools while preserving backward compatibility for existing
callers.

---

## Why Now

- MCP tool signatures have grown quickly with feature additions.
- Validation/parsing is duplicated across tools.
- New ER capabilities (cross-collection, multi-stage, gating) will add more knobs.
- We control most dependents, so migration cost is low relative to long-term gain.

---

## Migration Principles

1. Keep existing top-level parameters functional during migration.
2. Introduce a canonical normalized contract used internally by handlers.
3. Resolve conflicts predictably (`options` overrides legacy args).
4. Emit deprecation warnings in responses/logs for overlapping legacy usage.
5. Add parity tests to prove legacy and `options` payloads behave identically.

---

## Phases

### Phase 0 — Safety Rails (no behavior change)

- Add this migration plan.
- Add compatibility/deprecation policy for MCP tools.
- Add placeholder telemetry counters for legacy-overlap usage.

### Phase 1 — Contracts + Normalization (no behavior change)

- Add typed MCP request contracts (`contracts.py`).
- Add normalization helpers (`normalization.py`) that:
  - parse `options`
  - merge with legacy args
  - generate deprecation/conflict warnings
- Add dedicated tests for normalizers.

### Phase 2 — Server Signature Modernization (backward compatible)

- Add `options: Dict[str, Any] | None` to selected MCP tools:
  - `find_duplicates`
  - `resolve_entity`
  - advisor tools over time
- Keep existing params and route through normalizers.

### Phase 3 — Handler Refactor

- Convert pipeline/entity/advisor handlers to consume normalized contracts.
- Centralize error envelopes and validation behavior.

### Phase 4 — Migration & Deprecation

- Publish migration guide with copy/paste examples.
- Begin soft deprecation warnings for legacy top-level params.
- Keep removal out of current release train.

---

## Canonical Shape (target)

```json
{
  "collection": "companies",
  "fields": ["name", "address"],
  "options": {
    "blocking": { "strategy": "bm25", "max_block_size": 500 },
    "similarity": { "confidence_threshold": 0.85 },
    "clustering": { "store_clusters": true, "edge_collection": "companies_similarity_edges" },
    "active_learning": {
      "enabled": false,
      "feedback_collection": null,
      "refresh_every": 100,
      "model": null,
      "low_threshold": 0.55,
      "high_threshold": 0.80
    },
    "diagnostics": { "include_warnings": true }
  }
}
```

---

## Compatibility Policy

- During migration:
  - legacy top-level args are accepted
  - `options` is accepted
  - if both specify the same value, `options` wins
- Responses may include:
  - `deprecation_warnings` for overlapping legacy/`options` fields
- No breaking signature removals in this pass.

---

## Test Requirements

- Unit tests for normalization:
  - legacy-only payload
  - `options`-only payload
  - mixed payload with deterministic precedence
  - invalid option block shape
- Existing MCP tests must stay green.

---

## Exit Criteria for This Pass

- Normalization module in place and covered by tests.
- At least `find_duplicates` and `resolve_entity` can accept `options`.
- Handler internals use normalized contracts.
- Backward compatibility confirmed with parity tests.
