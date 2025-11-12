# Migration Guide to v2.0

**Target Audience:** Projects with direct ER implementations  
**Goal:** Refactor to use enhanced library features  
**Version:** Migrating to arango-entity-resolution v2.0

---

## Overview

Version 2.0 introduces powerful new components that replace common direct implementations:

- **CollectBlockingStrategy** - COLLECT-based composite key blocking
- **BM25BlockingStrategy** - Fast fuzzy text matching  
- **BatchSimilarityService** - Optimized similarity computation
- **SimilarityEdgeService** - Bulk edge creation
- **WCCClusteringService** - AQL-based clustering

This guide shows how to migrate from direct implementations to library classes.

---

## Benefits of Migration

### Before Migration
- ❌ Custom blocking code (100-200 lines per strategy)
- ❌ Custom similarity logic (50-100 lines)
- ❌ Custom edge creation (30-50 lines)
- ❌ Custom clustering (100-150 lines)
- ❌ Need to maintain all this code

### After Migration
- ✅ Use library classes (10-20 lines per component)
- ✅ Generic, reusable, tested code
- ✅ Better performance (optimized implementations)
- ✅ Automatic updates and improvements
- ✅ Standard patterns across projects

---

## Step-by-Step Migration

### Step 1: Update Dependencies

**Add or update library version:**

```python
# requirements.txt
arango-entity-resolution>=2.0.0
```

**Install:**
```bash
pip install --upgrade arango-entity-resolution
```

**Verify:**
```bash
python -c "from entity_resolution import CollectBlockingStrategy; print('OK')"
```

---

### Step 2: Migrate Blocking Strategies

#### Pattern A: COLLECT-based Blocking

**Before (Direct Implementation):**
```python
def blocking_strategy_phone_state(db):
    """Phone + State blocking using COLLECT"""
    query = """
    FOR d IN my_collection
        FILTER d.phone != null
        FILTER d.phone != "0000000000"
        FILTER LENGTH(d.phone) >= 10
        FILTER d.state != null
        
        COLLECT phone = d.phone, state = d.state
        INTO group
        KEEP d
        
        LET doc_keys = group[*].d._key
        FILTER LENGTH(doc_keys) >= 2
        FILTER LENGTH(doc_keys) <= 100
        
        FOR i IN 0..LENGTH(doc_keys)-2
            FOR j IN (i+1)..LENGTH(doc_keys)-1
                RETURN {
                    doc1: doc_keys[i],
                    doc2: doc_keys[j]
                }
    """
    cursor = db.aql.execute(query)
    pairs = list(cursor)
    # ... convert to set, normalize, etc ...
    return unique_pairs
```

**After (Using Library):**
```python
from entity_resolution import CollectBlockingStrategy

def blocking_strategy_phone_state(db):
    """Phone + State blocking using library"""
    strategy = CollectBlockingStrategy(
        db=db,
        collection="my_collection",
        blocking_fields=["phone", "state"],
        filters={
            "phone": {
                "not_null": True,
                "not_equal": ["0000000000"],
                "min_length": 10
            },
            "state": {"not_null": True}
        },
        max_block_size=100,
        min_block_size=2
    )
    
    pairs = strategy.generate_candidates()
    return pairs
```

**Benefits:**
- 70% less code
- Automatic normalization and deduplication
- Statistics tracking built-in
- Reusable across projects

#### Pattern B: BM25 Fuzzy Blocking

**Before (Direct Implementation):**
```python
def blocking_strategy_bm25_name(db, limit_per_entity=20):
    """BM25 name matching"""
    query = """
    FOR d1 IN my_collection
        FILTER d1.name != null
        FILTER LENGTH(d1.name) > 3
        FILTER d1.state != null
        
        FOR d2 IN my_search_view
            SEARCH ANALYZER(
                PHRASE(d2.name, d1.name, "text_en"),
                "text_en"
            )
            LET bm25_score = BM25(d2)
            FILTER bm25_score > 2.0
            FILTER d2.state == d1.state
            FILTER d1._key < d2._key
            LIMIT @limit
            
            RETURN {
                doc1: d1._key,
                doc2: d2._key,
                score: bm25_score
            }
    """
    cursor = db.aql.execute(query, bind_vars={'limit': limit_per_entity})
    pairs = list(cursor)
    # ... process ...
    return unique_pairs
```

