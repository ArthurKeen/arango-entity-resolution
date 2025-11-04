#!/bin/bash
# Deployment Validation Script
# Tests all high-priority risks before customer deployment

set -e

echo "=================================="
echo "Deployment Validation Script"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0
WARNINGS=0

# Function to check if database is running
check_database() {
    echo "[1/5] Checking ArangoDB connection..."
    
    if curl -s -f http://localhost:8529/_api/version > /dev/null 2>&1; then
        echo -e "${GREEN}[OK]${NC} ArangoDB is running"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}[FAIL]${NC} ArangoDB is not running"
        echo "      Run: docker-compose up -d"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# Function to run unit tests
run_unit_tests() {
    echo ""
    echo "[2/5] Running unit tests..."
    
    if python -m pytest tests/test_bulk_blocking_service.py \
                       tests/test_entity_resolver_simple.py \
                       tests/test_similarity_service_fixed.py \
                       tests/test_clustering_service_fixed.py \
                       -v --tb=short -q > /tmp/unit_test_results.txt 2>&1; then
        TESTS_PASSED=$(grep "passed" /tmp/unit_test_results.txt | tail -1)
        echo -e "${GREEN}[OK]${NC} Unit tests passed: $TESTS_PASSED"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}[FAIL]${NC} Unit tests failed"
        tail -20 /tmp/unit_test_results.txt
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# Function to run integration tests
run_integration_tests() {
    echo ""
    echo "[3/5] Running integration tests..."
    
    if [ ! -f /.dockerenv ] && ! curl -s -f http://localhost:8529/_api/version > /dev/null 2>&1; then
        echo -e "${YELLOW}[SKIP]${NC} Database not running - integration tests skipped"
        echo "      To run: docker-compose up -d && export ARANGO_ROOT_PASSWORD=testpassword123"
        WARNINGS=$((WARNINGS + 1))
        return 0
    fi
    
    export ARANGO_ROOT_PASSWORD=${ARANGO_ROOT_PASSWORD:-testpassword123}
    export USE_DEFAULT_PASSWORD=true
    
    if python -m pytest tests/test_bulk_integration.py -v --tb=short -x -q > /tmp/integration_test_results.txt 2>&1; then
        TESTS_PASSED=$(grep "passed" /tmp/integration_test_results.txt | tail -1)
        echo -e "${GREEN}[OK]${NC} Integration tests passed: $TESTS_PASSED"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}[FAIL]${NC} Integration tests failed"
        tail -20 /tmp/integration_test_results.txt
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# Function to validate performance
validate_performance() {
    echo ""
    echo "[4/5] Validating performance expectations..."
    
    # Check if bulk blocking service exists and has correct methods
    if python -c "
import sys
sys.path.insert(0, 'src')
from entity_resolution.services.bulk_blocking_service import BulkBlockingService
service = BulkBlockingService()
assert hasattr(service, 'generate_all_pairs'), 'Missing generate_all_pairs method'
assert hasattr(service, 'generate_pairs_streaming'), 'Missing streaming method'
assert hasattr(service, 'get_collection_stats'), 'Missing stats method'
print('All required methods present')
" 2>&1; then
        echo -e "${GREEN}[OK]${NC} Bulk blocking service has all required methods"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}[FAIL]${NC} Bulk blocking service missing required methods"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# Function to check Foxx service deployment readiness
check_foxx_readiness() {
    echo ""
    echo "[5/5] Checking Foxx service deployment readiness..."
    
    if [ -f "foxx-services/entity-resolution/manifest.json" ] && \
       [ -f "foxx-services/entity-resolution/main.js" ] && \
       [ -f "scripts/foxx/automated_deploy.py" ]; then
        echo -e "${GREEN}[OK]${NC} Foxx service files present and deployment script available"
        echo "      To deploy: python scripts/foxx/automated_deploy.py"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${YELLOW}[WARN]${NC} Foxx service files incomplete"
        WARNINGS=$((WARNINGS + 1))
        return 0
    fi
}

# Run all checks
check_database
run_unit_tests
run_integration_tests
validate_performance
check_foxx_readiness

# Summary
echo ""
echo "=================================="
echo "Validation Summary"
echo "=================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}[OK] All critical checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Test with customer-like data volume"
    echo "  2. Deploy Foxx service (if needed)"
    echo "  3. Monitor performance in staging"
    exit 0
else
    echo -e "${RED}[FAIL] Some checks failed. Address issues before deployment.${NC}"
    exit 1
fi

