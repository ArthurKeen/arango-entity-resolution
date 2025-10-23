#!/usr/bin/env bash
#
# Setup Git Hooks
# 
# This script installs Git hooks from .githooks/ directory
# to .git/hooks/ for automated pre-commit testing
#

set -e

echo "=========================================="
echo " Git Hooks Setup"
echo "=========================================="
echo ""

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "[ERROR] Not in a git repository"
    echo "Please run this script from the project root"
    exit 1
fi

# Check if .githooks directory exists
if [ ! -d ".githooks" ]; then
    echo "[ERROR] .githooks directory not found"
    exit 1
fi

# Create hooks directory if it doesn't exist
mkdir -p .git/hooks

# Install pre-commit hook
if [ -f ".githooks/pre-commit" ]; then
    echo "[1/5] Installing pre-commit hook..."
    cp .githooks/pre-commit .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
    echo "  [OK] Pre-commit hook installed"
else
    echo "  [SKIP] No pre-commit hook found in .githooks/"
fi

# Install pre-push hook
if [ -f ".githooks/pre-push" ]; then
    echo "[2/5] Installing pre-push hook..."
    cp .githooks/pre-push .git/hooks/pre-push
    chmod +x .git/hooks/pre-push
    echo "  [OK] Pre-push hook installed"
else
    echo "  [SKIP] No pre-push hook found in .githooks/"
fi

# Verify installation
echo ""
echo "[3/5] Verifying installation..."
if [ -x ".git/hooks/pre-commit" ]; then
    echo "  [OK] Pre-commit hook is executable"
else
    echo "  [ERROR] Pre-commit hook is not executable"
    exit 1
fi

if [ -x ".git/hooks/pre-push" ]; then
    echo "  [OK] Pre-push hook is executable"
else
    echo "  [ERROR] Pre-push hook is not executable"
    exit 1
fi

# Test the pre-commit hook
echo ""
echo "[4/5] Testing pre-commit hook..."
echo "  (Running in test mode...)"
.git/hooks/pre-commit

if [ $? -eq 0 ]; then
    echo "  [OK] Pre-commit hook test passed"
else
    echo "  [ERROR] Pre-commit hook test failed"
    exit 1
fi

# Test the pre-push hook (with skip flag to avoid long test run)
echo ""
echo "[5/5] Testing pre-push hook..."
echo "  (Running in test mode with SKIP_TESTS flag...)"
SKIP_TESTS=1 .git/hooks/pre-push

if [ $? -eq 0 ]; then
    echo "  [OK] Pre-push hook test passed"
else
    echo "  [ERROR] Pre-push hook test failed"
    exit 1
fi

echo ""
echo "=========================================="
echo " Git Hooks Setup Complete"
echo "=========================================="
echo ""
echo "Two hooks are now installed:"
echo ""
echo "1. PRE-COMMIT HOOK (~5 seconds)"
echo "   Runs before each commit:"
echo "   - Python syntax validation"
echo "   - No hardcoded credentials"
echo "   - No emoji characters (ASCII-only)"
echo "   - Critical module imports"
echo ""
echo "2. PRE-PUSH HOOK (~2-3 minutes)"
echo "   Runs before each push:"
echo "   - Full unit test suite"
echo "   - Service integration tests"
echo "   - End-to-end tests"
echo "   - Code quality checks"
echo ""
echo "To skip hooks (not recommended):"
echo "  git commit --no-verify   # Skip pre-commit"
echo "  SKIP_TESTS=1 git push    # Skip pre-push tests"
echo ""
echo "To uninstall:"
echo "  rm .git/hooks/pre-commit .git/hooks/pre-push"
echo ""

exit 0

