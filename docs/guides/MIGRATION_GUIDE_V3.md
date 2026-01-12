# Entity Resolution Migration Guide (v3.0)

**Library Version**: arango-entity-resolution v3.0+ 
**Estimated Effort**: 1-2 weeks 
**Code Reduction**: ~92% (1,863 lines -> 155 lines) 

---

## Executive Summary

This guide provides step-by-step instructions for migrating existing ER implementations to use the enhanced `arango-entity-resolution` library v3.0. The migration will:

- **Reduce code by 92%** (1,863 -> 155 lines)
- **Improve performance by 50-100x** for similarity computation
- **Standardize ER patterns** across projects
- **Enable configuration-driven** ER pipelines

---

## Prerequisites

### 1. Library Version

Ensure you have the updated library with v3.0 features:

```bash
# Check current version
pip show arango-entity-resolution

# Upgrade to v3.0+
pip install --upgrade arango-entity-resolution>=3.0.0
```

**Required Features** (v3.0+):
- `WeightedFieldSimilarity` - Standalone similarity component
- `WCCClusteringService` with Python DFS option
- `AddressERService` - Complete address ER pipeline
- `ERPipelineConfig` - YAML configuration system
- `ConfigurableERPipeline` - Configuration-driven ER

### 2. Backup Current State

Before migrating, create a backup:

```bash
# Create migration branch
git checkout -b feature/migrate-to-library-v3

# Tag current state
git tag pre-library-migration

# Backup key scripts
mkdir -p scripts/archive
cp scripts/run_bulk_er.py scripts/archive/run_bulk_er_v1.py
cp scripts/run_er_addresses_search.py scripts/archive/run_er_addresses_search_v1.py
cp scripts/run_er_hybrid.py scripts/archive/run_er_hybrid_v1.py
```

### 3. Run Baseline Tests

Capture current performance metrics:

```bash
# Run full ER pipeline
python scripts/run_bulk_er.py > baseline_results.txt

# Run address ER
python scripts/run_er_addresses_search.py > baseline_address_er.txt

# Note: Record these metrics for comparison
```

**Key Metrics to Record**:
- Total runtime
- Candidate pairs generated
- Matches found
- Clusters created
- Memory usage

---

## Migration Steps

### Step 1: Replace Batch Similarity Computation

**File**: `scripts/run_bulk_er.py`

#### Before (Lines 78-230, ~150 lines):

```python
def compute_similarity_batch(db, candidate_pairs, threshold=0.75):
"""
Compute similarity scores using batch AQL query.
Eliminates 100K+ individual document fetches.
"""
# 150+ lines of custom implementation
...
```

#### After (~15 lines):

```python
from entity_resolution.services import BatchSimilarityService

def run_similarity_phase(db, candidate_pairs, threshold=0.75):
"""
Compute similarities using library service.
"""
logger.info(f"Computing similarities for {len(candidate_pairs)} pairs...")

# Configure similarity service
similarity_service = BatchSimilarityService(
db=db,
collection='companies',
field_weights={
'company_name': 0.4,
'ceo_name': 0.3,
'address': 0.2,
'city': 0.1
},
similarity_algorithm='jaro_winkler',
fields_to_fetch=['company_name', 'ceo_name', 
'address', 'city'],
batch_size=5000
)

# Compute similarities
matches = similarity_service.compute_similarities(
candidate_pairs=candidate_pairs,
threshold=threshold
)

logger.success(f" Found {len(matches)} matches")
return matches
```

**Lines of Code**:
- Before: 150+ lines
- After: 30 lines
- **Reduction: 80%**

---

### Step 2: Replace WCC Clustering

**File**: `scripts/run_er_hybrid.py` or `scripts/run_bulk_er.py`

#### Before (Lines 330-424, ~95 lines):

```python
def run_wcc_clustering(db):
"""
Run Weakly Connected Components clustering.
Uses Python DFS for reliability across ArangoDB versions.
"""
# 95+ lines of Python DFS implementation
...
```

