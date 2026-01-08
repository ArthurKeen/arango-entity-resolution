# Changelog

All notable changes to the arango-entity-resolution library will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Deterministic Edge Keys

**Feature**: Idempotent edge creation across all deployment types

**Component**: `SimilarityEdgeService`

- Added `use_deterministic_keys` parameter (default: `True`)
- Generates MD5 hash of `_from + _to` as edge `_key`
- Order-independent: `(A, B)` and `(B, A)` generate same key
- Uses `overwriteMode='ignore'` to prevent duplicates
- Works for both SmartGraph and non-SmartGraph deployments
- No special handling needed - same simple pattern for all deployment types

**Benefits**:
- Idempotent pipelines - safe to run multiple times
- No duplicate edges
- Backward compatible - can disable with `use_deterministic_keys=False`
- Verified against production code (dnb_er project pattern)

**Usage**:
```python
service = SimilarityEdgeService(
db=db,
edge_collection='similarTo',
use_deterministic_keys=True # Default
)

# Run multiple times - no duplicates created
service.create_edges(matches)
service.create_edges(matches) # Safe - same edges won't duplicate
```

**SmartGraph Support**:
- Works transparently with SmartGraph vertex keys (e.g., `"570:12345"`)
- Edge key is pure hash (no shard prefix)
- ArangoDB handles edge placement via `_from` field automatically

## [3.1.0] - 2026-01-08

**Version Identifier**: 3.1.0-stable

### Added - Entity Resolution Enrichments

**New Feature**: Specialized components for technical, hierarchical, and domain-specific entity resolution.

**New Components**:

1. **TypeCompatibilityFilter** (`src/entity_resolution/enrichments/type_constraints.py`)
- Pre-filters candidates using a compatibility matrix before similarity scoring.
- Prevents nonsensical matches between incompatible types.
- Supports strict and loose matching modes.

2. **HierarchicalContextResolver** (`src/entity_resolution/enrichments/context_resolver.py`)
- Blends base similarity with token overlap between parent context and candidate description.
- Resolves ambiguities in hierarchical data where parent context provides critical disambiguation.
- Configurable weight for context influence.

3. **AcronymExpansionHandler** (`src/entity_resolution/enrichments/acronym_handler.py`)
- Expands search terms using domain-specific abbreviation dictionaries.
- Critical for technical and medical domains with heavy abbreviation use.
- Supports case-sensitive and case-insensitive matching.

4. **RelationshipProvenanceSweeper** (`src/entity_resolution/enrichments/relationship_sweeper.py`)
- Remaps relationships after deduplication to canonical golden entities.
- Maintains full audit trail and provenance of original source relationships.
- Optional relationship deduplication during remapping.

### Improved - Library Infrastructure

- **Lazy Configuration Loading**: Modified logging utilities to support standalone module imports without requiring database credentials.
- **Anonymized Documentation**: Removed specific customer references and anonymized examples for public distribution.
- **Emoji Removal**: Standardized all documentation to plain text for professional distribution.

### Fixed

- **Logging**: Fixed segfaults and import-time dependencies in `entity_resolution.utils.logging`.
- **Pre-commit Hooks**: Updated to correctly handle `PYTHONPATH` during import verification.

---

## [3.0.0] - 2025-12-09

**Version Identifier**: 3.0.0-stable

This is the current production release including all major ER services extracted from customer projects. See [VERSION_HISTORY.md](VERSION_HISTORY.md) for complete version timeline.

### Added - Vector Search-Based Entity Resolution (Phase 2)

**New Feature:** Tier 3 (Vector Blocking) with Semantic Embeddings

Implements Phase 2 Tier 3 (vector blocking) using pre-trained sentence-transformers models
and vector similarity search. Enables semantic matching that goes beyond exact text
or fuzzy string matching.

**New Components:**

1. **EmbeddingService** (`src/entity_resolution/services/embedding_service.py`)
- Generate vector embeddings for database records
- Uses sentence-transformers with pre-trained models (see config/vector_search_setup.md for model comparison)
- Batch processing for efficiency (1000+ records/batch)
- Automatic embedding storage in ArangoDB documents
- Coverage tracking and statistics

2. **VectorBlockingStrategy** (`src/entity_resolution/strategies/vector_blocking.py`)
- Tier 3 (vector blocking) for semantic similarity-based candidate generation
- Cosine similarity with configurable threshold
- Optional geographic/categorical blocking constraints
- Similarity distribution analysis for threshold tuning
- Compatible with existing blocking strategies

**Key Features:**
- Finds fuzzy matches that exact and text-based blocking miss
- Handles typos, abbreviations, and semantic variations
- Configurable similarity threshold (default: see DEFAULT_SIMILARITY_THRESHOLD in source)
- Limit candidates per entity to prevent explosion
- Combines with Tier 1 (exact) and Tier 2 (fuzzy text) blocking
- Performance: ~100-500 docs/second embedding generation (CPU)

