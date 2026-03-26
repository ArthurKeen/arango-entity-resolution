# Testing Guide

Current testing and release-validation guidance for `v3.5.0`.

---

## Overview

The test surface combines:
- unit tests for core algorithms and services
- database-backed tests using ArangoDB
- release validation through pre-push hooks and GitHub Actions
- targeted Docker-backed end-to-end checks for user-facing workflows

## Current Release Snapshot

During the `3.2.3` release pass (historical):
- focused regression suites passed locally
- Docker-backed end-to-end validation passed for pipeline run, status, clusters, export, and benchmark flows
- SmartGraph deterministic edge-key validation passed against a local Docker-based Enterprise ArangoDB SmartGraph
- the prior `3.2.2` release/push validation completed with **625 passed**

## Prerequisites

Install test dependencies:

```bash
pip install -e ".[test]"
```

Optional extras for broader surfaces:

```bash
pip install -e ".[test,mcp,llm,ml]"
```

## Environment Variables

Common environment variables:

```bash
export ARANGO_HOST=localhost
export ARANGO_PORT=8529
export ARANGO_USERNAME=root
export ARANGO_PASSWORD=testpassword123
export ARANGO_DATABASE=entity_resolution_test
export USE_DEFAULT_PASSWORD=true
```

The repo also supports a local `.env`-driven test setup.

## Running Tests

### Full Suite

```bash
pytest -v
```

### Unit-Marked Tests

```bash
pytest -v -m unit
```

### Targeted File or Slice

```bash
pytest tests/test_cli.py -v
pytest tests/test_pipeline_utils.py tests/test_mcp_tools.py -v
```

### Minimal Local Source Validation

When you want to ensure the local `src/` tree is used:

```bash
PYTHONPATH=src python -m pytest tests/test_cli.py -q
```

## Docker-Backed Validation

For local end-to-end or integration-style validation, run against a local ArangoDB container.

Example:

```bash
docker run -d --name arango-er-test -p 18530:8529 \
  -e ARANGO_ROOT_PASSWORD=testpassword123 \
  arangodb:3.12
```

Then point the CLI or tests at that instance with the standard env vars or command-line overrides.

## What To Validate Before Release

- CLI commands: `run`, `status`, `clusters`, `export`, `benchmark`
- MCP server startup: `arango-er-mcp`
- demo startup: `arango-er-demo` or `arango-er-mcp --demo`
- package build and metadata checks
- published version visibility on PyPI

## CI Expectations

Current CI workflows validate:
- the main Python test/build workflow
- the publish-to-PyPI workflow on release or manual dispatch

## Historical Testing Docs

Older status reports and archived testing artifacts remain under `docs/testing/` and `docs/archive/`, but this file is the current source of truth for how to test the project now.

---

## Related Docs

- [docs/testing/README.md](testing/README.md)
- [Release Checklist](development/RELEASE_CHECKLIST.md)
- [README](../README.md)
