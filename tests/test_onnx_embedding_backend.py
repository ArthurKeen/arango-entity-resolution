from __future__ import annotations

from entity_resolution.services.onnx_embedding_backend import (
    OnnxRuntimeEmbeddingBackend,
    PROVIDER_AUTO,
    PROVIDER_COREML,
    PROVIDER_CPU,
    PROVIDER_CUDA,
    PROVIDER_TENSORRT,
)


def test_resolve_provider_prefers_coreml_on_apple_silicon(monkeypatch) -> None:
    backend = OnnxRuntimeEmbeddingBackend(model_path="/tmp/model.onnx", provider=PROVIDER_AUTO)
    monkeypatch.setattr(backend, "_is_apple_silicon", lambda: True)
    monkeypatch.setattr(
        backend,
        "_get_available_ort_providers",
        lambda: ["CoreMLExecutionProvider", "CPUExecutionProvider"],
    )
    assert backend.resolve_provider() == PROVIDER_COREML


def test_resolve_provider_prefers_tensorrt_then_cuda_on_linux(monkeypatch) -> None:
    backend = OnnxRuntimeEmbeddingBackend(model_path="/tmp/model.onnx", provider=PROVIDER_AUTO)
    monkeypatch.setattr(backend, "_is_apple_silicon", lambda: False)

    monkeypatch.setattr(
        backend,
        "_get_available_ort_providers",
        lambda: ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    assert backend.resolve_provider() == PROVIDER_TENSORRT

    monkeypatch.setattr(
        backend,
        "_get_available_ort_providers",
        lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    assert backend.resolve_provider() == PROVIDER_CUDA


def test_resolve_provider_falls_back_to_cpu(monkeypatch) -> None:
    backend = OnnxRuntimeEmbeddingBackend(model_path="/tmp/model.onnx", provider=PROVIDER_AUTO)
    monkeypatch.setattr(backend, "_is_apple_silicon", lambda: False)
    monkeypatch.setattr(backend, "_get_available_ort_providers", lambda: ["CPUExecutionProvider"])
    assert backend.resolve_provider() == PROVIDER_CPU


def test_health_reports_available_providers_without_session(monkeypatch) -> None:
    backend = OnnxRuntimeEmbeddingBackend(model_path="/tmp/model.onnx", provider=PROVIDER_AUTO)
    monkeypatch.setattr(backend, "_get_available_ort_providers", lambda: ["CPUExecutionProvider"])
    health = backend.health()
    assert health["ok"] is True
    assert health["session_initialized"] is False
    assert "CPUExecutionProvider" in health["available_ort_providers"]


def test_explicit_unavailable_provider_falls_back_to_cpu(monkeypatch) -> None:
    backend = OnnxRuntimeEmbeddingBackend(model_path="/tmp/model.onnx", provider=PROVIDER_CUDA)
    monkeypatch.setattr(backend, "_get_available_ort_providers", lambda: ["CPUExecutionProvider"])
    resolved = backend.resolve_provider(PROVIDER_CUDA)
    assert resolved == PROVIDER_CPU
    assert backend.fallback_count == 1
    assert "falling back to 'cpu'" in (backend.last_fallback_reason or "")


def test_load_model_silent_coreml_drop_falls_back_to_cpu(monkeypatch) -> None:
    class _FakeSession:
        def __init__(self, providers):
            self._providers = (
                ["CPUExecutionProvider"]
                if "CoreMLExecutionProvider" in providers
                else ["CPUExecutionProvider"]
            )

        def get_providers(self):
            return self._providers

        def get_inputs(self):
            return []

        def run(self, *_args, **_kwargs):
            return []

    class _FakeORT:
        class GraphOptimizationLevel:
            ORT_ENABLE_BASIC = 1
            ORT_ENABLE_ALL = 2

        class SessionOptions:
            def __init__(self):
                self.graph_optimization_level = None

        @staticmethod
        def get_available_providers():
            return ["CoreMLExecutionProvider", "CPUExecutionProvider"]

        @staticmethod
        def InferenceSession(_model_path, sess_options=None, providers=None):
            return _FakeSession(providers or [])

    monkeypatch.setitem(__import__("sys").modules, "onnxruntime", _FakeORT)
    backend = OnnxRuntimeEmbeddingBackend(
        model_path="/tmp/model.onnx",
        provider=PROVIDER_COREML,
    )
    backend.load_model()
    assert backend.resolved_provider == PROVIDER_CPU
    assert backend.fallback_count == 1
    assert "not active" in (backend.last_fallback_reason or "")


def test_load_model_coreml_warmup_fallbacks_on_high_p95(monkeypatch) -> None:
    class _FakeNodeArg:
        def __init__(self, name, type_str, shape):
            self.name = name
            self.type = type_str
            self.shape = shape

    class _FakeSession:
        def __init__(self, providers):
            self._providers = providers
            self._run_count = 0

        def get_providers(self):
            return self._providers

        def get_inputs(self):
            return [_FakeNodeArg("input_ids", "tensor(int64)", [None, None])]

        def run(self, *_args, **_kwargs):
            self._run_count += 1
            return []

    class _FakeORT:
        class GraphOptimizationLevel:
            ORT_ENABLE_BASIC = 1
            ORT_ENABLE_ALL = 2

        class SessionOptions:
            def __init__(self):
                self.graph_optimization_level = None

        @staticmethod
        def get_available_providers():
            return ["CoreMLExecutionProvider", "CPUExecutionProvider"]

        @staticmethod
        def InferenceSession(_model_path, sess_options=None, providers=None):
            # preserve order requested by backend
            return _FakeSession(providers or ["CPUExecutionProvider"])

    monkeypatch.setitem(__import__("sys").modules, "onnxruntime", _FakeORT)
    backend = OnnxRuntimeEmbeddingBackend(
        model_path="/tmp/model.onnx",
        provider=PROVIDER_COREML,
        coreml_warmup_runs=3,
        coreml_max_p95_latency_ms=1.0,  # force fallback
    )
    # Force warmup p95 above threshold deterministically.
    monkeypatch.setattr(backend, "_run_coreml_warmup", lambda: 99.0)
    backend.load_model()
    assert backend.resolved_provider == PROVIDER_CPU
    assert backend.fallback_count == 1
    assert "warmup p95 latency exceeded threshold" in (backend.last_fallback_reason or "")