**Configuration:**
```yaml
blocking:
strategy: "vector"
vector:
embedding_model: "all-MiniLM-L6-v2"
similarity_threshold: 0.7
limit_per_entity: 20
text_fields: ["name", "company", "address"]
```

**Usage Example:**
```python
from entity_resolution.services import EmbeddingService
from entity_resolution.strategies import VectorBlockingStrategy

# Step 1: Generate embeddings
embedding_service = EmbeddingService()
embedding_service.ensure_embeddings_exist(
'customers', 
text_fields=['name', 'company', 'address']
)

# Step 2: Find similar pairs
strategy = VectorBlockingStrategy(
db=db,
collection='customers',
similarity_threshold=0.7
)
pairs = strategy.generate_candidates()
```

**Testing:**
- 300+ unit tests for EmbeddingService
- 400+ integration tests for VectorBlockingStrategy
- End-to-end example with sample data
- Performance baselines established

**Documentation:**
- Configuration guide: `config/vector_search_setup.md`
- API reference updated
- Complete example: `examples/vector_blocking_example.py`
- Research notes: `research/papers/embeddings/`

**Dependencies:**
- Added `sentence-transformers>=2.2.0`
- Added `torch>=2.0.0`

**Based on Research:**
- Ebraheem et al. (2018): "Distributed Representations of Tuples for Entity Resolution"
- See: `research/papers/embeddings/2018_Ebraheem_DistributedEntityMatching_notes.md`

**Documentation:**
- API Reference: `docs/api/API_REFERENCE.md#embedding-service`
- Configuration Guide: `config/vector_search_setup.md`
- Working Example: `examples/vector_blocking_example.py`
- Code Quality Review: `docs/development/vector-search-code-quality-review.md`

### Fixed - CRITICAL: WCC Performance Issue (100x Speedup)

**Issue:** N+1 Query Anti-Pattern 
**Impact:** 100x performance degradation on production datasets 
**Severity:** HIGH - Made WCC unusable on real data

**Problem:**
- Old implementation: 24,256 separate queries for a 24K vertex graph
- Time: 300+ seconds (5+ minutes), often timeout
- Root cause: Per-vertex AQL traversal in a loop

**Solution:**
- New implementation: 1 bulk query + Python DFS
- Time: 3-8 seconds for same graph
- **Improvement: 40-100x faster** 

**Changes:**
- Added `_find_connected_components_bulk()` method
- Fetches ALL edges in ONE query
- Builds graph in Python memory (fast, no network calls)
- Runs DFS in Python (no database round-trips)

- Added `use_bulk_fetch` parameter (default: `True`)
- `True`: Use bulk fetch + Python DFS (FAST, recommended)
- `False`: Use per-vertex AQL traversal (SLOW, only for >10M edges)

- Backward compatible
- Existing code works without changes
- Default behavior is now 40-100x faster
- Old AQL approach still available if needed

**Performance:**
- Small graphs (100 edges): 4-5x faster
- Medium graphs (16K edges): 30-40x faster
- Large graphs (1M edges): 50-100x faster
- Memory: ~3-5 MB per 16K edges (negligible for ER use cases)

**Testing:**
- 5/5 performance tests passing
- Small, medium, large graphs tested
- Both approaches produce identical results
- Default behavior verified
- Empty graph edge case handled

**Migration:**
```python
# Before (implicit, slow):
service = WCCClusteringService(db, edge_collection='similarTo')

# After (explicit, fast - but default anyway):
service = WCCClusteringService(db, edge_collection='similarTo', use_bulk_fetch=True)

# Or keep slow approach for huge graphs:
service = WCCClusteringService(db, edge_collection='similarTo', use_bulk_fetch=False)
```

**Identified by:** dnb_er customer project 
**Test coverage:** `test_wcc_performance.py` (5/5 passing)

### Added
- **New Utility Modules** - Generic ER utilities ported from production implementations
- **`view_utils`**: ArangoSearch view analyzer verification and self-healing
- `resolve_analyzer_name()`: Automatically detects database-prefixed analyzer names
- `verify_view_analyzers()`: Tests view accessibility and detects analyzer issues
- `fix_view_analyzer_names()`: Recreates views with correct analyzer names
- `verify_and_fix_view_analyzers()`: Combined verification and auto-fix
- Prevents common deployment failures from analyzer name mismatches
- **`pipeline_utils`**: ER pipeline state management
- `clean_er_results()`: Removes previous ER results from collections
- Gracefully handles missing collections and errors
- Configurable collection list with sensible defaults
- **`config_utils`**: Configuration and environment utilities
- `verify_arango_environment()`: Validates required ArangoDB environment variables
- `get_arango_config_from_env()`: Loads ArangoDB config from environment
- Provides user-friendly error messages for missing configuration
- **`validation_utils`**: ER result validation
- `validate_er_results()`: Compares expected vs actual document counts
- Detects data consistency issues early
- Configurable validation rules with sensible defaults
- All utilities are exported from `entity_resolution.utils` for easy access
- Comprehensive test coverage (38 new test cases)
- See `docs/development/LIBRARY_PORT_ANALYSIS.md` for details

