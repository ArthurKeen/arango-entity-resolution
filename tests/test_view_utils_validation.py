import pytest

from entity_resolution.utils.view_utils import verify_view_analyzers


class _DummyDB:
    def views(self):
        raise AssertionError("db.views should not be called for invalid view_name")


def test_verify_view_analyzers_rejects_invalid_view_name() -> None:
    with pytest.raises(ValueError, match="name"):
        verify_view_analyzers(_DummyDB(), view_name="bad-view", collection_name="companies")

