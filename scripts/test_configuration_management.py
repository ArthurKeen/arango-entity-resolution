#!/usr/bin/env python3
"""
Test Configuration Management

This script tests the new enhanced configuration management system.
"""

import sys
import os
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.enhanced_config import get_config

def test_configuration_management():
    """Test the enhanced configuration management."""
    print("🧪 TESTING ENHANCED CONFIGURATION MANAGEMENT")
    print("="*50)
    
    try:
        # Test configuration loading
        config = get_config()
        print("✅ Configuration loading successful")
        
        # Test database configuration
        print("\n📊 Testing database configuration...")
        print(f"   Host: {config.database.host}")
        print(f"   Port: {config.database.port}")
        print(f"   Username: {config.database.username}")
        print(f"   Database Name: {config.database.database_name}")
        print(f"   Timeout: {config.database.timeout}")
        
        # Test service configuration
        print("\n📊 Testing service configuration...")
        print(f"   Blocking Service URL: {config.service.blocking_service_url}")
        print(f"   Similarity Service URL: {config.service.similarity_service_url}")
        print(f"   Clustering Service URL: {config.service.clustering_service_url}")
        print(f"   Service Timeout: {config.service.timeout}")
        
        # Test logging configuration
        print("\n📊 Testing logging configuration...")
        print(f"   Log Level: {config.logging.level}")
        print(f"   Log Format: {config.logging.format}")
        print(f"   Log File: {config.logging.file_path}")
        
        # Test performance configuration
        print("\n📊 Testing performance configuration...")
        print(f"   Max Workers: {config.performance.max_workers}")
        print(f"   Batch Size: {config.performance.batch_size}")
        print(f"   Cache Size: {config.performance.cache_size}")
        print(f"   Cache TTL: {config.performance.cache_ttl}")
        
        # Test configuration validation
        print("\n📊 Testing configuration validation...")
        if config.validate_config():
            print("✅ Configuration validation passed")
        else:
            print("❌ Configuration validation failed")
            return False
        
        # Test database URL generation
        print("\n📊 Testing database URL generation...")
        db_url = config.get_database_url()
        print(f"   Database URL: {db_url}")
        
        # Test service URL generation
        print("\n📊 Testing service URL generation...")
        blocking_url = config.get_service_url('blocking')
        similarity_url = config.get_service_url('similarity')
        clustering_url = config.get_service_url('clustering')
        print(f"   Blocking URL: {blocking_url}")
        print(f"   Similarity URL: {similarity_url}")
        print(f"   Clustering URL: {clustering_url}")
        
        # Test configuration file existence
        print("\n📊 Testing configuration file...")
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config_data = json.load(f)
                print("✅ Configuration file exists and is valid JSON")
                print(f"   Database host: {config_data.get('database', {}).get('host', 'N/A')}")
        else:
            print("⚠️  Configuration file not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration management test failed: {e}")
        return False

def main():
    """Main test function."""
    success = test_configuration_management()
    
    if success:
        print("\n🎉 Configuration management test completed successfully!")
        return 0
    else:
        print("\n❌ Configuration management test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
