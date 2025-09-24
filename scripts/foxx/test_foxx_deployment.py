#!/usr/bin/env python3
"""
Test Foxx Service Deployment

Tests all Foxx service endpoints to verify deployment and functionality.
"""

import sys
import requests
from pathlib import Path

# Add src to path for imports  
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from entity_resolution.utils.config import Config, get_config
from entity_resolution.utils.logging import get_logger

logger = get_logger(__name__)

def test_foxx_service(config: Config, mount_point: str = "/entity-resolution"):
    """Test all Foxx service endpoints"""
    base_url = f"http://{config.db.host}:{config.db.port}/_db/{config.db.database}{mount_point}"
    auth = config.get_auth_tuple()
    
    results = {}
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", auth=auth, timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            results['health'] = 'OK'
            logger.info(f"Health check: {health_data.get('status', 'unknown')}")
            logger.info(f"Active modules: {health_data.get('active_modules', [])}")
        else:
            results['health'] = f'HTTP {response.status_code}'
    except Exception as e:
        results['health'] = f'ERROR: {str(e)}'
    
    # Test info endpoint
    try:
        response = requests.get(f"{base_url}/info", auth=auth, timeout=5)
        if response.status_code == 200:
            info_data = response.json()
            results['info'] = 'OK'
            logger.info(f"Service: {info_data.get('name', 'unknown')}")
            logger.info(f"Status: {info_data.get('status', 'unknown')}")
        else:
            results['info'] = f'HTTP {response.status_code}'
    except Exception as e:
        results['info'] = f'ERROR: {str(e)}'
    
    # Test similarity endpoint
    try:
        test_payload = {
            "docA": {"first_name": "John", "last_name": "Smith", "email": "john@example.com"},
            "docB": {"first_name": "Jon", "last_name": "Smith", "email": "john@example.com"},
            "includeDetails": True
        }
        response = requests.post(f"{base_url}/similarity/compute", 
                               auth=auth, json=test_payload, timeout=10)
        if response.status_code == 200:
            similarity_data = response.json()
            results['similarity'] = 'OK'
            logger.info(f"Similarity test: {similarity_data.get('success', False)}")
        else:
            results['similarity'] = f'HTTP {response.status_code}'
    except Exception as e:
        results['similarity'] = f'ERROR: {str(e)}'
    
    # Test similarity functions endpoint
    try:
        response = requests.get(f"{base_url}/similarity/functions", auth=auth, timeout=5)
        if response.status_code == 200:
            results['similarity_functions'] = 'OK'
            logger.info("Similarity functions endpoint accessible")
        else:
            results['similarity_functions'] = f'HTTP {response.status_code}'
    except Exception as e:
        results['similarity_functions'] = f'ERROR: {str(e)}'
    
    # Test blocking stats endpoint  
    try:
        response = requests.get(f"{base_url}/blocking/stats", auth=auth, timeout=5)
        results['blocking_stats'] = 'OK' if response.status_code in [200, 404] else f'HTTP {response.status_code}'
    except Exception as e:
        results['blocking_stats'] = f'ERROR: {str(e)}'
    
    # Test clustering analyze endpoint
    try:
        response = requests.get(f"{base_url}/clustering/analyze", auth=auth, timeout=5)
        results['clustering_analyze'] = 'OK' if response.status_code in [200, 404] else f'HTTP {response.status_code}'
    except Exception as e:
        results['clustering_analyze'] = f'ERROR: {str(e)}'
    
    return results

def main():
    """Main test function"""
    logger.info("Testing Foxx service deployment")
    
    config = get_config()
    
    # Test connection
    try:
        response = requests.get(f"http://{config.db.host}:{config.db.port}/_api/version", 
                              auth=config.get_auth_tuple(), timeout=5)
        if response.status_code != 200:
            logger.error("Cannot connect to ArangoDB")
            return False
    except Exception as e:
        logger.error(f"Cannot connect to ArangoDB: {e}")
        return False
    
    # Test Foxx service
    results = test_foxx_service(config)
    
    # Report results
    logger.info("FOXX SERVICE TEST RESULTS:")
    all_ok = True
    for endpoint, result in results.items():
        status_symbol = "PASS" if result == 'OK' else "FAIL"
        logger.info(f"  {endpoint}: {status_symbol} ({result})")
        if result != 'OK':
            all_ok = False
    
    if all_ok:
        logger.info("ALL TESTS PASSED - Foxx service is working correctly")
        return True
    else:
        logger.warning("Some tests failed - Check deployment or service status")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
