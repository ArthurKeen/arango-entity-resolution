# Blocking Benchmarks

This project now supports one official benchmark workflow for evaluator-facing
blocking comparisons.

## Supported Command

Use `arango-er benchmark` to compare:

- baseline: exact COLLECT-based blocking
- comparison: BM25 ArangoSearch blocking

Example:

```bash
arango-er benchmark \
  --collection companies \
  --ground-truth ./ground_truth.json \
  --baseline-field name \
  --search-view companies_search \
  --search-field name \
  --output-dir ./benchmark_results
```

## Ground Truth Format

JSON:

```json
[
  {"record_a_id": "1", "record_b_id": "2", "is_match": true}
]
```

CSV:

```csv
record_a_id,record_b_id,is_match
1,2,true
3,4,false
```

## Output Artifacts

Each benchmark run writes:

- one JSON report with metadata, baseline metrics, hybrid metrics, and deltas
- one CSV comparison table suitable for evaluator review

## What To Record

For release or evaluator reporting, record:

- dataset and collection name
- ground-truth source
- baseline exact fields
- BM25 search view and search field
- runtime and throughput
- precision, recall, F1, and reduction ratio
