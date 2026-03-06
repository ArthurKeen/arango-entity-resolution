# Release Checklist

Target release: `3.2.2`

## Checklist

- Bump the version source of truth in `src/entity_resolution/utils/constants.py`.
- Update `CHANGELOG.md` with the `3.2.2` release notes.
- Confirm package metadata and console scripts in `pyproject.toml`.
- Run the Phase 1 test suite and capture any manual verification notes.
- Verify `arango-er`, `arango-er-mcp`, and `arango-er-mcp --demo` still start correctly.
- Create and push the `3.2.2` git tag.
- Create a GitHub Release from that tag.
- Confirm the GitHub Release triggers `.github/workflows/publish.yml`.
- Verify `3.2.2` appears on PyPI.
- Verify `pip install arango-entity-resolution==3.2.2` succeeds.

## Important

PyPI publication is triggered by creating a GitHub Release. Pushing a tag alone does not publish the package.
