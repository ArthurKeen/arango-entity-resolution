# Version Summary - arango-entity-resolution

**Quick Reference for Current Library State**

---

## Current Version: 3.1.2

**Released**: February 2026
**Status**: Production Ready

### Version String
```python
import entity_resolution
print(entity_resolution.__version__) # "3.1.2"
```

### Version Code Location
**File**: `src/entity_resolution/utils/constants.py`
```python
VERSION_INFO = {
'major': 3,
'minor': 1,
'patch': 2,
'release': ''
}
```

---

## What's Included in v3.1.0

### Specialized Enrichments

1. **TypeCompatibilityFilter** - Pre-filter candidates by compatibility matrix
2. **HierarchicalContextResolver** - Parent context disambiguation
3. **AcronymExpansionHandler** - Domain-specific abbreviation expansion
4. **RelationshipProvenanceSweeper** - Post-resolution relationship remapping

### Core Services (from v3.0.0)

1. **AddressERService** - Address deduplication pipeline
2. **CrossCollectionMatchingService** - Match entities across collections
3. **EmbeddingService** - Vector embedding generation
4. **VectorBlockingStrategy** - Semantic similarity blocking
5. **BatchSimilarityService** - Bulk similarity computation
6. **WCCClusteringService** - Graph clustering (optimized)
7. **SimilarityEdgeService** - Edge creation

### Key Features

- **Entity Resolution Enrichments** - Domain-specific technical ER (v3.1.0)
- **Vector search-based ER** - Phase 2 (v3.0.0)
- **Address entity resolution** (v3.0.0)
- **Cross-collection matching** (v3.0.0)
- **WCC 40-100x performance improvement** (v3.0.0)
- **Bulk document fetching** (v3.0.0)
- **Configuration-driven pipelines** (v3.0.0)

---

## Version Identification

### How to Distinguish Versions

| Version | Identifier | Key Features |
|---------|-----------|--------------|
| **v3.1.2** | `"3.1.2"` | <- **CURRENT** - Includes ER Enrichments + Phase 3 Node2Vec prototype + testing/security hardening |
| v3.1.1 | `"3.1.1"` | Golden record persistence + deterministic edge keys |
| v3.1.0 | `"3.1.0-stable"` | Historical “stable” identifier used for production-ready 3.1.0 release |
| v3.0.0 | `"3.0.0-stable"` | All core services, no enrichments |
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
print(get_version_string()) # "3.1.2"
print(VERSION_INFO) # {'major': 3, 'minor': 1, 'patch': 2, 'release': ''}
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

**Current State**: Uses v3.0.0-stable 

**Services Used**:
- AddressERService (from library)
- CrossCollectionMatchingService (from library)
- All blocking strategies
- Batch similarity
- WCC clustering
- Vector search (Phase 2)

**Architecture Rating**: (4/5 - Very Good)

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

