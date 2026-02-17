import pytest

from entity_resolution.services.cross_collection_matching_service import CrossCollectionMatchingService


class _DummyDB:
    def collection(self, name: str):
        return object()

    def has_collection(self, name: str) -> bool:
        return True

    def create_collection(self, name: str, edge: bool = False):
        return object()


def test_init_rejects_invalid_collection_names() -> None:
    with pytest.raises(ValueError, match="collection name"):
        CrossCollectionMatchingService(
            db=_DummyDB(),
            source_collection="bad-name",
            target_collection="companies",
            edge_collection="similarTo",
        )


def test_init_rejects_invalid_search_view_name() -> None:
    with pytest.raises(ValueError, match="name"):
        CrossCollectionMatchingService(
            db=_DummyDB(),
            source_collection="registrations",
            target_collection="companies",
            edge_collection="similarTo",
            search_view="bad-view",
        )


def test_configure_matching_rejects_invalid_logical_field_identifiers() -> None:
    svc = CrossCollectionMatchingService(
        db=_DummyDB(),
        source_collection="registrations",
        target_collection="companies",
        edge_collection="similarTo",
    )

    with pytest.raises(ValueError, match="field name"):
        svc.configure_matching(
            source_fields={"bad-name": "company_name"},
            target_fields={"bad-name": "legal_name"},
            field_weights={"bad-name": 1.0},
            blocking_fields=["bad-name"],
        )


def test_configure_matching_rejects_invalid_source_target_field_names() -> None:
    svc = CrossCollectionMatchingService(
        db=_DummyDB(),
        source_collection="registrations",
        target_collection="companies",
        edge_collection="similarTo",
    )

    with pytest.raises(ValueError, match="field name"):
        svc.configure_matching(
            source_fields={"name": "bad-field!"},
            target_fields={"name": "legal_name"},
            field_weights={"name": 1.0},
        )

