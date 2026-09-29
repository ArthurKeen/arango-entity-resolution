"""The README must agree with the code it describes.

No gate read prose in this repo, and the prose drifted: the README's main config
example used keys the loader silently ignores (``collection``,
``similarity.fields``), so a user copying it would resolve a collection named
``entities`` with no field weights, and a blocking strategy name the validator
rejects. Each check below compares a documented fact against the object that
defines it — the config loader, the MCP registry, the click CLI, the filesystem —
rather than against a second copy of the prose.

Known discrepancies are pinned ``xfail(strict=True)``: fixing the README flips
them to XPASS, which fails, so the pin has to be removed in the same commit.
"""

from __future__ import annotations

import asyncio
import re
import shlex
import subprocess
from pathlib import Path

import pytest
import yaml

from entity_resolution.config.er_config import ClusteringConfig, ERPipelineConfig

REPO_ROOT = Path(__file__).resolve().parent.parent
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

_YAML_BLOCKS = re.findall(r"```yaml\n(.*?)```", README, re.S)


def _known(reason: str):
    return pytest.mark.xfail(strict=True, reason=f"KNOWN BUG: {reason} Remove when the README is fixed.")


def _key_paths(node, prefix=()):
    paths = set()
    if isinstance(node, dict):
        for key, value in node.items():
            paths.add(prefix + (key,))
            paths |= _key_paths(value, prefix + (key,))
    return paths


def _as_pipeline_dict(block: dict) -> dict:
    """Wrap a README snippet (``clustering:``, ``embedding:``...) as a full config."""
    er = block.get("entity_resolution", block)
    return {"blocking": {"strategy": "exact", "fields": [{"field": "x"}]}, **er}


# Pinned per block, by the first top-level key, so a reordered README still maps.
_YAML_KNOWN = {
    "embedding": _known("README uses embedding.model; the loader reads model_name."),
    "active_learning": _known("README uses refresh_every_n; the loader reads refresh_every."),
    "entity_resolution": _known(
        "README config example uses collection and similarity.fields; the loader "
        "reads collection_name and similarity.field_weights, and ignores the rest."
    ),
}


def _yaml_params():
    params = []
    for block in _YAML_BLOCKS:
        top = next(iter(yaml.safe_load(block)))
        marks = [_YAML_KNOWN[top]] if top in _YAML_KNOWN else []
        params.append(pytest.param(block, id=top, marks=marks))
    return params


def test_readme_has_yaml_examples_to_check() -> None:
    assert len(_YAML_BLOCKS) >= 4


@pytest.mark.parametrize("block", _yaml_params())
def test_readme_yaml_keys_are_ones_the_loader_reads(block: str) -> None:
    # The loader drops unknown keys without a word, so a misspelt key is not an
    # error anywhere — it just silently runs the default. Compare against what
    # the parsed config reports back.
    documented = yaml.safe_load(block)
    config = ERPipelineConfig.from_dict({"entity_resolution": _as_pipeline_dict(documented)})
    echoed = config.to_dict()
    echoed = echoed.get("entity_resolution", echoed)
    ignored = _key_paths(documented.get("entity_resolution", documented)) - _key_paths(echoed)
    assert not ignored, f"README keys the loader ignores: {sorted(ignored)}"


@pytest.mark.parametrize(
    "block",
    [
        pytest.param(
            b,
            id="entity_resolution",
            marks=_known("README blocking.strategy 'collect' is not a valid strategy; 'exact' is."),
        )
        for b in _YAML_BLOCKS
        if "entity_resolution" in yaml.safe_load(b)
    ],
)
def test_readme_full_config_examples_validate(block: str) -> None:
    config = ERPipelineConfig.from_dict(yaml.safe_load(block))
    assert config.validate() == []


def _readme_section(start: str, end: str) -> str:
    return README.split(start, 1)[1].split(end, 1)[0]


def _registered_mcp_tools() -> set:
    pytest.importorskip("mcp")
    from entity_resolution.mcp import server

    return {tool.name for tool in asyncio.run(server.mcp.list_tools())}


