# Version History

High-level capability timeline for the public library.

---

## 3.5.0 (Current) - 2026-03-16

**Status**: Release-prepared and validated

### Highlights
- GAE clustering backend with dual-mode connection layer (self-managed JWT + AMP oasisctl)
- Full GAE engine lifecycle: deploy, load graph, run WCC, store results, read results, cleanup
- `backend='auto'` becomes the default — auto-selects GAE, sparse, or union-find based on context
- `GAEClusteringConfig` for enterprise GAE settings (engine size, deployment mode, timeouts)
- Live integration validated against self-managed GAE platform

## 3.4.0 - 2026-03-15

**Status**: Released

### Highlights
- Embedding `device` default promoted from `'cpu'` to `'auto'` (CUDA/MPS/CPU detection)
- Clustering `backend` default promoted from `'python_dfs'` to `'python_union_find'`
- `PythonSparseBackend` for large dense graphs (scipy, optional dependency)
- `backend='auto'` introduced as opt-in value
- `LLMMatchVerifier.healthcheck()` for provider reachability checks
- `max_batch_size` cap and OOM warnings for GPU embedding workloads

## 3.3.0 - 2026-03-14

**Status**: Released

### Highlights
- Clustering backend abstraction: `python_dfs`, `python_union_find`, `aql_graph` as pluggable backends
- Embedding runtime/device expansion: `'mps'`, `'auto'` devices; `runtime` config field
- `LLMProviderConfig` for structured Ollama/OpenRouter/OpenAI/Anthropic provider settings
- ONNX Runtime backend scaffold with provider resolution and CPU fallback
- Runtime health CLI commands: baseline, compare, gate workflows for CI
- Phase 0 GPU-readiness foundation completed

## 3.2.3 - 2026-03-08

**Status**: Historical release

### Highlights
- SmartGraph-aware deterministic keys for `SimilarityEdgeService`
- Automatic SmartGraph detection from live `python-arango` graph metadata
- Local Docker-backed Enterprise SmartGraph validation for the `ERR 1466` failure path

## 3.2.2 - 2026-03-08

**Status**: Historical release

### Highlights
- Config-driven similarity field transformers
- `arango-er` CLI expanded with `status`, `clusters`, `export`, and `benchmark`
- JSON/CSV cluster export and reporting helpers
- Supported exact-vs-BM25 blocking benchmark workflow
- Cluster quality metadata surfaced in stored clusters and MCP `get_clusters`

## 3.2.x - 2026 Q1

**Status**: Historical release line

### Highlights
- MCP tool/resource surface introduced
- Incremental single-record resolver
- LLM match verifier and active-learning support
- Security hardening across blocking and pipeline utility AQL paths

## 3.1.x - 2026 Q1

**Status**: Historical release line

### Highlights
- Domain enrichments such as compatibility filtering, hierarchical context resolution, and provenance sweeping
- Golden-record persistence improvements
- Additional service and test hardening

## 3.0.0 - 2025 Q4

**Status**: Historical major release

### Highlights
- General-purpose library formalization
- Configurable pipelines
- Address ER and cross-collection matching
- Vector search / embedding infrastructure
- WCC clustering and bulk-fetch performance improvements

## 2.x

**Status**: Legacy

### Highlights
- Early extraction of reusable blocking and similarity services
- Partial generalization from project-specific implementations

## 1.x

**Status**: Legacy

### Highlights
- Initial entity-resolution framework and basic multi-model patterns

---

## How To Check Your Version

```python
import entity_resolution
print(entity_resolution.__version__)
```

```python
from entity_resolution.utils.constants import VERSION_INFO, get_version_string

print(get_version_string())
print(VERSION_INFO)
```

## Related Docs

- [VERSION_SUMMARY.md](VERSION_SUMMARY.md) - Current release snapshot
- [CHANGELOG.md](CHANGELOG.md) - Detailed release notes
- [docs/guides/MIGRATION_GUIDE_V3.md](docs/guides/MIGRATION_GUIDE_V3.md) - Migration guidance for older versions

---

**Last Updated**: 2026-03-16

