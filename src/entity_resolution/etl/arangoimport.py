"""
``arangoimport`` helper for bulk-loading JSONL files into ArangoDB.

Consolidates the connection-args extraction previously scattered across
``AddressERService`` and ad-hoc migration scripts into a single reusable
function.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from typing import Any, Optional

from ..utils.constants import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_USERNAME, DEFAULT_DATABASE

logger = logging.getLogger(__name__)

_CREATED_RE = re.compile(r"created:\s*(\d+)")
_ERRORS_RE = re.compile(r"errors:\s*(\d+)")
_IGNORED_RE = re.compile(r"ignored:\s*(\d+)")
_UPDATED_RE = re.compile(r"updated:\s*(\d+)")


def get_arangoimport_connection_args(
    db: Any = None,
) -> dict[str, str]:
    """Extract ArangoDB connection parameters for ``arangoimport``.

    Resolution order (later wins):
    1. Defaults (``localhost:8529``, ``root``, empty password).
    2. Attributes on *db* object (python-arango ``StandardDatabase``).
    3. Environment variables (``ARANGO_HOST``, ``ARANGO_PORT``, etc.).

    Returns
    -------
    dict
        Keys: ``endpoint``, ``username``, ``password``, ``database``.
    """
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    username = DEFAULT_USERNAME
    password = ""
    database = DEFAULT_DATABASE

    if db is not None:
        try:
            database = db.name
        except Exception as e:
            logger.debug("Could not read db.name: %s", e)
        try:
            conn = getattr(db, "connection", None) or getattr(db, "_conn", None)
            if conn is not None:
                for attr in ("host", "_host"):
                    if hasattr(conn, attr):
                        host = getattr(conn, attr)
                        break
                for attr in ("port", "_port"):
                    if hasattr(conn, attr):
                        port = getattr(conn, attr)
                        break
                for attr in ("username", "_username"):
                    if hasattr(conn, attr):
                        username = getattr(conn, attr)
                        break
                for attr in ("password", "_password"):
                    if hasattr(conn, attr):
                        password = getattr(conn, attr)
                        break
        except Exception as e:
            logger.debug("Could not extract connection attributes from db object: %s", e)

    host = os.getenv("ARANGO_HOST", os.getenv("ARANGO_DB_HOST", host))
    port = int(os.getenv("ARANGO_PORT", os.getenv("ARANGO_DB_PORT", str(port))))
    username = os.getenv("ARANGO_USERNAME", os.getenv("ARANGO_ROOT_USERNAME", username))
    password = os.getenv("ARANGO_PASSWORD", os.getenv("ARANGO_ROOT_PASSWORD", password))
    database = os.getenv("ARANGO_DATABASE", os.getenv("ARANGO_DB_NAME", database))

    return {
        "endpoint": f"http://{host}:{port}",
        "username": username,
        "password": password,
        "database": database,
    }


def arangoimport_jsonl(
    file_path: str,
    collection: str,
    db: Any = None,
    connection_args: Optional[dict[str, str]] = None,
    collection_type: str = "document",
    on_duplicate: str = "replace",
    threads: int = 4,
    arangoimport_bin: str = "arangoimport",
    timeout: int = 3600,
) -> dict[str, int]:
    """Run ``arangoimport`` on a JSONL file.

    Parameters
    ----------
    file_path : str
        Path to the ``.jsonl`` file.
    collection : str
        Target collection name.
    db : Any
        Optional python-arango database object (used to derive connection args).
    connection_args : dict | None
        Explicit ``{endpoint, username, password, database}``; takes priority
        over *db*.
    collection_type : str
        ``"document"`` or ``"edge"``.
    on_duplicate : str
        ``"replace"``, ``"update"``, ``"ignore"``, or ``"error"``.
    threads : int
        Number of import threads.
    arangoimport_bin : str
        Path or name of the ``arangoimport`` binary.
    timeout : int
        Subprocess timeout in seconds.

    Returns
    -------
    dict
        ``{created, errors, ignored, updated}``.

    Raises
    ------
    FileNotFoundError
        If the ``arangoimport`` binary cannot be found.
    subprocess.CalledProcessError
        If ``arangoimport`` exits with a non-zero status.
    """
    if shutil.which(arangoimport_bin) is None:
        raise FileNotFoundError(
            f"'{arangoimport_bin}' not found on PATH. "
            "Install ArangoDB client tools or set arangoimport_bin."
        )

    args = connection_args or get_arangoimport_connection_args(db)

    cmd = [
        arangoimport_bin,
        "--server.endpoint", args["endpoint"],
        "--server.username", args["username"],
        "--server.password", args["password"],
        "--server.database", args["database"],
        "--collection", collection,
        "--type", "jsonl",
        "--file", str(file_path),
        "--create-collection", "false",
        "--on-duplicate", on_duplicate,
        "--threads", str(threads),
    ]

    if collection_type == "edge":
        cmd.extend(["--create-collection-type", "edge"])

    logger.info(
        "Running arangoimport: collection=%s type=%s file=%s",
        collection,
        collection_type,
        file_path,
    )

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
    )

    output = result.stdout + "\n" + result.stderr

    def _parse(pattern: re.Pattern[str]) -> int:
        m = pattern.search(output)
        return int(m.group(1)) if m else 0

    stats = {
        "created": _parse(_CREATED_RE),
        "errors": _parse(_ERRORS_RE),
        "ignored": _parse(_IGNORED_RE),
        "updated": _parse(_UPDATED_RE),
    }

    logger.info("arangoimport result: %s", stats)
    return stats
