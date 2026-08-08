#!/usr/bin/env python3
"""Secret scanner for committed files, with an advisory pass over the worktree.

Two distinct jobs, because they have different severities:

1. **Committed secrets (blocking).** Anything tracked by git that looks like a
   real credential fails the scan. This is what CI gates on.
2. **Worktree secrets (advisory).** Untracked files such as a developer ``.env``
   are reported but do not fail the build. They are correctly gitignored, yet
   they are still real credentials sitting on disk — worth surfacing, and worth
   confirming they are genuinely ignored.

Most scanners only inspect committed content and therefore say nothing about a
``.env`` holding a live publish token. That gap is deliberate here.

Usage::

    python scripts/scan_secrets.py            # committed (blocking) + advisory
    python scripts/scan_secrets.py --committed-only
    python scripts/scan_secrets.py --quiet

Exit codes: ``0`` clean, ``1`` committed secret found, ``2`` scan error.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files that are *supposed* to contain credential-shaped placeholder text.
ALLOWLIST_PATHS = {
    "env.example",
    ".env.example",
    "config.example.json",
    "docker-compose.yml",
    "docker-compose.test.yml",
    "scripts/scan_secrets.py",
    "SECURITY.md",
}

ALLOWLIST_DIRS = ("docs/", "examples/", "tests/", "legacy/", "ui/node_modules/")

# Obvious placeholders — their presence is the point of an example file.
PLACEHOLDER_MARKERS = (
    "change_me",
    "changeme",
    "your_",
    "yourpassword",
    "xxx",
    "<",
    "example",
    "placeholder",
    "dummy",
    "sample",
    "test",
    "fake",
    "redacted",
    "rootpassword",
    "openSesame",
    "demo",  # ephemeral local demo containers use throwaway passwords
    "${",
)

BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".whl",
    ".onnx", ".bin", ".so", ".dylib", ".woff", ".woff2", ".ttf",
}


class Pattern(NamedTuple):
    name: str
    regex: re.Pattern


PATTERNS: List[Pattern] = [
    Pattern("PyPI API token", re.compile(r"pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_\-]{16,}")),
    Pattern("OpenAI API key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}")),
    Pattern("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    Pattern("OpenRouter API key", re.compile(r"sk-or-v1-[A-Za-z0-9]{32,}")),
    Pattern("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    Pattern("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    Pattern("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}")),
    Pattern("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    # Only a QUOTED LITERAL counts. Matching bare right-hand sides flags
    # ordinary code (``password=self.config.password``, ``token: Optional[str]``)
    # and a scanner that cries wolf gets ignored, which is worse than no scanner.
    Pattern(
        "Hardcoded credential literal",
        re.compile(
            r"(?i)\b(?:password|passwd|secret|api_?key|access_?token|auth_?token)"
            r"\s*[:=]\s*[\"']([^\"'\s]{8,})[\"']"
        ),
    ),
]

#: Substrings indicating the captured value is code or an env lookup, not a literal.
_CODE_MARKERS = ("self.", "os.", "config.", "getenv", "environ", "(", ")", "[", "]", "{", "}", "$")


class Finding(NamedTuple):
    path: str
    line_no: int
    pattern: str
    excerpt: str


def _is_allowlisted(rel_path: str) -> bool:
    if rel_path in ALLOWLIST_PATHS:
        return True
    return any(rel_path.startswith(d) for d in ALLOWLIST_DIRS)


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _looks_like_code(value: str) -> bool:
    """True when the captured value is an expression rather than a literal secret."""
    return any(marker in value for marker in _CODE_MARKERS)


def _redact(text: str) -> str:
    stripped = text.strip()
    if len(stripped) <= 12:
        return "***"
    return f"{stripped[:6]}...{stripped[-2:]} ({len(stripped)} chars)"


def scan_file(path: Path, rel_path: str) -> List[Finding]:
    if path.suffix.lower() in BINARY_SUFFIXES or not path.is_file():
        return []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    findings: List[Finding] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        if len(line) > 4000:  # minified assets
            continue
        for pattern in PATTERNS:
            match = pattern.regex.search(line)
            if not match:
                continue
            captured = match.group(1) if match.groups() else match.group(0)
            if _looks_like_placeholder(captured) or _looks_like_placeholder(line):
                continue
            if _looks_like_code(captured):
                continue
            findings.append(
                Finding(rel_path, line_no, pattern.name, _redact(captured))
            )
    return findings


def _git(args: List[str]) -> List[str]:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def tracked_files() -> Iterable[str]:
    return _git(["ls-files"])


def untracked_files() -> Iterable[str]:
    """Untracked files, including gitignored ones — that is where ``.env`` lives.

    Two invocations are needed: ``--exclude-standard`` lists untracked-but-not-
    ignored files, and ``--ignored --exclude-standard`` lists the ignored ones.
    """
    plain = _git(["ls-files", "--others", "--exclude-standard"])
    ignored = _git(["ls-files", "--others", "--ignored", "--exclude-standard"])
    skip_prefixes = (
        ".venv/", "venv/", "node_modules/", "ui/node_modules/", ".git/",
        "artifacts/", "htmlcov/", "dist/", "build/", ".pytest_cache/",
        ".mypy_cache/", "__pycache__/",
    )
    seen, result = set(), []
    for rel in [*plain, *ignored]:
        if rel in seen or any(rel.startswith(p) for p in skip_prefixes):
            continue
        seen.add(rel)
        result.append(rel)
    return result


def _report(title: str, findings: List[Finding], quiet: bool) -> None:
    if quiet and not findings:
        return
    print(f"\n{title}")
    if not findings:
        print("  none")
        return
    for f in findings:
        print(f"  {f.path}:{f.line_no}: {f.pattern} -> {f.excerpt}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--committed-only", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    committed: List[Finding] = []
    for rel_path in tracked_files():
        if _is_allowlisted(rel_path):
            continue
        committed.extend(scan_file(REPO_ROOT / rel_path, rel_path))

    _report("Committed files (blocking):", committed, args.quiet)

    if not args.committed_only:
        worktree: List[Finding] = []
        for rel_path in untracked_files():
            if _is_allowlisted(rel_path) or rel_path.startswith(".git/"):
                continue
            worktree.extend(scan_file(REPO_ROOT / rel_path, rel_path))
        _report("Untracked worktree files (advisory, not gitignore-safe):", worktree, args.quiet)
        if worktree:
            print(
                "\n  NOTE: these are not committed, but they are real credentials on\n"
                "  disk. Confirm they are gitignored and consider a secrets manager."
            )

    if committed:
        print(
            f"\nFAIL: {len(committed)} potential secret(s) in committed files.\n"
            "Remove them, rotate the credential, and purge from history if needed."
        )
        return 1

    print("\nOK: no secrets detected in committed files.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        print(f"scan error: {exc}", file=sys.stderr)
        sys.exit(2)
