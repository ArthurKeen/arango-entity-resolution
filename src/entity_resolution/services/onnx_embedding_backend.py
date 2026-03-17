"""
ONNX Runtime embedding backend scaffold.

Provides a runtime/provider abstraction for ONNX-based embedding inference with
platform-aware provider resolution and deterministic CPU fallback.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
import math
import time

import numpy as np


PROVIDER_CPU = "cpu"
PROVIDER_COREML = "coreml"
PROVIDER_CUDA = "cuda"
PROVIDER_TENSORRT = "tensorrt"
PROVIDER_AUTO = "auto"

_CANONICAL_PROVIDERS = {
    PROVIDER_CPU,
    PROVIDER_COREML,
    PROVIDER_CUDA,
    PROVIDER_TENSORRT,
    PROVIDER_AUTO,
}

_ORT_PROVIDER_NAMES = {
    PROVIDER_CPU: "CPUExecutionProvider",
    PROVIDER_COREML: "CoreMLExecutionProvider",
    PROVIDER_CUDA: "CUDAExecutionProvider",
    PROVIDER_TENSORRT: "TensorrtExecutionProvider",
}


@dataclass
class OnnxProviderInfo:
    """Resolved provider metadata exposed to callers and telemetry."""

    requested_provider: str
    resolved_provider: str
    available_providers: List[str]
    fallback_to_cpu: bool


class OnnxRuntimeEmbeddingBackend:
    """ONNX Runtime backend with provider resolution and fallback."""

    def __init__(
        self,
        model_path: str,
        provider: str = PROVIDER_AUTO,
        provider_options: Optional[Dict[str, Any]] = None,
        fallback_to_cpu: bool = True,
        coreml_use_basic_optimizations: bool = True,
        coreml_warmup_runs: int = 10,
        coreml_max_p95_latency_ms: float = 65.0,
        coreml_warmup_batch_size: int = 8,
        coreml_warmup_seq_len: int = 128,
    ):
        if provider not in _CANONICAL_PROVIDERS:
            raise ValueError(
                "provider must be one of 'cpu', 'coreml', 'cuda', 'tensorrt', or 'auto', "
                f"got: {provider}"
            )

        self.model_path = model_path
        self.requested_provider = provider
        self.provider_options = provider_options or {}
        self.fallback_to_cpu = fallback_to_cpu
        self.coreml_use_basic_optimizations = coreml_use_basic_optimizations
        self.coreml_warmup_runs = coreml_warmup_runs
        self.coreml_max_p95_latency_ms = coreml_max_p95_latency_ms
        self.coreml_warmup_batch_size = coreml_warmup_batch_size
        self.coreml_warmup_seq_len = coreml_warmup_seq_len
        self.session = None
        self.resolved_provider = PROVIDER_CPU
        self.available_ort_providers: List[str] = []
        self.fallback_count = 0
        self.last_fallback_reason: Optional[str] = None
        self.last_warmup_p95_latency_ms: Optional[float] = None
        self.session_optimization_level: Optional[str] = None

    @staticmethod
    def _get_available_ort_providers() -> List[str]:
        try:
            import onnxruntime as ort
        except ImportError:
            return [_ORT_PROVIDER_NAMES[PROVIDER_CPU]]
        return list(ort.get_available_providers())

    @staticmethod
    def _is_apple_silicon() -> bool:
        return platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")

    def resolve_provider(self, requested: Optional[str] = None) -> str:
        """Resolve requested provider to a canonical provider value."""
        provider = requested or self.requested_provider
        available = self._get_available_ort_providers()
        self.available_ort_providers = available

        if provider != PROVIDER_AUTO:
            provider_name = _ORT_PROVIDER_NAMES.get(provider)
            if provider_name in available:
                return provider
            if self.fallback_to_cpu and provider != PROVIDER_CPU:
                self.fallback_count += 1
                self.last_fallback_reason = (
                    f"requested provider '{provider}' unavailable; falling back to 'cpu'"
                )
                return PROVIDER_CPU
            return provider

        if self._is_apple_silicon():
            if _ORT_PROVIDER_NAMES[PROVIDER_COREML] in available:
                return PROVIDER_COREML
            return PROVIDER_CPU

        if _ORT_PROVIDER_NAMES[PROVIDER_TENSORRT] in available:
            return PROVIDER_TENSORRT
        if _ORT_PROVIDER_NAMES[PROVIDER_CUDA] in available:
            return PROVIDER_CUDA
        return PROVIDER_CPU

    def _providers_for_session(self, resolved: str) -> List[Any]:
        providers: List[Any] = []
        primary_name = _ORT_PROVIDER_NAMES.get(resolved, _ORT_PROVIDER_NAMES[PROVIDER_CPU])
        if self.provider_options:
            providers.append((primary_name, self.provider_options))
        else:
            providers.append(primary_name)

        if self.fallback_to_cpu and resolved != PROVIDER_CPU:
            providers.append(_ORT_PROVIDER_NAMES[PROVIDER_CPU])
        return providers

    def _build_session_options(self, ort: Any, resolved_provider: str) -> Any:
        options = ort.SessionOptions()
        if (
            resolved_provider == PROVIDER_COREML
            and self.coreml_use_basic_optimizations
        ):
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
            self.session_optimization_level = "ORT_ENABLE_BASIC"
        else:
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session_optimization_level = "ORT_ENABLE_ALL"
        return options

    @staticmethod
    def _node_arg_dtype(type_str: str) -> Any:
        mapping = {
            "tensor(float)": np.float32,
            "tensor(float16)": np.float16,
            "tensor(double)": np.float64,
            "tensor(int64)": np.int64,
            "tensor(int32)": np.int32,
            "tensor(int16)": np.int16,
            "tensor(int8)": np.int8,
            "tensor(uint8)": np.uint8,
            "tensor(bool)": np.bool_,
        }
        return mapping.get(type_str, np.float32)

    def _dummy_input_shape(self, shape: Sequence[Any]) -> List[int]:
        resolved: List[int] = []
        for idx, dim in enumerate(shape or []):
            if isinstance(dim, int) and dim > 0:
                resolved.append(dim)
                continue
            if idx == 0:
                resolved.append(self.coreml_warmup_batch_size)
            elif idx == 1:
                resolved.append(self.coreml_warmup_seq_len)
            else:
                resolved.append(1)
        if not resolved:
            resolved = [self.coreml_warmup_batch_size, self.coreml_warmup_seq_len]
        return resolved

    def _build_dummy_inputs(self) -> Dict[str, np.ndarray]:
        if self.session is None:
            raise RuntimeError("ONNX session is not initialized")
        feed: Dict[str, np.ndarray] = {}
        for node_arg in self.session.get_inputs():
            dtype = self._node_arg_dtype(node_arg.type)
            shape = self._dummy_input_shape(node_arg.shape)
            if np.issubdtype(dtype, np.integer):
                arr = np.random.randint(0, 1000, size=shape, dtype=dtype)
            elif dtype == np.bool_:
                arr = np.zeros(shape, dtype=np.bool_)
            else:
                arr = np.random.rand(*shape).astype(dtype)
            feed[node_arg.name] = arr
        return feed

    def _run_coreml_warmup(self) -> float:
        if self.session is None:
            return 0.0
        if self.coreml_warmup_runs <= 0:
            return 0.0
        inputs = self._build_dummy_inputs()
        latencies_ms: List[float] = []
        for _ in range(self.coreml_warmup_runs):
            start = time.perf_counter()
            self.session.run(None, inputs)
            end = time.perf_counter()
            latencies_ms.append(float((end - start) * 1000.0))
        if not latencies_ms:
            return 0.0
        sorted_latencies = sorted(latencies_ms)
        p95_idx = max(0, math.ceil(0.95 * len(sorted_latencies)) - 1)
        return float(sorted_latencies[p95_idx])

    def _fallback_to_cpu(self, ort: Any, reason: str) -> None:
        if not self.fallback_to_cpu:
            return
        self.fallback_count += 1
        self.last_fallback_reason = reason
        self.resolved_provider = PROVIDER_CPU
        cpu_options = ort.SessionOptions()
        cpu_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session_optimization_level = "ORT_ENABLE_ALL"
        self.session = ort.InferenceSession(
            self.model_path,
            sess_options=cpu_options,
            providers=[_ORT_PROVIDER_NAMES[PROVIDER_CPU]],
        )

    def load_model(self) -> None:
        """Create and cache an ONNX Runtime inference session."""
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ImportError(
                "onnxruntime is required for OnnxRuntimeEmbeddingBackend. "
                "Install with: pip install onnxruntime"
            ) from exc

        self.resolved_provider = self.resolve_provider(self.requested_provider)
        providers = self._providers_for_session(self.resolved_provider)
        session_options = self._build_session_options(ort, self.resolved_provider)
        self.session = ort.InferenceSession(
            self.model_path,
            sess_options=session_options,
            providers=providers,
        )

        # ORT can silently drop CoreML and run CPU only.
        active = set(self.session.get_providers())
        if (
            self.resolved_provider == PROVIDER_COREML
            and _ORT_PROVIDER_NAMES[PROVIDER_COREML] not in active
            and self.fallback_to_cpu
        ):
            self._fallback_to_cpu(
                ort,
                "coreml provider requested but not active in initialized session",
            )
            return

        if self.resolved_provider == PROVIDER_COREML and self.fallback_to_cpu:
            p95 = self._run_coreml_warmup()
            self.last_warmup_p95_latency_ms = round(p95, 3)
            if p95 > float(self.coreml_max_p95_latency_ms):
                self._fallback_to_cpu(
                    ort,
                    (
                        "coreml warmup p95 latency exceeded threshold: "
                        f"{round(p95, 3)}ms > {self.coreml_max_p95_latency_ms}ms"
                    ),
                )

    def infer(self, inputs: Dict[str, np.ndarray]) -> List[np.ndarray]:
        """Run ONNX inference using pre-tokenized tensor inputs."""
        if self.session is None:
            self.load_model()
        if self.session is None:
            raise RuntimeError("ONNX session failed to initialize")
        return self.session.run(None, inputs)

    def health(self) -> Dict[str, Any]:
        """Return health and provider-state information."""
        if not self.available_ort_providers:
            self.available_ort_providers = self._get_available_ort_providers()
        return {
            "ok": self.session is not None or bool(self.available_ort_providers),
            "model_path": self.model_path,
            "requested_provider": self.requested_provider,
            "provider": self.resolved_provider,
            "available_ort_providers": self.available_ort_providers,
            "session_initialized": self.session is not None,
            "active_session_providers": self.session.get_providers() if self.session is not None else [],
            "session_optimization_level": self.session_optimization_level,
            "fallback_count": self.fallback_count,
            "last_fallback_reason": self.last_fallback_reason,
            "coreml_warmup_p95_latency_ms": self.last_warmup_p95_latency_ms,
            "coreml_max_p95_latency_ms": self.coreml_max_p95_latency_ms,
        }

    def provider_info(self) -> OnnxProviderInfo:
        """Return structured provider selection details."""
        return OnnxProviderInfo(
            requested_provider=self.requested_provider,
            resolved_provider=self.resolved_provider,
            available_providers=self.available_ort_providers,
            fallback_to_cpu=self.fallback_to_cpu,
        )

