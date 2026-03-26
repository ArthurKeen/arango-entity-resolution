# GAE Enhancement Path for WCC Clustering

**Date:** November 12, 2025 (original), March 16, 2026 (updated)  
**Status:** IMPLEMENTED in Release 3.5.0

---

## Overview

This document originally outlined the path for adding GAE (Graph Analytics Engine) support to `WCCClusteringService`. **GAE support was implemented in Release 3.5.0** (March 2026) with a full dual-mode connection layer supporting both self-managed and ArangoGraph Managed Platform deployments.

### Current Implementation (3.5.0)

**Six Pluggable WCC Backends:**
- **`python_dfs`** — bulk edge fetch + iterative DFS
- **`python_union_find`** — near-linear Union-Find with path compression
- **`python_sparse`** — scipy sparse matrix WCC (optional dependency)
- **`aql_graph`** — server-side AQL traversal
- **`gae_wcc`** — ArangoDB Graph Analytics Engine (enterprise)
- **`auto`** — automatic selection based on context (default since 3.5.0)

### GAE Backend

**Graph Analytics Engine (GAE)** is ArangoDB's enterprise graph analytics engine. The `GAEWCCBackend` manages the full engine lifecycle:
- Engine deployment and readiness polling
- Graph data loading
- WCC algorithm execution
- Result storage to vertex documents
- Optional engine cleanup

---

## Implemented Architecture (3.5.0)

### Connection Layer

**`gae_connection.py`** provides a dual-mode connection abstraction:

- **`SelfManagedGAEConnection`** — Authenticates via JWT obtained from `/_open/auth`.
  Engine lifecycle managed via `/gen-ai/v1/graphanalytics`. Engine API via `/gral/<short_id>/v1/...`.
- **`AMPGAEConnection`** — Authenticates via `oasisctl` bearer token.
  GAE management API on port 8829. Engine API on a dynamic base URL.
- **`get_gae_connection()`** — Factory function that routes by `TEST_DEPLOYMENT_MODE` or `GAE_DEPLOYMENT_MODE` environment variable.

### Backend

**`GAEWCCBackend`** (`gae_wcc.py`) orchestrates the full GAE pipeline:

1. Deploy or reuse an existing GAE engine
2. Wait for engine API readiness (consecutive-OK probes)
3. Load graph data (vertex + edge collections)
4. Run WCC algorithm
5. Store results back to vertex documents
6. Read component labels from vertex attributes with key mapping
7. Optional engine cleanup

### Configuration

```yaml
clustering:
  backend: "auto"
  gae:
    enabled: true
    deployment_mode: "self_managed"
    graph_name: "companies_similarity_graph"
    engine_size: "e16"
    auto_cleanup: true
    timeout_seconds: 3600
```

### Auto-Selection Logic

When `backend='auto'` (default since 3.5.0), `WCCClusteringService._auto_select_backend()`:

1. Checks if GAE is enabled and available — selects `gae_wcc` for large graphs
2. Falls back to `python_sparse` (if scipy installed and edge count exceeds threshold)
3. Falls back to `python_union_find` as general-purpose default

---

## Testing

### Unit Tests (`tests/test_gae_clustering.py`)

29 unit tests covering:
- `GAEClusteringConfig` defaults, `from_dict`/`to_dict`, validation
- `ClusteringConfig` GAE integration
- `GAEWCCBackend` backend name, `is_available` (mocked)
- `WCCClusteringService` auto-selection with GAE priority

### Integration Tests (`tests/test_gae_integration.py`)

Skip-marked with `@requires_gae` (checks `ARANGO_GAE_ENABLED=1`):
- Engine availability test
- Full cluster pipeline: seed graph, deploy, load, WCC, store, read clusters
- Fallback behavior when GAE is unavailable

### Validated

Live integration validated against self-managed GAE on `prod.demo.pilot.arango.ai:8529`.

---

## Usage

### Configuration-Driven

```yaml
entity_resolution:
  clustering:
    backend: "auto"
    gae:
      enabled: true
      deployment_mode: "self_managed"
      engine_size: "e16"
      timeout_seconds: 3600
```

### Programmatic

```python
from entity_resolution.services.wcc_clustering_service import WCCClusteringService
from entity_resolution.config import GAEClusteringConfig

gae_config = GAEClusteringConfig(enabled=True, deployment_mode="self_managed")
service = WCCClusteringService(
    db=db,
    edge_collection="similarTo",
    backend="auto",
    gae_config=gae_config,
)
clusters = service.cluster()
stats = service.get_statistics()
# stats includes: backend_used, gae_job_id, gae_runtime_seconds (when GAE used)
```

### When to Use GAE

| Scenario | Recommended Backend |
|----------|-------------------|
| Most use cases (< 2M edges) | `python_union_find` (auto-selected) |
| Large dense graphs with scipy | `python_sparse` (auto-selected) |
| Enterprise-scale (> 2M edges, GAE available) | `gae_wcc` (auto-selected) |
| Server-side processing preference | `aql_graph` (explicit) |
| Legacy compatibility | `python_dfs` (explicit) |

---

## Key Implementation Files

| File | Purpose |
|------|---------|
| `services/clustering_backends/gae_connection.py` | Dual-mode GAE connection abstraction |
| `services/clustering_backends/gae_wcc.py` | GAE WCC backend implementation |
| `config/er_config.py` | `GAEClusteringConfig` class |
| `services/wcc_clustering_service.py` | Backend dispatch and auto-selection |
| `tests/test_gae_clustering.py` | Unit tests |
| `tests/test_gae_integration.py` | Integration tests (skip-marked) |

---

**Document Version:** 2.0 
**Created:** November 12, 2025 
**Updated:** March 16, 2026 
**Status:** Implemented in Release 3.5.0

