# Platform Setup Guide

**Version:** 3.5.1 | **Last Updated:** March 30, 2026

This guide covers hardware-specific setup for embedding generation and GPU-accelerated workloads across supported platforms.

---

## CPU (All Platforms)

CPU is the default and requires no extra setup.

```bash
pip install arango-entity-resolution[ml]
```

```yaml
entity_resolution:
  embedding:
    device: cpu
    runtime: pytorch
```

Typical throughput: ~50–200 records/second depending on model size and CPU.

---

## Apple Silicon (MPS)

Apple M1/M2/M3/M4 chips support Metal Performance Shaders (MPS) for GPU-accelerated PyTorch inference.

### Prerequisites

- macOS 12.3+ (Monterey or later)
- Python 3.10+
- PyTorch 2.0+ (ships with MPS support)

### Installation

```bash
pip install arango-entity-resolution[ml]
```

No additional drivers required — MPS is built into macOS.

### Configuration

```yaml
entity_resolution:
  embedding:
    device: auto    # auto-detects MPS on Apple Silicon
    runtime: pytorch
```

Or explicitly:

```yaml
entity_resolution:
  embedding:
    device: mps
    runtime: pytorch
```

### Verification

```python
import torch
print(torch.backends.mps.is_available())  # True on Apple Silicon
print(torch.backends.mps.is_built())      # True if PyTorch built with MPS
```

### Performance Notes

- MPS is typically 2-5x faster than CPU for embedding generation
- Some operations may fall back to CPU silently — check logs for warnings
- `max_batch_size` can be increased (e.g., 256–512) on machines with 16GB+ unified memory

---

## Linux CUDA (NVIDIA GPUs)

### Prerequisites

- NVIDIA GPU with CUDA Compute Capability 3.5+
- CUDA Toolkit 11.8+ or 12.x
- cuDNN 8.6+
- NVIDIA driver 525+

### Installation

```bash
# Install PyTorch with CUDA support
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install arango-entity-resolution[ml]
```

### Configuration

```yaml
entity_resolution:
  embedding:
    device: auto    # auto-detects CUDA
    runtime: pytorch
    max_batch_size: 512
```

### Verification

```python
import torch
print(torch.cuda.is_available())        # True
print(torch.cuda.get_device_name(0))    # e.g., "NVIDIA A100"
print(torch.cuda.get_device_properties(0).total_memory / 1e9)  # GB
```

### OOM Protection

If you encounter CUDA out-of-memory errors, reduce `max_batch_size`:

```yaml
entity_resolution:
  embedding:
    max_batch_size: 64   # reduce until stable
```

The system will log a warning and automatically retry with smaller batches.

---

## ONNX Runtime (Optional)

ONNX Runtime provides an alternative inference backend with platform-specific accelerators.

### Installation

```bash
# CPU only
pip install arango-entity-resolution[onnx]

# GPU (CUDA)
pip install onnxruntime-gpu
```

### Supported Providers

| Provider | Platform | Install |
|----------|----------|---------|
| CPUExecutionProvider | All | `pip install onnxruntime` |
| CUDAExecutionProvider | Linux + NVIDIA | `pip install onnxruntime-gpu` |
| TensorrtExecutionProvider | Linux + NVIDIA | `pip install onnxruntime-gpu` |
| CoreMLExecutionProvider | macOS | `pip install onnxruntime` (built-in on macOS wheels) |

### Configuration

```yaml
entity_resolution:
  embedding:
    runtime: onnxruntime
    provider: auto         # selects best available
    onnx_model_path: ./models/all-MiniLM-L6-v2.onnx
```

### Provider Auto-Selection

When `provider: auto`:

1. **macOS** — CoreML if available, else CPU
2. **Linux** — TensorRT > CUDA > CPU (first available wins)
3. **All** — CPU as final fallback

---

## Device Auto-Detection

Setting `device: auto` (the default since v3.4.0) runs this resolution:

1. Check for CUDA (`torch.cuda.is_available()`)
2. Check for MPS (`torch.backends.mps.is_available()`)
3. Fall back to CPU

The resolved device is logged at startup and included in pipeline metadata:

```python
service = EmbeddingService(model_name="all-MiniLM-L6-v2", device="auto")
print(service.resolved_device)  # "mps", "cuda", or "cpu"
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `device: auto` selects CPU despite GPU | PyTorch not built with GPU support | Reinstall PyTorch with correct index URL |
| CUDA OOM errors | Batch too large for GPU memory | Reduce `max_batch_size` |
| MPS crash on older macOS | MPS requires macOS 12.3+ | Update macOS or use `device: cpu` |
| ONNX CoreML fallback to CPU | CoreML provider not in wheel | Check `ort.get_available_providers()` |
