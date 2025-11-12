# Python API Documentation

## Overview

The Python API provides a complete SDK for entity resolution in Python applications. It supports both direct database access and Foxx service integration for optimal performance.

## Installation

Add the `src` directory to your Python path:

```python
import sys
sys.path.append('/path/to/arango-entity-resolution/src')
```

Or install as a package (if you've created a setup.py):

```bash
cd /path/to/arango-entity-resolution
pip install -e .
```

## Core Components

### EntityResolutionPipeline

Main orchestrator for the complete entity resolution workflow.

```python
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

pipeline = EntityResolutionPipeline()
```

### Services

- **BlockingService**: Record blocking and candidate generation
- **SimilarityService**: Fellegi-Sunter similarity computation
- **ClusteringService**: Graph-based entity clustering
- **DataManager**: Data loading and management

---

## Configuration

### Using Config Object

```python
from entity_resolution.utils.config import Config

config = Config(
    arango_host="localhost",
    arango_port=8529,
    arango_username="root",
    arango_password="your_password",
    arango_database="entity_resolution"
)

pipeline = EntityResolutionPipeline(config=config)
```

### Using Environment Variables

```bash
export ARANGO_HOST=localhost
export ARANGO_PORT=8529
export ARANGO_USERNAME=root
export ARANGO_PASSWORD=your_password
export ARANGO_DATABASE=entity_resolution
```

```python
# Config will automatically use environment variables
pipeline = EntityResolutionPipeline()
```

---

## EntityResolutionPipeline API

### connect()

Initialize connections to ArangoDB and services.

```python
if pipeline.connect():
    print("Connected successfully")
else:
    print("Connection failed")
```

**Returns:** `bool` - True if successful

### load_data(source, collection_name="customers")

Load data from file or DataFrame into ArangoDB.

```python
# From CSV file
result = pipeline.load_data("customers.csv", collection_name="customers")

# From DataFrame
import pandas as pd
df = pd.read_csv("customers.csv")
result = pipeline.load_data(df, collection_name="customers")

# From JSON file
result = pipeline.load_data("customers.json", collection_name="customers")
```

**Parameters:**
- `source` (str | pd.DataFrame): File path or DataFrame
- `collection_name` (str): Target collection name

**Returns:** `Dict[str, Any]`
```python
{
    "success": True,
    "records_imported": 10000,
    "collection": "customers",
    "processing_time": 5.23
}
```

### setup_collections(collection_names)

Set up analyzers and views for collections.

```python
result = pipeline.setup_collections(["customers", "entities"])
```

**Parameters:**
- `collection_names` (List[str]): Collections to set up

**Returns:** `Dict[str, Any]`

### run_complete_pipeline(collection_name, strategies=None, similarity_threshold=0.8, max_candidates=100)

Execute the complete entity resolution pipeline.

```python
results = pipeline.run_complete_pipeline(
    collection_name="customers",
    strategies=["ngram", "exact"],
    similarity_threshold=0.8,
    max_candidates=100
)
```

**Parameters:**
- `collection_name` (str): Collection to process
- `strategies` (List[str], optional): Blocking strategies. Default: ["ngram", "exact"]
- `similarity_threshold` (float, optional): Match threshold. Default: 0.8
- `max_candidates` (int, optional): Max candidates per record. Default: 100

**Returns:** `Dict[str, Any]`
```python
{
    "blocking": {
        "total_candidates": 50000,
        "processing_time": 12.5
    },
    "similarity": {
        "pairs_processed": 50000,
        "matches_found": 5000,
        "processing_time": 45.3
    },
    "clustering": {
        "total_clusters": 1200,
        "valid_clusters": 1180,
        "processing_time": 8.7
    },
    "overall": {
        "total_time": 66.5,
        "records_processed": 10000,
        "duplicate_groups": 1200
    }
}
```

### get_pipeline_stats()

Get statistics from the most recent pipeline run.

```python
stats = pipeline.get_pipeline_stats()
print(f"Total time: {stats['total_time_seconds']}s")
print(f"Clusters found: {stats['clustering']['total_clusters']}")
```

**Returns:** `Dict[str, Any]`

---

## BlockingService API

### Setup

```python
from entity_resolution.services.blocking_service import BlockingService

blocking = BlockingService()
blocking.connect()
```

### setup_for_collections(collections)

Set up analyzers and views for blocking.

```python
result = blocking.setup_for_collections(["customers"])
```

**Parameters:**
- `collections` (List[str]): Collections to set up

**Returns:** `Dict[str, Any]`

### generate_candidates(collection, target_record_id, strategies=None, limit=None)

Generate candidate pairs for a target record.

```python
candidates = blocking.generate_candidates(
    collection="customers",
    target_record_id="customers/12345",
    strategies=["ngram", "exact"],
    limit=100
)
```

**Parameters:**
- `collection` (str): Source collection
- `target_record_id` (str): Target document ID
- `strategies` (List[str], optional): Blocking strategies
- `limit` (int, optional): Maximum candidates

**Returns:** `Dict[str, Any]`
```python
{
    "success": True,
    "candidates": [
        {
            "candidateId": "customers/67890",
            "score": 8.5,
            "matchedFields": ["email", "city"],
            "candidate": { ... }
        }
    ],
    "statistics": {
        "candidate_count": 15,
        "reduction_ratio": 0.9985
    }
}
```

### generate_candidates_batch(collection, target_record_ids, strategies=None, limit=None)

Generate candidates for multiple records in batch.

```python
results = blocking.generate_candidates_batch(
    collection="customers",
    target_record_ids=["customers/123", "customers/456"],
    strategies=["ngram", "exact"],
    limit=100
)
```

**Parameters:**
- `collection` (str): Source collection
- `target_record_ids` (List[str]): Target document IDs (max 100)
- `strategies` (List[str], optional): Blocking strategies
- `limit` (int, optional): Max candidates per target

**Returns:** `Dict[str, Any]`

---

## SimilarityService API

### Setup

```python
from entity_resolution.services.similarity_service import SimilarityService

similarity = SimilarityService()
similarity.connect()
```

### compute_similarity(doc_a, doc_b, field_weights=None, include_details=False)

Compute Fellegi-Sunter similarity between two documents.

```python
doc_a = {
    "first_name": "John",
    "last_name": "Smith",
    "email": "john.smith@example.com",
    "phone": "555-1234"
}

doc_b = {
    "first_name": "Jon",
    "last_name": "Smith",
    "email": "j.smith@example.com",
    "phone": "555-1234"
}

result = similarity.compute_similarity(
    doc_a=doc_a,
    doc_b=doc_b,
    include_details=True
)

print(f"Match decision: {result['similarity']['decision']}")
print(f"Confidence: {result['similarity']['confidence']:.2f}")
```

**Parameters:**
- `doc_a` (Dict[str, Any]): First document
- `doc_b` (Dict[str, Any]): Second document
- `field_weights` (Dict[str, Any], optional): Custom Fellegi-Sunter weights
- `include_details` (bool, optional): Include field-level details

**Returns:** `Dict[str, Any]`
```python
{
    "success": True,
    "similarity": {
        "total_score": 3.45,
        "is_match": True,
        "confidence": 0.89,
        "decision": "match",
        "field_scores": {
            "name_ngram": {
                "similarity": 0.85,
                "agreement": True,
                "weight": 2.1
            }
        }
    }
}
```

### compute_batch_similarity(pairs, field_weights=None, include_details=False)

Compute similarity for multiple document pairs.

```python
pairs = [
    {"docA": doc1, "docB": doc2},
    {"docA": doc3, "docB": doc4}
]

results = similarity.compute_batch_similarity(
    pairs=pairs,
    include_details=False
)

print(f"Matches found: {results['statistics']['matches_found']}")
```

**Parameters:**
- `pairs` (List[Dict[str, Any]]): Document pairs (max 1000)
- `field_weights` (Dict[str, Any], optional): Custom weights
- `include_details` (bool, optional): Include details

**Returns:** `Dict[str, Any]`

### get_default_field_weights()

Get default Fellegi-Sunter field weights configuration.

```python
weights = similarity.get_default_field_weights()
```

**Returns:** `Dict[str, Any]`

### Custom Field Weights

Customize Fellegi-Sunter probabilities for your data:

```python
custom_weights = {
    "email_exact": {
        "m_prob": 0.98,      # P(agreement | match)
        "u_prob": 0.001,     # P(agreement | non-match)
        "threshold": 1.0,    # Agreement threshold
        "importance": 1.5    # Field importance multiplier
    },
    "name_ngram": {
        "m_prob": 0.85,
        "u_prob": 0.02,
        "threshold": 0.7,
        "importance": 1.0
    },
    "global": {
        "upper_threshold": 3.0,   # Clear match
        "lower_threshold": -2.0   # Clear non-match
    }
}

result = similarity.compute_similarity(
    doc_a=doc_a,
    doc_b=doc_b,
    field_weights=custom_weights
)
```

---

## ClusteringService API

### Setup

```python
from entity_resolution.services.clustering_service import ClusteringService

clustering = ClusteringService()
clustering.connect()
```

### build_similarity_graph(scored_pairs, threshold=0.8, edge_collection="similarities")

Build a similarity graph from scored pairs.

```python
scored_pairs = [
    {
        "docA_id": "customers/123",
        "docB_id": "customers/456",
        "total_score": 3.5,
        "is_match": True
    }
]

result = clustering.build_similarity_graph(
    scored_pairs=scored_pairs,
    threshold=0.8,
    edge_collection="similarities"
)

print(f"Created {result['results']['created_count']} edges")
```

**Parameters:**
- `scored_pairs` (List[Dict]): Scored document pairs (max 10,000)
- `threshold` (float, optional): Minimum score threshold. Default: 0.8
- `edge_collection` (str, optional): Edge collection name. Default: "similarities"

**Returns:** `Dict[str, Any]`

### execute_wcc_clustering(edge_collection="similarities", min_similarity=0.8, max_cluster_size=100)

Execute Weakly Connected Components clustering.

```python
clusters = clustering.execute_wcc_clustering(
    edge_collection="similarities",
    min_similarity=0.8,
    max_cluster_size=100
)

print(f"Found {len(clusters['clusters'])} entity clusters")

for cluster in clusters['clusters'][:5]:
    print(f"Cluster {cluster['cluster_id']}: {cluster['cluster_size']} members")
    print(f"  Average similarity: {cluster['average_similarity']:.2f}")
    print(f"  Quality score: {cluster['quality_score']:.2f}")
```

**Parameters:**
- `edge_collection` (str, optional): Similarity edge collection. Default: "similarities"
- `min_similarity` (float, optional): Minimum edge weight. Default: 0.8
- `max_cluster_size` (int, optional): Maximum cluster size. Default: 100

**Returns:** `Dict[str, Any]`
```python
{
    "success": True,
    "clusters": [
        {
            "cluster_id": "cluster_abc123",
            "member_ids": ["customers/123", "customers/456"],
            "cluster_size": 2,
            "average_similarity": 0.92,
            "density": 1.0,
            "quality_score": 0.95,
            "is_valid": True
        }
    ],
    "statistics": {
        "total_clusters": 45,
        "valid_clusters": 43
    }
}
```

### validate_cluster_quality(clusters, quality_thresholds=None)

Validate cluster quality metrics.

```python
validation = clustering.validate_cluster_quality(
    clusters=clusters['clusters'],
    quality_thresholds={
        "min_cluster_size": 2,
        "min_avg_similarity": 0.7,
        "min_density": 0.3
    }
)

print(f"Valid clusters: {validation['statistics']['valid_clusters']}")
```

**Parameters:**
- `clusters` (List[Dict]): Clusters to validate
- `quality_thresholds` (Dict, optional): Custom thresholds

**Returns:** `Dict[str, Any]`

---

## DataManager API

### Setup

```python
from entity_resolution.data.data_manager import DataManager

data_manager = DataManager()
data_manager.connect()
```

### load_data(source, collection_name, batch_size=1000)

Load data from various sources.

```python
# From CSV
result = data_manager.load_data(
    source="customers.csv",
    collection_name="customers",
    batch_size=1000
)

# From JSON
result = data_manager.load_data(
    source="customers.json",
    collection_name="customers"
)

# From DataFrame
import pandas as pd
df = pd.read_csv("customers.csv")
result = data_manager.load_data(
    source=df,
    collection_name="customers"
)
```

**Parameters:**
- `source` (str | pd.DataFrame): Data source
- `collection_name` (str): Target collection
- `batch_size` (int, optional): Batch size for imports. Default: 1000

**Returns:** `Dict[str, Any]`

### get_collection_stats(collection_name)

Get statistics for a collection.

```python
stats = data_manager.get_collection_stats("customers")
print(f"Record count: {stats['count']}")
```

**Parameters:**
- `collection_name` (str): Collection name

**Returns:** `Dict[str, Any]`

### export_clusters(output_file, cluster_collection="entity_clusters")

Export entity clusters to file.

```python
data_manager.export_clusters(
    output_file="entity_clusters.json",
    cluster_collection="entity_clusters"
)
```

**Parameters:**
- `output_file` (str): Output file path
- `cluster_collection` (str, optional): Cluster collection name

---

## Complete Workflow Example

```python
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

# Initialize pipeline
pipeline = EntityResolutionPipeline()

# Connect to ArangoDB
if not pipeline.connect():
    print("Failed to connect to ArangoDB")
    exit(1)

# Load customer data
print("Loading data...")
load_result = pipeline.load_data(
    source="customers.csv",
    collection_name="customers"
)
print(f"Loaded {load_result['records_imported']} records")

# Set up analyzers and views
print("Setting up entity resolution...")
pipeline.setup_collections(["customers"])

# Run complete pipeline
print("Running entity resolution pipeline...")
results = pipeline.run_complete_pipeline(
    collection_name="customers",
    strategies=["ngram", "exact"],
    similarity_threshold=0.8,
    max_candidates=100
)

# Display results
print("\n[RESULTS]")
print(f"Total processing time: {results['overall']['total_time']:.2f}s")
print(f"Records processed: {results['overall']['records_processed']}")
print(f"Entity clusters found: {results['clustering']['total_clusters']}")
print(f"Valid clusters: {results['clustering']['valid_clusters']}")
print(f"Blocking efficiency: {results['blocking']['reduction_ratio']:.2%}")

# Get detailed statistics
stats = pipeline.get_pipeline_stats()
print(f"\nAverage candidates per record: {stats['blocking']['avg_candidates_per_record']:.1f}")
print(f"Match rate: {stats['similarity']['match_rate']:.1%}")
```

---

## Advanced Usage

### Custom Blocking Strategies

```python
from entity_resolution.services.blocking_service import BlockingService

blocking = BlockingService()
blocking.connect()

# Use only exact matching for high-precision blocking
candidates = blocking.generate_candidates(
    collection="customers",
    target_record_id="customers/12345",
    strategies=["exact"],
    limit=50
)

# Use all strategies including phonetic
candidates = blocking.generate_candidates(
    collection="customers",
    target_record_id="customers/12345",
    strategies=["ngram", "exact", "phonetic"],
    limit=200
)
```

### Progressive Entity Resolution

Process records in batches for large datasets:

```python
from entity_resolution.services.blocking_service import BlockingService
from entity_resolution.services.similarity_service import SimilarityService

blocking = BlockingService()
similarity = SimilarityService()

# Get all record IDs
record_ids = ["customers/1", "customers/2", "customers/3", ...]

# Process in batches
batch_size = 100
for i in range(0, len(record_ids), batch_size):
    batch = record_ids[i:i+batch_size]
    
    # Generate candidates for batch
    candidates_result = blocking.generate_candidates_batch(
        collection="customers",
        target_record_ids=batch,
        strategies=["ngram", "exact"],
        limit=100
    )
    
    # Compute similarities for candidates
    # ... (process candidates)
    
    print(f"Processed batch {i//batch_size + 1}")
```

### Integrating with Existing Workflows

```python
# Use entity resolution as part of data pipeline

def process_customer_data(raw_data):
    pipeline = EntityResolutionPipeline()
    pipeline.connect()
    
    # Load raw data
    pipeline.load_data(raw_data, collection_name="raw_customers")
    
    # Run entity resolution
    results = pipeline.run_complete_pipeline(
        collection_name="raw_customers",
        similarity_threshold=0.85
    )
    
    # Export deduplicated data
    deduped_data = export_golden_records(results)
    
    return deduped_data
```

---

## Error Handling

```python
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

pipeline = EntityResolutionPipeline()

try:
    # Connect with error handling
    if not pipeline.connect():
        raise ConnectionError("Failed to connect to ArangoDB")
    
    # Load data with validation
    result = pipeline.load_data("customers.csv", collection_name="customers")
    if not result.get('success', False):
        raise ValueError(f"Data load failed: {result.get('error')}")
    
    # Run pipeline with error handling
    results = pipeline.run_complete_pipeline(
        collection_name="customers",
        similarity_threshold=0.8
    )
    
    if not results.get('success', False):
        raise RuntimeError(f"Pipeline failed: {results.get('error')}")
        
except ConnectionError as e:
    print(f"Connection error: {e}")
    # Handle connection failure
    
except ValueError as e:
    print(f"Validation error: {e}")
    # Handle invalid data
    
except RuntimeError as e:
    print(f"Runtime error: {e}")
    # Handle processing error
    
except Exception as e:
    print(f"Unexpected error: {e}")
    # Handle unexpected errors
    
finally:
    # Cleanup if needed
    pass
```

---

## Performance Tips

### 1. Use Foxx Services for Production

Foxx services provide better performance for large datasets:

```python
# Automatically uses Foxx services when available
pipeline = EntityResolutionPipeline()
```

### 2. Batch Operations

Process records in batches for better throughput:

```python
# Batch candidate generation
blocking.generate_candidates_batch(
    collection="customers",
    target_record_ids=batch_ids,  # 50-100 records per batch
    limit=100
)

# Batch similarity computation
similarity.compute_batch_similarity(
    pairs=candidate_pairs,  # 500-1000 pairs per batch
    include_details=False  # Faster without details
)
```

### 3. Optimize Blocking Strategies

Choose strategies based on your data:

```python
# For clean data: use exact matching
strategies = ["exact"]

# For messy data: use n-gram
strategies = ["ngram"]

# For comprehensive matching: use all
strategies = ["ngram", "exact", "phonetic"]
```

### 4. Tune Similarity Thresholds

Adjust thresholds based on precision/recall needs:

```python
# High precision (fewer false positives)
results = pipeline.run_complete_pipeline(
    collection_name="customers",
    similarity_threshold=0.9  # Higher threshold
)

# High recall (fewer false negatives)
results = pipeline.run_complete_pipeline(
    collection_name="customers",
    similarity_threshold=0.7  # Lower threshold
)
```

---

## Type Hints

The Python API uses type hints for better IDE support:

```python
from typing import Dict, List, Any, Optional

def process_customers(
    file_path: str,
    collection: str = "customers",
    threshold: float = 0.8
) -> Dict[str, Any]:
    pipeline = EntityResolutionPipeline()
    
    if not pipeline.connect():
        return {"success": False, "error": "Connection failed"}
    
    results: Dict[str, Any] = pipeline.run_complete_pipeline(
        collection_name=collection,
        similarity_threshold=threshold
    )
    
    return results
```

---

## Next Steps

- Review [API Examples](./API_EXAMPLES.md) for practical use cases
- See [REST API Reference](./API_REFERENCE.md) for Foxx service endpoints
- Check [OpenAPI Specification](./openapi.yaml) for complete REST API schema
- Try [Quick Start Guide](../README.md#getting-started) for hands-on tutorial