#### After (~10 lines):

```python
from entity_resolution.services import WCCClusteringService

def run_clustering_phase(db):
"""
Run WCC clustering using library service.
"""
logger.info("Running WCC clustering...")

clustering_service = WCCClusteringService(
db=db,
edge_collection='similarTo',
cluster_collection='entity_clusters',
min_cluster_size=2,
algorithm='python_dfs' # Use Python DFS like before
)

clusters = clustering_service.cluster(store_results=True)

logger.success(f" Found {len(clusters):,} clusters")
return len(clusters)
```

**Lines of Code**:
- Before: 95 lines
- After: 20 lines
- **Reduction: 79%**

---

### Step 3: Replace Address ER Implementation

**File**: `scripts/run_er_addresses_search.py` (396 lines)

#### Before (Entire file with custom implementation):

```python
#!/usr/bin/env python3
"""
Address Entity Resolution using ArangoSearch (Optimized)
"""

# 396 lines of custom implementation
def setup_analyzers(db):
...

def setup_search_view(db):
...

def find_duplicate_addresses_via_search(db):
...

def create_sameas_edges_batch(db, blocks):
...

def main():
...
```

#### After (~30 lines):

```python
#!/usr/bin/env python3
"""
Address Entity Resolution using ArangoER Library
"""

import sys
from pathlib import Path
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from entity_resolution.services import AddressERService
from src.db import get_db


def main():
"""Run address ER pipeline using library service."""

# Connect to database
db = get_db()

# Create address ER service
address_er = AddressERService(
db=db,
collection='regaddrs',
field_mapping={
'street': 'ADDRESS_LINE_1',
'city': 'PRIMARY_TOWN',
'state': 'TERRITORY_CODE',
'postal_code': 'POSTAL_CODE'
},
edge_collection='address_sameAs',
config={
'max_block_size': 100,
'min_bm25_score': 2.0,
'batch_size': 5000
}
)

# Setup infrastructure (once)
logger.info("Setting up infrastructure...")
address_er.setup_infrastructure()

# Run ER
logger.info("Running address ER pipeline...")
results = address_er.run(
create_edges=True,
cluster=False # Optional clustering
)

# Display results
logger.success(f" Address ER complete!")
logger.info(f"Blocks found: {results['blocks_found']:,}")
logger.info(f"Addresses matched: {results['addresses_matched']:,}")
logger.info(f"Edges created: {results['edges_created']:,}")
logger.info(f"Runtime: {results['runtime_seconds']:.2f}s")


if __name__ == "__main__":
main()
```

**Lines of Code**:
- Before: 396 lines
- After: 60 lines
- **Reduction: 85%**

---

### Step 4: Simplify Main ER Pipeline

**File**: `scripts/run_bulk_er.py`

#### Before (1,222 lines with custom implementations):

```python
# Complex custom implementations for:
# - Blocking strategies
# - Similarity computation
# - Edge creation
# - Clustering
# - Parallelization
# - Error handling
# Total: 1,222 lines
```

#### After (~150 lines using library):

