# Project Health Scorecard

**Evaluated:** September 22, 2026  
**Release baseline:** `v3.8.0` plus committed post-release work  
**Assessment scope:** released code plus committed, gate-passing work on `main`  
**Overall health:** **7.7/10 — B**

This is the current operational scorecard. The June 2026 reviews remain useful
as historical baselines, but their security, matching, UI, and graph-feature
findings no longer describe the current system.

The September 22 re-evaluation moves the score **down** 0.1, and that is the
scorecard working as intended. A published benchmark table was found to have five
of nine rows wrong, including the headline, and the README carried a quality claim
that measurement contradicts. Both were corrected properly — the withdrawn figures
are named in the documents — but the lapse is a documentation-discipline fact and
is scored as one. Correctness improved in the same period: two real defects were
found by measurement and fixed with mutation-tested regressions.

## Scoring method

Scores use a 0–10 scale: 9–10 leading, 8–8.9 strong, 7–7.9 healthy with
material gaps, 5–6.9 usable but constrained, and below 5 high risk. The overall
score is weighted by impact on correctness, trust, and production use.

| Dimension | Weight | Score | Current evidence |
|---|---:|---:|---|
| Architecture and core design | 12% | **9.0** | Config-driven pipeline, pluggable blocking and clustering, shared services behind CLI/MCP/UI, native ArangoDB graph/vector paths |
| Correctness and reliability | 12% | **8.8** | Binding human verdicts, null-safe scoring, configuration-hashed model loading, strict known-defect and conformance gates; a degenerate parameter fit is flagged on both estimation paths rather than returned silently; the LLM verifier's response budget no longer truncates verbose verdicts. Both of those were shipped defects found by measurement this cycle, which is why the score holds rather than rises |
| Tests and mechanical verification | 12% | **8.7** | `make verify`: 1,790 passed, 8 skipped, 75.37% coverage against a 72% floor; matching-quality and wiring gates are blocking; every regression test added this cycle was mutation-checked against the reversion it guards. Gates cover code, not prose — see risk 6 |
| Security and privacy | 12% | **7.0** | Optional API/WebSocket auth and rate limiting, AQL hardening, SPA containment, secret scan, and optional LLM masking; secure deployment still depends on configuration |
| Matching quality and evaluation | 12% | **8.4** | Two public benchmark families covering both task shapes, B-cubed metrics, multi-level Fellegi–Sunter learned end to end, an explicit reference population for `u`, a measurable rule for choosing a scorer, and now an oracle-bounded measurement of the LLM tier. The FEBRL conclusion was corrected to what the data supports — FS wins through comparison levels, and the win is robustness at the shipped threshold rather than peak accuracy |
| Steward Workbench and API UX | 10% | **7.2** | Binding edits, audit, threshold tuning, profiling, survivorship overrides, auth UX, and dark mode; frontend and enterprise workflow coverage remain thin |
| Maintainability and debt | 10% | **6.5** | Good layering and deprecation discipline, offset by legacy exports, unwired strategies, oversized modules, 4,057 advisory flake8 findings (flat since August 6), and no clean mypy baseline |
| Documentation and release discipline | 8% | **8.0** | PRD reconciled against measurement, benchmark methodology current, every FEBRL row now records its command. Down from 8.5: a published benchmark table had five of nine rows wrong for four weeks and the README asserted a precision improvement that measurement contradicts. Both are corrected with the withdrawn figures named, but no gate reads prose, so nothing would have caught either without a manual re-run |
| Performance and scalability | 7% | **6.5** | GAE and local backend choices are strong; BM25 candidate generation is now adaptively chunked against a wall-clock budget and verified at 66,879 records against the default client timeout it previously exceeded, with a streaming `iter_candidates()` path; strategies still materialise all pairs client-side before deduplication, and nothing above ~67k is evidenced |
| Operations and deployment | 5% | **5.0** | Health endpoints, migrations, and runtime-provider gates exist, but there is no service image/Kubernetes package or standard Prometheus/OpenTelemetry stack |

**Weighted total:** 7.7/10.

## Verification snapshot

- Python correctness gate: **pass** — 1,790 tests passed; critical lint, secret
  scan, version consistency, wiring conformance, statistical quality floors, and
  72% coverage floor all passed on September 22.
- Python coverage: **75.34%**.
- UI unit tests: **pass** — 7 tests across 3 files.
- UI production build: **pass**. Vite reports a large main bundle
  (~1.02 MB minified / ~292 KB gzip), so code splitting remains worthwhile.
- Playwright smoke tests exist and CI installs Chromium. The local rerun was
  environment-blocked because the Playwright browser binary was not installed,
  not because an application assertion failed.
- Full flake8 remains advisory and currently reports **4,057 findings** (`make
  lint`, line length 120), mostly formatting plus some unused imports — flat
  against August 6, so the debt is stable rather than growing. The blocking
  syntax/undefined-name subset passes.
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

Since the August 6 evaluation:

- Multi-level Fellegi–Sunter is complete end to end — categorical EM, learned
  per-level persistence, production wiring, and published benchmarks — with
  bands inferable per field from the observed score distribution rather than
  hand-placed against labels.
