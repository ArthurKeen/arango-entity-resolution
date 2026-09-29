"""The scorecard checker must read every statement of a fact, not the first.

The health scorecard gave its test count as 1,790, 1,790 and 1,779 and its
coverage as 75.37% and 75.34% on one page. ``re.search`` saw only the first
mention of each, so the disagreement was invisible to the one gate that reads
the scorecards.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("check_scorecard", REPO_ROOT / "scripts" / "check_scorecard.py")
check_scorecard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_scorecard)


def _doc(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "card.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_every_phrasing_of_a_fact_is_read(tmp_path: Path) -> None:
    path = _doc(tmp_path, (
        "`make verify`: 1,790 passed, 8 skipped, 75.37% coverage against a 72% floor\n"
        "- gate: **pass** — 1,790 tests passed\n"
        "- Python coverage: **75.34%**.\n"
        "`make verify` passes (1,779 tests, 75.34%\ncoverage)\n"
        "- UI unit tests: **pass** — 7 tests across 3 files.\n"
        "4,057 advisory flake8 findings\n"
    ))
    facts = check_scorecard.stated_facts(path)
    assert facts["tests_passed"] == [1790, 1790, 1779]
    assert facts["coverage_pct"] == [75.37, 75.34, 75.34]
    assert facts["flake8_findings"] == [4057]


def test_disagreement_is_reported(tmp_path: Path) -> None:
    path = _doc(tmp_path, "1,790 passed and later (1,779 tests, 75.34% coverage)\n")
    assert check_scorecard.check_agreement(path) == {"tests_passed": [1779.0, 1790.0]}


def test_consistent_document_reports_nothing(tmp_path: Path) -> None:
    path = _doc(tmp_path, "1,790 passed, 75.37% coverage; again 1,790 tests passed\n")
    assert check_scorecard.check_agreement(path) == {}
