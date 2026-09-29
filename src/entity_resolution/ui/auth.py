"""Shared authentication helpers for the Entity Resolution UI.

Kept in a dedicated module so both the FastAPI app factory and the WebSocket
route can import them without a circular dependency.
"""

from __future__ import annotations

import hmac
from typing import Any, Dict, Optional

ANONYMOUS_REVIEWER = "anonymous"


def extract_request_token(headers: Any) -> Optional[str]:
    """Extract a bearer/API-key token from request headers.

    Supports ``Authorization: Bearer <token>`` and ``X-API-Key: <token>``.
    """
    auth = headers.get("authorization") or headers.get("Authorization")
    if auth:
        parts = auth.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        return auth.strip()
    api_key = headers.get("x-api-key") or headers.get("X-API-Key")
    if api_key:
        return api_key.strip()
    return None


def tokens_match(provided: Optional[str], expected: Optional[str]) -> bool:
    """Constant-time comparison of a provided token against the expected one."""
    if not expected or not provided:
        return False
    return hmac.compare_digest(provided, expected)


def token_is_accepted(
    provided: Optional[str],
    auth_token: Optional[str],
    reviewers_map: Optional[Dict[str, str]] = None,
) -> bool:
    """True for the shared token or any token ``ER_UI_REVIEWERS`` names.

    Reviewer tokens are credentials. Accepting only the shared token meant a
    mapped reviewer token was refused with 401, so the one configuration meant
    to give each steward their own identity could not be used.
    """
    if tokens_match(provided, auth_token):
        return True
    return any(tokens_match(provided, known) for known in (reviewers_map or {}))


def parse_reviewers(value: Optional[str]) -> Dict[str, str]:
    """Parse an ``ER_UI_REVIEWERS`` string into a ``{token: display_name}`` map.

    Format: comma-separated ``token=Display Name`` pairs, e.g.
    ``"abc123=Alice,def456=Bob"``. Blank/malformed entries are ignored.
    """
    mapping: Dict[str, str] = {}
    if not value:
        return mapping
    for pair in value.split(","):
        if "=" not in pair:
            continue
        token, name = pair.split("=", 1)
        token, name = token.strip(), name.strip()
        if token and name:
            mapping[token] = name
    return mapping


def resolve_reviewer(
    headers: Any,
    reviewers_map: Optional[Dict[str, str]] = None,
) -> str:
    """Resolve the acting reviewer for attribution in the audit trail.

    With a ``reviewers_map`` configured, identity comes from the token and ONLY
    the token: a mapped token gives its name, anything else is anonymous. The
    free-text ``X-Reviewer`` header is not consulted. It used to be, whenever
    the token was unmapped, so any holder of the shared token could record
    verdicts and merges as "Alice Chen" in a deployment that had gone to the
    trouble of giving Alice her own token.

    Without a map there are no identities to check against, so the header, a
    self-asserted session name the UI prompts for, is the attribution. It is
    not authentication, and nothing should treat it as such.
    """
    if reviewers_map:
        token = extract_request_token(headers)
        for known, name in reviewers_map.items():
            if tokens_match(token, known):
                return name
        return ANONYMOUS_REVIEWER
    explicit = headers.get("x-reviewer") or headers.get("X-Reviewer")
    if explicit and explicit.strip():
        return explicit.strip()
    return ANONYMOUS_REVIEWER
