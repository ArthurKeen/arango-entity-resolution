"""Tests for the test-environment safety guard.

Integration tests in this repo create, truncate and delete collections. The
developer ``.env`` has historically pointed ``ARANGO_ENDPOINT`` at a shared
prod-named server with root credentials, so a stray environment variable could
have destroyed real data. ``assert_safe_test_host`` is the guard; these tests
make sure the guard itself works, including its escape hatch.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# pytest registers tests/conftest.py as the module ``conftest`` and puts tests/ on
# sys.path, so this import never depends on collection order. ``tests.conftest``
# resolved only when an earlier module had happened to put the repo root on
# sys.path, and failed in CI the moment that order changed.
from conftest import assert_safe_test_host


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
        "arangodb",  # docker-compose service name
        "db",
        "LOCALHOST",  # case-insensitive
        "http://localhost:8529",  # full endpoint form
        "localhost:8529",
        "https://127.0.0.1:8529/",
    ],
)
def test_local_hosts_are_allowed(host):
    assert_safe_test_host(host)  # must not raise


@pytest.mark.parametrize(
    "host",
    [
        "prod.gae-demo.example.net",
        "https://prod.gae-demo.example.net:8529",
        "10.0.0.5",
        "customer-cluster.example.com",
        "arangodb.internal.corp",
    ],
)
def test_remote_hosts_are_refused(host):
    with pytest.raises(RuntimeError, match="Refusing to run tests"):
        assert_safe_test_host(host)


def test_escape_hatch_allows_remote_when_explicitly_opted_in(monkeypatch):
    """A disposable remote CI database can be opted into deliberately."""
    monkeypatch.setenv("ER_ALLOW_REMOTE_TEST_DB", "1")
    assert_safe_test_host("prod.gae-demo.example.net")  # must not raise


def test_escape_hatch_requires_exact_opt_in(monkeypatch):
    """Only the literal value "1" opts in — no accidental truthiness."""
    monkeypatch.setenv("ER_ALLOW_REMOTE_TEST_DB", "true")
    with pytest.raises(RuntimeError):
        assert_safe_test_host("prod.gae-demo.example.net")


def test_empty_host_is_refused():
    """An unset host must not silently pass the guard."""
    with pytest.raises(RuntimeError):
        assert_safe_test_host("")


def test_this_module_imports_when_collected_on_its_own(tmp_path):
    """Regression: collected alone, this module failed with
    ``ModuleNotFoundError: No module named 'tests.conftest'``.

    Runs pytest on this file in a fresh interpreter from a directory that is
    not the repository, so nothing earlier in a session can have prepared
    ``sys.path`` for it.
    """
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, pytest; sys.exit(pytest.main(sys.argv[1:]))",
            "-q",
            "-p",
            "no:cacheprovider",
            "-k",
            "not imports_when_collected_on_its_own",
            str(Path(__file__).resolve()),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
