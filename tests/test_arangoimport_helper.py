"""Unit tests for entity_resolution.etl.arangoimport."""

import os
from unittest.mock import MagicMock, patch

import pytest

from entity_resolution.etl.arangoimport import (
    arangoimport_jsonl,
    get_arangoimport_connection_args,
)


class TestGetArangoimportConnectionArgs:
    def test_defaults(self):
        args = get_arangoimport_connection_args()
        assert args["endpoint"] == "http://localhost:8529"
        assert args["username"] == "root"
        assert args["database"] == "_system"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("ARANGO_HOST", "db.example.com")
        monkeypatch.setenv("ARANGO_PORT", "9529")
        monkeypatch.setenv("ARANGO_USERNAME", "admin")
        monkeypatch.setenv("ARANGO_PASSWORD", "secret")
        monkeypatch.setenv("ARANGO_DATABASE", "mydb")

        args = get_arangoimport_connection_args()
        assert args["endpoint"] == "http://db.example.com:9529"
        assert args["username"] == "admin"
        assert args["password"] == "secret"
        assert args["database"] == "mydb"

    def test_from_db_object(self):
        db = MagicMock()
        db.name = "testdb"
        db.connection.host = "remotehost"
        db.connection.port = 1234
        db.connection.username = "testuser"
        db.connection.password = "testpass"

        args = get_arangoimport_connection_args(db)
        assert args["database"] == "testdb"

    def test_env_overrides_db(self, monkeypatch):
        monkeypatch.setenv("ARANGO_HOST", "envhost")
        db = MagicMock()
        db.name = "testdb"
        db.connection.host = "dbhost"
        db.connection.port = 8529
        db.connection.username = "root"
        db.connection.password = ""

        args = get_arangoimport_connection_args(db)
        assert "envhost" in args["endpoint"]


class TestArangoimportJsonl:
    def test_binary_not_found(self, tmp_path):
        f = tmp_path / "test.jsonl"
        f.write_text('{"_key":"1"}\n')
        with pytest.raises(FileNotFoundError, match="not found on PATH"):
            arangoimport_jsonl(
                str(f),
                "test_coll",
                arangoimport_bin="nonexistent_binary_xyz",
            )

    @patch("entity_resolution.etl.arangoimport.subprocess.run")
    @patch("entity_resolution.etl.arangoimport.shutil.which", return_value="/usr/bin/arangoimport")
    def test_command_construction(self, mock_which, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            stdout="created: 100\nerrors: 0\nignored: 0\nupdated: 0\n",
            stderr="",
            returncode=0,
        )
        f = tmp_path / "test.jsonl"
        f.write_text('{"_key":"1"}\n')

        result = arangoimport_jsonl(
            str(f),
            "my_collection",
            connection_args={
                "endpoint": "http://localhost:8529",
                "username": "root",
                "password": "pass",
                "database": "mydb",
            },
            collection_type="document",
            on_duplicate="replace",
            threads=2,
        )

        assert result["created"] == 100
        assert result["errors"] == 0

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "arangoimport"
        assert "--collection" in cmd
        idx = cmd.index("--collection")
        assert cmd[idx + 1] == "my_collection"
        assert "--type" in cmd
        assert "jsonl" in cmd
        assert "--threads" in cmd
        assert "2" in cmd

    @patch("entity_resolution.etl.arangoimport.subprocess.run")
    @patch("entity_resolution.etl.arangoimport.shutil.which", return_value="/usr/bin/arangoimport")
    def test_edge_collection_type(self, mock_which, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            stdout="created: 50\nerrors: 0\nignored: 0\nupdated: 0\n",
            stderr="",
            returncode=0,
        )
        f = tmp_path / "edges.jsonl"
        f.write_text('{"_from":"a/1","_to":"b/2"}\n')

        arangoimport_jsonl(
            str(f),
            "my_edges",
            connection_args={
                "endpoint": "http://localhost:8529",
                "username": "root",
                "password": "",
                "database": "mydb",
            },
            collection_type="edge",
        )

        cmd = mock_run.call_args[0][0]
        assert "--create-collection-type" in cmd
        idx = cmd.index("--create-collection-type")
        assert cmd[idx + 1] == "edge"

    @patch("entity_resolution.etl.arangoimport.subprocess.run")
    @patch("entity_resolution.etl.arangoimport.shutil.which", return_value="/usr/bin/arangoimport")
    def test_output_parsing(self, mock_which, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            stdout="created: 1234\nupdated: 56\nerrors: 3\nignored: 7\n",
            stderr="",
            returncode=0,
        )
        f = tmp_path / "test.jsonl"
        f.write_text("{}\n")

        result = arangoimport_jsonl(
            str(f),
            "coll",
            connection_args={
                "endpoint": "http://localhost:8529",
                "username": "root",
                "password": "",
                "database": "db",
            },
        )

        assert result == {"created": 1234, "errors": 3, "ignored": 7, "updated": 56}