- A second benchmark family (FEBRL deduplication) settled a claim the docs had
  been asserting without evidence: the probabilistic matcher wins decisively on
  structured multi-field records — decisively at the shipped threshold (febrl3
  0.9953 vs 0.547), narrowly at the best swept one — the reverse of its result on
  text. Which matcher applies is now predictable in advance from the spread in
  per-field chance agreement, without labels. The first published version of that
  table was wrong and has been withdrawn; see docs/BENCHMARKS.md.
- Candidate generation is adaptively chunked, closing the P0 scale constraint at
  the 67k scale that previously failed outright.
- Two correctness properties were discovered by measurement and made explicit:
  parameter estimation now names and records the population `u` is measured over
  (taking it from the wrong population cost 0.24 F1 at the shipped threshold
  while leaving peak F1 unchanged), and a degenerate fit is flagged rather than
  returned silently.

## Current risk register

Three risks from the August 6 register are closed. They are listed under
[Closed since August 6](#closed-since-august-6) rather than deleted, so the
register can be read as a history rather than only a snapshot.

1. **Operational packaging — P1 adoption constraint.** Add a supported service
   container, deployment example, structured logs, metrics, and tracing.
2. **Wiring completeness — P1 product constraint.** Geographic, hybrid, and
   graph-traversal strategies are exported and tested but are not selectable
   through `ConfigurableERPipeline.run_blocking()`, which reaches five of them
   (`exact`, `bm25`/`arangosearch`, `vector`, `lsh`, `graph_embedding`). Wire
   them or mark them experimental rather than describing them as uniformly
   shipped.
3. **Maintainability — P1 engineering constraint.** Establish a ratcheted
   full-lint baseline, make local type checking reproducible (`mypy` is still
   absent from the development environment), reduce oversized modules, and
   finish retiring duplicate legacy paths.
4. **Candidate-generation scale beyond 67k — P2 product constraint.** Adaptive
   chunking closed the immediate failure, but every strategy still materialises
   all candidate pairs in client memory before deduplication, and no run above
   66,879 records has been measured. `iter_candidates()` exists for callers that
   want to avoid the materialisation; the batch path does not yet use it.
5. **Governance — P2 enterprise constraint.** Shared-token authentication is
   appropriate for the current embedded scope, but RBAC, tenant isolation,
   immutable audit guarantees, erasure propagation, and default-on LLM masking
   remain v4 work.
6. **Prose is ungated — P1 trust constraint.** Every mechanical gate reads code.
   Nothing reads `README.md`, `docs/BENCHMARKS.md`, or these scorecards, which is
   how a benchmark table with five wrong rows and a README quality claim with no
   measurement behind it both shipped and survived. The surface most readers see
   is the least verified. First step taken: the scorecards now carry a
   mechanical staleness check (`make check-scorecards`, surfaced at session
   start). Still open: checking numbers quoted in docs against the artifacts
   they cite.
7. **Verification-tier defaults — P2 product constraint.** The LLM tier is now
   measured and works with a competent model, but ships with a band that holds
   8.5% of errors and recommends a local model that does not work. Derive the
   band from the error distribution and qualify the provider table.

### Closed since August 6

- **Release hygiene** *(was risk 1, immediate)*. The 76 uncommitted paths have
  been split, reviewed, and committed. The tree now carries two untracked files,
  both documentation or history, and `make verify` passes from it.
- **Candidate-generation scale** *(was risk 2, P0)*. BM25 now executes in
  adaptive chunks sized against a wall-clock budget, verified at 66,879 records
  against the default 60-second client timeout that previously failed outright.
  Chunked and unchunked runs are asserted to produce identical candidate sets.
  The residual concern is narrower and tracked as risk 4 above.
- **Multi-level probabilistic learning** *(was risk 3, P1)*. Categorical EM,
  learned-level persistence, automatic band configuration, production wiring,
  and benchmark ratchets are all shipped and measured. The accompanying claim
  that "binary FS remains materially worse than weighted similarity" was true
  only of text-heavy data and is now stated conditionally: on structured
  multi-field records the ordering reverses. The winning configuration there is
  FS with comparison levels, not the binary model, which collapses to an unfit
  solution on two of the three FEBRL datasets.

## Release-readiness decision

The code is **release-ready from `main`**. The blocking condition in the August 6
assessment — a working tree mixing unrelated work — no longer holds: the work is
committed in coherent groups, `make verify` passes (1,779 tests, 75.34%
coverage), and benchmark results are reproducible from the current commit by a
single documented command.

Two conditions remain before a release is cut rather than merely possible: rerun
the UI unit/build/E2E gates, which were last verified on August 6 and are not
covered by `make verify`; and decide the disposition of the two untracked files
(`AGENTS.md`, a contributor guide that has never been committed, and
`.prd-patches-pending.md`, now closed-out history).

## Evidence

- [Product requirements and shipped/open scope](PRD.md)
- [Public benchmark results and scale limits](BENCHMARKS.md)
- [Python CI gates](../.github/workflows/python-package.yml)
- [UI contract/unit workflow](../.github/workflows/ui-contract.yml)
- [UI Playwright workflow](../.github/workflows/ui-e2e.yml)
- [Security posture](../SECURITY.md)
- [June 2026 technical review](PROJECT_REVIEW_2026-06.md)
