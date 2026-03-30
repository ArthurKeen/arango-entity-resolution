"""Tests for ONNX backend encode(), tokenizer handling, and model exporter."""

from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from entity_resolution.services.onnx_embedding_backend import (
    OnnxRuntimeEmbeddingBackend,
    PROVIDER_CPU,
)


class TestOnnxEncodeMethod:
    """Tests for the high-level encode() method."""

    def _make_backend_with_mocks(self):
        """Create a backend with mocked session and tokenizer."""
        backend = OnnxRuntimeEmbeddingBackend(
            model_path="/tmp/model.onnx", provider=PROVIDER_CPU
        )

        mock_session = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "input_ids"
        mock_session.get_inputs.return_value = [mock_input]

        def fake_run(_, inputs):
            batch_size = inputs["input_ids"].shape[0]
            return [np.random.randn(batch_size, 5, 384).astype(np.float32)]

        mock_session.run.side_effect = fake_run
        backend.session = mock_session

        mock_tokenizer = MagicMock()

        def fake_tokenize(texts, **kwargs):
            n = len(texts)
            return {
                "input_ids": np.ones((n, 5), dtype=np.int64),
                "attention_mask": np.ones((n, 5), dtype=np.int64),
            }

        mock_tokenizer.side_effect = fake_tokenize
        backend._tokenizer = mock_tokenizer

        return backend

    def test_encode_returns_correct_shape(self):
        backend = self._make_backend_with_mocks()
        texts = ["hello world", "foo bar"]
        result = backend.encode(texts)
        assert result.shape == (2, 384)

    def test_encode_normalizes_by_default(self):
        backend = self._make_backend_with_mocks()
        result = backend.encode(["test text"])
        norms = np.linalg.norm(result, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-6)

    def test_encode_no_normalize(self):
        backend = self._make_backend_with_mocks()
        result = backend.encode(["test text"], normalize=False)
        norm = np.linalg.norm(result[0])
        # Pooled random logits are not unit length; normalize=False must skip L2 scaling.
        assert norm != pytest.approx(1.0, abs=0.01)

    def test_encode_batching(self):
        backend = self._make_backend_with_mocks()
        texts = [f"text {i}" for i in range(10)]
        result = backend.encode(texts, batch_size=3)
        assert result.shape[0] == 10
        assert backend.session.run.call_count == 4  # 3+3+3+1

    def test_encode_respects_max_batch_size(self):
        backend = self._make_backend_with_mocks()
        texts = [f"text {i}" for i in range(20)]
        result = backend.encode(texts, batch_size=100, max_batch_size=5)
        assert result.shape[0] == 20
        assert backend.session.run.call_count == 4  # 5+5+5+5

    def test_encode_auto_loads_model_if_needed(self):
        backend = OnnxRuntimeEmbeddingBackend(
            model_path="/tmp/model.onnx", provider=PROVIDER_CPU
        )
        assert backend.session is None

        with patch.object(backend, "load_model") as mock_load:
            with patch.object(backend, "load_tokenizer") as mock_tok:
                mock_load.side_effect = lambda: setattr(backend, "session", MagicMock())
                mock_tok.side_effect = lambda: setattr(backend, "_tokenizer", MagicMock())
                try:
                    backend.encode(["test"])
                except Exception:
                    pass
                mock_load.assert_called_once()

    def test_encode_empty_list(self):
        backend = self._make_backend_with_mocks()
        result = backend.encode([])
        assert result.size == 0


class TestOnnxTokenizerLoading:
    def test_load_tokenizer_raises_without_transformers(self, monkeypatch):
        backend = OnnxRuntimeEmbeddingBackend(
            model_path="/tmp/model.onnx", provider=PROVIDER_CPU
        )
        monkeypatch.setitem(
            __import__("sys").modules, "transformers", None
        )
        with pytest.raises(ImportError, match="transformers"):
            backend.load_tokenizer("/tmp")


class TestOnnxModelExporter:
    def test_export_model_raises_without_optimum(self, monkeypatch):
        monkeypatch.setitem(
            __import__("sys").modules, "optimum", None
        )
        monkeypatch.setitem(
            __import__("sys").modules, "optimum.onnxruntime", None
        )
        from entity_resolution.services.onnx_model_exporter import export_model

        with pytest.raises(ImportError, match="optimum"):
            export_model("all-MiniLM-L6-v2", "/tmp/onnx-out")

    def test_validate_onnx_model_missing_package(self, monkeypatch):
        monkeypatch.setitem(__import__("sys").modules, "onnx", None)
        from entity_resolution.services.onnx_model_exporter import validate_onnx_model

        result = validate_onnx_model("/tmp/nonexistent.onnx")
        assert result["valid"] is False
        assert "not installed" in result["error"]

    def test_validate_onnx_model_missing_file(self):
        from entity_resolution.services.onnx_model_exporter import validate_onnx_model

        result = validate_onnx_model("/tmp/definitely_not_a_file.onnx")
        assert result["valid"] is False
