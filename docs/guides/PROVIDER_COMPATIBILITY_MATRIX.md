# ONNX Runtime Provider Compatibility Matrix

**Version:** 3.5.1 | **Last Updated:** March 30, 2026

This document provides a detailed compatibility matrix for ONNX Runtime embedding
providers in the arango-entity-resolution system, covering platform requirements,
auto-detection behavior, fallback chains, and known limitations.

**Related docs:**
- [Platform Setup Guide](PLATFORM_SETUP.md) -- hardware-specific installation and configuration
- [Provider Matrix](PROVIDER_MATRIX.md) -- full provider table including PyTorch, LLMs, and clustering
- [Runtime Health CI Runbook](../development/RUNTIME_HEALTH_CI_RUNBOOK.md) -- CI gating and baseline management

---

## Provider Detail Table

### CPU (CPUExecutionProvider)

| Attribute | Value |
|-----------|-------|
| Platform | All (macOS, Linux, Windows) |
| Hardware | Any x86_64 or arm64 CPU |
| Driver versions | N/A |
| Python package | `pip install arango-entity-resolution[onnx]` (installs `onnxruntime`) |
| Auto-detection | Always available; final fallback for all platforms |
| Known limitations | None -- universally supported |
| Performance | Baseline reference (1x). Throughput scales with core count. |

CPU is the default and guaranteed provider. Every other provider falls back to CPU
on initialization failure. All sentence-transformers ONNX exports are expected to
work on CPU without restriction.

### CoreML (CoreMLExecutionProvider)

| Attribute | Value |
|-----------|-------|
| Platform | macOS (Apple Silicon and Intel Mac with macOS 12.3+) |
| Hardware | Apple M1/M2/M3/M4 (Neural Engine + GPU); Intel Mac (GPU only) |
| Driver versions | macOS 12.3+ (Monterey or later); Xcode Command Line Tools recommended |
| Python package | `pip install onnxruntime` (CoreML provider is built into the macOS wheel) |
| Auto-detection | Selected when `provider: auto` on macOS if CoreMLExecutionProvider is listed in `ort.get_available_providers()` |
| Known limitations | See section below |
| Performance | Typically 1.5--3x faster than CPU on Apple Silicon; varies by model and op coverage |

**CoreML known limitations:**

- Some ONNX opsets (>= 18) may include ops that CoreML cannot partition. In this
  case the session silently falls back to CPU for unsupported subgraphs, which can
  degrade performance below pure-CPU execution.
- CoreML compilation adds one-time startup latency (first session creation is slower).
  Use `coreml_warmup_runs` to amortize this.
- If the warmup p95 latency exceeds `coreml_max_p95_latency_ms`, the backend
  automatically falls back to CPU and records a `last_fallback_reason`.
- `coreml_use_basic_optimizations: true` is recommended to keep compilation time
  and memory usage predictable.

### CUDA (CUDAExecutionProvider)

| Attribute | Value |
|-----------|-------|
| Platform | Linux x86_64 |
| Hardware | NVIDIA GPU with CUDA Compute Capability 3.5+ |
| Driver versions | NVIDIA driver 525+, CUDA Toolkit 11.8+ or 12.x, cuDNN 8.6+ |
| Python package | `pip install onnxruntime-gpu` (replaces `onnxruntime` package) |
| Auto-detection | Selected when `provider: auto` on Linux if CUDAExecutionProvider is available and TensorRT is not |
| Known limitations | See section below |
| Performance | Typically 3--10x faster than CPU; highly dependent on GPU model and batch size |

**CUDA known limitations:**

- `onnxruntime-gpu` and `onnxruntime` cannot coexist in the same environment.
  Install only one.
- CUDA/cuDNN version mismatches cause silent session creation failures. Verify
  versions with `nvidia-smi` and `onnxruntime.get_device()`.
- Large models or batch sizes can trigger OOM. Reduce `max_batch_size` or use
  the OOM-protection retry built into the backend.

