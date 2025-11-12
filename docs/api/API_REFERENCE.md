# API Reference - Version 2.0

Complete API reference for enhanced entity resolution components.

---

## Table of Contents

- [Blocking Strategies](#blocking-strategies)
  - [BlockingStrategy (Base)](#blockingstrategy-base)
  - [CollectBlockingStrategy](#collectblockingstrategy)
  - [BM25BlockingStrategy](#bm25blockingstrategy)
- [Similarity Service](#similarity-service)
  - [BatchSimilarityService](#batchsimilarityservice)
- [Edge Service](#edge-service)
  - [SimilarityEdgeService](#similarityedgeservice)
- [Clustering Service](#clustering-service)
  - [WCCClusteringService](#wccclusteringservice)

---

## Blocking Strategies

### BlockingStrategy (Base)

Abstract base class for all blocking strategies.

**Import:**
```python
from entity_resolution import BlockingStrategy
```

**Methods:**

#### `__init__(db, collection, filters=None)`

Initialize base blocking strategy.

**Parameters:**
- `db` (StandardDatabase): ArangoDB database connection
- `collection` (str): Source collection name
- `filters` (dict, optional): Filters to apply to documents

**Filter Format:**
```python
{
    "field_name": {
        "not_null": True,
        "not_equal": ["value1", "value2"],
        "min_length": 5,
        "max_length": 100,
        "equals": "value",
        "contains": "substring",
        "regex": "pattern"
    }
}
```

#### `generate_candidates()` → List[Dict]

Generate candidate pairs (must be implemented by subclasses).

**Returns:** List of candidate pair dictionaries

#### `get_statistics()` → Dict

Get statistics about the blocking operation.

**Returns:**
```python
{
    "total_pairs": 12345,
    "execution_time_seconds": 2.3,
    "strategy_name": "CollectBlockingStrategy",
    "timestamp": "2025-11-12T14:30:22"
}
```

---

### CollectBlockingStrategy

COLLECT-based blocking for composite key matching.

**Import:**
```python
from entity_resolution import CollectBlockingStrategy
```

**Example:**
```python
strategy = CollectBlockingStrategy(
    db=db,
    collection="companies",
    blocking_fields=["phone", "state"],
    filters={
        "phone": {"not_null": True, "min_length": 10},
        "state": {"not_null": True}
    },
    max_block_size=100,
    min_block_size=2
)
pairs = strategy.generate_candidates()
```

#### `__init__(db, collection, blocking_fields, filters=None, max_block_size=100, min_block_size=2, computed_fields=None)`

**Parameters:**
- `db` (StandardDatabase): Database connection
- `collection` (str): Source collection
- `blocking_fields` (List[str]): Fields to use as composite blocking key
- `filters` (dict, optional): Field filters (see base class)
- `max_block_size` (int): Skip blocks larger than this (default: 100)
- `min_block_size` (int): Skip blocks smaller than this (default: 2)
- `computed_fields` (dict, optional): Computed fields like `{"zip5": "LEFT(postal_code, 5)"}`

**Returns pairs with format:**
```python
{
    "doc1_key": "123",
    "doc2_key": "456",
    "blocking_keys": {"phone": "5551234567", "state": "CA"},
    "block_size": 3,
    "method": "collect_blocking"
}
```

**Performance:** O(n) complexity

---

### BM25BlockingStrategy

BM25-based fuzzy blocking using ArangoSearch.

**Import:**
```python
from entity_resolution import BM25BlockingStrategy
```

**Prerequisites:** ArangoSearch view must exist:
```python
db.create_view(
    name='companies_search',
    view_type='arangosearch',
    properties={
        'links': {
            'companies': {
                'fields': {'name': {'analyzers': ['text_en']}}
            }
        }
    }
)
```

**Example:**
```python
strategy = BM25BlockingStrategy(
    db=db,
    collection="companies",
    search_view="companies_search",
    search_field="name",
    bm25_threshold=2.0,
    limit_per_entity=20,
    blocking_field="state"
)
pairs = strategy.generate_candidates()
```

#### `__init__(db, collection, search_view, search_field, bm25_threshold=2.0, limit_per_entity=20, blocking_field=None, filters=None, analyzer="text_en")`

**Parameters:**
- `db` (StandardDatabase): Database connection
- `collection` (str): Source collection
- `search_view` (str): ArangoSearch view name
- `search_field` (str): Field to perform BM25 search on
- `bm25_threshold` (float): Minimum BM25 score (default: 2.0)
- `limit_per_entity` (int): Max candidates per entity (default: 20)
- `blocking_field` (str, optional): Constraint field (e.g., "state")
- `filters` (dict, optional): Field filters
- `analyzer` (str): ArangoSearch analyzer (default: "text_en")

**Returns pairs with format:**
```python
{
    "doc1_key": "123",
    "doc2_key": "456",
    "bm25_score": 5.2,
    "search_field": "name",
    "blocking_field_value": "CA",
    "method": "bm25_blocking"
}
```

**Performance:** O(n log n), ~400x faster than Levenshtein

---

## Similarity Service

### BatchSimilarityService

Batch similarity computation with optimized document fetching.

**Import:**
```python
from entity_resolution import BatchSimilarityService
```

**Example:**
```python
service = BatchSimilarityService(
    db=db,
    collection="companies",
    field_weights={
        "name": 0.4,
        "ceo": 0.3,
        "address": 0.2,
        "city": 0.1
    },
    similarity_algorithm="jaro_winkler",
    batch_size=5000
)
matches = service.compute_similarities(pairs, threshold=0.75)
```

#### `__init__(db, collection, field_weights, similarity_algorithm="jaro_winkler", batch_size=5000, normalization_config=None, progress_callback=None)`

**Parameters:**
- `db` (StandardDatabase): Database connection
- `collection` (str): Source collection
- `field_weights` (Dict[str, float]): Field weights (will be normalized to sum to 1.0)
- `similarity_algorithm` (str or callable): Algorithm name or custom function
  - `"jaro_winkler"` (default) - Best for names/addresses
  - `"levenshtein"` - Edit distance
  - `"jaccard"` - Set-based similarity
  - Custom: `(str, str) -> float` callable
- `batch_size` (int): Documents per query (default: 5000)
- `normalization_config` (dict, optional): Field normalization options
- `progress_callback` (callable, optional): Progress function `(current, total) -> None`

**Normalization Config:**
```python
{
    "strip": True,
    "case": "upper",  # or "lower"
    "remove_extra_whitespace": True,
    "remove_punctuation": False
}
```

#### `compute_similarities(candidate_pairs, threshold=0.75, return_all=False)` → List[Tuple]

Compute similarities for candidate pairs.

**Parameters:**
- `candidate_pairs` (List[Tuple[str, str]]): List of (doc1_key, doc2_key) tuples
- `threshold` (float): Minimum similarity (0.0-1.0)
- `return_all` (bool): Return all pairs even below threshold

**Returns:** List of (doc1_key, doc2_key, score) tuples

**Performance:** ~100K+ pairs/second for Jaro-Winkler

#### `compute_similarities_detailed(candidate_pairs, threshold=0.75)` → List[Dict]

Compute similarities with per-field scores.

**Returns:**
```python
[
    {
        "doc1_key": "123",
        "doc2_key": "456",
        "overall_score": 0.87,
        "field_scores": {
            "name": 0.95,
            "ceo": 0.82,
            "address": 0.78,
            "city": 0.92
        },
        "weighted_score": 0.87
    }
]
```

#### `get_statistics()` → Dict

Get computation statistics.

**Returns:**
```python
{
    "pairs_processed": 50000,
    "pairs_above_threshold": 3421,
    "documents_cached": 15234,
    "batch_count": 4,
    "execution_time_seconds": 12.8,
    "pairs_per_second": 3906,
    "algorithm": "jaro_winkler"
}
```

---

## Edge Service

### SimilarityEdgeService

Bulk creation of similarity edges with metadata.

**Import:**
```python
from entity_resolution import SimilarityEdgeService
```

**Example:**
```python
service = SimilarityEdgeService(
    db=db,
    edge_collection="similarTo",
    vertex_collection="companies",
    batch_size=1000
)
edges_created = service.create_edges(
    matches=matches,
    metadata={"method": "hybrid", "algorithm": "jaro_winkler"}
)
```

#### `__init__(db, edge_collection="similarTo", vertex_collection=None, batch_size=1000, auto_create_collection=True)`

**Parameters:**
- `db` (StandardDatabase): Database connection
- `edge_collection` (str): Edge collection name (default: "similarTo")
- `vertex_collection` (str, optional): Vertex collection for _from/_to formatting
- `batch_size` (int): Edges per batch (default: 1000)
- `auto_create_collection` (bool): Create collection if missing (default: True)

#### `create_edges(matches, metadata=None, bidirectional=False)` → int

Create similarity edges in bulk.

**Parameters:**
- `matches` (List[Tuple[str, str, float]]): List of (doc1_key, doc2_key, score)
- `metadata` (dict, optional): Additional metadata for all edges
- `bidirectional` (bool): Create edges in both directions (default: False)

**Returns:** Number of edges created

**Performance:** ~10K+ edges/second

#### `create_edges_detailed(matches, bidirectional=False)` → int

Create edges with per-edge metadata.

**Parameters:**
- `matches` (List[Dict]): Detailed match records with metadata

#### `clear_edges(method=None, older_than=None)` → int

Clear similarity edges.

**Parameters:**
- `method` (str, optional): Only clear edges with this method
- `older_than` (str, optional): ISO timestamp - clear older edges

**Returns:** Number of edges removed

#### `get_statistics()` → Dict

Get edge creation statistics.

---

## Clustering Service

### WCCClusteringService

Weakly Connected Components clustering using AQL graph traversal.

**Import:**
```python
from entity_resolution import WCCClusteringService
```

**Example:**
```python
service = WCCClusteringService(
    db=db,
    edge_collection="similarTo",
    cluster_collection="entity_clusters",
    vertex_collection="companies",
    min_cluster_size=2
)
clusters = service.cluster(store_results=True)
```

#### `__init__(db, edge_collection="similarTo", cluster_collection="entity_clusters", vertex_collection=None, min_cluster_size=2, graph_name=None)`

**Parameters:**
- `db` (StandardDatabase): Database connection
- `edge_collection` (str): Edge collection with similarity edges
- `cluster_collection` (str): Collection to store clusters
- `vertex_collection` (str, optional): Vertex collection name
- `min_cluster_size` (int): Minimum entities per cluster (default: 2)
- `graph_name` (str, optional): Named graph to use

#### `cluster(store_results=True, truncate_existing=True)` → List[List[str]]

Run WCC clustering.

**Parameters:**
- `store_results` (bool): Store in cluster_collection (default: True)
- `truncate_existing` (bool): Clear existing clusters (default: True)

**Returns:** List of clusters (each cluster is a list of document keys)

**Performance:** Server-side processing, handles millions of edges

#### `get_cluster_by_member(member_key)` → Dict

Find cluster containing a specific member.

**Returns:**
```python
{
    "_key": "cluster_000123",
    "cluster_id": 123,
    "size": 5,
    "members": ["companies/c001", "companies/c002", ...],
    "member_keys": ["c001", "c002", ...],
    "timestamp": "2025-11-12T14:30:22",
    "method": "aql_graph_traversal"
}
```

#### `get_statistics()` → Dict

Get clustering statistics.

**Returns:**
```python
{
    "total_clusters": 234,
    "total_entities_clustered": 1523,
    "avg_cluster_size": 6.5,
    "max_cluster_size": 45,
    "min_cluster_size": 2,
    "cluster_size_distribution": {
        "2": 120,
        "3": 56,
        "4-10": 45,
        "11-50": 13
    },
    "algorithm_used": "aql_graph_traversal",
    "execution_time_seconds": 3.4
}
```

#### `validate_clusters()` → Dict

Validate cluster quality and consistency.

**Returns:**
```python
{
    "valid": True,
    "issues": [],
    "checks_performed": [
        "no_overlapping_clusters",
        "all_edges_respected",
        "min_size_requirement"
    ],
    "entities_checked": 1523,
    "edges_checked": 845
}
```

---

## Complete Pipeline Example

```python
from entity_resolution import (
    CollectBlockingStrategy,
    BM25BlockingStrategy,
    BatchSimilarityService,
    SimilarityEdgeService,
    WCCClusteringService
)

# 1. Blocking
phone_strategy = CollectBlockingStrategy(
    db=db, collection="companies",
    blocking_fields=["phone", "state"]
)
name_strategy = BM25BlockingStrategy(
    db=db, collection="companies",
    search_view="companies_search",
    search_field="name"
)

pairs = set()
for pair in phone_strategy.generate_candidates():
    pairs.add((pair['doc1_key'], pair['doc2_key']))
for pair in name_strategy.generate_candidates():
    pairs.add((pair['doc1_key'], pair['doc2_key']))

# 2. Similarity
similarity = BatchSimilarityService(
    db=db, collection="companies",
    field_weights={"name": 0.5, "address": 0.3, "phone": 0.2}
)
matches = similarity.compute_similarities(list(pairs), threshold=0.75)

# 3. Edges
edges = SimilarityEdgeService(
    db=db, edge_collection="similarTo"
)
edges.create_edges(matches, metadata={"method": "hybrid"})

# 4. Clustering
clustering = WCCClusteringService(
    db=db, edge_collection="similarTo"
)
clusters = clustering.cluster(store_results=True)

print(f"Found {len(clusters)} clusters!")
```

---

## Error Handling

All components raise standard Python exceptions:

- `ValueError`: Invalid parameters or configuration
- `ImportError`: Missing required libraries (e.g., jellyfish)
- `RuntimeError`: Operational errors (e.g., database connection)

**Example:**
```python
try:
    service = BatchSimilarityService(
        db=db,
        collection="companies",
        field_weights={"name": 0.0}  # Invalid: all weights zero
    )
except ValueError as e:
    print(f"Configuration error: {e}")
```

---

## Performance Guidelines

### Blocking
- **CollectBlockingStrategy**: O(n) - Use for exact composite key matching
- **BM25BlockingStrategy**: O(n log n) - Use for fuzzy text matching

### Similarity
- Batch size 5000 recommended for most cases
- Jaro-Winkler: ~100K pairs/sec
- Consider progress callbacks for > 100K pairs

### Clustering
- AQL handles millions of edges efficiently
- Server-side processing (no Python overhead)
- See [GAE Enhancement Path](GAE_ENHANCEMENT_PATH.md) for very large graphs

---

**Document Version:** 1.0  
**Library Version:** 2.0.0  
**Last Updated:** November 12, 2025

