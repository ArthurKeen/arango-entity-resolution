"""
ONNX model export utility for sentence-transformer models.

Exports a sentence-transformers model to ONNX format for use with
:class:`OnnxRuntimeEmbeddingBackend`. Optionally applies INT8 quantization
for faster CPU inference.

Requires ``optimum`` and ``onnx``::

    pip install optimum[onnxruntime] onnx

Example::

    from entity_resolution.services.onnx_model_exporter import export_model
    export_model("all-MiniLM-L6-v2", "./models/minilm-onnx", quantize=True)
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def export_model(
    model_name: str,
    output_dir: str,
    *,
    quantize: bool = False,
    opset: int = 14,
    task: str = "feature-extraction",
) -> Dict[str, Any]:
    """Export a sentence-transformers / HuggingFace model to ONNX.

    Parameters
    ----------
    model_name:
        HuggingFace model ID or local path (e.g. ``"all-MiniLM-L6-v2"``
        or ``"sentence-transformers/all-MiniLM-L6-v2"``).
    output_dir:
        Directory to write the ``.onnx`` model and tokenizer files.
    quantize:
        If True, apply dynamic INT8 quantization after export.
    opset:
        ONNX opset version (default 14 for broad compatibility).
    task:
        ``optimum`` task name.  ``"feature-extraction"`` produces the
        hidden-state output used for embeddings.

    Returns
    -------
    dict
        Metadata about the export: ``model_path``, ``quantized``,
        ``model_size_mb``, ``tokenizer_dir``.
    """
    try:
        from optimum.onnxruntime import ORTModelForFeatureExtraction
    except ImportError as exc:
        raise ImportError(
            "optimum[onnxruntime] is required for ONNX model export. "
            "Install with: pip install optimum[onnxruntime] onnx"
        ) from exc

    from transformers import AutoTokenizer

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    hf_name = model_name
    if "/" not in hf_name:
        hf_name = f"sentence-transformers/{hf_name}"

    logger.info("Exporting %s to ONNX (opset=%d) ...", hf_name, opset)
    model = ORTModelForFeatureExtraction.from_pretrained(
        hf_name,
        export=True,
    )
    model.save_pretrained(str(out))

    tokenizer = AutoTokenizer.from_pretrained(hf_name)
    tokenizer.save_pretrained(str(out))

    onnx_path = out / "model.onnx"
    if not onnx_path.exists():
        candidates = list(out.glob("*.onnx"))
        if candidates:
            onnx_path = candidates[0]

    result: Dict[str, Any] = {
        "model_path": str(onnx_path),
        "tokenizer_dir": str(out),
        "quantized": False,
        "model_size_mb": round(onnx_path.stat().st_size / (1024 * 1024), 1) if onnx_path.exists() else None,
    }

    if quantize:
        result = _quantize(onnx_path, out, result)

    logger.info(
        "Export complete: %s (%.1f MB, quantized=%s)",
        result["model_path"],
        result.get("model_size_mb", 0),
        result["quantized"],
    )
    return result


def _quantize(
    onnx_path: Path,
    output_dir: Path,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply dynamic INT8 quantization."""
    try:
        from optimum.onnxruntime import ORTQuantizer
        from optimum.onnxruntime.configuration import AutoQuantizationConfig
    except ImportError:
        logger.warning("optimum quantization not available; skipping")
        return result

    quantizer = ORTQuantizer.from_pretrained(str(output_dir))
    qconfig = AutoQuantizationConfig.avx512_vnni(is_static=False, per_channel=False)

    quantized_dir = output_dir / "quantized"
    quantized_dir.mkdir(exist_ok=True)
    quantizer.quantize(save_dir=str(quantized_dir), quantization_config=qconfig)

    q_path = quantized_dir / "model_quantized.onnx"
    if not q_path.exists():
        candidates = list(quantized_dir.glob("*.onnx"))
        if candidates:
            q_path = candidates[0]

    if q_path.exists():
        result["model_path"] = str(q_path)
        result["quantized"] = True
        result["model_size_mb"] = round(q_path.stat().st_size / (1024 * 1024), 1)

    return result


def validate_onnx_model(model_path: str) -> Dict[str, Any]:
    """Validate an ONNX model file and return its metadata.

    Parameters
    ----------
    model_path:
        Path to the ``.onnx`` file.

    Returns
    -------
    dict
        ``valid``, ``opset_version``, ``inputs``, ``outputs``,
        ``model_size_mb``, ``error``.
    """
    try:
        import onnx
    except ImportError:
        return {"valid": False, "error": "onnx package not installed"}

    try:
        model = onnx.load(model_path)
        onnx.checker.check_model(model)

        inputs = []
        for inp in model.graph.input:
            shape = [
                d.dim_value if d.dim_value else d.dim_param
                for d in inp.type.tensor_type.shape.dim
            ]
            inputs.append({"name": inp.name, "shape": shape})

        outputs = []
        for out in model.graph.output:
            shape = [
                d.dim_value if d.dim_value else d.dim_param
                for d in out.type.tensor_type.shape.dim
            ]
            outputs.append({"name": out.name, "shape": shape})

        opset = model.opset_import[0].version if model.opset_import else None

        return {
            "valid": True,
            "opset_version": opset,
            "inputs": inputs,
            "outputs": outputs,
            "model_size_mb": round(os.path.getsize(model_path) / (1024 * 1024), 1),
            "error": None,
        }
    except Exception as exc:
        return {"valid": False, "error": str(exc)}
