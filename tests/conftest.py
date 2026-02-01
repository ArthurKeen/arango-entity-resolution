"""
Pytest Configuration and Shared Fixtures

Provides common fixtures and configuration for all tests.
"""

import pytest
import os
import sys
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.config import Config, get_config
from entity_resolution.services.bulk_blocking_service import BulkBlockingService

# Ensure unit tests don't fail due to missing environment variables
os.environ.setdefault("USE_DEFAULT_PASSWORD", "true")


# Configure pytest
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require database)"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests (slow)"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast, no dependencies)"
    )


# Fixtures for configuration
@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration"""
    # Ensure we have a valid config for unit tests without environment lookups
    # setting USE_DEFAULT_PASSWORD=true makes get_config() not fail
    os.environ["USE_DEFAULT_PASSWORD"] = "true"
    config = get_config()
    
    # Override with test-specific settings
    config.db.database = os.getenv("TEST_DB_NAME", "entity_resolution_test")
    
    return config


@pytest.fixture(scope="session")
def db_connection(test_config):
    """Provide database connection for tests"""
    from arango import ArangoClient
    
    try:
        client = ArangoClient(hosts=f"http://{test_config.db.host}:{test_config.db.port}")
        db = client.db(
            test_config.db.database,
            username=test_config.db.username,
            password=test_config.db.password
        )
        # Validate connection and permissions up front to avoid auth errors in tests
        try:
            db.properties()
        except Exception as e:
            pytest.skip(f"Cannot access database (auth/connection): {e}")
        yield db
    except Exception as e:
        pytest.skip(f"Cannot connect to database: {e}")


# Fixtures for test data
@pytest.fixture
def sample_customers():
    """Provide sample customer records for testing"""
    return [
        {
            "_key": "1",
            "first_name": "John",
            "last_name": "Smith",
            "email": "john.smith@example.com",
            "phone": "555-1234",
            "address": "123 Main St",
            "city": "Boston",
            "company": "Acme Corp"
        },
        {
            "_key": "2",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
            "phone": "555-5678",
            "address": "456 Oak Ave",
            "city": "New York",
            "company": "TechCo"
        },
        {
            "_key": "3",
            "first_name": "John",
            "last_name": "Smith",  # Duplicate
            "email": "j.smith@example.com",
            "phone": "555-1234",  # Same phone
            "address": "123 Main Street",  # Slightly different address
            "city": "Boston",
            "company": "Acme Corporation"
        }
    ]


@pytest.fixture
def sample_candidate_pairs():
    """Provide sample candidate pairs for testing"""
    return [
        {
            "record_a_id": "customers/1",
            "record_b_id": "customers/2",
            "strategy": "exact_phone",
            "blocking_key": "555-1234"
        },
        {
            "record_a_id": "customers/1",
            "record_b_id": "customers/3",
            "strategy": "ngram_name",
            "blocking_key": "JOH_2"
        }
    ]


# Fixtures for services
@pytest.fixture
def bulk_service(test_config):
    """Provide BulkBlockingService instance"""
    service = BulkBlockingService(test_config)
    return service


@pytest.fixture
def connected_bulk_service(bulk_service):
    """Provide connected BulkBlockingService"""
    if not bulk_service.connect():
        pytest.skip("Cannot connect to database")
    return bulk_service


# Fixtures for test collections
@pytest.fixture
def temp_collection(db_connection):
    """Create a temporary collection for testing"""
    import uuid
    
    collection_name = f"test_temp_{uuid.uuid4().hex[:8]}"
    
    # Create collection
    if db_connection.has_collection(collection_name):
        db_connection.delete_collection(collection_name)
    
    collection = db_connection.create_collection(collection_name)
    
    yield collection_name
    
    # Cleanup
    if db_connection.has_collection(collection_name):
        db_connection.delete_collection(collection_name)


@pytest.fixture
def populated_collection(db_connection, temp_collection, sample_customers):
    """Create and populate a test collection"""
    collection = db_connection.collection(temp_collection)
    collection.insert_many(sample_customers)
    
    return temp_collection


# Helper functions
def assert_valid_result(result: Dict[str, Any]):
    """Assert that a result dictionary is valid"""
    assert isinstance(result, dict)
    assert 'success' in result
    
    if result['success']:
        assert 'candidate_pairs' in result or 'clusters' in result
    else:
        assert 'error' in result


def assert_valid_statistics(stats: Dict[str, Any]):
    """Assert that statistics dictionary is valid"""
    assert isinstance(stats, dict)
    assert 'execution_time' in stats
    assert stats['execution_time'] >= 0
    
    if 'total_pairs' in stats:
        assert stats['total_pairs'] >= 0
    
    if 'pairs_per_second' in stats:
        assert stats['pairs_per_second'] >= 0


# Pytest hooks for better output
def pytest_collection_modifyitems(config, items):
    """Modify test items to add markers based on test name/location"""
    for item in items:
        # Add markers based on test file name
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        elif "performance" in item.nodeid or "benchmark" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        else:
            item.add_marker(pytest.mark.unit)


def pytest_report_header(config):
    """Add custom header to pytest output"""
    env_info = [
        "Test Environment:",
        f"  Database: {os.getenv('ARANGO_DATABASE', 'entity_resolution_test')}",
        f"  Host: {os.getenv('ARANGO_HOST', 'localhost')}:{os.getenv('ARANGO_PORT', '8529')}",
        f"  Skip Integration: {os.getenv('SKIP_INTEGRATION_TESTS', 'false')}",
        f"  Skip Performance: {os.getenv('SKIP_PERFORMANCE_TESTS', 'false')}",
    ]
    return env_info

