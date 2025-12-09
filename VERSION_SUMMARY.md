# Version Summary - arango-entity-resolution

**Quick Reference for Current Library State**

---

## Current Version: 3.0.0-stable

**Released**: December 2025  
**Status**: ✅ Production Ready

### Version String
```python
import entity_resolution
print(entity_resolution.__version__)  # "3.0.0-stable"
```

### Version Code Location
**File**: `src/entity_resolution/utils/constants.py`
```python
VERSION_INFO = {
    'major': 3,
    'minor': 0,
    'patch': 0,
    'release': 'stable'
}
```

---

## What's Included in v3.0.0

### ✅ Complete Services

1. **AddressERService** - Address deduplication pipeline
2. **CrossCollectionMatchingService** - Match entities across collections
3. **EmbeddingService** - Vector embedding generation
4. **VectorBlockingStrategy** - Semantic similarity blocking
5. **BatchSimilarityService** - Bulk similarity computation
6. **WCCClusteringService** - Graph clustering (optimized)
7. **SimilarityEdgeService** - Edge creation

### ✅ Blocking Strategies

- CollectBlockingStrategy (exact key)
- BM25BlockingStrategy (fuzzy text)
- HybridBlockingStrategy (BM25 + distance)
- GeographicBlockingStrategy (location)
- GraphTraversalBlockingStrategy (relationships)
- VectorBlockingStrategy (semantic)

### ✅ Key Features

- Vector search-based ER (Phase 2)
- Address entity resolution
- Cross-collection matching
- WCC 40-100x performance improvement
- Bulk document fetching
- Configuration-driven pipelines
- Comprehensive utilities

---

## Version Identification

### How to Distinguish Versions

| Version | Identifier | Key Features |
|---------|-----------|--------------|
| **v3.0.0** | `"3.0.0-stable"` | ← **CURRENT** - All services included |
| v2.x | `"2.x.x-*"` | Partial services, no address ER |
| v1.x | `"1.x.x-*"` | Legacy basic ER |

### Check Current Version

**Command Line**:
```bash
cd /path/to/arango-entity-resolution
grep -A 4 "VERSION_INFO" src/entity_resolution/utils/constants.py
```

**Python**:
```python
from entity_resolution.utils.constants import VERSION_INFO, get_version_string
print(get_version_string())  # "3.0.0-stable"
print(VERSION_INFO)  # {'major': 3, 'minor': 0, 'patch': 0, 'release': 'stable'}
```

---

## Documentation References

| Document | Purpose |
|----------|---------|
| [VERSION_HISTORY.md](VERSION_HISTORY.md) | Complete version timeline and feature history |
| [CHANGELOG.md](CHANGELOG.md) | Detailed change log with migration notes |
| [README.md](README.md) | Overview with version badge |

---

## Customer Project Compatibility

### DNB ER Project

**Current State**: Uses v3.0.0-stable ✅

**Services Used**:
- ✅ AddressERService (from library)
- ✅ CrossCollectionMatchingService (from library)
- ✅ All blocking strategies
- ✅ Batch similarity
- ✅ WCC clustering
- ✅ Vector search (Phase 2)

**Architecture Rating**: ⭐⭐⭐⭐ (4/5 - Very Good)

---

## Semantic Versioning

Format: `MAJOR.MINOR.PATCH-RELEASE`

**Current**: `3.0.0-stable`
- **Major (3)**: Includes all extracted services
- **Minor (0)**: Initial v3 release
- **Patch (0)**: No patches yet
- **Release (stable)**: Production ready

---

## Future Versions

### Potential v3.1.0
- Enhanced deterministic edge keys
- Additional analyzers
- Performance monitoring dashboard
- Machine learning similarity thresholds

**Note**: Architecture assessment (Dec 2025) rates current version at 4/5 stars. Minor enhancements could bring it to 5/5.

---

**Document Purpose**: Quick reference for library version identification  
**Last Updated**: 2025-12-09  
**Current Library Version**: 3.0.0-stable

