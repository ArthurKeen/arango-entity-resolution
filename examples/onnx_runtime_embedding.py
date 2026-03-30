"""
Example: ONNX Runtime Embedding Backend

Demonstrates exporting a sentence-transformers model to ONNX format and
using the OnnxRuntimeEmbeddingBackend for faster embedding generation.

The example walks through three stages:
  1. Export a HuggingFace model to ONNX (with optional INT8 quantization)
  2. Validate the exported ONNX artifact
  3. Encode texts with the ONNX backend and compare latency against the
     default sentence-transformers PyTorch backend

Prerequisites:
  - pip install entity-resolution[onnx]
    (installs onnxruntime, optimum, onnx, transformers, sentence-transformers)

Usage:
    python examples/onnx_runtime_embedding.py
"""

import shutil
import tempfile
import time
from pathlib import Path


MODEL_NAME = "all-MiniLM-L6-v2"

SAMPLE_TEXTS = [
    "Acme Corporation, 123 Main St, Springfield IL 62701",
    "ACME Corp, 123 Main Street, Springfield, IL 62701",
    "Globex Industries, 742 Evergreen Terrace, Shelbyville IL 62565",
    "Wayne Enterprises, 1007 Mountain Dr, Gotham NJ 07001",
    "Wayne Corp, 1007 Mountain Drive, Gotham, New Jersey 07001",
    "Stark Industries, 10880 Malibu Point, Malibu CA 90265",
    "Stark Ind., 10880 Malibu Pt, Malibu California 90265",
    "Umbrella Corporation, Raccoon City, Arklay County",
]


def step_export(output_dir: str, quantize: bool = False):
    """Export a sentence-transformers model to ONNX."""
    try:
        from entity_resolution.services.onnx_model_exporter import export_model
    except ImportError:
        print(
            "ERROR: optimum[onnxruntime] is required for ONNX export.\n"
            "       pip install optimum[onnxruntime] onnx"
        )
        return None

    print(f"Exporting '{MODEL_NAME}' to ONNX (quantize={quantize})...")
    result = export_model(MODEL_NAME, output_dir, quantize=quantize)

    print(f"  Model path : {result['model_path']}")
    print(f"  Size       : {result['model_size_mb']} MB")
    print(f"  Quantized  : {result['quantized']}")
    print(f"  Tokenizer  : {result['tokenizer_dir']}")
    return result


def step_validate(model_path: str):
    """Validate the exported ONNX model."""
    try:
        from entity_resolution.services.onnx_model_exporter import validate_onnx_model
    except ImportError:
        print("(onnx package not installed — skipping validation)")
        return None

    print(f"\nValidating {model_path} ...")
    info = validate_onnx_model(model_path)

    if info["valid"]:
        print(f"  Valid       : True")
        print(f"  Opset       : {info['opset_version']}")
        print(f"  Inputs      : {info['inputs']}")
        print(f"  Outputs     : {info['outputs']}")
        print(f"  Size        : {info['model_size_mb']} MB")
    else:
        print(f"  Valid: False — {info['error']}")

    return info


def step_onnx_encode(model_path: str, texts: list[str]):
    """Encode texts using the ONNX backend."""
    try:
        from entity_resolution.services.onnx_embedding_backend import (
            OnnxRuntimeEmbeddingBackend,
        )
    except ImportError:
        print("ERROR: onnxruntime is required.  pip install onnxruntime")
        return None, 0.0

    print(f"\nEncoding {len(texts)} texts with ONNX backend...")

    backend = OnnxRuntimeEmbeddingBackend(model_path=model_path, provider="auto")
    backend.load_model()
    backend.load_tokenizer()

    health = backend.health()
    print(f"  Provider    : {health['provider']}  (requested: {health['requested_provider']})")
    print(f"  Optimization: {health['session_optimization_level']}")
    if health.get("coreml_warmup_p95_latency_ms") is not None:
        print(f"  CoreML p95  : {health['coreml_warmup_p95_latency_ms']} ms")

    start = time.perf_counter()
    embeddings = backend.encode(texts, batch_size=32)
    elapsed = time.perf_counter() - start

    print(f"  Shape       : {embeddings.shape}")
    print(f"  Time        : {elapsed:.4f}s ({elapsed / len(texts) * 1000:.1f} ms/text)")
    return embeddings, elapsed


def step_pytorch_encode(texts: list[str]):
    """Encode texts using the default sentence-transformers PyTorch backend."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("(sentence-transformers not installed — skipping PyTorch comparison)")
        return None, 0.0

    print(f"\nEncoding {len(texts)} texts with PyTorch backend...")
    model = SentenceTransformer(MODEL_NAME)

    start = time.perf_counter()
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)
    elapsed = time.perf_counter() - start

    print(f"  Shape       : {embeddings.shape}")
    print(f"  Time        : {elapsed:.4f}s ({elapsed / len(texts) * 1000:.1f} ms/text)")
    return embeddings, elapsed


def compare_embeddings(onnx_emb, pytorch_emb):
    """Compare cosine similarity between ONNX and PyTorch outputs."""
    import numpy as np

    if onnx_emb is None or pytorch_emb is None:
        return

    norms_a = np.linalg.norm(onnx_emb, axis=1, keepdims=True)
    norms_b = np.linalg.norm(pytorch_emb, axis=1, keepdims=True)
    cos_sim = np.sum(
        (onnx_emb / np.maximum(norms_a, 1e-12))
        * (pytorch_emb / np.maximum(norms_b, 1e-12)),
        axis=1,
    )

    print(f"\nONNX vs PyTorch cosine similarity per text:")
    for i, sim in enumerate(cos_sim):
        print(f"  [{i}] {sim:.6f}")
    print(f"  Mean: {cos_sim.mean():.6f}  Min: {cos_sim.min():.6f}")


def main():
    tmp_dir = tempfile.mkdtemp(prefix="onnx_er_example_")
    print(f"Working directory: {tmp_dir}\n")

    try:
        # --- Stage 1: Export ---
        print("=" * 60)
        print("Stage 1: Export model to ONNX")
        print("=" * 60)
        export_result = step_export(tmp_dir, quantize=False)
        if export_result is None:
            return

        # --- Stage 2: Validate ---
        print("\n" + "=" * 60)
        print("Stage 2: Validate ONNX model")
        print("=" * 60)
        step_validate(export_result["model_path"])

        # --- Stage 3: Encode & Compare ---
        print("\n" + "=" * 60)
        print("Stage 3: Encode texts & compare backends")
        print("=" * 60)
        onnx_emb, onnx_time = step_onnx_encode(export_result["model_path"], SAMPLE_TEXTS)
        pytorch_emb, pytorch_time = step_pytorch_encode(SAMPLE_TEXTS)

        if onnx_time > 0 and pytorch_time > 0:
            speedup = pytorch_time / onnx_time
            faster = "ONNX" if speedup > 1.0 else "PyTorch"
            ratio = max(speedup, 1.0 / speedup)
            print(f"\n  >>> {faster} is ~{ratio:.1f}x faster on this batch")

        compare_embeddings(onnx_emb, pytorch_emb)

    finally:
        # Cleanup
        print(f"\nCleaning up {tmp_dir}")
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("\nDone.")


if __name__ == "__main__":
    main()