### TensorRT (TensorrtExecutionProvider)

| Attribute | Value |
|-----------|-------|
| Platform | Linux x86_64 |
| Hardware | NVIDIA GPU with CUDA Compute Capability 6.1+ (Pascal or newer) |
| Driver versions | NVIDIA driver 525+, CUDA 11.8+/12.x, cuDNN 8.6+, TensorRT 8.6+ |
| Python package | `pip install onnxruntime-gpu` (TensorRT provider included in GPU wheel) |
| Auto-detection | Selected first when `provider: auto` on Linux if TensorrtExecutionProvider is available |
| Known limitations | See section below |
| Performance | Typically 5--15x faster than CPU; best throughput for batch embedding on supported hardware |

**TensorRT known limitations:**

- TensorRT engine compilation is expensive on first run (can take several minutes
  per model). Subsequent loads use cached engines if the model and hardware match.
- Not all ONNX ops are supported. Unsupported ops fall back to CUDA or CPU
  subgraph execution, which may reduce throughput gains.
- TensorRT version must match the `onnxruntime-gpu` build. Mismatches produce
  opaque initialization errors.
- TensorRT provider is only available in the `onnxruntime-gpu` package; the
  standard `onnxruntime` package does not include it.

---

## Model Compatibility

Most sentence-transformers models export to ONNX and work across all providers.
The table below lists models that have been explicitly tested in CI or development.

| Model | CPU | CoreML (macOS) | CUDA (Linux) | TensorRT (Linux) | Notes |
|-------|-----|----------------|--------------|-------------------|-------|
| `all-MiniLM-L6-v2` | Tested | Tested | Tested | Tested | Primary CI model; small and fast |
| `all-MiniLM-L12-v2` | Tested | Tested | Tested | Tested | Higher quality, moderate size |
| `all-mpnet-base-v2` | Tested | Tested | Tested | Not tested | Larger model; good accuracy |
| `paraphrase-MiniLM-L6-v2` | Tested | Tested | Not tested | Not tested | Paraphrase-optimized variant |
| `multi-qa-MiniLM-L6-cos-v1` | Tested | Not tested | Not tested | Not tested | QA-optimized; CPU verified |

**General model compatibility notes:**

- Any model that exports to ONNX opset 14--17 is expected to work on all providers.
- Opset 18+ models may encounter unsupported ops on CoreML or TensorRT, causing
  partial subgraph fallback. Check `resolved_provider` and `fallback_count` in
  runtime-health telemetry to detect this.
- Custom fine-tuned models should be validated with `arango-er runtime-health`
  before production use.

---

## Fallback Chain

The ONNX Runtime backend uses a deterministic fallback chain that depends on the
platform and available providers.

### macOS Apple Silicon

```
CoreML -> CPU
```

1. If `provider: auto`, the backend checks for `CoreMLExecutionProvider`.
2. If CoreML is available, a warmup probe runs `coreml_warmup_runs` batches.
3. If warmup p95 latency exceeds `coreml_max_p95_latency_ms`, CoreML is abandoned
   and the backend falls back to CPU. The `last_fallback_reason` field records the
   cause (e.g., `warmup_latency_exceeded`).
4. If CoreML is not available in `ort.get_available_providers()`, CPU is used
   directly.

### Linux NVIDIA

```
TensorRT -> CUDA -> CPU
```

1. If `provider: auto`, the backend checks providers in priority order:
   TensorRT, then CUDA, then CPU.
2. The first provider that initializes successfully is used.
3. If TensorRT initialization fails (e.g., version mismatch, unsupported ops),
   the backend tries CUDA.
4. If CUDA initialization also fails, the backend falls back to CPU.

### Other Platforms (Linux without NVIDIA, Windows, Intel Mac)

```
CPU
```

CPU is used directly. No accelerator probing occurs.

### Failure Behavior

