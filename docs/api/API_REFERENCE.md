# API Reference - v3.2.3

Current reference for the shipped public surface of `arango-entity-resolution`.

This document focuses on the interfaces users are most likely to touch directly:

- CLI entrypoints
- MCP server entrypoints
- configuration-driven pipelines
- core Python services

For deeper historical notes, see `VERSION_HISTORY.md` and older planning documents in `docs/`.

---

## Installation Extras

```bash
pip install arango-entity-resolution
pip install "arango-entity-resolution[mcp]"
pip install "arango-entity-resolution[llm]"
pip install "arango-entity-resolution[ml]"
```

## Entry Points

| Command | Purpose |
|---------|---------|
| `arango-er` | Run pipelines and use the current CLI surface |
| `arango-er-demo` | Launch the interactive demo |
| `arango-er-mcp` | Start the MCP server |

---

## CLI Reference

### `arango-er run`

Run a configuration-driven entity-resolution pipeline.

```bash
arango-er run --config config/er_config.example.yaml
```

Common connection overrides:

```bash
arango-er run --config my_config.yaml \
  --database mydb --host localhost --port 8529 -u root -p secret
```

### `arango-er status`

Inspect the current ER state for a collection.

```bash
arango-er status --collection companies
```

Returns a JSON summary including:
- `total_documents`
- `edge_stats`
- `cluster_count`
- collection names used for edges and clusters

### `arango-er clusters`

List stored clusters and their quality signals.

```bash
arango-er clusters --collection companies --limit 20 --min-size 2
```

Returns cluster entries containing:
- `cluster_id`
- `members`
- `size`
- `representative`
- `edge_count`
- `average_similarity`
- `min_similarity`
- `max_similarity`
- `density`
- `quality_score`

### `arango-er export`

Export stored clusters and pipeline statistics to JSON and CSV.

```bash
arango-er export --collection companies --output-dir ./exports
```

Output artifacts:
- one JSON envelope with `metadata`, `stats`, and `clusters`
- one flat CSV summary with cluster-level quality fields

### `arango-er benchmark`

Run the supported exact-vs-BM25 blocking benchmark workflow.

```bash
arango-er benchmark \
  --collection companies \
  --ground-truth ./ground_truth.json \
  --baseline-field city \
  --search-view companies_search \
  --search-field name \
  --output-dir ./benchmark_results
```

This command is built on `ABEvaluationHarness` and writes JSON/CSV benchmark artifacts.

---

## MCP Server Reference

Start the MCP server:

```bash
arango-er-mcp
arango-er-mcp --transport sse --port 8080
```

### Tools

- `list_collections`
- `find_duplicates`
- `pipeline_status`
- `resolve_entity`
- `explain_match`
- `get_clusters`
- `merge_entities`

### Resources

- `arango://collections/{collection}/summary`
- `arango://clusters/{collection}/{key}`

Use `stdio` for Claude Desktop and local IDE integrations. Use SSE only for clients that support remote HTTP MCP connections.

---

## Configuration-Driven Pipeline

Primary classes:

```python
from entity_resolution.config.er_config import ERPipelineConfig
from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline
```

### Key Config Objects

- `BlockingConfig`
- `SimilarityConfig`
- `ClusteringConfig`
- `ActiveLearningConfig`
- `ERPipelineConfig`

### Example

```python
from entity_resolution.config.er_config import (
    BlockingConfig,
    ClusteringConfig,
    ERPipelineConfig,
    SimilarityConfig,
)
from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline

cfg = ERPipelineConfig(
    entity_type="company",
    collection_name="companies",
    edge_collection="companies_similarity_edges",
    cluster_collection="companies_clusters",
    blocking=BlockingConfig(strategy="exact", fields=["name", "city"]),
    similarity=SimilarityConfig(
        threshold=0.85,
        field_weights={"name": 0.7, "city": 0.3},
        transformers={"name": ["company_suffix"], "state": ["state_code"]},
    ),
    clustering=ClusteringConfig(store_results=True),
)

pipeline = ConfigurableERPipeline(db=db, config=cfg)
results = pipeline.run()
```

---

## Python Services

### Blocking

- `CollectBlockingStrategy`
- `BM25BlockingStrategy`
- `VectorBlockingStrategy`
- `HybridBlockingStrategy`
- `GeographicBlockingStrategy`
- `GraphTraversalBlockingStrategy`

### Similarity and Matching

- `WeightedFieldSimilarity`
- `BatchSimilarityService`
- `SimilarityEdgeService`
- `IncrementalResolver`

### Clustering and Consolidation

- `WCCClusteringService`
- `GoldenRecordPersistenceService`

### Reporting and Evaluation

- `ClusterExportService`
- `ABEvaluationHarness`
- `run_blocking_benchmark()`

### LLM / Reasoning

- `LLMMatchVerifier`
- `AdaptiveLLMVerifier`
- `FeedbackStore`
- `ThresholdOptimizer`

---

## Data Shapes

### Candidate Pair Shape

Blocking strategies typically return:

```python
{
    "doc1_key": "a1",
    "doc2_key": "a2",
    "method": "collect_blocking",
}
```

### Ground-Truth Shape for Benchmarks

```json
[
  {"record_a_id": "a1", "record_b_id": "a2", "is_match": true}
]
```

### Exported Cluster Shape

```json
{
  "cluster_id": "cluster_000001",
  "size": 2,
  "member_keys": ["a1", "a2"],
  "edge_count": 1,
  "average_similarity": 0.91,
  "density": 1.0,
  "quality_score": 0.95
}
```

---

## Related Documentation

- [Quick Start Guide](../guides/QUICK_START.md)
- [Testing Guide](../TESTING.md)
- [Blocking Benchmarks](../development/BLOCKING_BENCHMARKS.md)
- [README](../../README.md)