- **AddressERService** - Dual edge loading methods for optimal performance
- **Optimized API method**: Cross-block batching reduces API calls by 100x (285K → ~400 calls)
- 3-4x faster than original per-block approach
- Configurable batch size via `edge_batch_size` (default: 1000)
- Good for datasets with <100K edges
- **CSV + arangoimport method**: 10-20x faster for large datasets (>100K edges)
- Exports edges to CSV and uses ArangoDB's native bulk import tool
- Single import operation vs thousands of API calls
- Automatic fallback to API method if arangoimport unavailable
- Configurable via `edge_loading_method='csv'` in config
- **Method selection**: Choose 'api' (default) or 'csv' via configuration
- **Progress logging**: Both methods log progress every 100K edges
- See `docs/development/EDGE_BULK_LOADING_ANALYSIS.md` for details

### Fixed
- **AddressERService** - Fixed analyzer name resolution for database-prefixed analyzers
- Added `_resolve_analyzer_name()` method to detect and use database-prefixed analyzer names (e.g., `database_name::analyzer_name`)
- `_setup_search_view()` now automatically detects and uses the correct analyzer names whether they're prefixed or not
- Fixes address matching issues when analyzers are stored with database prefixes in ArangoDB
- Backward compatible: works with both prefixed and non-prefixed analyzer names
- Includes fallback logic for built-in analyzers like `text_en` and `identity`

## [3.0.0] - 2025-11-17

### Added - General-Purpose ER Components

#### Core Similarity Component
- **`WeightedFieldSimilarity`** - Standalone reusable similarity computation
- Multiple algorithms (Jaro-Winkler, Levenshtein, Jaccard)
- Configurable field weights and null handling
- String normalization options
- Can be used independently or with batch services

#### Enhanced Clustering
- **`WCCClusteringService`** - Now supports multiple algorithms:
- **Python DFS** - Reliable across all ArangoDB versions, uses bulk edge fetching
- **AQL Graph** (default) - Server-side processing for large graphs
- Eliminates N+1 query problems with single bulk edge fetch

#### Address Entity Resolution
- **`AddressERService`** - Complete address deduplication pipeline
- Custom analyzer setup for address normalization
- ArangoSearch view configuration
- Blocking with registered agent handling
- Edge creation and optional clustering
- Configurable field mapping (works with any address schema)

#### Configuration-Driven ER
- **`ERPipelineConfig`** - YAML/JSON-based ER pipeline configuration
- **`ConfigurableERPipeline`** - Run complete ER pipelines from configuration files
- Automatic service instantiation
- Validation and error handling
- Standardized ER patterns

### Fixed
- **WCC Clustering Service** - Added missing `WITH` clause in AQL graph traversal queries
- Fixes "collection not known to traversal" error (ArangoDB Error 1521)
- Auto-detects vertex collections from edge `_from` and `_to` fields
- Supports both explicit and auto-detected vertex collections
- Handles multi-collection graphs correctly
- **AddressERService** - Fixed logger.success() calls (replaced with logger.info())
- **Security** - Added field name validation to prevent AQL injection
- **Test Coverage** - Added comprehensive tests for ConfigurableERPipeline, graph_utils, config, and database modules

### Changed
- **BatchSimilarityService** - Now uses WeightedFieldSimilarity internally for consistency
- **Default Constants** - Centralized in constants.py for consistency

## [2.0.0] - 2025-11-12

### Added - Enhanced Entity Resolution Components

#### New Blocking Strategies
- **`CollectBlockingStrategy`** - COLLECT-based composite key blocking
- Efficient O(n) complexity without cartesian products
- Supports multi-field blocking (phone+state, address+zip, etc.)
- Configurable filters per field
- Block size limits to prevent explosion
- **Computed fields support** - Derive blocking keys from existing fields using AQL expressions
- Extract ZIP5 from POSTAL_CODE: `LEFT(d.postal_code, 5)`
- Normalize phone numbers: `REGEX_REPLACE(d.phone, '[^0-9]', '')`
- Combine fields: `CONCAT(d.field1, '_', d.field2)`
- Filter on computed fields
- No validation conflicts with non-standard field names

- **`BM25BlockingStrategy`** - Fast fuzzy text matching
- Uses ArangoSearch BM25 scoring
- 400x faster than Levenshtein for initial filtering
- Configurable BM25 thresholds
- Limit results per entity
- Optional blocking field constraints

