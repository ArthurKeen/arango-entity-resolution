# Git Hooks Documentation

This document explains the Git hooks configured for this repository to ensure code quality and prevent common issues.

## Overview

Two git hooks are configured:

1. **Pre-Commit Hook** (~5 seconds) - Quick validation before each commit
2. **Pre-Push Hook** (~2-3 minutes) - Comprehensive tests before pushing to remote

## Pre-Commit Hook

The pre-commit hook runs automatically before each commit to verify code quality and catch issues early.

### What It Checks

1. **Python Syntax** - Validates syntax in core Python files
2. **Hardcoded Credentials** - Scans for hardcoded passwords or secrets
3. **Emoji Characters** - Warns if emojis are found (ASCII-only policy)
4. **Module Imports** - Verifies critical modules can be imported

### Installation

The hook is stored in `.githooks/pre-commit` and can be installed with:

```bash
./scripts/setup-git-hooks.sh
```

This script:
- Copies hooks from `.githooks/` to `.git/hooks/`
- Makes them executable
- Tests them to ensure they work

### Usage

Once installed, the hook runs automatically:

```bash
git add .
git commit -m "Your commit message"

# Hook runs automatically here:
# [1/4] Checking Python syntax...
# [2/4] Checking for hardcoded credentials...
# [3/4] Checking for emoji characters...
# [4/4] Running critical module imports...
# [OK] ALL PRE-COMMIT CHECKS PASSED
```

### Skipping the Hook

In rare cases where you need to bypass the hook (not recommended):

```bash
git commit --no-verify -m "Emergency fix"
```

### What Happens on Failure

If the hook detects issues, the commit is blocked:

```
[FAIL] Found hardcoded password in code
Passwords must be loaded from environment variables
```

Fix the issues and try committing again.

### Hook Details

#### 1. Python Syntax Check
Validates Python syntax in:
- `src/entity_resolution/utils/config.py`
- `src/entity_resolution/utils/constants.py`

This catches syntax errors before they reach CI/CD.

#### 2. Hardcoded Credentials Check
Searches for patterns like:
```python
password = "secret123" # BAD - will be caught
password = os.getenv("ARANGO_PASSWORD") # GOOD - passes
password = "" # GOOD - empty default
```

The check excludes:
- Environment variable loads (`getenv`)
- Empty strings
- Comment lines

#### 3. Emoji Check
Ensures ASCII-only code and documentation per project standards.

Emojis in Python files trigger a warning (doesn't fail):
```
[WARNING] Found emoji characters (should use ASCII only)
Consider replacing emojis with [OK], [ERROR], [WARNING] indicators
```

Replace with ASCII indicators:
- `[OK]` instead of 
- `[ERROR]` instead of 
- `[WARNING]` instead of 
- `[INFO]` instead of ℹ

#### 4. Module Import Check
Verifies that core modules can be imported:
- `entity_resolution.utils.config`
- `entity_resolution.utils.constants`
- `entity_resolution.services.*`
- `entity_resolution.core.entity_resolver`

This catches import errors and missing dependencies early.

### Performance

The hook is optimized for speed:
- Syntax checks: < 1 second
- Credential scans: < 2 seconds
- Import tests: < 3 seconds
- **Total time: ~5 seconds**

Fast enough to not disrupt workflow, but thorough enough to catch real issues.

### Customizing the Hook

To modify the hook:

1. Edit `.githooks/pre-commit`
2. Test your changes:
```bash
./.githooks/pre-commit
```
3. Reinstall for all developers:
```bash
./scripts/setup-git-hooks.sh
```

### Uninstalling

To remove the hook:

```bash
rm .git/hooks/pre-commit
```

Or to disable temporarily:

```bash
chmod -x .git/hooks/pre-commit
```

## Pre-Push Hook

The pre-push hook runs automatically before pushing to the remote repository to ensure all tests pass.

### What It Checks

1. **Core Unit Tests** - Configuration and constants modules
2. **Service Tests** - Blocking, similarity, and clustering services
3. **Integration Tests** - End-to-end entity resolution pipeline
4. **Module Imports** - Verifies all critical modules can be imported
5. **Code Quality** - Python syntax validation

### Usage

Once installed, the hook runs automatically:

```bash
git push origin main

# Hook runs automatically:
# [TEST] Core Unit Tests... [PASS]
# [TEST] Service Tests... [PASS]
# [TEST] Integration Tests... [PASS]
# [TEST] Module Imports... [PASS]
# [TEST] Code Quality... [PASS]
# [OK] ALL TESTS PASSED
# [OK] Safe to push to remote repository
```

### What Happens on Failure

If tests fail, the push is blocked:

```
[FAIL] Cannot push - 2 test section(s) failed:
- Service Tests
- Integration Tests

Please fix the failing tests before pushing.
```

Fix the issues and try pushing again.

### Skipping the Hook

In rare emergency cases where you need to push despite test failures (NOT RECOMMENDED):

```bash
SKIP_TESTS=1 git push
```

This should only be used for critical hotfixes or when the CI/CD pipeline can catch the issues.

### Performance

The pre-push hook is designed to be thorough but reasonable:
- **Target time**: 2-3 minutes
- **Test coverage**: Core functionality and integration tests
- **Optimized output**: Only shows summary and last 20 lines of each test section

This is acceptable since pushes happen less frequently than commits.

## Future Hooks

Additional hooks can be added for:
- **Commit-Msg**: Validate commit message format
- **Post-Commit**: Notify team or update issue trackers
- **Post-Merge**: Run integration tests after merges

## Best Practices

1. **Install hooks immediately** after cloning the repository
2. **Never use `--no-verify`** unless absolutely necessary
3. **Keep hooks fast** (< 10 seconds) to avoid disrupting workflow
4. **Make hooks helpful** with clear error messages and fix suggestions
5. **Test hooks regularly** to ensure they still work as expected

## Troubleshooting

### "Permission denied" error
```bash
chmod +x .git/hooks/pre-commit
```

### Hook not running
Check if it's installed:
```bash
ls -la .git/hooks/pre-commit
```

If not present, run the setup script:
```bash
./scripts/setup-git-hooks.sh
```

### False positives
Edit the hook to refine the check patterns, then reinstall.

### Python path issues
The hook sets `PYTHONPATH` automatically:
```bash
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"
```

## Resources

- [Git Hooks Documentation](https://git-scm.com/docs/githooks)
- [Pre-commit Framework](https://pre-commit.com/) (alternative approach)
- Project coding standards: `docs/CLAUDE.md`

---

**Note**: Git hooks are not committed to the repository by default (`.git/hooks/` is excluded). That's why we keep templates in `.githooks/` and provide a setup script for team members to install them locally.