**After (Using Library):**
```python
from entity_resolution import BM25BlockingStrategy

def blocking_strategy_bm25_name(db, limit_per_entity=20):
    """BM25 name matching using library"""
    strategy = BM25BlockingStrategy(
        db=db,
        collection="my_collection",
        search_view="my_search_view",
        search_field="name",
        bm25_threshold=2.0,
        limit_per_entity=limit_per_entity,
        blocking_field="state",
        filters={
            "name": {"not_null": True, "min_length": 3},
            "state": {"not_null": True}
        }
    )
    
    pairs = strategy.generate_candidates()
    return pairs
```

**Benefits:**
- 60% less code
- BM25 score tracking
- Automatic field filtering
- Clear configuration

---

### Step 3: Migrate Similarity Computation

**Before (Direct Implementation):**
```python
def compute_similarity_batch(db, candidate_pairs, threshold=0.75):
    """Batch similarity computation"""
    # Extract unique keys
    all_keys = set()
    for doc1, doc2 in candidate_pairs:
        all_keys.add(doc1)
        all_keys.add(doc2)
    
    # Batch fetch documents
    doc_cache = {}
    for i in range(0, len(all_keys), 5000):
        batch = list(all_keys)[i:i+5000]
        query = """
        FOR doc IN my_collection
            FILTER doc._key IN @keys
            RETURN {
                _key: doc._key,
                name: doc.name || '',
                ceo: doc.ceo || '',
                address: doc.address || ''
            }
        """
        cursor = db.aql.execute(query, bind_vars={'keys': batch})
        for doc in cursor:
            doc_cache[doc['_key']] = doc
    
    # Compute similarities
    matches = []
    weights = {'name': 0.5, 'ceo': 0.3, 'address': 0.2}
    
    for doc1, doc2 in candidate_pairs:
        d1 = doc_cache.get(doc1)
        d2 = doc_cache.get(doc2)
        if not d1 or not d2:
            continue
        
        total_score = 0.0
        total_weight = 0.0
        
        for field, weight in weights.items():
            val1 = (d1.get(field) or '').strip().upper()
            val2 = (d2.get(field) or '').strip().upper()
            
            if val1 and val2:
                import jellyfish
                score = jellyfish.jaro_winkler_similarity(val1, val2)
                total_score += score * weight
                total_weight += weight
        
        if total_weight > 0:
            final_score = total_score / total_weight
            if final_score >= threshold:
                matches.append((doc1, doc2, final_score))
    
    return matches
```

**After (Using Library):**
```python
from entity_resolution import BatchSimilarityService

def compute_similarity_batch(db, candidate_pairs, threshold=0.75):
    """Batch similarity computation using library"""
    service = BatchSimilarityService(
        db=db,
        collection="my_collection",
        field_weights={
            'name': 0.5,
            'ceo': 0.3,
            'address': 0.2
        },
        similarity_algorithm="jaro_winkler",
        batch_size=5000
    )
    
    matches = service.compute_similarities(
        candidate_pairs=candidate_pairs,
        threshold=threshold
    )
    
    return matches
```

**Benefits:**
- 80% less code
- Multiple algorithm support
- Progress callbacks available
- Statistics tracking
- Automatic normalization

---

### Step 4: Migrate Edge Creation