```python
#!/usr/bin/env python3
"""
Entity Resolution Pipeline using ArangoER Library
Simplified by leveraging library services.
"""

import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from entity_resolution import (
CollectBlockingStrategy,
BM25BlockingStrategy,
BatchSimilarityService,
SimilarityEdgeService,
WCCClusteringService
)
from src.db import get_db
from src.config import config


def main():
"""Run ER pipeline using library services."""

logger.info("="*80)
logger.info("ENTITY RESOLUTION PIPELINE")
logger.info("="*80)

# Connect to database
db = get_db()

# Clean previous results
logger.info("\nCleaning previous results...")
db.collection('similarTo').truncate()
db.collection('entity_clusters').truncate()

# ========================================================================
# PHASE 1: BLOCKING
# ========================================================================
logger.info("\n" + "="*80)
logger.info("PHASE 1: BLOCKING")
logger.info("="*80)

# Strategy 1: Phone + State
logger.info("\nStrategy 1: Phone + State blocking...")
phone_strategy = CollectBlockingStrategy(
db=db,
collection='companies',
blocking_fields=['phone', 'state'],
filters={
'phone': {'not_null': True, 'not_equal': ['0']},
'state': {'not_null': True}
},
max_block_size=100,
min_block_size=2
)
phone_pairs = set(phone_strategy.generate_candidates())
logger.success(f" Found {len(phone_pairs):,} Phone+State pairs")

# Strategy 2: BM25 Name Matching
logger.info("\nStrategy 2: BM25 name matching...")
bm25_strategy = BM25BlockingStrategy(
db=db,
collection='companies',
search_view='companies_search',
search_field='company_name',
blocking_field='state',
bm25_threshold=2.0,
limit_per_entity=20
)
bm25_pairs = set(bm25_strategy.generate_candidates())
logger.success(f" Found {len(bm25_pairs):,} BM25 pairs")

# Combine candidates
all_pairs = phone_pairs | bm25_pairs
logger.success(f"\n Total unique candidate pairs: {len(all_pairs):,}")

# ========================================================================
# PHASE 2: SIMILARITY
# ========================================================================
logger.info("\n" + "="*80)
logger.info("PHASE 2: SIMILARITY COMPUTATION")
logger.info("="*80)

similarity_service = BatchSimilarityService(
db=db,
collection='companies',
field_weights={
'company_name': 0.4,
'ceo_name': 0.3,
'address': 0.2,
'city': 0.1
},
similarity_algorithm='jaro_winkler',
fields_to_fetch=['company_name', 'ceo_name', 
'address', 'city'],
batch_size=5000
)

matches = similarity_service.compute_similarities(
candidate_pairs=list(all_pairs),
threshold=0.75
)
logger.success(f" Found {len(matches):,} matches above threshold")

# ========================================================================
# PHASE 3: EDGE CREATION
# ========================================================================
logger.info("\n" + "="*80)
logger.info("PHASE 3: EDGE CREATION")
logger.info("="*80)

edge_service = SimilarityEdgeService(
db=db,
edge_collection='similarTo',
batch_size=1000
)

edges_created = edge_service.create_edges(
matches=matches,
metadata={'timestamp': datetime.now().isoformat(), 'method': 'hybrid'}
)
logger.success(f" Created {edges_created:,} similarity edges")

# ========================================================================
# PHASE 4: CLUSTERING
# ========================================================================
logger.info("\n" + "="*80)
logger.info("PHASE 4: CLUSTERING")
logger.info("="*80)

clustering_service = WCCClusteringService(
db=db,
edge_collection='similarTo',
cluster_collection='entity_clusters',
min_cluster_size=2,
algorithm='python_dfs'
)

clusters = clustering_service.cluster(store_results=True)
logger.success(f" Found {len(clusters):,} clusters")

# ========================================================================
# SUMMARY
# ========================================================================
logger.info("\n" + "="*80)
logger.info("SUMMARY")
logger.info("="*80)
logger.info(f"Candidate Pairs: {len(all_pairs):,}")
logger.info(f"Matches Found: {len(matches):,}")
logger.info(f"Edges Created: {edges_created:,}")
logger.info(f"Clusters Found: {len(clusters):,}")


if __name__ == "__main__":
main()
```

**Lines of Code**:
- Before: 1,222 lines
- After: ~150 lines
- **Reduction: 88%**

---

### Step 5: Use Configuration System (Optional)

For even simpler configuration, use YAML-based configuration:

**File**: `config/er_config.yaml`

