#!/usr/bin/env python3
"""Assert the version is identical everywhere it is stated.

``docs/PRD.md`` claimed release 3.5.1 and ``README.md`` badged 3.5.1 while
``constants.__version__`` and the changelog were already at 3.8.0 — the PRD is
this project's declared source of truth, so a stale header quietly undermines
every drift audit run against it. A ``RELEASE_CHECKLIST.md`` existed but nothing
enforced it, which is the recurring pattern: intent written down, never made
executable.

Checked sources:

* ``src/entity_resolution/utils/constants.py`` — ``__version__`` (authoritative)
* ``CHANGELOG.md`` — most recent released ``## [x.y.z]`` heading
* ``docs/PRD.md`` — ``**Current Release**: `x.y.z```
* ``README.md`` — ``**Version x.y.z**``

Usage::

    python scripts/check_version_consistency.py

Exit codes: ``0`` consistent, ``1`` mismatch, ``2`` a version could not be found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

SEMVER = r"(\d+\.\d+\.\d+)"


def _read(rel_path: str) -> Optional[str]:
    path = REPO_ROOT / rel_path
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="ignore")


def _search(content: Optional[str], pattern: str) -> Optional[str]:
    """First capture group of ``pattern``, searched line-wise.

    ``re.MULTILINE`` matters: several patterns anchor with ``^`` to match a
    heading or assignment at the start of a line, not the start of the file.
    """
    if not content:
        return None
    match = re.search(pattern, content, re.MULTILINE)
    return match.group(1) if match else None


def collect_versions() -> Dict[str, Optional[str]]:
    constants = _read("src/entity_resolution/utils/constants.py")
    changelog = _read("CHANGELOG.md")
    prd = _read("docs/PRD.md")
    readme = _read("README.md")

    return {
        "constants.py __version__": _search(
            constants, rf'^__version__\s*=\s*["\']{SEMVER}["\']'
        )
        or _search(constants, rf'__version__\s*=\s*["\']{SEMVER}["\']'),
        # Skip an "Unreleased" heading; take the first real released version.
        "CHANGELOG.md latest release": _search(changelog, rf"^##\s*\[{SEMVER}\]"),
        "docs/PRD.md Current Release": _search(
            prd, rf"\*\*Current Release\*\*:\s*`?{SEMVER}`?"
        ),
        "README.md version badge": _search(readme, rf"\*\*Version\s+{SEMVER}\*\*"),
    }


def main() -> int:
    versions = collect_versions()

    missing = [name for name, value in versions.items() if value is None]
    if missing:
        print("Could not determine the version from:")
        for name in missing:
            print(f"  - {name}")
        print("\nUpdate this script if a file's version format changed.")
        return 2

    print("Declared versions:")
    for name, value in versions.items():
        print(f"  {name:34} {value}")

    distinct = set(versions.values())
    if len(distinct) > 1:
        authoritative = versions["constants.py __version__"]
        print(
            f"\nFAIL: version mismatch across {len(distinct)} distinct values.\n"
            f"constants.py is authoritative ({authoritative}); bring the others "
            "into line (see docs/development/RELEASE_CHECKLIST.md)."
        )
        for name, value in versions.items():
            if value != authoritative:
                print(f"  - {name} says {value}, expected {authoritative}")
        return 1

    print(f"\nOK: all sources agree on {distinct.pop()}.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        print(f"version check error: {exc}", file=sys.stderr)
        sys.exit(2)
