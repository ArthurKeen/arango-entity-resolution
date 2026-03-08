# Quick Start Guide

Current quick start for `arango-entity-resolution` `v3.2.3`.

---

## 1. Install

```bash
pip install arango-entity-resolution
```

Optional extras:

```bash
pip install "arango-entity-resolution[mcp]"
pip install "arango-entity-resolution[llm]"
pip install "arango-entity-resolution[ml]"
```

## 2. Point the Library at ArangoDB

Set the standard environment variables:

```bash
export ARANGO_HOST=localhost
export ARANGO_PORT=8529
export ARANGO_USERNAME=root
export ARANGO_PASSWORD=your-password
export ARANGO_DATABASE=your-database
```

## 3. Run a Pipeline

Create a config file:

```yaml
entity_resolution:
  entity_type: "company"
  collection_name: "companies"
  edge_collection: "companies_similarity_edges"
  cluster_collection: "companies_clusters"
  blocking:
    strategy: "exact"
    fields: ["name", "city"]
  similarity:
    algorithm: "jaro_winkler"
    threshold: 0.85
    field_weights:
      name: 0.7
      city: 0.3
  clustering:
    store_results: true
```

Run it:

```bash
arango-er run --config ./er_config.yaml
```

## 4. Inspect Results

Check the pipeline state:

```bash
arango-er status --collection companies
```

List stored clusters:

```bash
arango-er clusters --collection companies --limit 20
```

## 5. Export Results

```bash
arango-er export --collection companies --output-dir ./exports
```

This writes:
- one JSON export with metadata, stats, and clusters
- one CSV cluster summary with quality fields

## 6. Run a Blocking Benchmark

Create a ground-truth file:

```json
[
  {"record_a_id": "a1", "record_b_id": "a2", "is_match": true}
]
```

Run the benchmark:

```bash
arango-er benchmark \
  --collection companies \
  --ground-truth ./ground_truth.json \
  --baseline-field city \
  --search-view companies_search \
  --search-field name \
  --output-dir ./benchmark_results
```

## 7. Start the MCP Server

For local IDE / Claude Desktop use:

```bash
arango-er-mcp
```

For remote HTTP MCP clients:

```bash
arango-er-mcp --transport sse --port 8080
```

## 8. Enable Advanced Options

### Field Transformers

```yaml
similarity:
  transformers:
    phone: ["e164"]
    state: ["state_code"]
    name: ["company_suffix"]
```

### Active Learning

```yaml
active_learning:
  enabled: true
  feedback_collection: "companies_llm_feedback"
  refresh_every: 25
  low_threshold: 0.55
  high_threshold: 0.80
```

---

## Related Docs

- [API Reference](../api/API_REFERENCE.md)
- [Testing Guide](../TESTING.md)
- [README](../../README.md)
