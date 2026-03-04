"""
Unit tests for utils/database.py

Covers DatabaseManager, DatabaseMixin, and the module-level helpers
without requiring a live ArangoDB instance.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db():
    """Return a mock that looks like a StandardDatabase."""
    db = MagicMock()
    db.properties.return_value = {"name": "test_db"}
    return db


def _make_mock_client(db=None):
    """Return a mock ArangoClient that yields *db* on .db(...)."""
    client = MagicMock()
    client.db.return_value = db or _make_mock_db()
    return client


# ---------------------------------------------------------------------------
# DatabaseManager
# ---------------------------------------------------------------------------

class TestDatabaseManager:
    """Tests for the DatabaseManager singleton."""

    def setup_method(self):
        """Reset the singleton before each test."""
        from entity_resolution.utils import database as mod
        # Wipe singleton state so tests are independent
        mod.DatabaseManager._instance = None
        mod.DatabaseManager._client = None
        mod.DatabaseManager._databases = {}

    def test_singleton_returns_same_instance(self):
        from entity_resolution.utils.database import DatabaseManager
        a = DatabaseManager()
        b = DatabaseManager()
        assert a is b

    def test_get_database_caches_connection(self):
        from entity_resolution.utils import database as mod

        mock_db = _make_mock_db()
        mock_client = _make_mock_client(mock_db)

        with patch.object(mod.DatabaseManager, "client", new_callable=PropertyMock, return_value=mock_client):
            manager = mod.DatabaseManager()
            db1 = manager.get_database("my_db")
            db2 = manager.get_database("my_db")

        assert db1 is db2
        mock_client.db.assert_called_once()

    def test_get_database_raises_on_failure(self):
        from entity_resolution.utils import database as mod
        from arango.exceptions import ArangoError

        mock_client = MagicMock()
        mock_client.db.side_effect = Exception("connection refused")

        with patch.object(mod.DatabaseManager, "client", new_callable=PropertyMock, return_value=mock_client):
            manager = mod.DatabaseManager()
            with pytest.raises(ArangoError):
                manager.get_database("bad_db")

    def test_test_connection_returns_true_on_success(self):
        from entity_resolution.utils import database as mod

        mock_db = _make_mock_db()
        mock_client = _make_mock_client(mock_db)

        with patch.object(mod.DatabaseManager, "client", new_callable=PropertyMock, return_value=mock_client):
            manager = mod.DatabaseManager()
            assert manager.test_connection() is True

    def test_test_connection_returns_false_on_failure(self):
        from entity_resolution.utils import database as mod

        mock_client = MagicMock()
        mock_client.db.side_effect = Exception("boom")

        with patch.object(mod.DatabaseManager, "client", new_callable=PropertyMock, return_value=mock_client):
            manager = mod.DatabaseManager()
            assert manager.test_connection() is False

    def test_get_connection_info_returns_dict(self):
        from entity_resolution.utils.database import DatabaseManager
        info = DatabaseManager().get_connection_info()
        assert "host" in info
        assert "port" in info
        assert "database" in info
        assert "url" in info

    def test_close_connections_clears_cache(self):
        from entity_resolution.utils import database as mod

        mock_db = _make_mock_db()
        mock_client = _make_mock_client(mock_db)

        with patch.object(mod.DatabaseManager, "client", new_callable=PropertyMock, return_value=mock_client):
            manager = mod.DatabaseManager()
            manager.get_database("db_to_clear")
            assert "db_to_clear" in manager._databases

        manager.close_connections()
        assert manager._databases == {}

    def test_create_database_if_not_exists_creates_when_missing(self):
        from entity_resolution.utils import database as mod

        system_db = MagicMock()
        system_db.has_database.return_value = False

        mock_client = MagicMock()
        mock_client.db.return_value = system_db
        system_db.properties.return_value = {}

        with patch.object(mod.DatabaseManager, "client", new_callable=PropertyMock, return_value=mock_client):
            manager = mod.DatabaseManager()
            result = manager.create_database_if_not_exists("new_db")

        assert result is True
        system_db.create_database.assert_called_once_with("new_db")

    def test_create_database_if_not_exists_skips_when_present(self):
        from entity_resolution.utils import database as mod

        system_db = MagicMock()
        system_db.has_database.return_value = True
        system_db.properties.return_value = {}

        mock_client = MagicMock()
        mock_client.db.return_value = system_db

        with patch.object(mod.DatabaseManager, "client", new_callable=PropertyMock, return_value=mock_client):
            manager = mod.DatabaseManager()
            result = manager.create_database_if_not_exists("existing_db")

        assert result is True
        system_db.create_database.assert_not_called()


# ---------------------------------------------------------------------------
# DatabaseMixin
# ---------------------------------------------------------------------------

class TestDatabaseMixin:
    """Tests for the DatabaseMixin helper class."""

    def setup_method(self):
        from entity_resolution.utils import database as mod
        mod.DatabaseManager._instance = None
        mod.DatabaseManager._client = None
        mod.DatabaseManager._databases = {}

    def test_database_property_caches_connection(self):
        from entity_resolution.utils import database as mod

        mock_db = _make_mock_db()
        mock_client = _make_mock_client(mock_db)

        with patch.object(mod.DatabaseManager, "client", new_callable=PropertyMock, return_value=mock_client):
            mixin = mod.DatabaseMixin()
            db1 = mixin.database
            db2 = mixin.database

        assert db1 is db2
        mock_client.db.assert_called_once()

    def test_test_connection_delegates_to_manager(self):
        from entity_resolution.utils import database as mod

        mock_db = _make_mock_db()
        mock_client = _make_mock_client(mock_db)

        with patch.object(mod.DatabaseManager, "client", new_callable=PropertyMock, return_value=mock_client):
            mixin = mod.DatabaseMixin()
            assert mixin.test_connection() is True

    def test_get_connection_info_returns_dict(self):
        from entity_resolution.utils import database as mod
        mixin = mod.DatabaseMixin()
        info = mixin.get_connection_info()
        assert isinstance(info, dict)
        assert "host" in info


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

class TestModuleFunctions:
    def setup_method(self):
        from entity_resolution.utils import database as mod
        mod.DatabaseManager._instance = None
        mod.DatabaseManager._client = None
        mod.DatabaseManager._databases = {}

    def test_get_database_manager_returns_singleton(self):
        from entity_resolution.utils.database import get_database_manager, DatabaseManager
        mgr = get_database_manager()
        assert isinstance(mgr, DatabaseManager)

    def test_get_connection_args_returns_expected_keys(self):
        from entity_resolution.utils.database import get_connection_args
        args = get_connection_args()
        assert set(args.keys()) == {"host", "port", "username", "password", "database"}

    def test_get_default_connection_args_emits_deprecation_warning(self):
        from entity_resolution.utils.database import get_default_connection_args
        with pytest.warns(DeprecationWarning):
            args = get_default_connection_args()
        assert "host" in args

    def test_arango_base_connection_emits_deprecation_warning(self):
        from entity_resolution.utils.database import ArangoBaseConnection
        with pytest.warns(DeprecationWarning):
            conn = ArangoBaseConnection()
        # Check the mixin's private attribute exists (accessing .database would trigger a real connection)
        assert hasattr(conn, "_database")
