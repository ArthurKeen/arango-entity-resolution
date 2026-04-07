# Provider Rollout Runbook

**Version:** 3.5.1 | **Last Updated:** March 30, 2026

This runbook covers the operational procedures for rolling out, monitoring, and
rolling back ONNX Runtime provider changes in the arango-entity-resolution system.

**Related docs:**
- [Platform Setup Guide](../guides/PLATFORM_SETUP.md) -- hardware-specific installation and configuration
- [Provider Compatibility Matrix](../guides/PROVIDER_COMPATIBILITY_MATRIX.md) -- provider details, fallback chains, and model compatibility
- [Runtime Health CI Runbook](RUNTIME_HEALTH_CI_RUNBOOK.md) -- CI gating, baselines, and benchmark commands

---

## Pre-Rollout Checklist

Complete every item before changing provider defaults or promoting a provider
from experimental to supported.

### 1. Baseline Benchmarks

- [ ] Baseline registry exists for the target environment label
      (`arango-er runtime-health-baseline --label <label>`)
- [ ] Benchmark artifacts exist with at least 10 repeats
      (`arango-er runtime-health-benchmark --repeats 10`)
- [ ] Baseline latency numbers are documented and committed to
      `ci/runtime-quality/baselines/<profile>.json`

### 2. Quality Gates

- [ ] Quality baseline metrics exist
      (`arango-er runtime-quality-baseline --corpus <corpus> --model-name <model>`)
- [ ] Cosine similarity drift threshold is configured (recommended: < 0.01)
- [ ] Top-K overlap threshold is configured (recommended: >= 0.95)
- [ ] Quality comparison passes against current baseline:

```bash
arango-er runtime-quality-compare \
  --current-metrics artifacts/quality/current_metrics.json \
  --baseline-metrics artifacts/quality/baseline_metrics.json \
  --cosine-drift-max 0.01 \
  --topk-overlap-min 0.95
```

### 3. Retrieval Stability

- [ ] Run the full embedding pipeline on a representative sample with the new
      provider and compare retrieval results against the CPU baseline
- [ ] Confirm that match/non-match classification is stable (no new false
      positives or false negatives beyond expected variance)

### 4. Platform Verification

- [ ] New provider is listed in `ort.get_available_providers()` on target machines
- [ ] `arango-er runtime-health -c config.yaml` shows the expected
      `resolved_provider` value
- [ ] No WARNING or ERROR entries related to provider initialization in logs

---

## Rollout Procedure

### Step 1: Establish Baseline for the New Provider

Capture a fresh baseline with the new provider active:

```bash
# Set provider in config.yaml to the new provider (or auto)
arango-er runtime-health-baseline \
  -c config.yaml \
  --registry-file artifacts/runtime/runtime_registry.json \
  --label <environment-label>

arango-er runtime-quality-baseline \
  --corpus artifacts/quality/runtime_quality_corpus.json \
  --model-name all-MiniLM-L6-v2 \
  --device auto \
  --output-dir artifacts/quality
```

### Step 2: Per-Model Feature Flag Approach

Roll out the provider change incrementally using per-model configuration:

```yaml
# Promote one model at a time
entity_resolution:
  embedding:
    runtime: onnxruntime
    provider: auto               # or explicit provider name
    models:
      all-MiniLM-L6-v2:
        provider: coreml         # promoted model
      all-mpnet-base-v2:
        provider: cpu            # not yet promoted -- stays on CPU
```

This allows per-model rollback without affecting other models.

### Step 3: Choose `provider: auto` vs Explicit Provider

| Approach | When to use |
|----------|-------------|
| `provider: auto` | Default for most deployments. The backend selects the best available provider per platform. Safest option because it falls back gracefully. |
| Explicit (`provider: coreml`, `provider: cuda`, etc.) | Use when you need deterministic provider selection, such as benchmarking or when `auto` selects an unwanted provider. |

In CI, prefer explicit providers for reproducibility. In production, prefer
`provider: auto` for resilience.

### Step 4: CI Gate Validation

Run the CI gate with `--fail-on-regression` to validate the new provider before
merging:

```bash
arango-er runtime-health-gate \
  -c config.yaml \
  --registry-file artifacts/runtime/runtime_registry.json \
  --label ci-linux \
  --latency-regression-pct 20 \
  --fail-on-regression

# With quality gate
arango-er runtime-health-gate \
  -c config.yaml \
  --registry-file artifacts/runtime/runtime_registry.json \
  --label ci-linux \
  --quality-current-metrics artifacts/quality/current_metrics.json \
  --quality-baseline-metrics artifacts/quality/baseline_metrics.json \
  --quality-cosine-drift-max 0.01 \
  --quality-topk-overlap-min 0.95 \
  --fail-on-regression
```

Exit codes:
- `0` -- no regressions detected
- `1` -- command or runtime error
- `2` -- regression detected

### Step 5: Merge and Deploy

