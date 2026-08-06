# Project Health Scorecard

**Evaluated:** August 6, 2026  
**Release baseline:** `v3.8.0`  
**Assessment scope:** released code plus the current verified working tree  
**Overall health:** **7.6/10 — B**

This is the current operational scorecard. The June 2026 reviews remain useful
as historical baselines, but their security, matching, UI, and graph-feature
findings no longer describe the current system.

## Scoring method

Scores use a 0–10 scale: 9–10 leading, 8–8.9 strong, 7–7.9 healthy with
material gaps, 5–6.9 usable but constrained, and below 5 high risk. The overall
score is weighted by impact on correctness, trust, and production use.

| Dimension | Weight | Score | Current evidence |
|---|---:|---:|---|
| Architecture and core design | 12% | **9.0** | Config-driven pipeline, pluggable blocking and clustering, shared services behind CLI/MCP/UI, native ArangoDB graph/vector paths |
| Correctness and reliability | 12% | **8.7** | Binding human verdicts, null-safe scoring, configuration-hashed model loading, strict known-defect and conformance gates |
| Tests and mechanical verification | 12% | **8.6** | `make verify`: 1,687 passed, 10 skipped, 75.34% coverage against a 72% floor; matching-quality and wiring gates are blocking |
| Security and privacy | 12% | **7.0** | Optional API/WebSocket auth and rate limiting, AQL hardening, SPA containment, secret scan, and optional LLM masking; secure deployment still depends on configuration |
| Matching quality and evaluation | 12% | **7.7** | Reproducible public benchmarks, B-cubed metrics, EM/TF Fellegi–Sunter, supervised and guarded unsupervised threshold selection |
| Steward Workbench and API UX | 10% | **7.2** | Binding edits, audit, threshold tuning, profiling, survivorship overrides, auth UX, and dark mode; frontend and enterprise workflow coverage remain thin |
| Maintainability and debt | 10% | **6.5** | Good layering and deprecation discipline, offset by legacy exports, unwired strategies, oversized modules, 4,060 advisory flake8 findings, and no clean mypy baseline |
| Documentation and release discipline | 8% | **8.0** | Current PRD, benchmark methodology, security and release docs; some historical docs and API/version references remain stale |
| Performance and scalability | 7% | **5.5** | GAE and local backend choices are strong; BM25 candidate generation is monolithic, non-streaming, and takes ~19 minutes at 66,879 records |
| Operations and deployment | 5% | **5.0** | Health endpoints, migrations, and runtime-provider gates exist, but there is no service image/Kubernetes package or standard Prometheus/OpenTelemetry stack |

**Weighted total:** 7.6/10.

## Verification snapshot

- Python correctness gate: **pass** — 1,687 tests passed; critical lint, secret
  scan, version consistency, wiring conformance, statistical quality floors, and
  72% coverage floor all passed on August 6.
- Python coverage: **75.34%**.
- UI unit tests: **pass** — 7 tests across 3 files.
- UI production build: **pass**. Vite reports a large main bundle
  (~1.02 MB minified / ~292 KB gzip), so code splitting remains worthwhile.
- Playwright smoke tests exist and CI installs Chromium. The local rerun was
  environment-blocked because the Playwright browser binary was not installed,
  not because an application assertion failed.
- Full flake8 remains advisory and currently reports **4,060 findings**, mostly
  formatting plus some unused imports. The blocking syntax/undefined-name subset
  passes.
- Local `make typecheck` is not self-contained because `mypy` is absent from the
  active development environment; CI installs it but treats findings as advisory.

## Material improvement since June 2026

The project moved from a strong core with risky surfaces to a substantially more
complete product:

- Web/MCP exposure is authenticated and rate-limited; AQL interpolation paths,
  SPA file serving, reviewer attribution, and golden-record metadata are
  hardened.
- Human verdicts now affect edges and clusters, with auditability and backend
  conformance checks.
- Fellegi–Sunter now has EM estimation, unbiased `u`, null semantics,
  term-frequency adjustment, calibrated posterior scoring, and config-specific
  model persistence.
- Public benchmark and quality-gate workflows replaced unverified performance
  and accuracy claims.
- The Workbench gained threshold tuning, cluster curation, profiling, golden
  record editing, dark mode, component tests, and Playwright smoke coverage.
- Graph-context scoring, collective resolution, incremental maintenance, and
  graph-embedding blocking now make the ArangoDB integration substantive rather
  than merely a storage choice.

## Current risk register

1. **Release hygiene — immediate.** The current working tree contains 76
   uncommitted paths (57 modified, 19 untracked). It mixes scoring, security,
   quality gates, benchmarks, UI auth, and unrelated Fabric WP13 files. The
   capability is healthier than the deliverable until these are split, reviewed,
   committed, and rerun from a clean checkout.
2. **Candidate-generation scale — P0 product constraint.** BM25 must emit and
   consume candidate chunks through a streaming cursor before claims above
   roughly 50k records are defensible.
3. **Multi-level probabilistic learning — P1 quality constraint.** The runtime
   scorer accepts exact/fuzzy/fallback levels, but categorical EM, learned-level
   persistence, automatic configuration, production wiring, and benchmark
   ratchets are still open. Binary FS remains materially worse than weighted
   similarity on text-heavy benchmarks.
4. **Operational packaging — P1 adoption constraint.** Add a supported service
   container, deployment example, structured logs, metrics, and tracing.
5. **Wiring completeness — P1 product constraint.** Geographic, hybrid, and
   shard-parallel strategies exist and are tested but are not selectable through
   the primary `ConfigurableERPipeline.run_blocking()` path. Wire them or mark
   them experimental rather than describing them as uniformly shipped.
6. **Maintainability — P1 engineering constraint.** Establish a ratcheted
   full-lint baseline, make local type checking reproducible, reduce oversized
   modules, and finish retiring duplicate legacy paths.
7. **Governance — P2 enterprise constraint.** Shared-token authentication is
   appropriate for the current embedded scope, but RBAC, tenant isolation,
   immutable audit guarantees, erasure propagation, and default-on LLM masking
   remain v4 work.

## Release-readiness decision

The code is **capability-ready but not release-ready in its current worktree**.
Ship after splitting the unrelated work, committing coherent groups, rerunning
`make verify`, UI unit/build/E2E gates, and reproducing the benchmark artifact
from the exact release commit.

## Evidence

- [Product requirements and shipped/open scope](PRD.md)
- [Public benchmark results and scale limits](BENCHMARKS.md)
- [Python CI gates](../.github/workflows/python-package.yml)
- [UI contract/unit workflow](../.github/workflows/ui-contract.yml)
- [UI Playwright workflow](../.github/workflows/ui-e2e.yml)
- [Security posture](../SECURITY.md)
- [June 2026 technical review](PROJECT_REVIEW_2026-06.md)
