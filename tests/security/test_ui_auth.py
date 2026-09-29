"""Security tests for the Web UI authentication layer (PR2)."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from entity_resolution.ui.app import create_app
from entity_resolution.ui.auth import (
    ANONYMOUS_REVIEWER,
    extract_request_token,
    parse_reviewers,
    resolve_reviewer,
    tokens_match,
)


TOKEN = "s3cr3t-token-value"


class _FakeHeaders(dict):
    """dict subclass standing in for case-insensitive header access in tests."""


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def test_extract_bearer_token():
    assert extract_request_token({"authorization": "Bearer abc"}) == "abc"


def test_extract_api_key_token():
    assert extract_request_token({"x-api-key": "abc"}) == "abc"


def test_extract_token_none_when_absent():
    assert extract_request_token({}) is None


def test_tokens_match():
    assert tokens_match("abc", "abc") is True
    assert tokens_match("abc", "xyz") is False
    assert tokens_match(None, "abc") is False
    assert tokens_match("abc", None) is False
    assert tokens_match("", "") is False


# ---------------------------------------------------------------------------
# Reviewer identity (attribution, not auth) — plan 2.0
# ---------------------------------------------------------------------------

def test_parse_reviewers():
    assert parse_reviewers("a=Alice, b=Bob") == {"a": "Alice", "b": "Bob"}
    assert parse_reviewers("") == {}
    assert parse_reviewers(None) == {}
    assert parse_reviewers("garbage,c=Carol") == {"c": "Carol"}


def test_header_is_ignored_once_reviewers_are_configured():
    # This test used to assert the opposite: with a reviewer map configured, a
    # caller holding no mapped token could still name themselves "Alice" and be
    # recorded as Alice. Identity now comes from the token alone.
    assert resolve_reviewer({"x-reviewer": "Alice"}, {"tok": "Bob"}) == ANONYMOUS_REVIEWER
    shared = {"authorization": "Bearer shared-token", "x-reviewer": "Alice Chen"}
    assert resolve_reviewer(shared, {"tok-alice": "Alice Chen"}) == ANONYMOUS_REVIEWER


def test_header_is_the_attribution_when_no_reviewers_are_configured():
    # No identities exist to check it against; it is a session name, not auth.
    assert resolve_reviewer({"x-reviewer": "Alice"}, {}) == "Alice"


def test_resolve_reviewer_from_token_map():
    assert resolve_reviewer({"authorization": "Bearer tok"}, {"tok": "Bob"}) == "Bob"


def test_mapped_token_identity_cannot_be_spoofed_by_header():
    headers = {
        "authorization": "Bearer tok",
        "x-reviewer": "Mallory",
    }
    assert resolve_reviewer(headers, {"tok": "Bob"}) == "Bob"


def test_resolve_reviewer_anonymous_default():
    assert resolve_reviewer({}, {}) == ANONYMOUS_REVIEWER
    assert resolve_reviewer({"authorization": "Bearer unknown"}, {"tok": "Bob"}) == ANONYMOUS_REVIEWER


# ---------------------------------------------------------------------------
# HTTP auth middleware (db is None so passing auth surfaces as 503, not 200)
# ---------------------------------------------------------------------------

def _client(auth_token):
    return TestClient(create_app(db=None, auth_token=auth_token))


def test_health_is_exempt_from_auth():
    client = _client(TOKEN)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["auth_required"] is True


def test_api_requires_token_when_enabled():
    client = _client(TOKEN)
    resp = client.get("/api/collections")
    assert resp.status_code == 401


def test_api_rejects_wrong_token():
    client = _client(TOKEN)
    resp = client.get("/api/collections", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_api_accepts_valid_bearer_token():
    client = _client(TOKEN)
    resp = client.get("/api/collections", headers={"Authorization": f"Bearer {TOKEN}"})
    # Auth passed; db is None so the db-connection middleware returns 503.
    assert resp.status_code != 401


def test_api_accepts_valid_api_key_header():
    client = _client(TOKEN)
    resp = client.get("/api/collections", headers={"X-API-Key": TOKEN})
    assert resp.status_code != 401


def test_no_auth_mode_allows_api_without_token():
    client = _client(None)
    resp = client.get("/api/collections")
    assert resp.status_code != 401


# ---------------------------------------------------------------------------
# Static SPA containment
# ---------------------------------------------------------------------------

def test_spa_fallback_rejects_symlink_escape(monkeypatch, tmp_path):
    from entity_resolution.ui import app as app_module

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "assets").mkdir()
    (static_dir / "index.html").write_text("safe index")
    outside = tmp_path / "secret.txt"
    outside.write_text("must not be served")
    (static_dir / "leak.txt").symlink_to(outside)
    monkeypatch.setattr(app_module, "_STATIC_DIR", static_dir)

    client = TestClient(app_module.create_app(db=None))
    response = client.get("/leak.txt")

    assert response.status_code == 404
    assert "must not be served" not in response.text


# ---------------------------------------------------------------------------
# WebSocket auth
# ---------------------------------------------------------------------------

class _FakeDB:
    def has_collection(self, name):
        return False


def test_ws_rejects_without_token():
    client = TestClient(create_app(db=_FakeDB(), auth_token=TOKEN))
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/pipeline/run123") as ws:
            ws.receive_json()


def test_ws_accepts_with_token_query_param():
    client = TestClient(create_app(db=_FakeDB(), auth_token=TOKEN))
    with client.websocket_connect(f"/ws/pipeline/run123?token={TOKEN}") as ws:
        msg = ws.receive_json()
        # Auth passed and the handler ran (no runs collection on the fake db).
        assert msg["type"] == "error"


# ---------------------------------------------------------------------------
# CLI public-bind guard
# ---------------------------------------------------------------------------

def test_cli_refuses_public_bind_without_token(monkeypatch):
    from click.testing import CliRunner
    from entity_resolution.cli import main

    monkeypatch.delenv("ER_UI_AUTH_TOKEN", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["ui", "--serve-host", "0.0.0.0"])
    assert result.exit_code == 1
    assert "Refusing to bind" in result.output



# ---------------------------------------------------------------------------
# Reviewer tokens are credentials
# ---------------------------------------------------------------------------

def _reviewer_client():
    return TestClient(create_app(db=None, auth_token=TOKEN, reviewers={"tok-alice": "Alice Chen"}))


def test_reviewer_token_authenticates():
    # Previously a 401: only the shared token was accepted, so the reviewer map
    # could not be used with auth enabled. db is None, so passing auth is a 503.
    resp = _reviewer_client().get("/api/collections", headers={"Authorization": "Bearer tok-alice"})
    assert resp.status_code == 503


def test_unknown_token_is_still_refused_with_reviewers_configured():
    resp = _reviewer_client().get("/api/collections", headers={"Authorization": "Bearer tok-mallory"})
    assert resp.status_code == 401


def test_reviewer_token_authenticates_the_websocket():
    from starlette.websockets import WebSocketDisconnect

    class _NoRunsDB:
        def has_collection(self, name):
            return False

    client = TestClient(create_app(db=_NoRunsDB(), auth_token=TOKEN, reviewers={"tok-alice": "Alice Chen"}))
    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect("/ws/pipeline/some-run?token=tok-mallory") as ws:
            ws.receive_json()
    assert refused.value.code == 1008
    # A reviewer token gets past the handshake and reaches the run lookup.
    with client.websocket_connect("/ws/pipeline/some-run?token=tok-alice") as ws:
        assert ws.receive_json() == {"type": "error", "detail": "No pipeline runs collection"}
