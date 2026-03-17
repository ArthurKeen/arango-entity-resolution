# Product Requirements and Roadmap

This document captures the shipped baseline for `v3.2.3` and the forward-looking product roadmap.

It replaces older phase planning language that no longer matched the released product surface.

---

## Product Overview

**Product**: ArangoDB Entity Resolution System  
**Current Release**: `3.2.3`  
**Status**: Published, tested, and production-ready for the currently shipped scope

### Goal

Provide a practical, ArangoDB-native entity-resolution toolkit that supports:
- batch entity-resolution pipelines
- interactive inspection and analyst workflows
- AI-agent access via MCP
- optional LLM-assisted review for ambiguous matches
- export/reporting and evaluator-ready benchmark workflows

## Stakeholders

- Product and platform engineers
- Data engineers
- Data analysts and reviewers
- AI-agent / tool-integration consumers
- Business owners who need trustworthy deduplication outputs

---

## Shipped Scope Through 3.2.3

### Core Resolution Workflow

- Candidate generation through exact/COLLECT, BM25, vector, LSH, geographic, and graph-traversal blocking paths
- Weighted similarity scoring with configurable field weights
- Config-driven pipelines via `ERPipelineConfig` and `ConfigurableERPipeline`
- Similarity edge creation and WCC clustering
- Golden-record persistence support

### Trust and Review Features

- Cluster quality metadata (`edge_count`, `average_similarity`, `density`, `quality_score`)
- `merge_entities` preview in the MCP path
- Active-learning configuration for uncertain-pair review
- LLM-assisted verification through `LLMMatchVerifier` / `AdaptiveLLMVerifier`

### User-Facing Interfaces

- `arango-er` CLI:
  - `run`
  - `status`
  - `clusters`
  - `export`
  - `benchmark`
- `arango-er-mcp` MCP server:
  - 7 tools
  - 2 resources
- `arango-er-demo`

### Reporting and Evaluation

- JSON/CSV cluster export artifacts
- Cluster and pipeline statistics for downstream reporting
- Exact-vs-BM25 blocking benchmark workflow built on `ABEvaluationHarness`

### Matching Quality Improvements

- Config-driven similarity field transformers for:
  - phone normalization
  - state normalization
  - street suffix normalization
  - company suffix normalization

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

---

## Non-Functional Requirements

- **Scalability**: Handle large datasets through blocking and set-based ArangoDB operations
- **Security**: Prevent AQL injection through validated identifiers and bind-variable usage
- **Maintainability**: Keep new capabilities configuration-driven and layered on existing services
- **Explainability**: Surface quality signals and structured benchmark outputs
- **Extensibility**: Preserve room for future GraphRAG, geospatial, and graph-learning additions
- **Performance Portability**: Support cross-platform GPU acceleration for embedding-heavy workloads on Apple Silicon and Linux with deterministic CPU fallback behavior

---

## Roadmap Beyond 3.2.3

These items remain forward-looking and are not part of the currently shipped `3.2.3` baseline.

### Future Investigation Areas

- richer GraphRAG and document-entity extraction flows
- geospatial-temporal validation
- graph-neural or context-aware matching
- stricter anti-merge constraints and policy controls
- lower-latency streaming / registry APIs
- richer evaluator reports and benchmark datasets
- cross-platform GPU inference for ONNX-based embedding workloads (Apple Silicon CoreML/Metal path and Linux CUDA/TensorRT path)

### Planned GPU Inference Capability

GPU acceleration is now a roadmap priority for embedding workflows that materially benefit from model inference speedups (for example GraphML, ColBERT, and BERT ONNX variants).

Key requirements:
- one runtime abstraction with provider selection by platform
- Apple Silicon support using a native macOS GPU path with CPU fallback
- Linux GPU support (NVIDIA-first) with pinned compatibility matrix
- provider-level observability (selected backend, fallbacks, latency, throughput)
- rollout safety via feature flags and per-model enablement

### Roadmap Principle

Future additions should extend the current pipeline, CLI, MCP, and reporting surfaces rather than creating parallel systems.

---

## Success Criteria for the Current Product

The current product is successful when users can:

- configure and run a pipeline
- inspect clusters and trust signals
- export portable result artifacts
- benchmark blocking strategies with repeatable inputs
- optionally use MCP and LLM-assisted review without changing the core deployment path

---

## Related Docs

- [README](../README.md)
- [Quick Start Guide](guides/QUICK_START.md)
- [API Reference](api/API_REFERENCE.md)
- [Blocking Benchmarks](development/BLOCKING_BENCHMARKS.md)
- [Release Checklist](development/RELEASE_CHECKLIST.md)
