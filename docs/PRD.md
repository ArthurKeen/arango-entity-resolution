# Product Requirements and Roadmap

This document captures the shipped baseline through `v3.8.0` and the forward-looking product roadmap.

---

## Product Overview

**Product**: ArangoDB Entity Resolution System
**Current Release**: `3.8.0`
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

## Shipped Scope Through 3.8.0

### Core Resolution Workflow

- Candidate generation through exact/COLLECT, BM25, vector, LSH, geographic, and graph-traversal blocking paths
- **BM25 text blocking** defaults to disjunctive token match (`match_mode: tokens`), ranked by BM25 score. Legacy phrase match (`match_mode: phrase`) remains for backward compatibility but is near-exact and unsuitable for noisy product text.
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
- `arango-er-mcp` MCP server: 17 tools, 2 resources
- `arango-er-demo`

### Reporting and Evaluation

- JSON/CSV cluster export artifacts
- Cluster and pipeline statistics for downstream reporting
- Exact-vs-BM25 blocking benchmark workflow built on `ABEvaluationHarness`
- Runtime health comparison artifacts (JSON, Markdown, CSV)

### Matching Quality Improvements

- Config-driven similarity field transformers for phone, state, street suffix, and company suffix normalization, plus `missing_sentinels` to map placeholders such as `NULL`, `UNKNOWN`, and `N/A` to absent values so they follow null-comparison semantics
- Fellegi-Sunter probabilistic scoring with unsupervised EM parameter estimation (m/u probabilities, log-likelihood weights, versioned model persistence keyed by config hash), selectable alongside weighted-heuristic scoring; field profiling for semantic type/completeness/cardinality analysis
- **Null comparison level**: unobserved fields contribute zero evidence, distinct from an observed mismatch which takes the full disagreement weight. Training and scoring share this definition, so per-field m/u are estimated only over the pairs where that field was actually compared
- **Two-population parameter estimation**: `m` from blocked candidate pairs (where true matches concentrate) and `u` from a random sample of record pairs (which are effectively all non-matches). `u` is measured directly rather than inferred jointly, because candidate pairs have already passed a similarity gate and cannot furnish a representative non-match sample. Each persisted model records which estimation regime produced it
- **Term-frequency-adjusted agreement weight**: when two records share an identical value, the match weight is computed from that value's observed frequency rather than the field's average chance-agreement rate, so agreeing on a rare value counts as stronger evidence than agreeing on a common one. Values absent from the maintained per-field table fall back to the field average rather than being guessed
- **Multi-level comparison bands**: a field may be compared at several ordered levels (for example exact / close / else) rather than one agree/disagree cutoff, with per-level m/u learned by EM. Only the band structure is configured; the probabilities are estimated, so a configured table cannot assert values that contradict the data. The band structure forms part of a model's identity, so changing it invalidates a previously trained model rather than silently reusing parameters learned under different bands. Bands may also be inferred per field from the observed score distribution, and inference declines rather than guessing when a field shows no separation
- **Data-driven threshold selection** (`similarity.auto_threshold`, off by default): unsupervised inference from the score distribution via Otsu's method, plus supervised selection from labelled pairs. Inference is refused when the scores are not meaningfully bimodal, so the configured threshold is never replaced by an unsupported guess

### Graph-Aware and Incremental Resolution (Phase 3.1–3.4)