1. Open a PR with the provider configuration change.
2. Ensure CI gate passes (exit code 0).
3. Include benchmark artifacts in the PR for reviewer reference.
4. Merge after reviewer approval.
5. Monitor post-deployment (see Monitoring section below).

---

## Monitoring

### Key Telemetry Fields

After rollout, monitor the following fields in embedding metadata and
`arango-er runtime-health` output:

| Field | Where | What to watch |
|-------|-------|---------------|
| `requested_provider` | runtime-health JSON | Should match intended provider or `auto` |
| `resolved_provider` | runtime-health JSON | Should match expected accelerator (not `cpu` unless intended) |
| `fallback_count` | runtime-health JSON, telemetry | Should be 0 in steady state; any increase indicates fallback events |
| `last_fallback_reason` | runtime-health JSON, telemetry | Should be `null`; non-null indicates a fallback occurred |
| `coreml_warmup_p95_latency_ms` | runtime-health JSON (CoreML only) | Should be below `coreml_max_p95_latency_ms` |
| `session_optimization_level` | runtime-health JSON | Should match configured level |

### Monitoring Commands

Quick health check:

```bash
arango-er runtime-health -c config.yaml | jq '{
  requested_provider,
  resolved_provider,
  health: {
    provider: .health.provider,
    fallback_count: .health.fallback_count,
    last_fallback_reason: .health.last_fallback_reason,
    active_session_providers: .health.active_session_providers
  },
  telemetry: {
    provider_used: .telemetry.provider_used,
    fallback_count: .telemetry.fallback_count,
    fallback_occurred: .telemetry.fallback_occurred
  }
}'
```

Latency trend check (run periodically):

```bash
arango-er runtime-health-benchmark \
  -c config.yaml \
  --profile prod-coreml \
  --repeats 10 \
  --output-dir artifacts/runtime/benchmark \
  --filename-prefix monitoring_benchmark
```

Compare against baseline to detect drift:

```bash
arango-er runtime-health-compare \
  -c config.yaml \
  --registry-file artifacts/runtime/runtime_registry.json \
  --label prod-mac \
  --latency-regression-pct 20 \
  --output-dir artifacts/runtime/compare \
  --filename-prefix monitoring_compare
```

### Alert Conditions

| Condition | Severity | Action |
|-----------|----------|--------|
| `resolved_provider` != `requested_provider` (and not `auto`) | High | Investigate provider initialization failure; consider rollback |
| `fallback_count` > 0 after deployment | Medium | Check `last_fallback_reason`; may indicate transient issue or persistent incompatibility |
| Latency regression > 20% vs baseline | Medium | Re-run benchmark to confirm; if sustained, investigate or rollback |
| Quality drift (cosine > 0.01 or top-K overlap < 0.95) | High | Immediate rollback; investigate model or provider change |

---

## Rollback Procedure

### Emergency CPU Override

Force all embedding inference to CPU immediately by setting the provider
explicitly in the pipeline config:

```yaml
entity_resolution:
  embedding:
    runtime: onnxruntime
    provider: cpu        # forces CPU, bypasses auto-detection
```

Alternatively, set `device: cpu` if using the PyTorch runtime:

```yaml
entity_resolution:
  embedding:
    device: cpu
    runtime: pytorch
```

No code change or restart of the embedding backend is needed if the system
re-reads configuration on each pipeline run. For long-running services, a
restart is required after config change.

### Per-Model Rollback

If only one model is affected, roll back that model's provider while keeping
others on the accelerator:

```yaml
entity_resolution:
  embedding:
    runtime: onnxruntime
    provider: auto
    models:
      all-MiniLM-L6-v2:
        provider: cpu            # rolled back to CPU
      all-mpnet-base-v2:
        provider: auto           # still using accelerator
```

### Global Rollback

To revert the entire provider change:

1. Revert the config PR (or push a new commit setting `provider: cpu`).
2. Re-run CI gate to confirm CPU baseline still passes:

```bash
arango-er runtime-health-gate \
  -c config.yaml \
  --registry-file artifacts/runtime/runtime_registry.json \
  --label ci-linux \
  --fail-on-regression
```

3. Deploy the reverted config.
4. Verify with `arango-er runtime-health` that `resolved_provider` is `cpu`.

### Rollback Verification

After any rollback, confirm:

- [ ] `resolved_provider` is the expected fallback provider
- [ ] `fallback_count` is 0 (no additional fallbacks occurring)
- [ ] Quality metrics match CPU baseline within thresholds
- [ ] Latency is within expected CPU range

---

## Incident Response

### Provider Initialization Failure

**Symptoms:** `resolved_provider` shows `cpu` when an accelerator was expected;
WARNING log entries about provider initialization.

**Diagnosis:**

```bash
# Check available providers
python -c "import onnxruntime as ort; print(ort.get_available_providers())"

# Check runtime health for fallback details
arango-er runtime-health -c config.yaml | jq '{
  resolved_provider,
  health: {
    last_fallback_reason,
    fallback_count,
    active_session_providers
  }
}'
```

