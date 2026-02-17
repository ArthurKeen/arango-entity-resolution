## Code Quality Analysis Report (2026-02-12)

Scope: repository-wide review focused on **duplication**, **hard-wiring**, **security risks**, and **maintainability**.  
Method: targeted static review + pattern scans (AQL construction, env handling, subprocess usage, repeated helper logic).

### Executive summary

- **Overall code health**: solid direction (validation utilities, safety limits, growing test suite), but there are several **high-leverage maintainability and security issues** driven by dynamic AQL string construction, inconsistent validation, and repeated query-building logic across strategies/services.
- **Biggest security theme**: **AQL injection surfaces** via f-string interpolation of collection/view names and field identifiers, with validation applied inconsistently.
- **Biggest maintainability theme**: duplicated “build AQL query by concatenating strings” patterns and multiple, inconsistent env var conventions, plus a few oversized modules.

---

## 1) Code duplication

### 1.1 Duplicated AQL query building patterns

Multiple modules build AQL with `query_parts` lists / f-strings, re-implementing similar concepts:

- **Filter condition builders duplicated in multiple places**
  - `src/entity_resolution/strategies/base_strategy.py` defines `_build_filter_conditions`
  - `src/entity_resolution/strategies/geographic_blocking.py` defines another `_build_filter_conditions`
  - `src/entity_resolution/strategies/graph_traversal_blocking.py` defines another `_build_filter_conditions`
  - `src/entity_resolution/strategies/collect_blocking.py` has its own `_build_filter_conditions` variant
  - `src/entity_resolution/services/cross_collection_matching_service.py` re-implements `_build_filter_conditions`

**Risk / cost**:
- behavior drift (same filter spec producing different AQL)
- harder to add new filter operators consistently
- repeated injection-hardening work

**Recommendation**:
- consolidate into a single shared “AQL filter builder” (pure function) with:
  - explicit allowed operators (equals/in/range/not_null/min_length/etc.)
  - validation of field names via `validate_field_name`
  - bind-var generation (avoid embedding values into query strings)

### 1.2 Repeated `sys.path.insert(...)` hacks across tests/scripts/examples

There are many `sys.path.insert` calls across:
- `tests/conftest.py`, `tests/test_config.py`
- many `scripts/*.py`
- `examples/*.py`

**Risk / cost**:
- import behavior differs by entrypoint (pytest vs script vs example)
- makes packaging harder (and tends to break IDE/static tooling)

**Recommendation**:
- prefer an installable package / editable install (`pip install -e .`) and remove most path hacks
- keep at most one “dev runner” shim if needed

---

## 2) Hard-wiring / configuration rigidity

### 2.1 Hard-coded defaults that may surprise users

- Default analyzer is hardwired to `"text_en"` in strategies like `HybridBlockingStrategy` (see `src/entity_resolution/strategies/hybrid_blocking.py`).
- Several services default collection names like `"similarTo"`, `"entity_clusters"` (see `src/entity_resolution/services/wcc_clustering_service.py`).
- Local docker test password appears widely in docs/scripts (`testpassword123`). This is fine for local testing, but it creates “copy/paste risk” into production automation.

**Recommendation**:
- centralize defaults into config objects (many already exist) and document “prod-safe” vs “dev-only” defaults
- keep docs explicit that `testpassword123` is test-only

### 2.2 Port/endpoint assumptions

- A lot of tooling assumes port 8529 unless overridden.
- The project now has dedicated local test scripts; those should be the preferred path to avoid conflicts.

---

## 3) Security risks

### 3.1 AQL injection surfaces via f-string interpolation

Several modules interpolate identifiers directly into AQL strings. Even if values are bound via bind vars, **collection names / view names / field identifiers** interpolated into queries can be an injection vector if they are ever user-controlled.

**Examples of dynamic identifier interpolation**:

- `Node2VecEmbeddingService.fetch_edges` builds:
  - `FOR e IN {self.edge_collection}` (see `src/entity_resolution/services/node2vec_embedding_service.py`)
  - **Issue**: `edge_collection` is not validated via `validate_collection_name` in `__init__`.

- `EmbeddingService.ensure_embeddings_exist` uses:
  - `query = f"FOR doc IN {collection_name} RETURN doc"` (see `src/entity_resolution/services/embedding_service.py`)
  - **Issue**: `collection_name` is not validated/sanitized before interpolation.

- `verify_view_analyzers` uses:
  - `test_query = f"FOR doc IN {view_name} LIMIT 1 RETURN 1"` (see `src/entity_resolution/utils/view_utils.py`)
  - **Issue**: `view_name` is not validated before interpolation.

- `CrossCollectionMatchingService` and multiple strategies build queries using `{self.source_collection_name}`, `{self.search_view}`, etc. (see `src/entity_resolution/services/cross_collection_matching_service.py` and strategies).
  - **Issue**: the constructor shown does not validate collection/view names.

