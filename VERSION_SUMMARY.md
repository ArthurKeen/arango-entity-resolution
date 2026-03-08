# Version Summary - arango-entity-resolution

Quick reference for the currently shipped release.

---

## Current Version: 3.2.3

- **Released**: March 8, 2026
- **Status**: Release-prepared and validated locally
- **PyPI**: Pending publish

## Version String

```python
import entity_resolution
print(entity_resolution.__version__)  # "3.2.3"
```

## Source of Truth

Version metadata lives in `src/entity_resolution/utils/constants.py`.

```python
from entity_resolution.utils.constants import VERSION_INFO, get_version_string

print(get_version_string())  # "3.2.3"
print(VERSION_INFO)          # {'major': 3, 'minor': 2, 'patch': 3, 'release': ''}
```

## What 3.2.3 Includes

### 3.2.3 Patch Fixes
- SmartGraph-aware deterministic keys for `SimilarityEdgeService`
- Automatic SmartGraph detection from live `python-arango` graph metadata
- Docker-backed Enterprise SmartGraph validation for the `ERR 1466` failure path

### Existing 3.2.2 Surface

### Core Resolution Surface
- Configuration-driven ER pipelines via `ERPipelineConfig` and `ConfigurableERPipeline`
- Blocking strategies including exact/COLLECT, BM25, vector, LSH, geographic, and graph-traversal paths
- Weighted multi-field similarity, similarity edge creation, WCC clustering, and golden-record persistence
- Incremental single-record resolution through `IncrementalResolver`

### User-Facing Interfaces
- `arango-er` CLI for `run`, `status`, `clusters`, `export`, and `benchmark`
- `arango-er-mcp` MCP server with 7 tools and 2 resources
- `arango-er-demo` demo launcher

### 3.2.x Additions
- Active-learning configuration wired into the configurable pipeline
- Cluster quality metadata exposed through stored clusters and MCP `get_clusters`
- Config-driven similarity field transformers
- JSON/CSV cluster export and reporting helpers
- Supported exact-vs-BM25 blocking benchmark workflow built on `ABEvaluationHarness`

## How To Distinguish Recent Versions

| Version | Status | Highlights |
|---------|--------|------------|
| **3.2.3** | Current | SmartGraph deterministic edge-key fix and SmartGraph auto-detection |
| 3.2.2 | Historical | Transformers, CLI expansion, export/reporting, blocking benchmark workflow |
| 3.2.1 | Historical | MCP server, demo quickstart, incremental resolver, LLM verifier, active-learning groundwork |
| 3.2.0 | Historical | Security hardening, MCP package, generalized pipeline cleanup |
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

---

**Last Updated**: 2026-03-08

