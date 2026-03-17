"""
Runtime telemetry export helpers.

Writes embedding runtime health snapshots to JSON artifacts for
environment/readiness tracking across hosts and releases.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class RuntimeTelemetryService:
    """Persist runtime health snapshots as timestamped JSON artifacts."""

    @staticmethod
    def export_snapshot(
        snapshot: Dict[str, Any],
        output_dir: str,
        filename_prefix: str = "runtime_health",
    ) -> str:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        json_path = output_path / f"{filename_prefix}_{timestamp}.json"

        payload = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
            },
            "snapshot": snapshot,
        }
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(json_path)