- Graph-context relationship features contributed to Fellegi-Sunter scoring as ordinary learned fields
- Collective / iterative resolution with fixpoint and cycle detection, reachable from `ConfigurableERPipeline.run()` via `collective.enabled`
- Incremental cluster maintenance: single-record resolve-and-commit with verdict-preserving, idempotent re-clustering. Handles merges and human-verdict splits; data-driven splits from record *updates* are not yet retracted
- Graph-embedding blocking over node2vec-style embeddings (prototype; unweighted random walks with count-SVD, hard-capped node count)
- Shard-parallel blocking for sharded clusters (note: pairs whose members live on different shards are only found when the blocking fields match the collection's shard keys)
- Hybrid blocking combining BM25 and Levenshtein candidate generation
- `AddressERPipeline` for street/city/state/postal resolution
- Cross-collection matching for linking entities across two collections
- MCP canonical `options`-based request shape with legacy reconciliation and deprecation warnings

### Evaluation and Verifiability

- Cluster-level metrics: B-cubed precision/recall/F1 and pairwise metrics over the transitive closure of produced clusters
- Published, reproducible results on the public Leipzig record-linkage benchmarks (`scripts/run_er_benchmarks.py`, `docs/BENCHMARKS.md`)
- Per-decision match-weight decomposition (additive log-odds waterfall) exposed through `explain_match`
- Mechanical quality gates in CI: blocking lint, secret scanning, version consistency, wiring/contract conformance, matching-quality F1 floors, coverage floor

### Steward Workbench UI (3.8.0)

- Optional browser-based curation UI (`pip install "arango-entity-resolution[ui]"`, `arango-er ui`): dashboard, review queue with verdict capture, cluster browse/edit with audit trail, threshold tuning, golden-record survivorship editing, data profiling, and pipeline execution with progress streaming
- All UI operations route through existing services (`FeedbackApplicationService`, `GoldenRecordPersistenceService`); no parallel resolution logic
- Manual golden-record field edits are stored as `fieldOverrides` and survive subsequent pipeline rebuilds: recomputed machine-derived values may change, but a steward override takes precedence until explicitly removed. Golden-record control metadata (`clusterId`, `clusterSize`, `memberIds`, `sourceClusterHash`, `stale`, `method`, `fieldOverrides`, and related fields) is protected from both source-document columns and steward edits

---

## Current Functional Requirements

### 1. Pipeline Execution

The product must allow users to run ER pipelines from configuration without writing orchestration glue code.

### 2. Result Inspection

The product must expose cluster summaries, cluster quality signals, and collection-level status in both CLI and MCP-facing workflows.

**Cluster output must be validated for structural integrity, not only produced.**
Validation must detect entities appearing in more than one cluster, clusters
below the configured minimum size, and clusters above a configured maximum — the
last because connected-component clustering takes the transitive closure, so a
single spurious edge can silently merge unrelated entities while the run reports
success. Suspect clusters are flagged for review, never discarded: removing them
deletes the evidence of the defect along with the data.

### 3. Review and Adjudication

The product must support optional active-learning and LLM-assisted review for ambiguous pairs without forcing those dependencies into the default runtime path.

**Adjudication decisions are binding on every execution path.** A pair recorded as
`no_match` must not appear in the same cluster under ANY clustering backend, and a
confirmed pair must survive a full rebuild. Backends that cannot express this
filter natively must achieve it by other means rather than ignoring it.
Parametrized conformance tests verify suppressed-edge exclusion across every WCC
backend, including GAE's active-edge projection. Confirmed-pair survival is
integration-tested, but per-backend parametrized confirmation coverage remains
to be added.

**Every irreversible curation action is audited.** A cluster merge or split, a
golden-record edit, an adjudication verdict and a threshold change must each
append an attributed entry to the audit trail. Auditing must never block the
action it records, but a failed audit write must be reported rather than
discarded: an action whose accountability record was lost silently is
indistinguishable from one that was never audited. Per-entity history must remain
retrievable at a cost that does not grow with the age of the log.

**Steward corrections survive recomputation.** A manually corrected golden-record
field must not be reverted by a subsequent pipeline run. Manual values are
recorded as overrides and re-applied after recomputation, with provenance
identifying them as human rather than machine choices.

### 4. Portability

The product must allow users to export results in JSON and CSV for analyst and downstream-system consumption.

### 5. Evaluation

The product must provide one supported benchmark workflow that compares blocking strategies using a simple ground-truth input format.

**Cluster-level quality.** The product must measure final cluster quality with
entity-centric metrics (B-cubed precision/recall/F1) alongside pairwise metrics
computed over the transitive closure of the produced clusters, so that
over-merging and under-merging are penalised symmetrically and the precision cost
of chain merges is measurable against ground truth.

**Public benchmarks.** The product must be measurable against public, third-party
entity-resolution benchmarks, reporting blocking pair completeness and reduction
ratio, pairwise precision/recall/F1, and entity-level B-cubed
precision/recall/F1, together with the configuration that produced them. Results
must be reproducible by a single documented command and published with the
release, so matching-quality claims are falsifiable rather than asserted.

**Evidence before recommendation.** A scoring method must not be presented as a
recommended default until benchmark evidence shows it competitive on the
published datasets. This project shipped a statistically more sophisticated
matcher that measured *worse* than the simple one on every dataset; only
measurement revealed it.

**Threshold selection.** The product must be able to choose a decision threshold
from data rather than requiring a hand-set constant. Benchmarking established
that a single fixed default is unsafe: the best-F1 threshold varies by more than
2x across datasets, and running the shipped 0.8 default on noisy product data
yielded roughly a tenth of the achievable F1. Threshold selection must therefore
be derivable from a labelled sample or from the score distribution, and the
chosen operating point must be reported with the score.

### 6. Integration

The product must support both human-operated CLI workflows and AI-agent workflows via MCP.

### 7. Enterprise Scalability

The product must support optional GAE clustering for enterprise-scale graphs, with graceful fallback to local backends when GAE is unavailable.

**Measured status (2026-08-16):** blocking now executes in adaptive chunks whose
size tracks a wall-clock budget, so no single request approaches the client read
timeout. Verified at 66,879 records against the default 60-second timeout, which
previously failed outright. Chunked and unchunked runs are asserted to produce
identical candidate sets, and the query sorts by `_key` before `LIMIT` so chunks
cannot overlap or skip documents.

Throughput is still modest: ~17 minutes for 66,879 records against ~7 seconds
for 4,910. Candidate pairs are also still materialised in client memory before
deduplication, though `iter_candidates()` offers a streaming path. The README's
1M-records figure remains unsubstantiated and claims above roughly 50k records
should cite measurements. See `docs/BENCHMARKS.md#scale-limits`.

### 8. Steward Workbench UI

The product must provide an optional browser-based curation UI (pip extra `[ui]`,
`arango-er ui`) exposing dashboard, review queue with verdict capture, cluster
browse/edit with audit trail, threshold tuning, golden-record survivorship
editing, data profiling, and pipeline execution with progress streaming. All UI
operations route through existing services; no parallel resolution logic.

**Override survival.** Manual golden-record field edits made through the
Workbench (stored as `fieldOverrides`) must survive subsequent pipeline rebuilds.
Consolidation may recompute machine-derived values, but steward overrides take
precedence and must not be silently reverted.

**Metadata integrity.** Consolidation writes domain fields first and control
metadata last, so a source column or steward edit named like `method`,
`clusterSize`, `stale`, or `fieldOverrides` cannot corrupt golden-record state.

**Authentication UX.** When `ER_UI_AUTH_TOKEN` is configured, the health
endpoint reports that authentication is required without exposing the secret.
The SPA keeps the supplied token in tab-scoped `sessionStorage`, sends it as a
bearer credential on API calls, and authenticates pipeline WebSocket
connections. When `ER_UI_REVIEWERS` maps tokens to display names, the mapped
authenticated identity outranks the freely editable `X-Reviewer` attribution
header.

---

## Non-Functional Requirements

- **Scalability**: Handle large datasets through blocking, set-based ArangoDB operations, and optional GAE for enterprise-scale graphs
- **Security**: Prevent AQL injection through validated identifiers, numeric coercion, and bind-variable usage across config-driven query paths. Static SPA routes must not serve files outside the packaged UI root, authenticated Workbench API and WebSocket traffic must be supported end to end, and user-controlled fields must not replace system-owned golden-record metadata
- **Maintainability**: Keep new capabilities configuration-driven and layered on existing services
- **Explainability**: Surface quality signals, backend selection rationale, structured benchmark outputs, and a per-decision evidence decomposition. For any candidate pair the system must be able to state which fields contributed to the decision and by how much, as additive log-odds summing to the final score, including the effect of value rarity. This decomposition is derived from the model itself rather than narrated after the fact
- **Verifiability**: quality intentions must be mechanically enforced, not documented only. CI blocks on syntax/undefined-name lint, committed-secret scanning, version consistency across all declared sources, wiring/contract conformance for every public entry point, matching-quality F1 floors, and a unit-test coverage floor. Current ratchet floors are **72% coverage**, **0.80 pairwise F1**, and **0.85 B-cubed F1** on the labeled regression fixture; floors rise with measured performance. Known defects are pinned with strict `xfail` markers so a fix cannot land without updating the ledger. Tests refuse to run against a non-local database
- **Extensibility**: Preserve room for future GraphRAG, geospatial, and graph-learning additions
- **Performance Portability**: Support cross-platform GPU acceleration for embedding-heavy workloads on Apple Silicon and Linux with deterministic CPU fallback behavior
- **Python Runtime**: Supported and CI-tested on Python **3.10–3.12** (`requires-python >= 3.10`)
- **Platform Baseline**: ArangoDB **3.12+** is the supported baseline. Vector / ANN blocking **requires** the native 3.12 vector index (`APPROX_NEAR_COSINE`); brute-force vector search is intentionally not supported, so vector features are unavailable on ArangoDB 3.11 and earlier. Non-vector capabilities (exact/BM25/LSH/graph blocking, similarity, clustering, golden records) do not require 3.12.

---

## Roadmap Beyond 3.8.0

These items remain forward-looking and are not part of the currently shipped `3.8.0` baseline.

### Centralized Enterprise ER Service (v4.x)

The highest-priority roadmap initiative is evolving the toolkit into a **centralized entity resolution service** — a shared enterprise infrastructure component where multiple business units submit records and receive resolved entities with global identifiers, golden records, relationship context, and enrichment signals from a continuously updated knowledge graph.

See [Centralized ER Service Design](architecture/CENTRALIZED_ER_SERVICE.md) for the full architecture and implementation plan.

#### Phase 1: Foundation (v4.0)

| Requirement | Description |
|-------------|-------------|
| **FR-8: Submit-and-Resolve API** | REST endpoint that accepts a single record, resolves it against the knowledge graph, and returns the matched entity with golden record and global identifiers. Synchronous, sub-500ms p95 latency. |
| **FR-9: Schema Registry** | Configurable field mapping per source/tenant, translating business-unit-specific field names to the canonical entity model. |
| **FR-10: Global ID Allocation** | Stable internal entity identifiers with cross-reference index to external IDs (LEI, DUNS, IMO, Tax ID, etc.). Entity IDs must not change after initial assignment except in explicit merge operations. |
| **FR-11: Source Provenance** | Every contributed record is preserved with full lineage: source identifier, ingestion timestamp, match confidence, and original payload. |
| **FR-12: Tenant Access Control** | Multi-tenant read/write permissions defining which entity types, fields, and operations each business unit can access. Authority ranking for survivorship decisions. |

#### Phase 2: Knowledge Graph (v4.1)

| Requirement | Description |
|-------------|-------------|
| **FR-13: Multi-Entity-Type Graph** | Support for company, person, vessel, and address entity types within the same knowledge graph, with typed relationship edges (subsidiary_of, beneficial_owner, operates_vessel, registered_at, same_as). |
| **FR-14: Authority-Ranked Survivorship** | Golden record field values determined by source authority rank, completeness, and freshness. Conflicts flagged for review when sources disagree beyond a configurable threshold. |
| **FR-15: External Feed Integration** | Scheduled ETL for authoritative external sources (GLEIF LEI registry, sanctions lists, vessel registries, company house filings). Resolved against the knowledge graph like any other source. |
| **FR-16: Graph Traversal API** | Query endpoint for walking the knowledge graph from an entity — following relationship edges with configurable depth, direction, and edge-type filters. |

#### Phase 3: Continuous Operation (v4.2)

| Requirement | Description |
|-------------|-------------|
| **FR-17: Entity Subscriptions** | Business units subscribe to entity change events (golden record updates, new relationships, sanctions flag changes) via webhooks or event bus. |
| **FR-18: Streaming Ingest** | Kafka/CDC connector for real-time record ingestion in addition to REST and batch modes. |
| **FR-19: Audit Trail** | Immutable log of every resolution decision — match/no-match verdicts, golden record field changes, merge operations, and human overrides — with full source provenance. |
| **FR-20: Batch Backfill** | When a new business unit onboards, its historical data is bulk-ingested via `ConfigurableERPipeline` and spliced into the live knowledge graph without downtime. Target: 1M records within 1 hour. |

#### Phase 4: Intelligence Layer (v4.3)

| Requirement | Description |
|-------------|-------------|
| **FR-21: AI Data Steward** | MCP-based workflow where an AI agent acts as a data steward — submitting records, reviewing ambiguous matches, querying relationships, and monitoring entity changes through natural language. |
| **FR-22: Automated Anomaly Detection** | Alerts for new sanctions matches, ownership structure changes, dormant entities becoming active, and data quality degradation. |
| **FR-23: Network Analysis** | Hidden relationship discovery through multi-hop graph analysis — identifying shared beneficial owners, circular ownership, and sanctions-adjacent entities. |

#### Non-Functional Requirements (Centralized Service)

| Requirement | Target |
|-------------|--------|
| **NFR-8: Synchronous resolution latency** | < 500ms p95 |
| **NFR-9: Batch backfill throughput** | 1M records/hour |
| **NFR-10: Entity ID stability** | < 0.1% reassignment rate |
| **NFR-11: Subscription delivery latency** | < 60 seconds from resolution to notification |
| **NFR-12: Audit coverage** | 100% of resolution decisions logged |
| **NFR-13: Multi-tenancy isolation** | Tenant data access enforced at query and API layer |

### Other Future Investigation Areas

Shipped since this list was written and therefore removed from it: shard-parallel
blocking, `AddressERPipeline` as a first-class class, graph-context / collective
matching, richer evaluator reports and public benchmark datasets, and the MCP
canonical `options` migration. See Shipped Scope above.

Still open:

- ONNX Runtime GPU provider promotion (CoreML on Apple Silicon, CUDA/TensorRT on Linux) after parity and quality gates pass
- Richer GraphRAG and document-entity extraction flows
- Geospatial-temporal validation as Fellegi-Sunter evidence rather than a binary pre-filter
- Graph-neural matching (the current graph-embedding blocker is an unweighted-DeepWalk prototype; GraphSAGE / ArangoGraphML is the scale path)
- Stricter anti-merge constraints and policy controls (minimum-evidence floor, conflicting-hard-identifier veto)
- **Chunked, streaming candidate generation** — required before any throughput claim above ~50k records (see Functional Requirement 7)
- **Active learning**: uncertainty-sampled pair selection for labelling, so a useful model needs tens rather than thousands of labels
- **Multi-level comparisons (learning path)**: unsupervised categorical EM estimation, configuration, and persistence of per-level m/u. The runtime scorer accepts configured levels, but levels are not yet learned or written by `ModelParameterEstimator`; weighted similarity therefore remains the default for text-heavy data until this path is wired and benchmarked
- **Embeddings as a scoring feature**, not blocking-only
- **LLM cascade for the clerical-review band** with explicit accuracy/cost/latency accounting
- Retraction in incremental maintenance, so a record *update* can split a cluster rather than only a human verdict

> The original library enhancement plan (Phases 0–4) is complete and archived at
> [docs/archive/completed-work/LIBRARY_ENHANCEMENT_PLAN.md](archive/completed-work/LIBRARY_ENHANCEMENT_PLAN.md);
> its still-open follow-ups are captured in this section.

### Roadmap Principle

Future additions should extend the current pipeline, CLI, MCP, and reporting surfaces rather than creating parallel systems. The centralized service specifically builds on `IncrementalResolver`, `ConfigurableERPipeline`, the MCP server, and the advisor tools rather than introducing parallel resolution paths.

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
- [Centralized ER Service Design](architecture/CENTRALIZED_ER_SERVICE.md)
- [System Design](architecture/DESIGN.md)
- [Quick Start Guide](guides/QUICK_START.md)
- [API Reference](api/API_REFERENCE.md)
- [Blocking Benchmarks](development/BLOCKING_BENCHMARKS.md)
- [Release Checklist](development/RELEASE_CHECKLIST.md)
- [GAE Enhancement Path](development/GAE_ENHANCEMENT_PATH.md)

---

**Last Updated:** August 5, 2026