**Common causes:**
- `onnxruntime-gpu` not installed (CUDA/TensorRT missing from available providers)
- CUDA/cuDNN version mismatch (driver too old for the installed `onnxruntime-gpu`)
- CoreML provider not present in macOS wheel (rare; check wheel build variant)
- TensorRT library not found or version incompatible

**Resolution:**
1. Fix the dependency or driver issue.
2. Re-run `arango-er runtime-health` to verify.
3. If the fix requires downtime, apply emergency CPU override first, then fix.

### OOM Errors on GPU

**Symptoms:** CUDA out-of-memory errors in logs; embedding pipeline crashes or
produces partial results.

**Diagnosis:**

```bash
# Check GPU memory usage
nvidia-smi

# Check configured batch size
grep max_batch_size config.yaml
```

**Resolution:**
1. Reduce `max_batch_size` in the pipeline config (try halving until stable):

```yaml
entity_resolution:
  embedding:
    max_batch_size: 32    # reduce from default
```

2. If OOM persists at batch size 1, the model is too large for the GPU.
   Fall back to CPU or use a smaller model.
3. Ensure no other processes are consuming GPU memory on the same device.

### Embedding Quality Drift Detected

**Symptoms:** `arango-er runtime-quality-compare` reports cosine drift > 0.01 or
top-K overlap < 0.95; downstream match results change unexpectedly.

**Diagnosis:**

```bash
arango-er runtime-quality-compare \
  --current-metrics artifacts/quality/current_metrics.json \
  --baseline-metrics artifacts/quality/baseline_metrics.json \
  --cosine-drift-max 0.01 \
  --topk-overlap-min 0.95
```

**Common causes:**
- Provider change causing numerical differences (different precision, op
  implementations, or subgraph partitioning)
- Model file corruption or version mismatch
- Tokenizer version skew

**Resolution:**
1. Apply emergency CPU override immediately.
2. Compare embeddings from the suspect provider vs CPU for a sample of records.
3. If the drift is within acceptable business tolerance, update the baseline:

```bash
arango-er runtime-quality-baseline \
  --corpus artifacts/quality/runtime_quality_corpus.json \
  --model-name all-MiniLM-L6-v2 \
  --device auto \
  --output-dir artifacts/quality
```

4. If the drift is unacceptable, keep CPU override and investigate the root cause
   (model version, provider version, ONNX opset).

### Model Load Timeout

**Symptoms:** Embedding service hangs during initialization; no embeddings
produced within expected startup window.

**Diagnosis:**
- Check if TensorRT engine compilation is in progress (first run on new hardware
  can take several minutes)
- Check if CoreML model compilation is blocked (disk I/O or memory pressure)
- Check system resource utilization (CPU, memory, disk I/O)

**Resolution:**
1. If this is the first run with TensorRT, wait for engine compilation to complete
   (can take 5--15 minutes depending on model size and GPU).
2. For CoreML, increase `coreml_warmup_runs` timeout or switch to CPU for initial
   deployment.
3. If the timeout is persistent:
   - Apply CPU override to restore service.
   - Pre-compile TensorRT engines offline and cache them.
   - For CoreML, verify disk space and I/O performance.

### Quick Triage Decision Tree

```
Is the service producing embeddings?
 |
 +-- NO --> Apply emergency CPU override (provider: cpu)
 |          Check logs for initialization errors
 |          Follow "Provider Initialization Failure" above
 |
 +-- YES --> Are embeddings correct (quality within thresholds)?
              |
              +-- NO --> Apply emergency CPU override
              |          Follow "Embedding Quality Drift" above
              |
              +-- YES --> Is latency acceptable?
                           |
                           +-- NO --> Check fallback_count and resolved_provider
                           |          If fallback occurred, follow rollback procedure
                           |          If no fallback, benchmark and compare to baseline
                           |
                           +-- YES --> System healthy; continue monitoring
```

---

## Appendix: CLI Command Quick Reference

| Task | Command |
|------|---------|
| Check runtime health | `arango-er runtime-health -c config.yaml` |
| Export health snapshot | `arango-er runtime-health-export -c config.yaml --output-dir artifacts/runtime` |
| Capture baseline | `arango-er runtime-health-baseline -c config.yaml --registry-file <registry> --label <label>` |
| Compare to baseline | `arango-er runtime-health-compare -c config.yaml --registry-file <registry> --label <label>` |
| CI gate (fail on regression) | `arango-er runtime-health-gate -c config.yaml --registry-file <registry> --label <label> --fail-on-regression` |
| Benchmark latency | `arango-er runtime-health-benchmark -c config.yaml --repeats 10` |
| Generate quality metrics | `arango-er runtime-quality-benchmark --corpus <corpus> --model-name <model>` |
| Capture quality baseline | `arango-er runtime-quality-baseline --corpus <corpus> --model-name <model>` |
| Compare quality metrics | `arango-er runtime-quality-compare --current-metrics <current> --baseline-metrics <baseline>` |
| Bootstrap baseline (first run) | `arango-er runtime-health-gate -c config.yaml --registry-file <registry> --label <label> --bootstrap-baseline` |