**Before (Direct Implementation):**
```python
def create_similarity_edges_bulk(db, matches):
    """Bulk edge creation"""
    similar_to = db.collection('similarTo')
    edges_created = 0
    
    batch_size = 1000
    for i in range(0, len(matches), batch_size):
        batch = matches[i:i+batch_size]
        batch_edges = []
        
        for doc1, doc2, score in batch:
            batch_edges.append({
                '_from': f'my_collection/{doc1}',
                '_to': f'my_collection/{doc2}',
                'similarity': score,
                'method': 'hybrid',
                'timestamp': datetime.now().isoformat()
            })
        
        if batch_edges:
            similar_to.insert_many(batch_edges)
            edges_created += len(batch_edges)
    
    return edges_created
```

**After (Using Library):**
```python
from entity_resolution import SimilarityEdgeService

def create_similarity_edges_bulk(db, matches):
    """Bulk edge creation using library"""
    service = SimilarityEdgeService(
        db=db,
        edge_collection="similarTo",
        vertex_collection="my_collection",
        batch_size=1000
    )
    
    edges_created = service.create_edges(
        matches=matches,
        metadata={
            'method': 'hybrid',
            'algorithm': 'jaro_winkler',
            'threshold': 0.75
        }
    )
    
    return edges_created
```

**Benefits:**
- 70% less code
- Automatic _from/_to formatting
- Bidirectional support
- Error handling
- Statistics tracking

---

### Step 5: Migrate Clustering

**Before (Direct Implementation):**
```python
def run_wcc_clustering(db):
    """WCC clustering using Python DFS"""
    # Fetch all edges
    edges_query = "FOR e IN similarTo RETURN {from: e._from, to: e._to}"
    edges = list(db.aql.execute(edges_query))
    
    # Build graph
    from collections import defaultdict
    graph = defaultdict(set)
    
    for edge in edges:
        from_key = edge['from'].split('/')[-1]
        to_key = edge['to'].split('/')[-1]
        graph[from_key].add(to_key)
        graph[to_key].add(from_key)
    
    # Find connected components (DFS)
    visited = set()
    clusters = []
    
    def dfs(node, component):
        if node in visited:
            return
        visited.add(node)
        component.append(node)
        for neighbor in graph[node]:
            dfs(neighbor, component)
    
    for node in graph:
        if node not in visited:
            component = []
            dfs(node, component)
            if len(component) >= 2:
                clusters.append(sorted(component))
    
    # Store clusters
    entity_clusters = db.collection('entity_clusters')
    entity_clusters.truncate()
    
    cluster_docs = []
    for i, members in enumerate(clusters):
        cluster_docs.append({
            '_key': f'cluster_{i:06d}',
            'cluster_id': i,
            'size': len(members),
            'members': [f'my_collection/{m}' for m in members],
            'member_keys': members,
            'timestamp': datetime.now().isoformat()
        })
    
    if cluster_docs:
        entity_clusters.insert_many(cluster_docs)
    
    return len(clusters)
```

**After (Using Library):**
```python
from entity_resolution import WCCClusteringService

def run_wcc_clustering(db):
    """WCC clustering using library (AQL graph traversal)"""
    service = WCCClusteringService(
        db=db,
        edge_collection="similarTo",
        cluster_collection="entity_clusters",
        vertex_collection="my_collection",
        min_cluster_size=2
    )
    
    clusters = service.cluster(store_results=True)
    
    # Get statistics
    stats = service.get_statistics()
    print(f"Found {stats['total_clusters']} clusters")
    print(f"Avg size: {stats['avg_cluster_size']}")
    
    return len(clusters)
```

**Benefits:**
- 85% less code
- Server-side processing (much faster)
- Validation methods
- Statistics tracking
- Handles millions of edges

---

## Complete Migration Example

### Before: Direct Implementation (~300 lines)

```python
# Multiple files, 300+ lines total
from datetime import datetime
import jellyfish
from collections import defaultdict

def blocking_strategy_1(db): ...  # 50 lines
def blocking_strategy_2(db): ...  # 50 lines
def compute_similarity(db, pairs): ...  # 100 lines
def create_edges(db, matches): ...  # 40 lines
def cluster(db): ...  # 60 lines

def run_pipeline(db):
    pairs1 = blocking_strategy_1(db)
    pairs2 = blocking_strategy_2(db)
    all_pairs = pairs1 | pairs2
    matches = compute_similarity(db, all_pairs)
    edges = create_edges(db, matches)
    clusters = cluster(db)
    return clusters
```