**Positive note**:
- Some strategies do validate identifiers:
  - `HybridBlockingStrategy` uses `validate_view_name` and `validate_field_name` (see `src/entity_resolution/strategies/hybrid_blocking.py`)
  - many strategies validate `collection` via `BlockingStrategy` base class calling `validate_collection_name`

**Recommendation (high priority)**:
- enforce identifier validation consistently:
  - validate `collection_name`, `edge_collection`, `view_name` at construction time
  - validate `field` names whenever inserted as `doc.{field}`
- ensure anything that can come from config/user input goes through `validate_*_name`

### 3.2 Credentials and logging exposure risk (subprocess tools)

`AddressERService` shells out to `arangoimport` and passes password on the command line:
- `--server.password`, `password`
- logs stdout/stderr on failures (see `src/entity_resolution/services/address_er_service.py`)

**Risks**:
- command-line passwords can show up in process lists and shell history (platform-dependent)
- `stdout/stderr` may include sensitive connection data and should be treated carefully

**Recommendation**:
- prefer using ArangoDB driver bulk APIs where feasible
- if `arangoimport` is required for performance:
  - use a config file / env var mechanism if supported to avoid plaintext in argv
  - redact or limit logging of `stdout/stderr` on failure

### 3.3 Test credential defaults in pytest fixture

`tests/conftest.py` sets:
- `USE_DEFAULT_PASSWORD=true`
- `ARANGO_ROOT_PASSWORD=testpassword123`

This is convenient, but increases the chance of accidental reliance on defaults.

**Recommendation**:
- keep the convenience, but scope it to test runs only and make the behavior explicit (e.g., only set defaults if not already set and if `PYTEST_CURRENT_TEST` present — partially done).

---

## 4) Maintainability issues

### 4.1 Oversized / multi-responsibility modules

Some modules appear to do multiple responsibilities and/or are large and thus harder to reason about and test:
- `src/entity_resolution/services/address_er_service.py` (edge creation strategies, CSV export, subprocess import, clustering orchestration)
- `src/entity_resolution/services/cross_collection_matching_service.py` (config, matching logic, query building, scoring)
- `src/entity_resolution/services/embedding_service.py` (DB, embedding generation, batch update, multi-resolution logic)

**Recommendation**:
- split “query builder” vs “executor” vs “domain orchestration”
- isolate pure functions for scoring/query generation (easy to unit test)

### 4.2 Inconsistent env var conventions

Code uses multiple naming conventions:
- `ARANGO_USERNAME` vs `ARANGO_USER`
- `ARANGO_ROOT_PASSWORD` vs `ARANGO_PASSWORD`
- `ARANGO_DATABASE` vs `TEST_DB_NAME`

This adds cognitive load and can cause subtle misconfiguration.

**Recommendation**:
- define a single canonical set (documented), maintain backwards-compatible aliases in one place only (config loader)

### 4.3 Low-coverage hotspots (risk areas)

Recent coverage run shows several critical areas with low coverage (these are risk multipliers):
- `strategies/vector_blocking.py` ~22%
- `similarity/ann_adapter.py` ~13%
- core orchestration (`core/entity_resolver.py`, `core/configurable_pipeline.py`) low/moderate
- `services/address_er_service.py` very low

**Recommendation**:
- prioritize tests around orchestration edges (error handling, limits, safety)
- integration tests for AQL-heavy components (to catch query breakage early)

---

## 5) Suggested remediation plan (no changes applied yet)

### High priority (security + correctness)
- Validate all interpolated identifiers (`collection`, `edge_collection`, `view_name`, embedding field names)
- Centralize filter/query building to reduce drift and injection risk
- Reduce password exposure in subprocess calls (`arangoimport`)

### Medium priority (maintainability)
- Reduce `sys.path.insert` sprawl (package properly / editable installs)
- Split oversized services into smaller units
- Standardize env var naming

### Low priority (cleanup)
- Review archived/unused modules under `utils/archive_unused/`

---

## Remediation applied (2026-02-16)

The following items from this report were remediated on branch `feature/phase3-node-embeddings` with small, incremental changes.

### Applied changes

- [SECURITY] Consistent AQL identifier validation (collections/views/fields) for modules that interpolate identifiers into AQL strings.
- [SECURITY] Reduced credential leakage risk by redacting `arangoimport` failure logs and avoiding logging exception strings that can include argv.
- [MAINTAINABILITY] Introduced a shared AQL filter builder (`build_aql_filter_conditions`) that returns `(conditions, bind_vars)` and refactored two strategies to use it.
- [MAINTAINABILITY] Standardized environment variable conventions by preferring canonical vars while accepting backwards-compatible aliases.

### Test results

- `pytest -q`: PASS (399 passed, 17 skipped, 2 warnings)
- `pytest --cov=src --cov-report=json -q`: PASS (399 passed, 17 skipped, 2 warnings) -> wrote `coverage.json`
- `bash scripts/run_node2vec_integration_with_docker.sh`: PASS (2 integration tests passed)