| Scenario | Behavior |
|----------|----------|
| Provider fails to initialize | Next provider in chain is tried; `fallback_count` incremented |
| Provider encounters unsupported op | Subgraph runs on CPU; session stays on original provider but with mixed execution |
| All providers fail | CPU is used as final fallback (always succeeds) |
| `fallback_to_cpu: false` set explicitly | Initialization error is raised instead of falling back |
| Provider produces OOM | Backend retries with reduced batch size; if still failing, raises error |

Fallback events are logged at WARNING level and recorded in telemetry fields:
- `fallback_count` -- total number of fallbacks during backend lifetime
- `last_fallback_reason` -- human-readable reason for the most recent fallback
- `requested_provider` vs `resolved_provider` -- shows whether fallback occurred

Use `arango-er runtime-health` to inspect these fields:

```bash
arango-er runtime-health -c config.yaml | jq '{
  requested_provider,
  resolved_provider,
  health: {
    fallback_count: .health.fallback_count,
    last_fallback_reason: .health.last_fallback_reason
  }
}'
```

---

## Quick Reference

Provider-by-platform status matrix:

| Provider | macOS Apple Silicon | macOS Intel | Linux x86_64 (NVIDIA) | Linux x86_64 (no GPU) | Windows |
|----------|--------------------:|------------:|----------------------:|----------------------:|--------:|
| CPU | Supported | Supported | Supported | Supported | Supported |
| CoreML | Supported | Supported | Not available | Not available | Not available |
| CUDA | Not available | Not available | Experimental | Not available | Not available |
| TensorRT | Not available | Not available | Experimental | Not available | Not available |

**Status definitions:**

- **Supported** -- tested in CI, expected to work in production.
- **Experimental** -- functional but not yet promoted to default; may require
  manual configuration or have edge-case issues. Use `arango-er runtime-health-gate`
  to validate before relying on it.
- **Not available** -- provider cannot be used on this platform (hardware or
  driver dependencies are not met).

### Installation Quick Reference

| Provider | Install command |
|----------|----------------|
| CPU | `pip install arango-entity-resolution[onnx]` |
| CoreML | `pip install arango-entity-resolution[onnx]` (macOS wheel includes CoreML) |
| CUDA | `pip install onnxruntime-gpu` |
| TensorRT | `pip install onnxruntime-gpu` (TensorRT included in GPU wheel) |

### Configuration Quick Reference

```yaml
# CPU (explicit)
entity_resolution:
  embedding:
    runtime: onnxruntime
    provider: cpu

# Auto-select best available
entity_resolution:
  embedding:
    runtime: onnxruntime
    provider: auto

# CoreML (macOS, explicit)
entity_resolution:
  embedding:
    runtime: onnxruntime
    provider: coreml
    coreml_use_basic_optimizations: true
    coreml_warmup_runs: 10
    coreml_max_p95_latency_ms: 65.0

# CUDA (Linux, explicit)
entity_resolution:
  embedding:
    runtime: onnxruntime
    provider: cuda

# TensorRT (Linux, explicit)
entity_resolution:
  embedding:
    runtime: onnxruntime
    provider: tensorrt
```

---

## Verification Commands

Check available providers in your environment:

```python
import onnxruntime as ort
print(ort.get_available_providers())
```

Verify runtime health and resolved provider:

```bash
arango-er runtime-health -c config.yaml
```

Run a CI gate to validate provider readiness against a baseline:

```bash
arango-er runtime-health-gate \
  -c config.yaml \
  --registry-file artifacts/runtime/runtime_registry.json \
  --label dev-mac \
  --fail-on-regression
```

Benchmark provider performance:

```bash
arango-er runtime-health-benchmark \
  -c config.yaml \
  --profile dev-mac-coreml \
  --repeats 10 \
  --output-dir artifacts/runtime/benchmark \
  --filename-prefix provider_benchmark
```
