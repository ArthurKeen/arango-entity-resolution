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
    echo "[1/3] Installing pre-commit hook..."
    cp .githooks/pre-commit .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
    echo "  [OK] Pre-commit hook installed"
else
    echo "  [SKIP] No pre-commit hook found in .githooks/"
fi

# Verify installation
echo ""
echo "[2/3] Verifying installation..."
if [ -x ".git/hooks/pre-commit" ]; then
    echo "  [OK] Pre-commit hook is executable"
else
    echo "  [ERROR] Pre-commit hook is not executable"
    exit 1
fi

# Test the hook
echo ""
echo "[3/3] Testing pre-commit hook..."
echo "  (Running in test mode...)"
.git/hooks/pre-commit

if [ $? -eq 0 ]; then
    echo "  [OK] Pre-commit hook test passed"
else
    echo "  [ERROR] Pre-commit hook test failed"
    exit 1
fi

echo ""
echo "=========================================="
echo " Git Hooks Setup Complete"
echo "=========================================="
echo ""
echo "The pre-commit hook will now run automatically before each commit."
echo ""
echo "What it checks:"
echo "  - Python syntax in modified files"
echo "  - No hardcoded credentials"
echo "  - No emoji characters (ASCII-only)"
echo "  - Critical module imports"
echo ""
echo "To skip the hook (not recommended):"
echo "  git commit --no-verify"
echo ""
echo "To uninstall:"
echo "  rm .git/hooks/pre-commit"
echo ""

exit 0

