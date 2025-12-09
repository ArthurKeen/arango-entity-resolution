# Testing Documentation

This directory contains test results, status reports, and testing-related documentation.

## Test Result Documents

### Current Test Status

- **[testing-status.md](./testing-status.md)** - Current testing status and coverage
- **[testing-complete.md](./testing-complete.md)** - Completion report for major testing milestones

### Test Results by Type

- **[e2e-test-results.md](./e2e-test-results.md)** - End-to-end test results
- **[functional-test-results.md](./functional-test-results.md)** - Functional test results for v2.x features
- **[post-merge-test-results.md](./post-merge-test-results.md)** - Results after merging v2.x and v3.0

## Test Suites

### Unit Tests
Location: `/tests/unit/`
- Core functionality tests
- Individual component tests
- Fast, isolated tests

### Integration Tests
Location: `/tests/integration/`
- Multi-component tests
- Database integration tests
- Service interaction tests

### End-to-End Tests
Location: `/tests/e2e/`
- Complete workflow tests
- Real-world scenarios
- Full pipeline validation

### Performance Tests
Location: `/tests/performance/`
- `test_wcc_performance.py` - WCC clustering performance tests
- Benchmark tests
- Scalability tests

## Running Tests

### Quick Test
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_similarity_service.py

# Run with coverage
pytest --cov=src/entity_resolution
```

### Test with Real Database
```bash
# Start test database
docker-compose -f docker-compose.test.yml up -d

# Set environment
export ARANGO_HOST=localhost
export ARANGO_PORT=8532
export ARANGO_PASSWORD=test_er_password_2025

# Run tests
pytest tests/integration/
```

### Performance Tests
```bash
python3 tests/test_wcc_performance.py
```

## Test Database

**Configuration:** See `/config/test-database.md`

**Docker Setup:**
```bash
# Test database runs on port 8532
docker-compose -f docker-compose.test.yml up -d

# Credentials
Host: localhost
Port: 8532
Username: root
Password: test_er_password_2025
Database: entity_resolution
```

## Test Coverage

**Target:** 80%+ code coverage

**Current Status:** See [testing-status.md](./testing-status.md)

**Coverage Report:**
```bash
pytest --cov=src/entity_resolution --cov-report=html
open htmlcov/index.html
```

## Continuous Testing

### Pre-Commit Hooks
- Syntax checks
- Import validation
- Code quality checks

### Pre-Push Hooks
- Module import tests
- Code style validation
- Quick smoke tests

**Note:** See `/docs/development/pre-push-hook-issue.md` for known issues with import-time config loading.

## Test Data

### Sample Data
Location: `/data/sample/`
- Small datasets for quick testing
- Known duplicate patterns
- Edge cases

### Generated Data
```bash
# Generate test data
python3 demo/scripts/data_generator.py --records 1000 --output-dir data/test/
```

## Test Reports

Test reports are generated in `/reports/` directory:
- Performance benchmarks
- Coverage summaries
- Test execution logs

## Contributing Tests

When adding new features:
1. ✅ Write unit tests first (TDD)
2. ✅ Add integration tests
3. ✅ Update test documentation
4. ✅ Ensure tests pass before commit
5. ✅ Aim for 80%+ coverage

## Related Documentation

- **Development Guide:** `/docs/development/`
- **Test Database Config:** `/config/test-database.md`
- **CI/CD Documentation:** `/docs/development/` (when available)

---

**Last Updated:** December 2, 2025  
**Test Framework:** pytest  
**Coverage Tool:** pytest-cov  
**Database:** ArangoDB (via Docker)

