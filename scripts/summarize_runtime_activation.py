#!/usr/bin/env python3
"""
Summarize runtime matrix activation artifacts.

Example:
  python scripts/summarize_runtime_activation.py \
    --artifacts-root artifacts \
    --output-json artifacts/runtime/activation_summary.json \
    --output-md artifacts/runtime/activation_summary.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from entity_resolution.services.runtime_activation_evidence_service import (
    RuntimeActivationEvidenceService,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize runtime matrix activation artifacts."
    )
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Root artifact directory that contains runtime/ and quality/.",
    )
    parser.add_argument(
        "--output-json",
        default="artifacts/runtime/activation_summary.json",
        help="Path to write JSON summary.",
    )
    parser.add_argument(
        "--output-md",
        default="artifacts/runtime/activation_summary.md",
        help="Path to write markdown summary.",
    )
    args = parser.parse_args()

    summary = RuntimeActivationEvidenceService.summarize(args.artifacts_root)
    markdown = RuntimeActivationEvidenceService.to_markdown(summary)

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(markdown + "\n", encoding="utf-8")

    print(json.dumps({"json": str(output_json), "markdown": str(output_md)}, indent=2))


if __name__ == "__main__":
    main()
