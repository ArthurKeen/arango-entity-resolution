"""Tests for EmbeddingConfig device/runtime validation and EmbeddingService.resolve_device()."""

from __future__ import annotations

import types
from unittest.mock import patch

import pytest

from entity_resolution.config.er_config import EmbeddingConfig


# ---------------------------------------------------------------------------
# EmbeddingConfig device validation
# ---------------------------------------------------------------------------

class TestEmbeddingConfigDevice:
    @pytest.mark.parametrize("device", ["cpu", "cuda", "mps", "auto"])
    def test_valid_devices_accepted(self, device):
        cfg = EmbeddingConfig(device=device)
        errors = cfg.validate()
        assert not any("device" in e for e in errors)

    def test_invalid_device_rejected(self):
        cfg = EmbeddingConfig(device="tpu")
        errors = cfg.validate()
        assert any("device" in e for e in errors)

    @pytest.mark.parametrize("runtime", ["pytorch", "onnxruntime"])
    def test_valid_runtimes_accepted(self, runtime):
        cfg = EmbeddingConfig(
            runtime=runtime,
            onnx_model_path="/tmp/model.onnx" if runtime == "onnxruntime" else None,
        )
        errors = cfg.validate()
        assert not any("runtime" in e for e in errors)

    def test_invalid_runtime_rejected(self):
        cfg = EmbeddingConfig(runtime="tflite")
        errors = cfg.validate()
        assert any("runtime" in e for e in errors)

    def test_batch_size_accepted(self):
        cfg = EmbeddingConfig(batch_size=64)
        assert cfg.batch_size == 64
        assert cfg.validate() == []

    def test_batch_size_zero_rejected(self):
        cfg = EmbeddingConfig(batch_size=0)
        errors = cfg.validate()
        assert any("batch_size" in e for e in errors)


# ---------------------------------------------------------------------------
# EmbeddingService.resolve_device
# ---------------------------------------------------------------------------

class TestResolveDevice:
    """Mirrors test_embedding_service_multi_resolution but focused on resolve_device."""

    def _make_service(self, device: str):
        from entity_resolution.services.embedding_service import EmbeddingService
        return EmbeddingService(device=device)

    def test_cpu_passthrough(self):
        svc = self._make_service("cpu")
        assert svc.device == "cpu"

    def test_auto_picks_cuda_when_available(self):
        fake_torch = types.SimpleNamespace(
            cuda=types.SimpleNamespace(is_available=lambda: True),
            backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False)),
        )
        with patch.dict("sys.modules", {"torch": fake_torch}):
            svc = self._make_service("auto")
            assert svc.device == "cuda"

    def test_auto_picks_mps_when_cuda_absent(self):
        fake_torch = types.SimpleNamespace(
            cuda=types.SimpleNamespace(is_available=lambda: False),
            backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: True)),
        )
        with patch.dict("sys.modules", {"torch": fake_torch}):
            svc = self._make_service("auto")
            assert svc.device == "mps"

    def test_auto_falls_back_to_cpu(self):
        fake_torch = types.SimpleNamespace(
            cuda=types.SimpleNamespace(is_available=lambda: False),
            backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False)),
        )
        with patch.dict("sys.modules", {"torch": fake_torch}):
            svc = self._make_service("auto")
            assert svc.device == "cpu"

    def test_requested_device_stored(self):
        svc = self._make_service("cpu")
        assert svc.requested_device == "cpu"
