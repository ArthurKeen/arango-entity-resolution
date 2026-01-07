# API Reference - Version 2.0

Complete API reference for enhanced entity resolution components.

---

## Table of Contents

- [Blocking Strategies](#blocking-strategies)
- [BlockingStrategy (Base)](#blockingstrategy-base)
- [CollectBlockingStrategy](#collectblockingstrategy)
- [BM25BlockingStrategy](#bm25blockingstrategy)
- [VectorBlockingStrategy](#vectorblockingstrategy) **NEW**
- [Embedding Service](#embedding-service) **NEW**
- [EmbeddingService](#embeddingservice)
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

### VectorBlockingStrategy

**NEW in v2.x** - Semantic similarity blocking using vector embeddings (Phase 2, Tier 3).

**Import:**
```python
from entity_resolution import VectorBlockingStrategy
```

**Description:**
Uses pre-trained sentence-transformers models to generate vector embeddings and finds
candidate pairs based on cosine similarity. Captures semantic matches that exact and
fuzzy text blocking may miss (typos, abbreviations, semantic variations).

**Prerequisites:**
1. Install dependencies: `pip install sentence-transformers torch`
2. Generate embeddings first using `EmbeddingService`

**Example:**
```python
from entity_resolution import EmbeddingService, VectorBlockingStrategy

# Step 1: Generate embeddings (one-time setup)
embedding_service = EmbeddingService(model_name='all-MiniLM-L6-v2')
embedding_service.ensure_embeddings_exist(
'customers',
text_fields=['name', 'company', 'address']
)

# Step 2: Use vector blocking
strategy = VectorBlockingStrategy(
db=db,
collection='customers',
similarity_threshold=0.7, # 70% similarity minimum
limit_per_entity=20, # Max 20 candidates per document
blocking_field='state' # Optional: only compare within same state
)
pairs = strategy.generate_candidates()
```

#### `__init__(db, collection, embedding_field='embedding_vector', similarity_threshold=0.7, limit_per_entity=20, blocking_field=None, filters=None)`

**Parameters:**
- `db` (StandardDatabase): ArangoDB database connection
- `collection` (str): Source collection name
- `embedding_field` (str): Field containing embeddings (default: DEFAULT_EMBEDDING_FIELD)
- `similarity_threshold` (float): Minimum cosine similarity 0-1 (default: DEFAULT_SIMILARITY_THRESHOLD)
- 0.9-1.0: Very similar (likely duplicates)
- 0.8-0.9: Similar (possible duplicates)
- 0.7-0.8: Somewhat similar (candidates)
- Below 0.7: Low similarity
- `limit_per_entity` (int): Max candidates per document (default: DEFAULT_LIMIT_PER_ENTITY)
- `blocking_field` (str, optional): Field for additional blocking (e.g., 'state', 'category')
- `filters` (dict, optional): Standard filters (see BlockingStrategy)

#### `generate_candidates()` → List[Dict]

Generate candidate pairs using vector similarity.

**Returns:**
```python
[
{
"doc1_key": "doc123",
"doc2_key": "doc456",
"similarity": 0.85, # Cosine similarity score
"method": "vector"
},
...
]
```

#### `get_similarity_distribution(sample_size=1000)` → Dict

Analyze similarity score distribution for threshold tuning.

**Parameters:**
- `sample_size` (int): Number of random pairs to sample (default: 1000)

**Returns:**
```python
{
"sample_size": 1000,
"min_similarity": 0.12,
"max_similarity": 0.98,
"mean_similarity": 0.45,
"median_similarity": 0.42,
"std_similarity": 0.18,
"distribution": [
{"bucket": 0.0, "count": 150},
{"bucket": 0.1, "count": 200},
...
],
"recommended_thresholds": {
"conservative": 0.82, # Top 10%
"balanced": 0.65, # Top 25%
"aggressive": 0.45 # Top 50%
}
}
```

**Use this to find the right threshold for your data:**
```python
stats = strategy.get_similarity_distribution()
print(f"Recommended threshold: {stats['recommended_thresholds']['balanced']}")
```

**Performance:** 
- Embedding generation: ~100-500 docs/second (CPU), ~1000-5000 (GPU)
- Query time: O(n²) worst case, but limited by `limit_per_entity`
- Memory: ~1.5 KB per document (384-dim embeddings)

**Best Practices:**
1. Use `get_similarity_distribution()` to tune threshold
2. Start with threshold=0.7, adjust based on precision/recall
3. Use `blocking_field` to reduce search space
4. Combine with Tier 1 (exact) and Tier 2 (fuzzy) blocking
5. Consider 384-dim model (faster) vs 768-dim (more accurate)

---

## Embedding Service

### EmbeddingService

**NEW in v2.x** - Generate and manage vector embeddings for entity resolution.

**Import:**
```python
from entity_resolution import EmbeddingService
```

**Description:**
Generates semantic vector embeddings for database records using pre-trained
sentence-transformers models. Embeddings enable similarity-based blocking
that captures semantic meaning beyond text matching.

**Example:**
```python
service = EmbeddingService(
model_name='all-MiniLM-L6-v2', # Fast, 384-dim
device='cpu' # or 'cuda' for GPU
)

# Generate embeddings for all documents
stats = service.ensure_embeddings_exist(
collection_name='customers',
text_fields=['name', 'company', 'email', 'address']
)
print(f"Generated {stats['generated']} embeddings")
```

#### `__init__(model_name='all-MiniLM-L6-v2', device='cpu', embedding_field='embedding_vector', db_manager=None)`

**Parameters:**
- `model_name` (str): Sentence-transformers model name
- `'all-MiniLM-L6-v2'` (default): 384-dim, fast, good quality
- `'all-mpnet-base-v2'`: 768-dim, slower, excellent quality
- `'all-distilroberta-v1'`: 768-dim, balanced
- `device` (str): 'cpu' or 'cuda' (default: 'cpu')
- `embedding_field` (str): Field name to store embeddings (default: 'embedding_vector')
- `db_manager` (DatabaseManager, optional): Database manager instance

**Supported Models:**
| Model | Dim | Speed | Quality | Use Case |
|-------|-----|-------|---------|----------|
| all-MiniLM-L6-v2 | 384 | Fast | Good | General purpose (recommended) |
| all-mpnet-base-v2 | 768 | Moderate | Excellent | High accuracy needed |
| all-distilroberta-v1 | 768 | Moderate | Very Good | Balance speed/quality |

#### `generate_embedding(record, text_fields=None)` → np.ndarray

Generate embedding for a single record.

**Parameters:**
- `record` (dict): Database record
- `text_fields` (list, optional): Fields to use for embedding

**Returns:** Numpy array of shape `(embedding_dim,)`

**Example:**
```python
record = {'name': 'John Smith', 'company': 'Acme Corp'}
embedding = service.generate_embedding(record, text_fields=['name', 'company'])
print(embedding.shape) # (384,)
```

#### `generate_embeddings_batch(records, text_fields=None, batch_size=32, show_progress=False)` → np.ndarray

Generate embeddings for multiple records (more efficient).

**Parameters:**
- `records` (list): List of records
- `text_fields` (list, optional): Fields to use
- `batch_size` (int): Batch size for processing (default: 32)
- `show_progress` (bool): Show progress bar (default: False)

**Returns:** Numpy array of shape `(num_records, embedding_dim)`

**Example:**
```python
records = [
{'name': 'John Smith', 'company': 'Acme'},
{'name': 'Jane Doe', 'company': 'TechCo'}
]
embeddings = service.generate_embeddings_batch(records, batch_size=32)
print(embeddings.shape) # (2, 384)
```

#### `store_embeddings(collection_name, records, embeddings, database_name=None)` → Dict

Store embeddings in ArangoDB collection.

**Parameters:**
- `collection_name` (str): Collection name
- `records` (list): Records (must have `_key` field)
- `embeddings` (np.ndarray): Embeddings array
- `database_name` (str, optional): Database name

**Returns:**
```python
{
"updated": 100,
"failed": 0,
"total": 100
}
```

#### `ensure_embeddings_exist(collection_name, text_fields, database_name=None, batch_size=100, force_regenerate=False)` → Dict

Ensure all documents in collection have embeddings (generates missing ones).

**Parameters:**
- `collection_name` (str): Collection name
- `text_fields` (list): Fields to use for embedding generation
- `database_name` (str, optional): Database name
- `batch_size` (int): Batch size for processing (default: DEFAULT_EMBEDDING_BATCH_SIZE)
- `force_regenerate` (bool): Regenerate all embeddings (default: False)

**Returns:**
```python
{
"total_docs": 1000,
"generated": 250, # Documents that were missing embeddings
"updated": 250,
"failed": 0
}
```

**Example:**
```python
# Generate embeddings for documents that don't have them
stats = service.ensure_embeddings_exist(
'customers',
text_fields=['name', 'company', 'address', 'email'],
batch_size=100
)
print(f"Generated {stats['generated']} new embeddings")
print(f"Coverage: {stats['updated']}/{stats['total_docs']}")
```

#### `get_embedding_stats(collection_name, database_name=None)` → Dict

Get statistics about embeddings in a collection.

**Returns:**
```python
{
"collection": "customers",
"total_documents": 1000,
"with_embeddings": 950,
"without_embeddings": 50,
"coverage_percent": 95.0,
"sample_metadata": {
"model": "all-MiniLM-L6-v2",
"dim": 384,
"timestamp": "2025-12-09T10:30:00Z",
"version": "v1.0"
}
}
```

**Performance:**
- CPU: ~100-500 documents/second
- GPU: ~1000-5000 documents/second
- Memory: Minimal (batch processing)
- Storage: ~1.5 KB per document (384-dim), ~3 KB (768-dim)

**Document Format:**
```javascript
{
"_key": "cust_001",
"name": "John Smith",
"company": "Acme Corp",

// Generated by EmbeddingService
"embedding_vector": [0.12, -0.45, 0.78, ...], // 384 or 768 floats
"embedding_metadata": {
"model": "all-MiniLM-L6-v2",
"dim": 384,
"timestamp": "2025-12-09T10:30:00Z",
"version": "v1.0"
}
}
```

**Configuration:**
See `config/vector_search_setup.md` for detailed configuration guide.

**Research:**
Based on Ebraheem et al. (2018): "Distributed Representations of Tuples for Entity Resolution"
- See: `research/papers/embeddings/2018_Ebraheem_DistributedEntityMatching_notes.md`

**See Also:**
- **Configuration Guide**: `config/vector_search_setup.md` - Setup, model selection, threshold tuning
- **Working Example**: `examples/vector_blocking_example.py` - End-to-end demonstration
- **Source Code**: `src/entity_resolution/services/embedding_service.py` - Implementation with DEFAULT_* constants
- **Source Code**: `src/entity_resolution/strategies/vector_blocking.py` - VectorBlockingStrategy implementation

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
"case": "upper", # or "lower"
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

Bulk creation of similarity edges with metadata tracking and deterministic key generation for idempotent pipelines.

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
batch_size=1000,
use_deterministic_keys=True # Default - prevents duplicates
)

# Safe to run multiple times - no duplicates created
edges_created = service.create_edges(
matches=matches,
metadata={"method": "hybrid", "algorithm": "jaro_winkler"}
)
```

**Deterministic Edge Keys** (default: enabled):
- Same vertex pair always generates same edge key (MD5 hash of `_from + _to`)
- Order-independent: `(A, B)` and `(B, A)` produce same key
- Uses `overwriteMode='ignore'` to prevent duplicates
- Works for both SmartGraph (`"570:12345"`) and non-SmartGraph (`"12345"`) vertex keys
- No shard prefix in edge key - ArangoDB handles placement via `_from` field

#### `__init__(db, edge_collection="similarTo", vertex_collection=None, batch_size=1000, auto_create_collection=True, use_deterministic_keys=True)`

**Parameters:**
- `db` (StandardDatabase): Database connection
- `edge_collection` (str): Edge collection name (default: "similarTo")
- `vertex_collection` (str, optional): Vertex collection for _from/_to formatting
- `batch_size` (int): Edges per batch (default: 1000)
- `auto_create_collection` (bool): Create collection if missing (default: True)
- `use_deterministic_keys` (bool): Generate deterministic edge keys to prevent duplicates (default: True). When enabled, the same vertex pair always generates the same edge key, making edge creation idempotent. Works for both SmartGraph and non-SmartGraph deployments.

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
field_weights={"name": 0.0} # Invalid: all weights zero
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