### After: Using Library (~50 lines)

```python
from entity_resolution import (
    CollectBlockingStrategy,
    BM25BlockingStrategy,
    BatchSimilarityService,
    SimilarityEdgeService,
    WCCClusteringService
)

def run_pipeline(db):
    # Blocking
    phone_strategy = CollectBlockingStrategy(
        db=db, collection="my_collection",
        blocking_fields=["phone", "state"],
        filters={"phone": {"not_null": True, "min_length": 10}}
    )
    name_strategy = BM25BlockingStrategy(
        db=db, collection="my_collection",
        search_view="my_search_view",
        search_field="name", bm25_threshold=2.0
    )
    
    pairs = set()
    for pair in phone_strategy.generate_candidates():
        pairs.add((pair['doc1_key'], pair['doc2_key']))
    for pair in name_strategy.generate_candidates():
        pairs.add((pair['doc1_key'], pair['doc2_key']))
    
    # Similarity
    similarity = BatchSimilarityService(
        db=db, collection="my_collection",
        field_weights={"name": 0.5, "address": 0.3, "phone": 0.2}
    )
    matches = similarity.compute_similarities(list(pairs), threshold=0.75)
    
    # Edges
    edges = SimilarityEdgeService(
        db=db, edge_collection="similarTo", vertex_collection="my_collection"
    )
    edges.create_edges(matches, metadata={"method": "hybrid"})
    
    # Clustering
    clustering = WCCClusteringService(
        db=db, edge_collection="similarTo", cluster_collection="entity_clusters"
    )
    clusters = clustering.cluster(store_results=True)
    
    return clusters
```

**Result:**
- **83% less code** (300 lines → 50 lines)
- **Easier to understand**
- **Easier to maintain**
- **Better performance**

---

## Migration Checklist

### Pre-Migration
- [ ] Backup current code
- [ ] Document current performance baseline
- [ ] Create test datasets
- [ ] Install library v2.0+

### During Migration
- [ ] Migrate blocking strategies (one at a time)
- [ ] Migrate similarity computation
- [ ] Migrate edge creation
- [ ] Migrate clustering
- [ ] Update configuration/parameters

### Post-Migration
- [ ] Test with sample data
- [ ] Compare results with baseline
- [ ] Measure performance
- [ ] Update documentation
- [ ] Deploy to production

---

## Troubleshooting

### Issue: Different Results After Migration

**Cause:** Parameter differences or normalization changes  
**Solution:**
1. Compare field weights (ensure they match)
2. Check normalization settings (case, whitespace)
3. Verify threshold values
4. Use `compute_similarities_detailed()` to debug

### Issue: Performance Regression

**Cause:** Configuration not optimized  
**Solution:**
1. Check batch_size parameters
2. Verify ArangoSearch view is created
3. Profile with `get_statistics()`
4. Adjust min/max block sizes

### Issue: Import Errors

**Cause:** Library not installed or old version  
**Solution:**
```bash
pip install --upgrade arango-entity-resolution
python -c "from entity_resolution import CollectBlockingStrategy"
```

---

## Getting Help

- **Examples:** See `examples/enhanced_er_examples.py`
- **API Docs:** See docstrings in each class
- **Issues:** GitHub issues or project documentation

---

## Summary

Migration to v2.0 provides:
- ✅ **83% less code** on average
- ✅ **Better performance** (server-side processing)
- ✅ **Standard patterns** (consistent across projects)
- ✅ **Automatic updates** (improvements flow through library)
- ✅ **Easier maintenance** (less custom code)

**Recommendation:** Migrate components incrementally, starting with blocking strategies.

---

**Document Version:** 1.0  
**Created:** November 12, 2025  
**Library Version:** arango-entity-resolution v2.0.0

