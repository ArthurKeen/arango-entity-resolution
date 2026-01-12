#!/usr/bin/env bash
#
# Local Publish Script for arango-entity-resolution
# Used for manual publishing or dry-runs.
#
# Requirements: pip install build twine

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo -e "${YELLOW}=========================================="
echo " ARANGO-ER: Local Publish Tool"
echo -e "==========================================${NC}"

# 1. Clean up old builds
echo -e "\n[1/5] Cleaning old builds..."
rm -rf dist/ build/ *.egg-info
echo -e "${GREEN}[OK] Cleaned${NC}"

# 2. Run tests first
echo -e "\n[2/5] Running tests..."
pytest || {
    echo -e "${RED}[FAIL] Tests failed. Fix them before publishing.${NC}"
    exit 1
}
echo -e "${GREEN}[OK] Tests passed${NC}"

# 3. Build the package
echo -e "\n[3/5] Building package..."
python3 -m build
echo -e "${GREEN}[OK] Build complete${NC}"

# 4. Check package quality
echo -e "\n[4/5] Checking package quality..."
twine check dist/* || {
    echo -e "${RED}[FAIL] Package quality check failed.${NC}"
    exit 1
}
echo -e "${GREEN}[OK] Quality check passed${NC}"

# 5. Publish
echo -e "\n[5/5] Ready to publish?"
echo "------------------------------------------"
echo "Options:"
echo "1) DRY RUN (Upload to TestPyPI)"
echo "2) PRODUCTION (Upload to PyPI)"
echo "3) CANCEL"
echo "------------------------------------------"
read -p "Select option [1-3]: " choice

case $choice in
    1)
        echo -e "${YELLOW}Uploading to TestPyPI...${NC}"
        twine upload --repository testpypi dist/*
        ;;
    2)
        echo -e "${RED}Uploading to PRODUCTION PyPI...${NC}"
        twine upload dist/*
        ;;
    *)
        echo "Cancelled."
        exit 0
        ;;
esac

echo -e "\n${GREEN}=========================================="
echo " PUBLISH PROCESS COMPLETE"
echo -e "==========================================${NC}"