#### New Similarity Service
- **`BatchSimilarityService`** - Optimized similarity computation
- Batch document fetching (reduces queries from 100K+ to ~10-15)
- Multiple algorithms: Jaro-Winkler, Levenshtein, Jaccard, custom
- Configurable field weights
- Field normalization options (case, whitespace, etc.)
- Progress callbacks for long operations
- Performance: ~100K+ pairs/second for Jaro-Winkler
- Detailed per-field similarity scores available

#### New Edge Service
- **`SimilarityEdgeService`** - Bulk edge creation
- Batch insertion with configurable batch sizes
- Automatic _from/_to formatting
- Comprehensive metadata tracking
- Bidirectional edge support
- Cleanup operations for iterative workflows
- Performance: ~10K+ edges/second

#### New Clustering Service
- **`WCCClusteringService`** - Weakly Connected Components clustering
- Server-side AQL graph traversal (efficient, works on all ArangoDB 3.11+)
- Handles graphs with millions of edges
- Cluster validation methods
- Comprehensive statistics tracking
- Configurable minimum cluster size
- Automatic cluster storage
- Future: GAE enhancement path documented

### Enhanced

#### Base Classes
- **`BlockingStrategy`** - Abstract base class for all blocking strategies
- Consistent API across all blocking methods
- Built-in filter condition builders
- Pair normalization and deduplication
- Statistics tracking
- Progress reporting

#### Library Exports
- All new classes properly exported from `entity_resolution` module
- Organized imports by category (strategies, services)
- Backward compatible with existing imports

### Documentation

#### New Documentation
- **Migration Guide** (`docs/MIGRATION_GUIDE_V2.md`) - Step-by-step guide to refactor from direct implementations
- **Usage Examples** (`examples/enhanced_er_examples.py`) - 8 complete examples demonstrating all new features
- **GAE Enhancement Path** (`docs/GAE_ENHANCEMENT_PATH.md`) - Future enhancement documentation for very large graphs
- **Enhancement Plan** (`docs/LIBRARY_ENHANCEMENT_PLAN.md`) - Detailed technical specifications
- **Design Rationale** (`DESIGN_SIMPLIFICATION.md`) - Explains design decisions (AQL vs Python DFS)

#### Updated Documentation
- **README** - Added v2.0 features section at the top
- **Examples** - Comprehensive examples showing generic patterns

### Testing

#### Unit Tests
- `test_blocking_strategies.py` - Complete unit tests for blocking strategies
- `test_similarity_and_edge_services.py` - Unit tests for similarity and edge services
- `test_wcc_clustering_service.py` - Unit tests for clustering service

#### Integration Tests
- `test_integration_and_performance.py` - End-to-end integration tests with real ArangoDB
- Performance benchmarks for all components
- Complete pipeline testing

### Performance Improvements

- **Blocking**: O(n) complexity vs O(n²) for composite keys
- **Similarity**: Batch fetching reduces network overhead by 99%+
- **Clustering**: Server-side AQL processing vs client-side Python
- **Overall**: ~87% code reduction for projects using these features

### Breaking Changes

**None** - Version 2.0 is fully backward compatible. All existing APIs remain unchanged.
New features are additive and don't modify existing functionality.

### Dependencies

- Existing: `jellyfish` and `python-Levenshtein` already in requirements.txt
- No new dependencies added

### Migration

Projects can migrate incrementally:
1. Existing code continues to work without changes
2. New features can be adopted component by component
3. See [Migration Guide](docs/guides/MIGRATION_GUIDE_V3.md) for detailed instructions

### Technical Details

#### Design Principles
- **Generic & Reusable**: No hardcoded collection or field names
- **Configuration-Driven**: All behavior controlled through parameters
- **Performance-Optimized**: Proven patterns from production use
- **Well-Documented**: Comprehensive API docs and examples

#### Quality Metrics
- Zero linter errors
- 100% type hints on public APIs
- 100% docstring coverage on public methods
- Comprehensive unit and integration tests

#### Supported Versions
- ArangoDB: 3.11+, 3.12+
- Python: 3.8+, 3.9+, 3.10+, 3.11+

---

## [1.x.x] - Previous Versions

See git history for previous version changes. Version 2.0 represents a major
enhancement adding production-grade entity resolution components while maintaining
full backward compatibility with version 1.x.

---

## Future Enhancements

### Planned Features
- GAE (Graph Analytics Engine) support for very large graphs (> 10M edges)
- Additional similarity algorithms
- Advanced blocking strategies
- Performance optimizations

### How to Contribute
See CONTRIBUTING.md (if available) or open issues/PRs on the project repository.

---

**Document Version:** 1.0 
**Date:** November 12, 2025 
**Library Version:** 2.0.0
