# ArangoDB Entity Resolution

A production-ready entity resolution system for ArangoDB that identifies and links records referring to the same real-world entity across multiple data sources. Uses record blocking, graph algorithms, and AI to scale from thousands to millions of records.

**Version 3.5.1** | [Changelog](CHANGELOG.md) | [Version History](VERSION_HISTORY.md) | [PyPI](https://pypi.org/project/arango-entity-resolution/)

## Installation

```bash
pip install arango-entity-resolution

# With optional features
pip install "arango-entity-resolution[mcp]"       # MCP server for AI agents
pip install "arango-entity-resolution[llm]"       # LLM match verification
pip install "arango-entity-resolution[ml]"        # Vector embeddings (sentence-transformers)
pip install "arango-entity-resolution[mcp,llm,ml]"  # Everything
```

## Quick Start

### CLI

```bash
# Run a pipeline from YAML config
arango-er run --config config/er_config.example.yaml

# Inspect clusters
arango-er status --collection companies
arango-er clusters --collection companies --limit 20

# Export results
arango-er export --collection companies --output-dir ./exports
```

### Python

```python
from entity_resolution import ConfigurableERPipeline, ERPipelineConfig

config = ERPipelineConfig.from_yaml("config/er_config.example.yaml")
pipeline = ConfigurableERPipeline(config=config, db=db)
results = pipeline.run()

print(f"Candidates: {results['blocking']['candidates_found']}")
print(f"Clusters:   {results['clustering']['clusters_found']}")
```

### MCP Server (AI Agent Integration)

```bash
# stdio for Claude Desktop / Cursor
arango-er-mcp

# SSE for remote clients
arango-er-mcp --transport sse --port 8080
```

Exposes 7 tools (`find_duplicates`, `resolve_entity`, `explain_match`, `get_clusters`, `merge_entities`, `pipeline_status`, `list_collections`) and 2 resources for any MCP-compatible AI agent.

## How It Works

Entity resolution runs as a multi-stage pipeline, each stage narrowing candidates and increasing precision:

```
Data Sources → Blocking → Similarity → Clustering → Golden Records
                 ↓            ↓            ↓
              99%+ pair    Field-level   Graph-based
              reduction    scoring       grouping
```

**Stage 1 — Record Blocking** reduces O(n²) comparisons to O(n) using ArangoSearch full-text indexes, phonetic matching, n-gram overlap, vector similarity, and geographic proximity.

**Stage 2 — Similarity Scoring** computes field-level similarity (Jaro-Winkler, Levenshtein, Jaccard) with configurable weights and a Fellegi-Sunter probabilistic framework.

**Stage 3 — Clustering** groups matched pairs into entity clusters using Weakly Connected Components with pluggable backends (Union-Find, DFS, scipy sparse, AQL graph, or GAE enterprise).

**Stage 4 — Golden Record Generation** fuses cluster members into authoritative master records with source ranking, conflict resolution, and full audit trail.

Optional AI stages can be inserted into the pipeline:

- **LLM Match Verification** — auto-calls an LLM for ambiguous pairs in the 0.55–0.80 confidence range
- **GraphRAG Entity Extraction** — extracts entities from unstructured documents and links them to the graph
- **Geospatial-Temporal Validation** — confirms or rejects matches based on location and time feasibility

## Key Features

### Blocking Strategies
| Strategy | Use Case |
|----------|----------|
| **Exact / COLLECT** | High-precision blocking on email, phone, composite keys |
| **BM25 / ArangoSearch** | Fuzzy text matching (400x faster than Levenshtein) |
| **Vector / ANN** | Semantic similarity via sentence-transformers embeddings |
| **Geographic** | Proximity-based blocking with coordinate distance |
| **LSH** | Locality-sensitive hashing for high-dimensional data |
| **Graph Traversal** | Shared-identifier network analysis |
| **Shard-Parallel** | Optimised for sharded ArangoDB clusters |

### Clustering Backends
| Backend | Best For |
|---------|----------|
| `python_union_find` | General purpose (default via `auto`) |
| `python_dfs` | Reliable DFS traversal |
| `python_sparse` | Very large dense graphs (scipy) |
| `aql_graph` | Server-side processing |
| `gae_wcc` | Enterprise-scale via Graph Analytics Engine |

### AI & Agent Integration
- **MCP Server** — 7 tools + 2 resources for Claude, Gemini, GPT-4, Cursor
- **LLM Verification** — OpenRouter, OpenAI, Anthropic, Ollama via litellm
- **ONNX Runtime** — faster CPU inference for embedding workloads
- **Incremental Resolver** — real-time single-record matching without batch re-run
- **Active Learning** — feedback loop with adaptive threshold optimization

## Configuration

Pipelines are driven by YAML (or JSON) configuration:

```yaml
entity_resolution:
  entity_type: company
  collection: companies

  blocking:
    strategy: collect
    fields:
      - field: state
      - field: city

  similarity:
    algorithm: jaro_winkler
    threshold: 0.80
    fields:
      name: 0.40
      address: 0.30
      phone: 0.20
      email: 0.10

  clustering:
    backend: auto          # picks best available backend
    min_cluster_size: 2
    store_results: true
```

See [`config/er_config.example.yaml`](config/er_config.example.yaml) for a complete example with all options.

## Why ArangoDB?

Entity resolution requires document storage, graph traversal, full-text search, and vector similarity — typically needing 3–4 separate systems. ArangoDB handles all of these natively:

- **Documents** — flexible schema for heterogeneous source records
- **Graphs** — native WCC, traversals, and relationship modeling
- **ArangoSearch** — integrated full-text search with phonetic, n-gram, and BM25 analyzers
- **Vectors** — embedding storage and ANN search in ArangoDB 3.12+

This eliminates the integration overhead of Elasticsearch + Neo4j + PostgreSQL stacks and keeps blocking, similarity, clustering, and golden records in a single transactional system.

## Performance

Record blocking reduces quadratic comparisons to linear:

| Records | Naive Pairs | After Blocking | Time |
|---------|-------------|----------------|------|
| 10K | 50M | 500K | ~2s |
| 100K | 5B | 5M | ~20s |
| 1M | 500B | 50M | ~3min |

Clustering backends scale from Union-Find (general purpose) through scipy sparse (large dense graphs) to GAE enterprise (millions of edges on dedicated compute).

## Project Structure

```
src/entity_resolution/
├── core/           Entity resolver, configurable pipeline, incremental resolver, orchestrator
├── services/       Blocking, similarity, clustering, embedding, export services
│   └── clustering_backends/   Union-Find, DFS, Sparse, AQL, GAE
├── strategies/     Exact, BM25, vector, geographic, LSH, shard-parallel blocking
├── mcp/            MCP server (7 tools, 2 resources)
├── reasoning/      LLM verifier, GraphRAG, feedback/active learning
├── enrichments/    Type constraints, context resolver, acronym handler, provenance sweeper
├── etl/            Canonical resolver, normalizers, arangoimport integration
├── similarity/     Weighted field similarity, geospatial/temporal validators
├── config/         YAML/JSON pipeline configuration
└── utils/          Database, logging, validation, constants
```

## Documentation

| Resource | Description |
|----------|-------------|
| [Documentation Index](docs/README.md) | Complete navigation |
| [Quick Start](docs/guides/QUICK_START.md) | Get started in 5 minutes |
| [API Reference](docs/api/API_REFERENCE.md) | CLI, MCP, Python, and config reference |
| [Advanced Modules Guide](docs/guides/ADVANCED_MODULES_GUIDE.md) | Orchestrator, GraphRAG, geospatial, feedback, ETL |
| [Performance Guide](docs/guides/PERFORMANCE_GUIDE.md) | Tuning and scaling |
| [Platform Setup](docs/guides/PLATFORM_SETUP.md) | ArangoDB, Docker, and provider setup |
| [Provider Matrix](docs/guides/PROVIDER_MATRIX.md) | LLM and embedding provider comparison |
| [Migration Guide](docs/guides/MIGRATION_GUIDE_V3.md) | Upgrading from v1.x or v2.x |
| [PRD](docs/PRD.md) | Product requirements and roadmap |

## Examples

| Example | Description |
|---------|-------------|
| [`yaml_config_pipeline.py`](examples/yaml_config_pipeline.py) | Config-driven end-to-end pipeline |
| [`clustering_backend_comparison.py`](examples/clustering_backend_comparison.py) | Compare all clustering backends |
| [`multi_strategy_orchestration.py`](examples/multi_strategy_orchestration.py) | Union/intersection blocking modes |
| [`onnx_runtime_embedding.py`](examples/onnx_runtime_embedding.py) | ONNX export and fast inference |
| [`incremental_resolution.py`](examples/incremental_resolution.py) | Real-time streaming resolution |
| [`ollama_llm_verification.py`](examples/ollama_llm_verification.py) | Local LLM match verification |
| [`vector_blocking_example.py`](examples/vector_blocking_example.py) | Semantic similarity blocking |

## Development

```bash
# Install with dev + test deps
pip install -e ".[dev,test,mcp,llm,ml]"

# Or use the Makefile
make install-all
make test          # all tests
make test-unit     # unit tests only
make lint          # flake8
make format        # black
make typecheck     # mypy
make build         # sdist + wheel
```

Pre-commit hooks validate syntax, check for hardcoded credentials, and verify critical imports. Pre-push hooks run the full test suite against a temporary ArangoDB instance.

## Contributing

1. Review the [PRD](docs/PRD.md) and [Documentation Index](docs/README.md)
2. Install git hooks: `./scripts/setup-git-hooks.sh`
3. Follow Python 3.10+ with type hints, DRY principles, and comprehensive docstrings
4. Run `make test` before submitting PRs
5. Update documentation for any user-facing changes

## License

[Apache License 2.0](LICENSE)