def test_readme_mcp_tool_count_matches_registry() -> None:
    counts = {int(n) for n in re.findall(r"(?:exposes|Exposes) (\d+) tools", README)}
    assert counts == {len(_registered_mcp_tools())}


@_known("resolve_and_commit and profile_fields are registered but not in the README tool tables.")
def test_readme_mcp_tool_tables_match_registry() -> None:
    section = _readme_section("### MCP Tools", "#### Resources")
    tables = section.split("The `recommend_resolution_strategy` tool evaluates")[0]
    documented = set(re.findall(r"^\| `([a-z_]+)` \|", tables, re.M))
    assert documented == _registered_mcp_tools()


def test_readme_backend_table_matches_valid_backends() -> None:
    section = _readme_section("### Clustering Backends", "#### GAE Clustering")
    documented = set(re.findall(r"^\| `([a-z_]+)` \|", section, re.M))
    assert documented == set(ClusteringConfig.VALID_BACKENDS) - {"auto"}


_CLI_LINES = [
    line.strip()
    for block in re.findall(r"```bash\n(.*?)```", README, re.S)
    for line in block.splitlines()
    if line.strip().startswith("arango-er ")
]


def test_readme_documents_cli_commands() -> None:
    assert len(_CLI_LINES) >= 4


@pytest.mark.parametrize("line", _CLI_LINES)
def test_readme_cli_commands_parse(line: str) -> None:
    import click

    from entity_resolution.cli import main

    name, *args = shlex.split(line)[1:]
    with click.Context(main) as ctx:
        command = main.get_command(ctx, name)
        assert command is not None, f"no such subcommand: {name}"
        command.make_context(name, list(args), parent=ctx)  # raises on a bad flag


@_known("README launches the UI with --port, which is the ArangoDB port; the UI port is --serve-port.")
def test_readme_ui_command_sets_the_ui_port() -> None:
    import click

    from entity_resolution.cli import main

    (line,) = [l for l in _CLI_LINES if l.startswith("arango-er ui ")]
    _, name, *args = shlex.split(line)
    with click.Context(main) as ctx:
        params = main.get_command(ctx, name).make_context(name, args, parent=ctx).params
    documented_port = int(re.search(r"--(?:serve-)?port (\d+)", line).group(1))
    assert params["serve_port"] == documented_port and params.get("port") is None


def _tracked_markdown():
    out = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    return [f for f in out if "/archive/" not in f and not f.startswith("ui/node_modules/")]


def test_relative_links_resolve() -> None:
    link = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
    broken = []
    for rel in _tracked_markdown():
        path = REPO_ROOT / rel
        text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8", errors="ignore"), flags=re.S)
        for target in link.findall(text):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            file_part = target.split("#", 1)[0]
            if file_part and not (path.parent / file_part).exists():
                broken.append(f"{rel} -> {target}")
    assert not broken, "broken relative links:\n" + "\n".join(broken)


def test_version_is_consistent_everywhere_it_is_stated() -> None:
    # The same gate `make check-version` runs, exercised in the unit suite so
    # widening the sources list cannot silently stop them being read.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_version_consistency", REPO_ROOT / "scripts" / "check_version_consistency.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    versions = module.collect_versions()
    assert "ui/openapi.json info.version" in versions
    assert None not in versions.values(), versions
    assert len(set(versions.values())) == 1, versions


def test_committed_openapi_matches_the_app() -> None:
    # CI's ui-contract job enforces this too, but it failed on every run for
    # weeks over a stale version string and a check that is always red is not
    # read. In the unit run, the same drift fails the suite people do read.
    pytest.importorskip("fastapi")
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location("export_openapi", REPO_ROOT / "scripts" / "export_openapi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = json.loads((REPO_ROOT / "ui" / "openapi.json").read_text(encoding="utf-8"))
    assert module.build_openapi() == committed, "run `make ui-types` and commit the result"
