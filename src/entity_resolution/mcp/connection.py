"""
Shared ArangoDB connection helpers for MCP tools/resources.
"""
from __future__ import annotations

import os


def get_arango_hosts(host: str, port: int) -> str:
    """
    Build ArangoClient hosts URL honoring endpoint/tls environment settings.

    Priority:
    1) ARANGO_ENDPOINT / ARANGO_HOSTS (if provided with scheme)
    2) host argument + ARANGO_TLS flag
    """
    endpoint = (os.getenv("ARANGO_ENDPOINT") or os.getenv("ARANGO_HOSTS") or "").strip()
    if endpoint:
        return endpoint

    host_text = (host or "").strip()
    if host_text.startswith("http://") or host_text.startswith("https://"):
        return host_text

    tls_value = (os.getenv("ARANGO_TLS") or "").strip().lower()
    use_tls = tls_value in {"1", "true", "yes", "on"}
    scheme = "https" if use_tls else "http"

    # If host already includes a port, avoid appending another.
    if ":" in host_text and not host_text.startswith("["):
        return f"{scheme}://{host_text}"
    return f"{scheme}://{host_text}:{port}"
