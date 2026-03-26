# Version Summary - arango-entity-resolution

Quick reference for the currently shipped release.

---

## Current Version: 3.5.0

- **Released**: March 16, 2026
- **Status**: Release-prepared and validated
- **PyPI**: Pending publish

## Version String

```python
import entity_resolution
print(entity_resolution.__version__)  # "3.5.0"
```

## Source of Truth

Version metadata lives in `src/entity_resolution/utils/constants.py`.

```python
from entity_resolution.utils.constants import VERSION_INFO, get_version_string

print(get_version_string())  # "3.5.0"
print(VERSION_INFO)          # {'major': 3, 'minor': 5, 'patch': 0, 'release': ''}
```

## What 3.5.0 Includes

### 3.5.0 — GAE Clustering Backend
- GAE WCC backend with full engine lifecycle (deploy, load, WCC, store results, cleanup)
- Dual-mode GAE connection layer (self-managed JWT + AMP oasisctl)
- `backend='auto'` as default clustering backend
- `GAEClusteringConfig` for enterprise GAE settings
- Live integration validated against self-managed GAE platform

### 3.4.0 — Promoted Defaults
- Embedding `device` default promoted to `'auto'` (CUDA/MPS/CPU detection)
- Clustering `backend` default promoted to `'python_union_find'`
- `PythonSparseBackend` for large dense graphs (scipy, optional)
- `backend='auto'` introduced as opt-in
- `LLMMatchVerifier.healthcheck()` for provider reachability
- `max_batch_size` cap and OOM warnings

### 3.3.0 — Backend Abstraction
- Pluggable WCC clustering backends: `python_dfs`, `python_union_find`, `aql_graph`
- Embedding runtime/device expansion: `'mps'`, `'auto'` devices
- `LLMProviderConfig` for structured LLM provider settings
- ONNX Runtime backend scaffold with provider resolution
- Runtime health CLI commands (baseline, compare, gate)
- Phase 0 GPU-readiness foundation

### Core Resolution Surface (inherited from 3.2.x)
- Configuration-driven ER pipelines via `ERPipelineConfig` and `ConfigurableERPipeline`
- Blocking strategies including exact/COLLECT, BM25, vector, LSH, geographic, and graph-traversal paths
- Weighted multi-field similarity, similarity edge creation, WCC clustering, and golden-record persistence
- Incremental single-record resolution through `IncrementalResolver`
- MCP server with 7 tools and 2 resources
- LLM match verification and active learning
- Config-driven similarity field transformers
- JSON/CSV cluster export and blocking benchmark workflows

### User-Facing Interfaces
- `arango-er` CLI for `run`, `status`, `clusters`, `export`, `benchmark`, `runtime-health`, and related commands
- `arango-er-mcp` MCP server with 7 tools and 2 resources
- `arango-er-demo` demo launcher

## How To Distinguish Recent Versions

| Version | Status | Highlights |
|---------|--------|------------|
| **3.5.0** | Current | GAE clustering backend, `backend='auto'` default, dual-mode GAE connection |
| 3.4.0 | Historical | Promoted `device='auto'` and `backend='python_union_find'`, sparse backend, LLM healthcheck |
| 3.3.0 | Historical | Clustering backend abstraction, embedding runtime expansion, LLM provider config, runtime health CLI |
| 3.2.3 | Historical | SmartGraph deterministic edge-key fix and SmartGraph auto-detection |
| 3.2.2 | Historical | Transformers, CLI expansion, export/reporting, blocking benchmark workflow |
| 3.2.x | Historical | MCP server, incremental resolver, LLM verifier, security hardening |
| 3.1.x | Historical | Enrichments, golden-record persistence, additional service hardening |
| 3.0.0 | Historical | General-purpose library formalization and core ER service surface |

## Documentation Map

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | Product overview, install options, CLI and MCP quick starts |
| [CHANGELOG.md](CHANGELOG.md) | Release-by-release changes |
| [VERSION_HISTORY.md](VERSION_HISTORY.md) | High-level capability timeline |
| [docs/guides/QUICK_START.md](docs/guides/QUICK_START.md) | Current setup and first-run workflow |
| [docs/api/API_REFERENCE.md](docs/api/API_REFERENCE.md) | Current CLI, MCP, and Python API surface |
| [docs/development/GAE_ENHANCEMENT_PATH.md](docs/development/GAE_ENHANCEMENT_PATH.md) | GAE clustering design and usage |

---

**Last Updated**: 2026-03-16

