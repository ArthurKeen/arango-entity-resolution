# Version History

High-level capability timeline for the public library.

---

## 3.2.3 (Current) - 2026-03-08

**Status**: Release-prepared and locally validated

### Highlights
- SmartGraph-aware deterministic keys for `SimilarityEdgeService`
- Automatic SmartGraph detection from live `python-arango` graph metadata
- Local Docker-backed Enterprise SmartGraph validation for the `ERR 1466` failure path

## 3.2.2 - 2026-03-08

**Status**: Published and release-validated

### Highlights
- Config-driven similarity field transformers
- `arango-er` CLI expanded with `status`, `clusters`, `export`, and `benchmark`
- JSON/CSV cluster export and reporting helpers
- Supported exact-vs-BM25 blocking benchmark workflow
- Cluster quality metadata surfaced in stored clusters and MCP `get_clusters`

## 3.2.1 - 2026-03-06

**Status**: Historical release

### Highlights
- MCP server package and demo quickstart
- Incremental single-record resolver
- LLM match verifier and active-learning support groundwork
- Release-publish workflow stabilization

## 3.2.0 - 2026-03-05

**Status**: Historical release

### Highlights
- MCP tool/resource surface introduced
- Security hardening across blocking and pipeline utility AQL paths
- General pipeline cleanup and broader test coverage

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

**Last Updated**: 2026-03-08

