#!/usr/bin/env python3
"""
Test Database Manager

Provides resilient database management for test files, similar to the demo
database setup but optimized for testing scenarios. This class can be
imported by test files to ensure they have a working database connection.
"""

import subprocess
import json
import time
import requests
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from arango import ArangoClient
from arango.exceptions import DatabaseCreateError, CollectionCreateError


class TestDatabaseManager:
    """Manages test database connections with resilience features"""
    
    def __init__(self, 
                 host: str = "localhost", 
                 port: int = 8529,
                 username: str = "root", 
                 password: str = "testpassword123",
                 database: str = "entity_resolution_test"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.base_url = f"http://{host}:{port}"
        self.client = None
        self.db = None
        self.connected = False
        
    def ensure_database_available(self) -> bool:
        """Ensure database is available, starting it if necessary"""
        print("🔍 Ensuring test database is available...")
        
        # First, try to connect
        if self.test_connection():
            print("✅ Database is already available")
            return True
        
        # If connection fails, try to start database
        print("⚠️  Database not available, attempting to start...")
        
        # Check if we can run the setup script
        setup_script = Path(__file__).parent / "setup_test_database.py"
        if setup_script.exists():
            print("🚀 Running test database setup...")
            result = subprocess.run([sys.executable, str(setup_script)], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Test database setup completed")
                # Wait a moment for database to be ready
                time.sleep(2)
                return self.test_connection()
            else:
                print(f"❌ Test database setup failed: {result.stderr}")
        
        print("❌ Could not ensure database availability")
        return False
    
    def test_connection(self) -> bool:
        """Test connection to the database"""
        try:
            self.client = ArangoClient(hosts=f"http://{self.host}:{self.port}")
            self.db = self.client.db(self.database, username=self.username, password=self.password)
            
            # Test the connection
            self.db.properties()
            self.connected = True
            return True
            
        except Exception as e:
            self.connected = False
            return False
    
    def connect(self) -> bool:
        """Connect to the database with resilience"""
        if self.connected:
            return True
        
        # Ensure database is available
        if not self.ensure_database_available():
            return False
        
        # Try to connect
        return self.test_connection()
    
    def get_database(self):
        """Get the database connection"""
        if not self.connected:
            if not self.connect():
                raise ConnectionError("Could not connect to test database")
        return self.db
    
    def get_client(self):
        """Get the ArangoDB client"""
        if not self.connected:
            if not self.connect():
                raise ConnectionError("Could not connect to test database")
        return self.client
    
    def create_test_collections(self) -> bool:
        """Create test collections if they don't exist"""
        if not self.connected:
            if not self.connect():
                return False
        
        collections = ['customers', 'similarity_pairs', 'clusters', 'golden_records']
        
        for collection_name in collections:
            try:
                if not self.db.has_collection(collection_name):
                    self.db.create_collection(collection_name)
                    print(f"✅ Created collection: {collection_name}")
                else:
                    print(f"✅ Collection exists: {collection_name}")
            except Exception as e:
                print(f"❌ Failed to create collection {collection_name}: {e}")
                return False
        
        return True
    
    def create_sample_data(self) -> bool:
        """Create sample test data if collections are empty"""
        if not self.connected:
            if not self.connect():
                return False
        
        try:
            # Create sample customers
            customers_collection = self.db.collection('customers')
            if customers_collection.count() == 0:
                sample_customers = [
                    {
                        "first_name": "John",
                        "last_name": "Smith", 
                        "email": "john.smith@email.com",
                        "phone": "555-1234",
                        "company": "Acme Corp"
                    },
                    {
                        "first_name": "Jon",
                        "last_name": "Smith",
                        "email": "jon.smith@email.com", 
                        "phone": "555-1234",
                        "company": "Acme Corporation"
                    },
                    {
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "email": "jane.doe@email.com",
                        "phone": "555-5678", 
                        "company": "Beta Inc"
                    },
                    {
                        "first_name": "John",
                        "last_name": "Smith",
                        "email": "j.smith@acme.com",
                        "phone": "555-1234",
                        "company": "Acme Corp"
                    }
                ]
                
                for customer in sample_customers:
                    customers_collection.insert(customer)
                
                print(f"✅ Created {len(sample_customers)} sample customers")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to create sample data: {e}")
            return False
    
    def cleanup_test_data(self) -> bool:
        """Clean up test data (optional, for test isolation)"""
        if not self.connected:
            return True
        
        try:
            collections = ['customers', 'similarity_pairs', 'clusters', 'golden_records']
            
            for collection_name in collections:
                if self.db.has_collection(collection_name):
                    collection = self.db.collection(collection_name)
                    collection.truncate()
                    print(f"✅ Cleaned collection: {collection_name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to cleanup test data: {e}")
            return False
    
    def get_sample_record(self, collection_name: str = 'customers'):
        """Get a sample record from a collection for testing"""
        if not self.connected:
            if not self.connect():
                return None
        
        try:
            collection = self.db.collection(collection_name)
            records = list(collection.all(limit=1))
            return records[0] if records else None
            
        except Exception as e:
            print(f"❌ Failed to get sample record: {e}")
            return None
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information"""
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "database": self.database,
            "url": f"http://{self.host}:{self.port}",
            "connected": self.connected
        }


# Convenience function for test files
def get_test_database_manager() -> TestDatabaseManager:
    """Get a test database manager instance"""
    return TestDatabaseManager()


def ensure_test_database() -> TestDatabaseManager:
    """Ensure test database is available and return manager"""
    manager = TestDatabaseManager()
    if manager.connect():
        manager.create_test_collections()
        manager.create_sample_data()
    return manager


if __name__ == "__main__":
    # Test the database manager
    manager = TestDatabaseManager()
    
    if manager.connect():
        print("✅ Test database connection successful!")
        print(f"📊 Connection info: {manager.get_connection_info()}")
        
        # Test sample data creation
        if manager.create_sample_data():
            print("✅ Sample data created successfully!")
            
            # Test getting a sample record
            sample = manager.get_sample_record()
            if sample:
                print(f"📝 Sample record: {sample}")
        
    else:
        print("❌ Test database connection failed!")
        sys.exit(1)