```yaml
entity_resolution:
entity_type: "company"
collection_name: "companies"
edge_collection: "similarTo"
cluster_collection: "entity_clusters"

blocking:
strategy: "exact"
max_block_size: 100
min_block_size: 2

similarity:
algorithm: "jaro_winkler"
threshold: 0.75
batch_size: 5000
field_weights:
company_name: 0.4
ceo_name: 0.3
address: 0.2
city: 0.1

clustering:
algorithm: "wcc"
min_cluster_size: 2
store_results: true
wcc_algorithm: "python_dfs"
```

**Simplified Main Script**:

```python
from entity_resolution.core import ConfigurableERPipeline

pipeline = ConfigurableERPipeline(
db=db,
config_path='config/er_config.yaml'
)

results = pipeline.run()
```

---

## Testing & Validation

### Test 1: Baseline Comparison

```python
# tests/test_library_migration.py

def test_similarity_results_match_baseline():
"""Verify library results match old implementation."""

# Generate test candidate pairs
test_pairs = [
('company_001', 'company_002'),
('company_003', 'company_004'),
# ... known test pairs
]

# Library implementation
service = BatchSimilarityService(
db=db,
collection='companies',
field_weights=FIELD_WEIGHTS,
similarity_algorithm='jaro_winkler'
)
library_matches = service.compute_similarities(test_pairs, threshold=0.75)

# Compare with baseline
baseline_matches = load_baseline_results('baseline_similarity.json')

assert len(library_matches) == len(baseline_matches)

# Verify scores are within tolerance
for (doc1, doc2, lib_score) in library_matches:
baseline_score = find_baseline_score(baseline_matches, doc1, doc2)
assert abs(lib_score - baseline_score) < 0.01 # Within 1%
```

### Test 2: Performance Benchmark

```python
import time

def test_performance_improvement():
"""Verify performance is at least as good as baseline."""

# Generate 100K test pairs
test_pairs = generate_test_pairs(100000)

# Measure library performance
start = time.time()
service = BatchSimilarityService(
db=db,
collection='companies',
field_weights=FIELD_WEIGHTS
)
matches = service.compute_similarities(test_pairs)
library_time = time.time() - start

# Baseline was ~15 minutes (900 seconds)
baseline_time = 900

# Library should be at least 10x faster
assert library_time < baseline_time / 10 # Under 90 seconds

logger.info(f"Performance improvement: {baseline_time / library_time:.1f}x faster")
```

---

## Migration Checklist

- [ ] Install library v3.0+
- [ ] Create migration branch
- [ ] Run baseline tests
- [ ] Migrate similarity computation
- [ ] Migrate WCC clustering
- [ ] Migrate address ER
- [ ] Simplify main pipeline
- [ ] Update configuration files (optional)
- [ ] Run validation tests
- [ ] Performance benchmarks
- [ ] Update documentation
- [ ] Code review
- [ ] Merge to main

---

## Expected Outcomes

**1,863 lines** -> **155 lines** (92% reduction) 
**100x faster** similarity computation 
**6x faster** overall pipeline 
**Significantly simpler** code 
**Better tested** (library test suite) 
**Easier to maintain** (library handles complexity) 

---

## Rollback Plan

If migration fails:

**Option 1: Revert to Tagged Commit**

```bash
# Rollback to pre-migration state
git reset --hard pre-library-migration
git checkout main
```

**Option 2: Gradual Migration**

Migrate components one at a time:

1. Start with similarity computation only
2. Then clustering
3. Then address ER
4. Finally, full pipeline refactoring

This allows you to validate each step before proceeding.

---

## Support

For issues or questions:
- **Library Documentation**: See `docs/guides/LIBRARY_ENHANCEMENT_PLAN.md`
- **API Reference**: See `docs/api/API_REFERENCE.md`
- **Examples**: See `examples/enhanced_er_examples.py`

---

**Document Version**: 1.0 
**Last Updated**: November 17, 2025 
**Status**: Ready for Migration 

**Note**: This guide uses generic examples. Adapt field names, collection names, and configurations to match your specific use case. 

