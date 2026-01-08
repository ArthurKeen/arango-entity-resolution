# Version History

This document provides a clear timeline of major library versions to distinguish different capability states.

---

## Version 3.1.0-stable (CURRENT) - January 2026

**Status**: **PRODUCTION READY**

### Major Features

**Entity Resolution Enrichments**:
- `TypeCompatibilityFilter` - Pre-filter candidates by type to prevent nonsensical matches
- `HierarchicalContextResolver` - Use parent context to disambiguate similar names in hierarchical data
- `AcronymExpansionHandler` - Handle domain-specific abbreviations and acronyms during search
- `RelationshipProvenanceSweeper` - Remap relationships through consolidation with full audit trails

**Improvements**:
- Standalone enrichment modules with lazy config loading (no database required for utility modules)
- Cross-domain validation on Hardware ER and Medical domains

---

## Version 3.0.0-stable - December 2025

**Status**: **PRODUCTION READY**

### Major Features

**Services Included**:
- `AddressERService` - Complete address deduplication pipeline
- `CrossCollectionMatchingService` - Match entities across collections
- `EmbeddingService` - Vector embedding generation (Phase 2)
- `BatchSimilarityService` - Bulk similarity computation
- `SimilarityEdgeService` - Edge creation
- `WCCClusteringService` - Graph clustering (with bulk fetch optimization)

**Blocking Strategies**:
- `CollectBlockingStrategy` - Exact key blocking
- `BM25BlockingStrategy` - Fuzzy text blocking
- `HybridBlockingStrategy` - Combined BM25 + distance metrics
- `GeographicBlockingStrategy` - Location-based blocking
- `GraphTraversalBlockingStrategy` - Graph relationship blocking
- `VectorBlockingStrategy` - Semantic similarity blocking (Phase 2)

**Key Capabilities**:
- Vector search-based ER (Tier 3 blocking)
- Address entity resolution
- Cross-collection matching
- WCC clustering with 40-100x performance improvement
- Bulk document fetching (100x faster than N+1)
- Deterministic edge keys capability
- Comprehensive pipeline utilities

### Architecture Assessment

**Division of Functionality Rating**: (4/5 - Very Good)

**What's Included in v3.0.0**:
- Core ER algorithms (blocking, similarity, clustering)
- Database optimizations (bulk fetching, batch processing)
- Address deduplication patterns
- Cross-collection matching patterns
- Hybrid similarity strategies
- Vector search and embeddings

**What Belongs in Customer Projects**:
- Domain-specific business logic
- Field mappings and configurations
- Data quality rules
- Test cases with domain knowledge
- Infrastructure setup
- Pipeline orchestration

---

## Version 2.x (Historical)

**Status**: Deprecated - Upgrade to 3.0.0+

### Major Features (v2.0)
- Initial extraction of general-purpose patterns from customer projects
- `BatchSimilarityService` introduced
- Enhanced blocking strategies
- Pipeline utilities

**Missing** (added in v3.0):
- `AddressERService`
- `CrossCollectionMatchingService`
- `VectorBlockingStrategy` and `EmbeddingService`
- WCC performance optimization
- `HybridBlockingStrategy`

**Note**: If you're on v2.x, please upgrade to v3.0.0 for significant performance improvements and new services.

---

## Version 1.x (Legacy)

**Status**: Deprecated - Upgrade to 3.0.0+

### Original Features
- Basic entity resolution framework
- Simple blocking and similarity services
- Foundation for multi-model ER

**Limitations**:
- No bulk fetching (N+1 query pattern)
- Limited blocking strategies
- Manual pipeline construction
- No address-specific support
- No cross-collection matching

---

## Future Roadmap

### Potential v3.1.0 Enhancements

**Under Consideration**:
- Enhanced deterministic edge key generation (currently optional)
- Additional pre-built analyzers for common patterns
- Performance monitoring and metrics dashboard
- Enhanced geographic blocking (radius-based)
- Machine learning-based similarity thresholds

**Note**: These are potential future enhancements based on user feedback and emerging patterns from customer projects.

---

## Version Identification

### How to Check Your Version

**In Python**:
```python
import entity_resolution
print(entity_resolution.__version__) # Output: "3.0.0-stable"
```

**In Code**:
```python
from entity_resolution.utils.constants import VERSION_INFO, get_version_string

version = get_version_string() # "3.0.0-stable"
major_version = VERSION_INFO['major'] # 3
```

---

## Migration Guide

### From v2.x to v3.0.0

**New Services Available**:
1. Replace custom address ER code with `AddressERService`
2. Replace custom cross-collection logic with `CrossCollectionMatchingService`
3. Add vector search with `EmbeddingService` and `VectorBlockingStrategy`

**Performance Improvements**:
- WCC clustering: 40-100x faster (enable `use_bulk_fetch=True`)
- Bulk document fetching: 100x faster (automatic in `BatchSimilarityService`)

**See**: `docs/guides/MIGRATION_GUIDE_V3.md` for detailed instructions

### From v1.x to v3.0.0

Significant breaking changes. Please review:
- `docs/guides/MIGRATION_GUIDE_V2.md`
- `docs/guides/MIGRATION_GUIDE_V3.md`

---

## Customer Project Version Compatibility

### DNB ER Project Compatibility

| DNB ER Version | Library Version | Status |
|----------------|-----------------|--------|
| Current | v3.0.0-stable | Fully Compatible |
| Legacy | v2.x | Upgrade Recommended |
| Original | v1.x | Not Compatible |

**Current State** (December 2025):
- DNB ER project successfully uses v3.0.0 library
- All services (`AddressERService`, `CrossCollectionMatchingService`) available
- Performance benchmarks met or exceeded
- Architecture separation rated 4/5 stars

---

## Semantic Versioning

This project follows [Semantic Versioning](https://semver.org/):
- **MAJOR** (X.0.0): Breaking API changes
- **MINOR** (3.X.0): New features, backward compatible
- **PATCH** (3.0.X): Bug fixes, backward compatible
- **RELEASE**: stable | beta | alpha

**Current**: `3.0.0-stable`
- Major: 3 (includes address ER, cross-collection, vector search)
- Minor: 0 (initial v3 release)
- Patch: 0 (no patches yet)
- Release: stable (production ready)

---

## Support Policy

### Version Support
- **v3.0.x**: Active support (current)
- **v2.x**: Security fixes only
- **v1.x**: End of life

### Upgrade Path
1. v1.x → v2.x → v3.0.0 (recommended)
2. v1.x → v3.0.0 (possible with careful migration)
3. v2.x → v3.0.0 (straightforward)

---

**Document Version**: 1.0 
**Last Updated**: 2025-12-09 
**Current Library Version**: 3.0.0-stable 
**Status**: Active Development

