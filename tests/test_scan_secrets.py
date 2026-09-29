"""The secret scanner must catch a real key wherever it sits in a shipped file.

Three blind spots let a live credential through the gate that exists to stop it:

* whole directories (``docs/``, ``examples/``, ``tests/``) were skipped, and all
  three ship in the sdist published to PyPI;
* the placeholder check read the *whole line*, so a trailing ``# test`` comment
  or the word "example" anywhere on it silenced a genuine key;
* only quoted literals matched, so a dotenv-style ``ARANGO_PASSWORD=...`` line —
  the most common way a credential is actually written down — was invisible.

Every credential-shaped string below is assembled at runtime, so this file does
not itself trip the scanner it tests.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "scan_secrets", REPO_ROOT / "scripts" / "scan_secrets.py"
)
scan_secrets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan_secrets)

# Realistic-looking values with no placeholder words in them.
_GH_TOKEN = "gh" + "p_" + "Q7rT2mZk9LwX4vB8nHc3JfYd6sGpA1eRuK0o"
_PASSWORD = "Ra7" + "KJqv9Lm2Wz"


def _scan(tmp_path: Path, rel_path: str, text: str):
    target = tmp_path / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return scan_secrets.scan_file(target, rel_path)


@pytest.mark.parametrize("rel_path", ["tests/test_x.py", "docs/guide.md", "examples/demo.py"])
def test_shipped_directories_are_scanned(rel_path: str) -> None:
    assert not scan_secrets._is_allowlisted(rel_path)


def test_vendored_node_modules_is_still_skipped() -> None:
    assert scan_secrets._is_allowlisted("ui/node_modules/pkg/index.js")


def test_trailing_placeholder_word_does_not_silence_a_real_token(tmp_path: Path) -> None:
    findings = _scan(tmp_path, "src/mod.py", f'TOKEN = "{_GH_TOKEN}"  # test fixture example\n')
    assert [f.pattern for f in findings] == ["GitHub token"]


def test_placeholder_inside_the_value_is_still_ignored(tmp_path: Path) -> None:
    assert _scan(tmp_path, "src/mod.py", 'password = "your_password_here"\n') == []


def test_unquoted_env_credential_is_detected(tmp_path: Path) -> None:
    findings = _scan(tmp_path, "deploy/app.env", f"ARANGO_PASSWORD={_PASSWORD}\n")
    assert [f.pattern for f in findings] == ["Unquoted env credential"]


@pytest.mark.parametrize(
    "line",
    [
        "ARANGO_PASSWORD=${ARANGO_PASSWORD}",   # interpolation, not a value
        "ARANGO_PASSWORD=changeme",             # placeholder
        "    password=password,",               # keyword argument, lower-case name
    ],
)
def test_unquoted_pattern_does_not_flag_ordinary_text(tmp_path: Path, line: str) -> None:
    assert _scan(tmp_path, "src/mod.py", line + "\n") == []


def test_allow_pragma_suppresses_only_its_own_line(tmp_path: Path) -> None:
    text = (
        f'password = "{_PASSWORD}"  # scan-secrets: allow\n'
        f'password = "{_PASSWORD}"\n'
    )
    assert [f.line_no for f in _scan(tmp_path, "docs/guide.md", text)] == [2]


def test_one_finding_per_line(tmp_path: Path) -> None:
    # A token assigned to an env-style name matches two patterns; report it once.
    assert len(_scan(tmp_path, "deploy/app.env", f"GITHUB_TOKEN={_GH_TOKEN}\n")) == 1


def test_findings_are_redacted(tmp_path: Path) -> None:
    (finding,) = _scan(tmp_path, "src/mod.py", f'TOKEN = "{_GH_TOKEN}"\n')
    assert _GH_TOKEN not in finding.excerpt


def test_committed_tree_is_clean() -> None:
    # The gate CI runs. Fails if a newly scanned directory holds a real key, or
    # if a deliberate example lacks its pragma.
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "scan_secrets.py"), "--committed-only"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_sdist_is_an_explicit_allowlist() -> None:
    # Without ``include``, hatch ships every file .gitignore does not exclude —
    # untracked worktree files and vendored node_modules included.
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        tomllib = pytest.importorskip("tomli")
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    include = config["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    assert "/src/entity_resolution" in include
    shipped_roots = {entry.strip("/").split("/")[0] for entry in include}
    assert not shipped_roots & {"docs", "demo", "examples", "ui", "scripts", "research", "reports", "data"}


def test_publish_workflow_scans_before_building() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
    scan = workflow.find("scan_secrets.py --committed-only")
    build = workflow.find("python -m build")
    assert 0 <= scan < build
