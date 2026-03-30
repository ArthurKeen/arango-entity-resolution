# Release Checklist

Target release: `3.5.1`

## Checklist

- Bump the version source of truth in `src/entity_resolution/utils/constants.py`.
- Update `CHANGELOG.md` with the release notes.
- Confirm package metadata and console scripts in `pyproject.toml`.
- Run the current release-validation suite and capture any manual verification notes.
- Verify `arango-er`, `arango-er-mcp`, and `arango-er-mcp --demo` still start correctly.
- Create and push the git tag (e.g., `3.5.1`).
- Create a GitHub Release from that tag.
- Confirm the GitHub Release triggers `.github/workflows/publish.yml`.
- Verify the version appears on PyPI.
- Verify `pip install arango-entity-resolution==3.5.1` succeeds.

## Important

PyPI publication is triggered by creating a GitHub Release. Pushing a tag alone does not publish the package.
