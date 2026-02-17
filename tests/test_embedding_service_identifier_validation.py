from unittest.mock import Mock

import pytest

import entity_resolution.services.embedding_service as embedding_service


def _make_service(monkeypatch: pytest.MonkeyPatch, db_manager: Mock) -> embedding_service.EmbeddingService:
    # Avoid requiring sentence-transformers for these identifier validation tests.
    monkeypatch.setattr(embedding_service, "SENTENCE_TRANSFORMERS_AVAILABLE", True)
    return embedding_service.EmbeddingService(db_manager=db_manager)


def test_ensure_embeddings_exist_rejects_invalid_collection_name(monkeypatch: pytest.MonkeyPatch) -> None:
    db_manager = Mock()
    service = _make_service(monkeypatch, db_manager)

    with pytest.raises(ValueError, match="collection name"):
        service.ensure_embeddings_exist("bad-name", text_fields=["name"])

    db_manager.get_database.assert_not_called()


def test_get_embedding_stats_rejects_invalid_collection_name(monkeypatch: pytest.MonkeyPatch) -> None:
    db_manager = Mock()
    service = _make_service(monkeypatch, db_manager)

    with pytest.raises(ValueError, match="collection name"):
        service.get_embedding_stats("bad-name")

    db_manager.get_database.assert_not_called()


def test_ensure_embeddings_exist_rejects_invalid_embedding_field_name(monkeypatch: pytest.MonkeyPatch) -> None:
    db_manager = Mock()
    monkeypatch.setattr(embedding_service, "SENTENCE_TRANSFORMERS_AVAILABLE", True)
    service = embedding_service.EmbeddingService(embedding_field="bad-field!", db_manager=db_manager)

    with pytest.raises(ValueError, match="field name"):
        service.ensure_embeddings_exist("companies", text_fields=["name"])

    db_manager.get_database.assert_not_called()

