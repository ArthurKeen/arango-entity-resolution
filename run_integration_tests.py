#!/usr/bin/env python3
"""
Integration Test Runner

Checks database connectivity and runs integration tests for arango-entity-resolution v2.0.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def check_database_connection():
    """Check if ArangoDB is available."""
    try:
        from entity_resolution.utils.database import get_database_manager
        
        print("=" * 80)
        print("CHECKING ARANGODB CONNECTION")
        print("=" * 80)
        
        db_manager = get_database_manager()
        conn_info = db_manager.get_connection_info()
        
        print(f"\nConnection details:")
        print(f"  Host: {conn_info['host']}")
        print(f"  Port: {conn_info['port']}")
        print(f"  Database: {conn_info['database']}")
        print(f"  URL: {conn_info['url']}")
        
        print(f"\nTesting connection...")
        
        if db_manager.test_connection():
            print("✅ Connection successful!")
            return True
        else:
            print("❌ Connection failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def run_integration_tests():
    """Run integration tests using pytest."""
    import pytest
    
    print("\n" + "=" * 80)
    print("RUNNING INTEGRATION TESTS")
    print("=" * 80 + "\n")
    
    # Run integration tests with verbose output
    test_file = "tests/test_integration_and_performance.py"
    
    # Check if test file exists
    if not Path(test_file).exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    # Run pytest
    result = pytest.main([
        test_file,
        "-v",           # Verbose
        "-s",           # Show print statements
        "-m", "integration",  # Only integration tests
        "--tb=short"    # Short traceback format
    ])
    
    return result == 0


def print_docker_instructions():
    """Print instructions for starting ArangoDB with Docker."""
    print("\n" + "=" * 80)
    print("HOW TO START ARANGODB WITH DOCKER")
    print("=" * 80)
    print("""
To run integration tests, you need ArangoDB running locally.

Start ArangoDB with Docker:

  docker run -d \\
    --name arangodb \\
    -p 8529:8529 \\
    -e ARANGO_ROOT_PASSWORD=test \\
    arangodb/arangodb:3.11

Access web interface:
  http://localhost:8529
  Username: root
  Password: test

Stop ArangoDB:
  docker stop arangodb

Remove container:
  docker rm arangodb

Check if running:
  docker ps | grep arango
""")


def main():
    """Main entry point."""
    print("\n" + "=" * 80)
    print("ARANGO-ENTITY-RESOLUTION v2.0 - INTEGRATION TEST SUITE")
    print("=" * 80 + "\n")
    
    # Check database connection
    if not check_database_connection():
        print("\n⚠️  Cannot connect to ArangoDB!")
        print_docker_instructions()
        
        print("\nOnce ArangoDB is running, run this script again:")
        print("  python run_integration_tests.py\n")
        return 1
    
    # Run integration tests
    success = run_integration_tests()
    
    if success:
        print("\n" + "=" * 80)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("=" * 80 + "\n")
        return 0
    else:
        print("\n" + "=" * 80)
        print("❌ SOME TESTS FAILED")
        print("=" * 80 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

