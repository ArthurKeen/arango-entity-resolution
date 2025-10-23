# Entity Resolution API Reference

## Overview

The ArangoDB Advanced Entity Resolution System provides two complementary APIs for entity resolution:

1. **REST API** (Foxx Services): High-performance ArangoDB-native endpoints for production use
2. **Python API**: Complete SDK for integration, orchestration, and automation

Both APIs provide the same functionality and can be used independently or together.

---

## Table of Contents

- [REST API](#rest-api)
  - [Authentication](#authentication)
  - [Base URL](#base-url)
  - [Endpoints](#endpoints)
- [Python API](#python-api)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [API Reference](#api-reference)
- [Error Handling](#error-handling)
- [Rate Limits](#rate-limits)
- [Examples](#examples)

---

## REST API

### Authentication

The REST API uses HTTP Basic Authentication with your ArangoDB credentials:

```bash
curl -u username:password http://localhost:8529/_db/your_database/entity-resolution/health
```

**Default Credentials:**
- Username: `root`
- Password: Your ArangoDB root password

### Base URL

```
http://<host>:<port>/_db/<database>/entity-resolution
```

**Example:**
```
http://localhost:8529/_db/entity_resolution/entity-resolution
```

### Endpoints

#### System Endpoints

##### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "entity-resolution",
  "version": "1.0.0",
  "timestamp": "2025-10-23T12:00:00.000Z",
  "mode": "production",
  "active_modules": ["setup", "blocking", "similarity", "clustering"]
}
```

##### GET /info

Service information and available endpoints.

**Response:**
```json
{
  "name": "Entity Resolution Service",
  "description": "High-performance entity resolution with record blocking",
  "version": "1.0.0",
  "status": "production",
  "active_endpoints": { ... }
}
```

---

#### Setup Endpoints

##### POST /setup/analyzers

Create custom ArangoSearch analyzers for entity resolution.

**Request Body:** (optional)
```json
{}
```

**Response:**
```json
{
  "success": true,
  "message": "Custom analyzers created successfully",
  "analyzers": {
    "ngram_analyzer": "created",
    "exact_analyzer": "created",
    "phonetic_analyzer": "created"
  },
  "configuration": {
    "ngramLength": 3,
    "phoneticEnabled": true
  }
}
```

**Analyzers Created:**
- `ngram_analyzer`: For typo-tolerant matching (configurable n-gram length)
- `exact_analyzer`: For structured field matching (emails, phones, IDs)
- `phonetic_analyzer`: For name variation matching (optional)

##### POST /setup/views

Create ArangoSearch views for blocking operations.

**Request Body:**
```json
{
  "collections": ["customers", "entities"]
}
```

**Response:**
```json
{
  "success": true,
  "message": "ArangoSearch views created successfully",
  "views": {
    "customers_blocking_view": "created",
    "entities_blocking_view": "created"
  },
  "collections": ["customers", "entities"]
}
```

**View Configuration:**
Each view is configured with multiple analyzers for:
- Names (n-gram, phonetic)
- Addresses (n-gram)
- Emails (exact)
- Phones (exact)
- Companies (n-gram)

##### GET /setup/status

Check entity resolution setup status.

**Response:**
```json
{
  "success": true,
  "status": {
    "analyzers": {
      "ngram_analyzer": true,
      "phonetic_analyzer": true,
      "exact_analyzer": true
    },
    "views": {
      "customers_blocking_view": true
    },
    "collections": {
      "customers": true
    }
  },
  "readiness": {
    "analyzers_ready": true,
    "views_configured": true,
    "collections_available": true,
    "overall_ready": true
  },
  "summary": {
    "analyzers": "3/3 created",
    "views": "1 configured",
    "collections": "1 available"
  }
}
```

##### POST /setup/initialize

Initialize complete entity resolution setup (analyzers + views).

**Request Body:**
```json
{
  "collections": ["customers"],
  "force": false
}
```

**Parameters:**
- `collections` (array, optional): Collections to set up. Default: ["customers"]
- `force` (boolean, optional): Force recreation of existing analyzers/views. Default: false

**Response:**
```json
{
  "success": true,
  "message": "Entity resolution setup initialized successfully",
  "results": {
    "analyzers": { ... },
    "views": { ... },
    "collections": { ... },
    "warnings": []
  },
  "configuration": {
    "ngramLength": 3,
    "collections": ["customers"],
    "force": false
  }
}
```

---

#### Blocking Endpoints

##### POST /blocking/candidates

Generate candidate pairs for a target record using multi-strategy blocking.

**Request Body:**
```json
{
  "collection": "customers",
  "targetDocId": "customers/12345",
  "strategies": ["ngram", "exact"],
  "limit": 100,
  "threshold": 0.1
}
```

**Parameters:**
- `collection` (string, required): Source collection name
- `targetDocId` (string, required): Document ID to find candidates for
- `strategies` (array, optional): Blocking strategies. Options: ["ngram", "exact", "phonetic"]. Default: ["ngram", "exact"]
- `limit` (integer, optional): Maximum candidates to return (1-1000). Default: 100
- `threshold` (number, optional): Minimum BM25 score threshold (0-1). Default: 0.1

**Response:**
```json
{
  "success": true,
  "collection": "customers",
  "targetDocId": "customers/12345",
  "candidates": [
    {
      "candidateId": "customers/67890",
      "targetId": "customers/12345",
      "score": 8.5,
      "matchedFields": ["email", "city"],
      "candidate": {
        "first_name": "John",
        "last_name": "Smith",
        "email": "john.smith@example.com",
        "phone": "555-1234",
        "city": "New York"
      }
    }
  ],
  "statistics": {
    "candidate_count": 15,
    "total_possible_pairs": 9999,
    "reduction_ratio": 0.9985,
    "processing_time_ms": 45
  },
  "strategies_used": ["ngram", "exact"],
  "parameters": {
    "limit": 100,
    "threshold": 0.1
  }
}
```

**Performance Note:** Record blocking typically reduces comparisons by 99%+ vs. naive pairwise comparison.

##### POST /blocking/candidates/batch

Generate candidates for multiple target records in batch.

**Request Body:**
```json
{
  "collection": "customers",
  "targetDocIds": ["customers/123", "customers/456"],
  "strategies": ["ngram", "exact"],
  "limit": 100,
  "threshold": 0.1
}
```

**Parameters:**
- `collection` (string, required): Source collection name
- `targetDocIds` (array, required): Array of document IDs (max 100)
- `strategies` (array, optional): Blocking strategies. Default: ["ngram", "exact"]
- `limit` (integer, optional): Maximum candidates per target. Default: 100
- `threshold` (number, optional): Minimum score threshold. Default: 0.1

**Response:**
```json
{
  "success": true,
  "collection": "customers",
  "batch_size": 2,
  "results": [
    {
      "targetDocId": "customers/123",
      "candidates": [...],
      "candidate_count": 15,
      "success": true
    },
    {
      "targetDocId": "customers/456",
      "candidates": [...],
      "candidate_count": 12,
      "success": true
    }
  ],
  "statistics": {
    "successful_targets": 2,
    "failed_targets": 0,
    "total_candidates": 27,
    "average_candidates_per_target": 13.5,
    "reduction_ratio": 0.9987,
    "processing_time_ms": 78
  }
}
```

##### GET /blocking/strategies

Get available blocking strategies and their configurations.

**Response:**
```json
{
  "success": true,
  "strategies": {
    "ngram": {
      "name": "N-gram Blocking",
      "description": "Uses n-gram tokens for typo-tolerant blocking",
      "analyzer": "ngram_analyzer",
      "ngram_length": 3,
      "fields": ["first_name", "last_name", "full_name", "address", "company"],
      "advantages": ["Typo tolerance", "Character-level matching", "Language independent"],
      "best_for": "Names and addresses with potential spelling variations"
    },
    "exact": {
      "name": "Exact Blocking",
      "description": "Uses exact string matching with normalization",
      "analyzer": "exact_analyzer",
      "fields": ["email", "phone", "ssn", "id_number"],
      "advantages": ["High precision", "Fast processing", "No false positives"],
      "best_for": "Structured fields like emails, phone numbers, IDs"
    },
    "phonetic": {
      "name": "Phonetic Blocking",
      "description": "Uses phonetic algorithms for name variations",
      "analyzer": "phonetic_analyzer",
      "fields": ["first_name", "last_name", "full_name"],
      "advantages": ["Pronunciation variations", "Cultural name differences", "Nickname matching"],
      "best_for": "Person names with phonetic variations"
    }
  },
  "configuration": {
    "ngram_length": 3,
    "phonetic_enabled": true,
    "default_limit": 100
  },
  "recommended_combinations": [
    {
      "name": "Standard Person Matching",
      "strategies": ["ngram", "exact"],
      "description": "Good for person records with names and contact info"
    },
    {
      "name": "Enhanced Person Matching",
      "strategies": ["ngram", "exact", "phonetic"],
      "description": "Comprehensive matching including phonetic variations"
    },
    {
      "name": "High Precision Matching",
      "strategies": ["exact"],
      "description": "Conservative matching for high-quality data"
    }
  ]
}
```

##### GET /blocking/stats/:collection

Get blocking performance statistics for a collection.

**Parameters:**
- `collection` (string, required): Collection name

**Response:**
```json
{
  "success": true,
  "collection": "customers",
  "view": "customers_blocking_view",
  "statistics": {
    "record_count": 10000,
    "total_possible_pairs": 49995000,
    "view_properties": { ... },
    "complexity_note": "Without blocking, 49,995,000 comparisons would be needed",
    "blocking_benefit": "Reduces comparisons by 90-99% typically"
  },
  "performance_estimates": {
    "pairs_with_10_percent_blocking": 4999500,
    "pairs_with_5_percent_blocking": 2499750,
    "pairs_with_1_percent_blocking": 499950
  }
}
```

---

#### Similarity Endpoints

##### POST /similarity/compute

Compute similarity score between two documents using Fellegi-Sunter framework.

**Request Body:**
```json
{
  "docA": {
    "first_name": "John",
    "last_name": "Smith",
    "email": "john.smith@example.com",
    "phone": "555-1234",
    "address": "123 Main St",
    "city": "New York"
  },
  "docB": {
    "first_name": "Jon",
    "last_name": "Smith",
    "email": "j.smith@example.com",
    "phone": "555-1234",
    "address": "123 Main Street",
    "city": "New York"
  },
  "fieldWeights": null,
  "includeDetails": true
}
```

**Parameters:**
- `docA` (object, required): First document to compare
- `docB` (object, required): Second document to compare
- `fieldWeights` (object, optional): Custom Fellegi-Sunter weights. Default: null (use defaults)
- `includeDetails` (boolean, optional): Include field-level details. Default: false

**Response:**
```json
{
  "success": true,
  "similarity": {
    "total_score": 3.45,
    "is_match": true,
    "is_possible_match": false,
    "confidence": 0.89,
    "decision": "match",
    "field_scores": {
      "name_ngram": {
        "similarity": 0.85,
        "agreement": true,
        "weight": 2.1,
        "threshold": 0.7
      },
      "email_exact": {
        "similarity": 0.0,
        "agreement": false,
        "weight": -0.8,
        "threshold": 1.0
      },
      "phone_exact": {
        "similarity": 1.0,
        "agreement": true,
        "weight": 2.15,
        "threshold": 1.0
      }
    },
    "thresholds": {
      "upper_threshold": 2.0,
      "lower_threshold": -1.0
    }
  },
  "processing_time_ms": 12,
  "field_weights_used": { ... }
}
```

**Decision Logic:**
- `match`: total_score > upper_threshold (default 2.0)
- `possible_match`: lower_threshold < total_score <= upper_threshold
- `non_match`: total_score <= lower_threshold (default -1.0)

##### POST /similarity/batch

Compute similarity for multiple document pairs in batch.

**Request Body:**
```json
{
  "pairs": [
    {
      "docA": { ... },
      "docB": { ... }
    },
    {
      "docA": { ... },
      "docB": { ... }
    }
  ],
  "fieldWeights": null,
  "includeDetails": false,
  "threshold": 0.8
}
```

**Parameters:**
- `pairs` (array, required): Array of document pairs (max 1000)
- `fieldWeights` (object, optional): Custom Fellegi-Sunter weights
- `includeDetails` (boolean, optional): Include field details. Default: false
- `threshold` (number, optional): Match threshold (0-1). Default: 0.8

**Response:**
```json
{
  "success": true,
  "batch_size": 100,
  "results": [
    {
      "index": 0,
      "success": true,
      "docA_id": "inline_0_A",
      "docB_id": "inline_0_B",
      "similarity": { ... }
    }
  ],
  "statistics": {
    "successful_computations": 98,
    "failed_computations": 2,
    "matches_found": 45,
    "match_rate": 0.46,
    "average_score": 1.23,
    "processing_time_ms": 234
  },
  "threshold_used": 0.8,
  "field_weights_used": { ... }
}
```

##### GET /similarity/functions

Get available similarity functions and recommended usage strategies.

**Response:**
```json
{
  "success": true,
  "similarity_functions": {
    "ngram_similarity": {
      "name": "N-gram Similarity",
      "description": "Computes similarity based on n-gram overlap",
      "function": "NGRAM_SIMILARITY(str1, str2, n)",
      "parameters": ["string1", "string2", "ngram_length"],
      "return_type": "number (0.0 to 1.0)",
      "best_for": "Text fields with potential typos",
      "example": "NGRAM_SIMILARITY(\"John Smith\", \"Jon Smith\", 3) -> 0.75"
    },
    "levenshtein_distance": {
      "name": "Levenshtein Distance",
      "description": "Computes edit distance between strings",
      "function": "LEVENSHTEIN_DISTANCE(str1, str2)",
      "parameters": ["string1", "string2"],
      "return_type": "number (0 to max_string_length)",
      "best_for": "Measuring exact differences between strings",
      "example": "LEVENSHTEIN_DISTANCE(\"kitten\", \"sitting\") -> 3"
    }
  },
  "field_strategies": {
    "names": {
      "recommended_functions": ["ngram_similarity", "normalized_levenshtein"],
      "typical_threshold": 0.7,
      "considerations": "Names often have variations, nicknames, and cultural differences"
    },
    "emails": {
      "recommended_functions": ["exact_match"],
      "typical_threshold": 1.0,
      "considerations": "Emails should match exactly or not at all"
    }
  },
  "default_configuration": { ... },
  "implementation_notes": {
    "performance": "ArangoDB native functions are optimized for large datasets",
    "accuracy": "Combine multiple functions for robust similarity scoring",
    "tuning": "Adjust thresholds based on data quality and business requirements"
  }
}
```

---

#### Clustering Endpoints

##### POST /clustering/build-graph

Build a similarity graph from scored document pairs.

**Request Body:**
```json
{
  "scoredPairs": [
    {
      "docA_id": "customers/123",
      "docB_id": "customers/456",
      "total_score": 3.5,
      "field_scores": { ... },
      "is_match": true
    }
  ],
  "threshold": 0.8,
  "edgeCollection": "similarities",
  "forceUpdate": false
}
```

**Parameters:**
- `scoredPairs` (array, required): Scored document pairs (max 10,000)
- `threshold` (number, optional): Minimum score to create edge. Default: 0.8
- `edgeCollection` (string, optional): Edge collection name. Default: "similarities"
- `forceUpdate` (boolean, optional): Force update existing edges. Default: false

**Response:**
```json
{
  "success": true,
  "edge_collection": "similarities",
  "results": {
    "created_count": 85,
    "updated_count": 12,
    "skipped_count": 3,
    "errors": []
  },
  "statistics": {
    "input_pairs": 100,
    "threshold_used": 0.8,
    "processing_time_ms": 145
  }
}
```

**Note:** Uses UPSERT for idempotent edge creation. Existing edges are updated with new scores unless forceUpdate is false.

##### POST /clustering/wcc

Execute Weakly Connected Components (WCC) clustering on similarity graph.

**Request Body:**
```json
{
  "edgeCollection": "similarities",
  "minSimilarity": 0.8,
  "maxClusterSize": 100,
  "outputCollection": "entity_clusters"
}
```

**Parameters:**
- `edgeCollection` (string, optional): Similarity edge collection. Default: "similarities"
- `minSimilarity` (number, optional): Minimum edge weight threshold. Default: 0.8
- `maxClusterSize` (integer, optional): Maximum cluster size (2-1000). Default: 100
- `outputCollection` (string, optional): Output collection for clusters. Default: "entity_clusters"

**Response:**
```json
{
  "success": true,
  "edge_collection": "similarities",
  "output_collection": "entity_clusters",
  "clusters": [
    {
      "cluster_id": "cluster_abc123",
      "member_ids": ["customers/123", "customers/456", "customers/789"],
      "cluster_size": 3,
      "edge_count": 3,
      "average_similarity": 0.92,
      "min_similarity": 0.85,
      "max_similarity": 0.98,
      "density": 1.0,
      "created_at": 1698067200000,
      "quality_score": 0.95,
      "quality_metrics": {
        "size_appropriate": true,
        "similarity_coherent": true,
        "density_adequate": true,
        "score_range_reasonable": true
      },
      "is_valid": true
    }
  ],
  "storage_results": {
    "stored_count": 45,
    "errors": []
  },
  "statistics": {
    "total_clusters": 45,
    "valid_clusters": 43,
    "average_cluster_size": 2.8,
    "largest_cluster_size": 12,
    "processing_time_ms": 567
  },
  "parameters": {
    "min_similarity": 0.8,
    "max_cluster_size": 100
  }
}
```

**Quality Metrics:**
- `density`: Edge count / theoretical maximum edges
- `quality_score`: Fraction of quality checks passed
- `is_valid`: Overall cluster validity

##### POST /clustering/validate

Validate cluster quality and coherence.

**Request Body:**
```json
{
  "clusters": [ ... ],
  "qualityThresholds": {
    "min_cluster_size": 2,
    "max_cluster_size": 50,
    "min_avg_similarity": 0.7,
    "min_density": 0.3,
    "max_score_range": 0.5,
    "min_quality_score": 0.6
  }
}
```

**Parameters:**
- `clusters` (array, required): Clusters to validate
- `qualityThresholds` (object, optional): Custom quality thresholds

**Response:**
```json
{
  "success": true,
  "validation_results": [
    {
      "cluster_id": "cluster_abc123",
      "quality_metrics": {
        "size_appropriate": true,
        "similarity_coherent": true,
        "density_adequate": true,
        "score_range_reasonable": true
      },
      "quality_score": 1.0,
      "quality_issues": [],
      "is_valid": true
    }
  ],
  "statistics": {
    "total_clusters": 45,
    "valid_clusters": 43,
    "invalid_clusters": 2,
    "overall_quality_score": 0.87,
    "validation_pass_rate": 0.96,
    "processing_time_ms": 89
  },
  "quality_thresholds": { ... },
  "recommendations": [
    {
      "type": "quality_improvement",
      "message": "2 clusters failed quality validation",
      "suggestion": "Review similarity thresholds and clustering parameters"
    }
  ]
}
```

##### GET /clustering/stats/:edgeCollection

Get clustering statistics for similarity graph.

**Parameters:**
- `edgeCollection` (string, required): Edge collection name

**Response:**
```json
{
  "success": true,
  "edge_collection": "similarities",
  "statistics": {
    "total_edges": 1234,
    "average_similarity": 0.87,
    "min_similarity": 0.70,
    "max_similarity": 0.99,
    "unique_vertices": 567,
    "average_degree": 4.35,
    "max_degree": 15
  }
}
```

---

## Python API

### Installation

The Python API is included in the project. Add the `src` directory to your Python path:

```python
import sys
sys.path.append('/path/to/arango-entity-resolution/src')

from entity_resolution.core.entity_resolver import EntityResolutionPipeline
```

### Quick Start

```python
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

# Initialize pipeline
pipeline = EntityResolutionPipeline()

# Connect to ArangoDB
if not pipeline.connect():
    print("Failed to connect")
    exit(1)

# Load data
result = pipeline.load_data("customers.csv", collection_name="customers")
print(f"Loaded {result['records_imported']} records")

# Run complete pipeline
results = pipeline.run_complete_pipeline(
    collection_name="customers",
    strategies=["ngram", "exact"],
    similarity_threshold=0.8
)

print(f"Found {results['clustering']['total_clusters']} entity clusters")
```

### API Reference

See [Python API Documentation](./API_PYTHON.md) for complete reference.

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | Success | Request completed successfully |
| 400 | Bad Request | Invalid parameters or malformed request |
| 404 | Not Found | Collection, view, or resource not found |
| 500 | Internal Server Error | Server-side error during processing |

### Error Response Format

All error responses follow this format:

```json
{
  "success": false,
  "error": "Detailed error message",
  "code": "ERROR_CODE"
}
```

### Common Error Codes

| Code | Cause | Solution |
|------|-------|----------|
| `MISSING_PARAMETERS` | Required parameters not provided | Check request body/params |
| `COLLECTION_NOT_FOUND` | Collection doesn't exist | Create collection first |
| `VIEW_NOT_FOUND` | ArangoSearch view doesn't exist | Run setup/initialize |
| `BATCH_SIZE_EXCEEDED` | Too many items in batch request | Reduce batch size |
| `EDGE_COLLECTION_NOT_FOUND` | Edge collection doesn't exist | Run clustering/build-graph first |
| `SIMILARITY_COMPUTATION_FAILED` | Error computing similarity | Check document format |
| `WCC_CLUSTERING_FAILED` | Error during clustering | Check edge collection |

### Error Handling Best Practices

1. **Always check `success` field** in responses
2. **Log error codes** for troubleshooting
3. **Implement retries** for transient errors (500)
4. **Validate data** before sending to API
5. **Use try-catch** blocks in production code

**Example:**
```python
try:
    response = requests.post(url, json=data, auth=auth)
    result = response.json()
    
    if not result.get('success', False):
        print(f"Error: {result.get('error')} (Code: {result.get('code')})")
        # Handle error appropriately
    else:
        # Process successful result
        pass
        
except requests.RequestException as e:
    print(f"Network error: {e}")
    # Implement retry logic
```

---

## Rate Limits

**Current Implementation:** No rate limits enforced

**Best Practices:**
- Batch operations when possible
- Use appropriate batch sizes (100-1000 items)
- Implement exponential backoff for retries
- Monitor processing times and adjust accordingly

**Batch Size Recommendations:**

| Operation | Recommended Batch Size | Maximum |
|-----------|----------------------|---------|
| Candidate Generation | 50-100 targets | 100 |
| Similarity Computation | 500-1000 pairs | 1000 |
| Graph Building | 5000-10000 pairs | 10000 |

---

## Examples

See [API Examples](./API_EXAMPLES.md) for comprehensive usage examples including:
- Complete entity resolution workflow
- Custom similarity scoring
- Advanced clustering scenarios
- Integration patterns
- Error handling examples

---

## Support

For issues and questions:
- GitHub Issues: [Project Repository](https://github.com/yourusername/arango-entity-resolution)
- Documentation: Check `docs/` directory
- Examples: See `examples/` directory

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-10-23 | Initial production release |

---

## Next Steps

1. Review [API Examples](./API_EXAMPLES.md) for common use cases
2. Check [Python API Documentation](./API_PYTHON.md) for SDK details
3. See [OpenAPI Specification](./openapi.yaml) for complete REST API schema
4. Try [Quick Start Guide](../README.md#getting-started) for hands-on tutorial

