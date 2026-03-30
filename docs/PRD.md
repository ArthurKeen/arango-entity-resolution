# Product Requirements and Roadmap

This document captures the shipped baseline through `v3.5.1` and the forward-looking product roadmap.

---

## Product Overview

**Product**: ArangoDB Entity Resolution System  
**Current Release**: `3.5.1`  
**Status**: Published, tested, and production-ready for the currently shipped scope

### Goal

Provide a practical, ArangoDB-native entity-resolution toolkit that supports:
- batch entity-resolution pipelines with pluggable clustering backends
- interactive inspection and analyst workflows
- AI-agent access via MCP
- optional LLM-assisted review for ambiguous matches
- export/reporting and evaluator-ready benchmark workflows
- enterprise-scale clustering via ArangoDB Graph Analytics Engine (GAE)
- cross-platform embedding execution with GPU-readiness infrastructure

## Stakeholders

- Product and platform engineers
- Data engineers
- Data analysts and reviewers
- AI-agent / tool-integration consumers
- Business owners who need trustworthy deduplication outputs

---

## Shipped Scope Through 3.5.0

### Core Resolution Workflow

- Candidate generation through exact/COLLECT, BM25, vector, LSH, geographic, and graph-traversal blocking paths
- Weighted similarity scoring with configurable field weights
- Config-driven pipelines via `ERPipelineConfig` and `ConfigurableERPipeline`
- Similarity edge creation and WCC clustering with pluggable backends
- Golden-record persistence support

### Clustering Backend Abstraction (3.3.0–3.5.0)

- Six pluggable WCC backends: `python_dfs`, `python_union_find`, `python_sparse`, `aql_graph`, `gae_wcc`, `auto`
- Automatic backend selection (`backend='auto'`, default since 3.5.0) based on edge count, optional dependency availability, and GAE status
- Union-Find backend with path compression and union by rank
- Sparse backend via `scipy.sparse.csgraph` for large dense graphs (optional dependency)
- GAE backend managing full engine lifecycle (deploy, load, WCC, store results, cleanup)
- Dual-mode GAE connection layer for self-managed (JWT) and ArangoGraph Managed Platform (oasisctl) deployments

### Embedding Runtime Expansion (3.3.0–3.4.0)

- Device auto-detection: `device='auto'` (default since 3.4.0) resolves to CUDA, MPS, or CPU
- ONNX Runtime backend scaffold with provider resolution and CPU fallback
- Runtime health CLI commands: baseline, compare, and CI gate workflows
- Explicit `batch_size` and `max_batch_size` (OOM safety) for embedding workloads
- `runtime` config field for future ONNX Runtime promotion

### LLM Provider Configuration (3.3.0–3.4.0)

- `LLMProviderConfig` for structured Ollama, OpenRouter, OpenAI, and Anthropic settings
- `LLMMatchVerifier.healthcheck()` for provider reachability validation
- `healthcheck_on_start` and `fallback_provider` for production resilience

### Trust and Review Features

- Cluster quality metadata (`edge_count`, `average_similarity`, `density`, `quality_score`)
- `merge_entities` preview in the MCP path
- Active-learning configuration for uncertain-pair review
- LLM-assisted verification through `LLMMatchVerifier` / `AdaptiveLLMVerifier`

### User-Facing Interfaces

- `arango-er` CLI:
  - `run`, `status`, `clusters`, `export`, `benchmark`
  - `runtime-health`, `runtime-health-export`, `runtime-health-baseline`, `runtime-health-compare`, `runtime-health-gate`
- `arango-er-mcp` MCP server: 7 tools, 2 resources
- `arango-er-demo`

### Reporting and Evaluation

- JSON/CSV cluster export artifacts
- Cluster and pipeline statistics for downstream reporting
- Exact-vs-BM25 blocking benchmark workflow built on `ABEvaluationHarness`
- Runtime health comparison artifacts (JSON, Markdown, CSV)

### Matching Quality Improvements

- Config-driven similarity field transformers for phone, state, street suffix, and company suffix normalization

---

## Current Functional Requirements

### 1. Pipeline Execution

The product must allow users to run ER pipelines from configuration without writing orchestration glue code.

### 2. Result Inspection

The product must expose cluster summaries, cluster quality signals, and collection-level status in both CLI and MCP-facing workflows.

### 3. Review and Adjudication

The product must support optional active-learning and LLM-assisted review for ambiguous pairs without forcing those dependencies into the default runtime path.

### 4. Portability

The product must allow users to export results in JSON and CSV for analyst and downstream-system consumption.

### 5. Evaluation

The product must provide one supported benchmark workflow that compares blocking strategies using a simple ground-truth input format.

### 6. Integration

The product must support both human-operated CLI workflows and AI-agent workflows via MCP.

### 7. Enterprise Scalability

The product must support optional GAE clustering for enterprise-scale graphs, with graceful fallback to local backends when GAE is unavailable.

---

## Non-Functional Requirements

- **Scalability**: Handle large datasets through blocking, set-based ArangoDB operations, and optional GAE for enterprise-scale graphs
- **Security**: Prevent AQL injection through validated identifiers and bind-variable usage
- **Maintainability**: Keep new capabilities configuration-driven and layered on existing services
- **Explainability**: Surface quality signals, backend selection rationale, and structured benchmark outputs
- **Extensibility**: Preserve room for future GraphRAG, geospatial, and graph-learning additions
- **Performance Portability**: Support cross-platform GPU acceleration for embedding-heavy workloads on Apple Silicon and Linux with deterministic CPU fallback behavior

---

## Roadmap Beyond 3.5.1

These items remain forward-looking and are not part of the currently shipped `3.5.1` baseline.

### Future Investigation Areas

- ONNX Runtime GPU provider promotion (CoreML on Apple Silicon, CUDA/TensorRT on Linux) after parity and quality gates pass
- Richer GraphRAG and document-entity extraction flows
- Geospatial-temporal validation
- Graph-neural or context-aware matching
- Shard-parallel address blocking for ArangoDB clusters
- `AddressERPipeline` first-class library class
- Stricter anti-merge constraints and policy controls
- Richer evaluator reports and benchmark datasets

### Roadmap Principle

Future additions should extend the current pipeline, CLI, MCP, and reporting surfaces rather than creating parallel systems.

---

## Success Criteria for the Current Product

The current product is successful when users can:

- configure and run a pipeline with automatic backend selection
- inspect clusters and trust signals
- export portable result artifacts
- benchmark blocking strategies with repeatable inputs
- optionally use MCP and LLM-assisted review without changing the core deployment path
- optionally leverage GAE for enterprise-scale clustering workloads

---

## Related Docs

- [README](../README.md)
- [Quick Start Guide](guides/QUICK_START.md)
- [API Reference](api/API_REFERENCE.md)
- [Blocking Benchmarks](development/BLOCKING_BENCHMARKS.md)
- [Release Checklist](development/RELEASE_CHECKLIST.md)
- [GAE Enhancement Path](development/GAE_ENHANCEMENT_PATH.md)

---

**Last Updated:** March 30, 2026
