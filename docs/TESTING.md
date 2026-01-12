# Testing Guide

**Last Updated**: November 17, 2025 
**Version**: 3.0.0

---

## Overview

This guide covers testing the arango-entity-resolution library, including unit tests, integration tests, and end-to-end testing with ArangoDB.

---

## Test Structure

### Test Files

- **Unit Tests**: Located in `tests/` directory
- **Integration Tests**: Marked with `@pytest.mark.integration`
- **Test Configuration**: `tests/conftest.py` provides shared fixtures

### Test Coverage

Current test coverage: **~80%** (estimated)

**Well-Covered Components:**
- v3.0 components (WeightedFieldSimilarity, AddressERService, ConfigurableERPipeline)
- v2.0 services (BatchSimilarityService, SimilarityEdgeService, strategies)
- Security utilities (validation.py)
- Configuration system (er_config.py, config.py)
- Database utilities (database.py, graph_utils.py)

**Coverage Report**: See [TEST_COVERAGE_AUDIT.md](archive/audits/TEST_COVERAGE_AUDIT.md) for detailed analysis.

---

## Running Tests

### Prerequisites

1. **Install Dependencies**:
```bash
# Recommended: install as a library in editable mode
pip install -e ".[test]"

# Alternative: install from requirements file
# pip install -r requirements.txt
```

2. **ArangoDB Container** (for integration tests):
```bash
docker run -d --name arangodb-test -p 8529:8529 \
-e ARANGO_ROOT_PASSWORD=testpassword123 \
-v ~/data:/data \
arangodb/arangodb:latest
```

### Environment Variables

Set these before running integration tests:

```bash
export ARANGO_ROOT_PASSWORD=testpassword123
export USE_DEFAULT_PASSWORD=true
export ARANGO_HOST=localhost
export ARANGO_PORT=8529
export ARANGO_DATABASE=entity_resolution_test
```

### Running Test Suites

#### All Tests
```bash
pytest tests/ -v
```

#### Unit Tests Only
```bash
pytest tests/ -v -m "not integration"
```

#### Integration Tests Only
```bash
pytest tests/ -v -m integration
```

#### Specific Test File
```bash
pytest tests/test_round_trip_v3.py -v
```

#### Simple Round-Trip Test
```bash
python test_round_trip_simple.py
```

---

## Test Results

### Latest Test Run (November 17, 2025)

**Status**: **All Tests Passing**

- **Total Tests**: 14 integration tests
- **Passed**: 14 
- **Failed**: 0
- **Runtime**: ~10 seconds

**Components Tested:**
- WeightedFieldSimilarity
- BatchSimilarityService
- AddressERService
- WCCClusteringService (Python DFS)
- Complete ER pipeline

**Full Results**: See [E2E_TEST_RESULTS.md](../E2E_TEST_RESULTS.md)

---

## Test Files by Component

### v3.0 Components
- `test_weighted_field_similarity.py` - WeightedFieldSimilarity unit tests
- `test_address_er_service.py` - AddressERService unit tests
- `test_er_config.py` - ERPipelineConfig tests
- `test_configurable_pipeline.py` - ConfigurableERPipeline tests
- `test_round_trip_v3.py` - v3.0 integration tests

### v2.0 Services
- `test_blocking_strategies.py` - Blocking strategy tests
- `test_similarity_and_edge_services.py` - BatchSimilarityService and SimilarityEdgeService
- `test_wcc_clustering_service.py` - WCCClusteringService tests

### Utilities
- `test_validation_security.py` - Security and validation tests
- `test_graph_utils.py` - Graph utility tests
- `test_config.py` - Configuration system tests
- `test_database.py` - Database management tests
- `test_algorithms_comprehensive.py` - Algorithm tests

### Integration
- `test_integration_and_performance.py` - Full integration tests
- `test_round_trip_v3.py` - Round-trip tests

---

## Writing Tests

### Test Structure

```python
import pytest
from entity_resolution import YourComponent

class TestYourComponent:
"""Test cases for YourComponent."""

def test_basic_functionality(self):
"""Test basic functionality."""
component = YourComponent()
result = component.do_something()
assert result is not None
```

### Using Fixtures

```python
@pytest.fixture
def test_db():
"""Provide test database connection."""
from entity_resolution import get_database
return get_database()
```

### Integration Test Markers

```python
@pytest.mark.integration
def test_with_database(test_db):
"""Integration test requiring database."""
# Test code here
```

---

## Continuous Integration

Tests should be run:
- Before committing code
- In CI/CD pipeline
- Before releases

---

## Troubleshooting

### Database Connection Issues
- Verify ArangoDB container is running: `docker ps | grep arangodb`
- Check environment variables are set
- Verify database exists: `curl -u root:testpassword123 http://localhost:8529/_api/database`

### Import Errors
- Ensure dependencies are installed: `pip install -r requirements.txt`
- Check Python path includes `src/` directory

### Test Failures
- Review test output for specific error messages
- Check test logs in `tests/` directory
- Verify test data is correct

---

## Coverage Goals

- **Target**: 80%+ overall coverage
- **Current**: ~80% (estimated)
- **Critical Components**: 100% coverage target
- **Utilities**: 70%+ coverage target

---

**For detailed coverage analysis, see**: [TEST_COVERAGE_AUDIT.md](archive/audits/TEST_COVERAGE_AUDIT.md)

