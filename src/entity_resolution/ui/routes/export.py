"""Cluster export endpoints."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from entity_resolution.ui.models.schemas import ExportRequest

router = APIRouter(prefix="/api/export", tags=["export"])


def _db(request: Request):
    return request.app.state.db


#: What the export service writes: ``<prefix>_<timestamp>.json|csv``.
_EXPORT_FILENAME = re.compile(r"^[A-Za-z0-9_-]{1,128}\.(json|csv)$")


def _export_dir(request: Request) -> Path:
    """The one directory this app writes exports to and serves them from.

    Created on first use, per app instance. The download route used to search
    the whole system temp directory, so it would serve any file there whose
    name looked safe, and it never found the exports, which were written to a
    fresh mkdtemp subdirectory it did not search.
    """
    state = request.app.state
    if getattr(state, "export_dir", None) is None:
        state.export_dir = Path(tempfile.mkdtemp(prefix="er_exports_"))
    return state.export_dir


@router.post("/{collection}")
async def export_clusters(
    request: Request,
    collection: str,
    body: ExportRequest,
) -> Dict[str, Any]:
    """Export clusters to JSON and CSV files."""
    from entity_resolution.services.cluster_export_service import ClusterExportService
    from entity_resolution.utils.validation import validate_collection_name

    if request.app.state.readonly:
        raise HTTPException(status_code=403, detail="Read-only mode")

    validate_collection_name(collection)
    db = _db(request)

    service = ClusterExportService(
        db=db,
        source_collection=collection,
        edge_collection=body.edge_collection,
        cluster_collection=body.cluster_collection,
    )

    result = service.export(
        output_dir=str(_export_dir(request)),
        filename_prefix=body.filename_prefix,
        limit=body.limit,
    )

    # Names only: the download route resolves them, and server paths are not
    # the client's business.
    return {
        "collection": collection,
        "output_files": {
            "json": Path(result["json"]).name,
            "csv": Path(result["csv"]).name,
        },
        "clusters_exported": result["clusters_exported"],
    }


@router.get("/{collection}/download/{filename}")
async def download_export(
    request: Request,
    collection: str,
    filename: str,
) -> FileResponse:
    """Serve a file this app exported, and nothing else."""
    if not _EXPORT_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    directory = _export_dir(request).resolve()
    candidate = (directory / filename).resolve()
    if candidate.parent != directory or not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    media_type = "application/json" if filename.endswith(".json") else "text/csv"
    return FileResponse(path=str(candidate), filename=filename, media_type=media_type)
