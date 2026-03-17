# Phase 0 Completion Notes

Date: 2026-03-14
Status: Completed
Scope: Embedding runtime GPU-readiness foundation (Apple Silicon + Linux)

## Delivered

- Added embedding runtime/provider config surface:
  - `runtime`, `provider`, `provider_options`, `onnx_model_path`, `startup_mode`
- Added ONNX runtime backend scaffold with provider resolution and fallback:
  - `coreml -> cpu` (Apple Silicon)
  - `tensorrt -> cuda -> cpu` (Linux NVIDIA)
- Added runtime setup, health, and telemetry in pipeline results.
- Added strict/permissive startup controls for provider/device readiness.
- Added vector/LSH config integration and embedding preflight diagnostics.
- Added runtime telemetry artifact export and baseline registry workflows.
- Added runtime compare workflows with JSON/Markdown/CSV report artifacts.
- Added one-shot CI gate command with optional fail-on-regression.
- Added baseline bootstrap mode for first-run environments.
- Added operations runbook:
  - `docs/development/RUNTIME_HEALTH_CI_RUNBOOK.md`

## CLI Commands Available

- `arango-er runtime-health`
- `arango-er runtime-health-export`
- `arango-er runtime-health-baseline`
- `arango-er runtime-health-compare`
- `arango-er runtime-health-gate`
- `arango-er status --include-runtime-health --config <path>`

## CI Gate Behavior

- Exit `0`: success/no gated regression
- Exit `1`: command/runtime error
- Exit `2`: regression detected when `--fail-on-regression` is enabled

## Recommended Next Steps (Phase 1)

- Build representative benchmark corpus and throughput/latency harness.
- Add quality drift and retrieval stability gates for target models.
- Expand CI matrix with dedicated Apple Silicon and Linux GPU runners.
- Use current runtime gate flow as required pre-promotion guardrail.

