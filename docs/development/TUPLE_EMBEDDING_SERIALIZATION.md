# Tuple Embedding Serialization Pipeline and A/B Evaluation Harness

## Overview

This document describes the implementation of the tuple-embedding serialization pipeline and A/B evaluation harness for comparing baseline vs hybrid blocking strategies.

## Components

### 1. TupleEmbeddingSerializer

**Location**: `src/entity_resolution/services/tuple_embedding_serializer.py`

Deterministic serialization of database records for embedding generation. Ensures consistent field ordering and weighting for reproducible embeddings.

#### Key Features

- **Deterministic Field Ordering**: Configurable field order (alphabetical by default)
- **Field Weighting**: Support for importance-based field weights (0.0-1.0)
- **Structured Embedding Paths**: Optional nested field access (e.g., `record["address"]["city"]`)
- **Backward Compatible**: Integrates seamlessly with existing `EmbeddingService`

#### Usage Example

```python
from entity_resolution.services import TupleEmbeddingSerializer, EmbeddingService

# Create serializer with deterministic field ordering
serializer = TupleEmbeddingSerializer(
    field_order=["name", "company", "email"],
    field_weights={"name": 0.5, "company": 0.3, "email": 0.2},
    structured_paths={"address_city": ["address", "city"]}
)

# Use with EmbeddingService
embedding_service = EmbeddingService(serializer=serializer)

# Serialize a record
record = {
    "name": "John Smith",
    "company": "Acme Corp",
    "email": "john@acme.com",
    "address": {"city": "New York"}
}
serialized = serializer.serialize(record)
# Result: "John Smith | Acme Corp | john@acme.com"
```

#### Configuration Options

- `field_order`: Ordered list of field names (None = alphabetical)
- `field_weights`: Dictionary mapping field names to weights (0.0-1.0)
- `structured_paths`: Dictionary mapping field names to nested paths
- `separator`: String separator between fields (default: " | ")
- `normalize_weights`: Whether to normalize weights to sum to 1.0 (default: True)
- `include_missing_fields`: Whether to include missing fields as empty strings (default: False)

### 2. ABEvaluationHarness

**Location**: `src/entity_resolution/services/ab_evaluation_harness.py`

A/B evaluation framework for comparing baseline (traditional) blocking vs hybrid (traditional + embeddings) blocking strategies.

#### Key Features

- **Comprehensive Metrics**: Precision, Recall, F1 Score, Reduction Ratio, Pairs Completeness
- **Performance Metrics**: Execution time, throughput (pairs per second)
- **Output Formats**: JSON and CSV export
- **Ground Truth Support**: Validates and uses labeled ground truth pairs

#### Metrics Calculated

- **Precision**: Correctness of predicted matches (TP / (TP + FP))
- **Recall**: Coverage of true matches (TP / (TP + FN))
- **F1 Score**: Harmonic mean of precision and recall
- **Reduction Ratio**: Percentage of comparisons avoided vs naive approach
- **Pairs Completeness**: Recall at blocking stage
- **Throughput**: Candidate pairs generated per second

#### Usage Example

```python
from entity_resolution.services import ABEvaluationHarness
from entity_resolution.utils.database import DatabaseManager

# Prepare ground truth
ground_truth = [
    {"record_a_id": "1", "record_b_id": "2", "is_match": True},
    {"record_a_id": "3", "record_b_id": "4", "is_match": True},
    {"record_a_id": "5", "record_b_id": "6", "is_match": False}
]

# Create harness
db_manager = DatabaseManager()
harness = ABEvaluationHarness(
    db_manager=db_manager,
    collection_name="customers",
    ground_truth=ground_truth
)

# Define blocking strategies
def baseline_blocking():
    # Traditional blocking implementation
    return {
        "candidate_pairs": [...],
        "execution_time": 1.0
    }

def hybrid_blocking():
    # Hybrid blocking (traditional + embeddings)
    return {
        "candidate_pairs": [...],
        "execution_time": 1.5
    }

# Run A/B evaluation
results = harness.evaluate(
    baseline_strategy=baseline_blocking,
    hybrid_strategy=hybrid_blocking
)

# Save results
harness.save_results(results, output_dir="./evaluation_results")
```

#### Output Formats

**JSON Output** (`ab_evaluation_YYYYMMDD_HHMMSS.json`):
```json
{
  "metadata": {
    "collection": "customers",
    "evaluation_date": "2026-02-01T12:00:00",
    "ground_truth_pairs": 100,
    "true_matches": 50
  },
  "baseline": {
    "precision": 0.85,
    "recall": 0.70,
    "f1_score": 0.77,
    ...
  },
  "hybrid": {
    "precision": 0.90,
    "recall": 0.85,
    "f1_score": 0.87,
    ...
  },
  "improvements": {
    "precision_delta": 0.05,
    "recall_delta": 0.15,
    "f1_delta": 0.10,
    "precision_pct_change": 5.88,
    ...
  }
}
```

**CSV Output** (`ab_evaluation_YYYYMMDD_HHMMSS.csv`):
```csv
Metric,Baseline,Hybrid,Delta,Percent Change
Precision,0.8500,0.9000,0.0500,5.88%
Recall,0.7000,0.8500,0.1500,21.43%
F1 Score,0.7700,0.8700,0.1000,12.99%
...
```

## Integration with EmbeddingService

The `TupleEmbeddingSerializer` is integrated with `EmbeddingService` for backward compatibility:

```python
# Without serializer (backward compatible)
service = EmbeddingService()
embedding = service.generate_embedding(record)

# With serializer (deterministic serialization)
serializer = TupleEmbeddingSerializer(field_order=["name", "company"])
service = EmbeddingService(serializer=serializer)
embedding = service.generate_embedding(record)
```

When a serializer is provided, `EmbeddingService._record_to_text()` uses the serializer instead of the default concatenation method.

## Testing

### Serialization Tests

**Location**: `tests/test_tuple_embedding_serializer.py`

- Deterministic field ordering
- Hash consistency
- Field weighting
- Structured paths
- Missing field handling
- Configuration export/import

### Evaluation Tests

**Location**: `tests/test_ab_evaluation_harness.py`

- Metrics calculation (precision, recall, F1)
- Ground truth validation
- A/B comparison
- JSON/CSV output
- Edge cases (empty ground truth, error handling)

## Backward Compatibility

- `EmbeddingService` works without serializer (default behavior unchanged)
- Existing code continues to work without modifications
- Serializer is optional parameter, defaults to None

## Future Enhancements

- Support for weighted concatenation in serialization (currently weights are stored but not applied)
- Additional evaluation metrics (e.g., ROC-AUC, precision-recall curves)
- Statistical significance testing
- Cross-validation support
