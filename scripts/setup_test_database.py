#!/usr/bin/env python3
"""
Test Database Setup Script

This script provides resilient database management for the test system, similar to
the demo database setup but optimized for testing scenarios:

1. Checks if there's a database running on port 8529
2. Verifies if it's the correct database for testing
3. Stops conflicting databases if needed
4. Starts the correct ArangoDB container for testing
5. Falls back to pulling and starting a fresh ArangoDB CE container
6. Creates test database and collections
7. Provides test data if needed
"""

import subprocess
import json
import time
import requests
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, List


class TestDatabaseSetup:
    """Handles automatic ArangoDB setup for entity resolution testing"""
    
    def __init__(self):
        self.project_name = "arango-entity-resolution-test"
        self.container_name = "arango-entity-resolution-test"
        self.port = 8529
        self.base_url = f"http://localhost:{self.port}"
        self.username = "root"
        self.password = config.db.password
        self.test_database = "entity_resolution_test"
        
    def run_command(self, command: str, capture_output: bool = True) -> subprocess.CompletedProcess:
        """Run a shell command and return the result"""
        try:
            if capture_output:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
            else:
                result = subprocess.run(command, shell=True)
            return result
        except Exception as e:
            print(f"❌ Error running command '{command}': {e}")
            return None
    
    def check_port_8529(self) -> Optional[Dict[str, Any]]:
        """Check what's running on port 8529"""
        print("🔍 Checking what's running on port 8529...")
        
        # Check if anything is listening on port 8529
        result = self.run_command(f"lsof -i :{self.port}")
        if result and result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # More than just the header
                print(f"📊 Found processes on port {self.port}:")
                for line in lines[1:]:  # Skip header
                    print(f"   {line}")
                return {"occupied": True, "processes": lines[1:]}
        
        print(f"✅ Port {self.port} is available")
        return {"occupied": False, "processes": []}
    
    def check_arango_connection(self) -> bool:
        """Check if we can connect to ArangoDB on port 8529"""
        print("🔗 Testing ArangoDB connection...")
        
        try:
            # Test basic connectivity
            response = requests.get(f"{self.base_url}/_api/version", timeout=5)
            if response.status_code == 200:
                version_info = response.json()
                print(f"✅ ArangoDB is running - Version: {version_info.get('version', 'Unknown')}")
                return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to ArangoDB: {e}")
            return False
        
        return False
    
    def check_docker_containers(self) -> Dict[str, Any]:
        """Check for existing Docker containers"""
        print("🐳 Checking Docker containers...")
        
        # Check for our specific test container
        result = self.run_command(f"docker ps -a --filter name={self.container_name} --format '{{{{.Names}}}} {{{{.Status}}}}'")
        if result and result.returncode == 0 and result.stdout.strip():
            print(f"📦 Found test container '{self.container_name}': {result.stdout.strip()}")
            return {"exists": True, "status": result.stdout.strip()}
        
        # Check for any ArangoDB containers
        result = self.run_command("docker ps -a --filter ancestor=arangodb --format '{{.Names}} {{.Status}}'")
        if result and result.returncode == 0 and result.stdout.strip():
            print(f"📦 Found ArangoDB containers:")
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    print(f"   {line}")
            return {"exists": True, "containers": result.stdout.strip().split('\n')}
        
        print("✅ No existing ArangoDB containers found")
        return {"exists": False}
    
    def stop_conflicting_containers(self) -> bool:
        """Stop any conflicting ArangoDB containers"""
        print("🛑 Stopping conflicting containers...")
        
        # Stop our test container if it exists
        result = self.run_command(f"docker stop {self.container_name}")
        if result and result.returncode == 0:
            print(f"✅ Stopped test container: {self.container_name}")
        
        # Stop any other ArangoDB containers that might conflict
        result = self.run_command("docker ps -q --filter ancestor=arangodb")
        if result and result.returncode == 0 and result.stdout.strip():
            container_ids = result.stdout.strip().split('\n')
            for container_id in container_ids:
                if container_id.strip():
                    print(f"🛑 Stopping conflicting container: {container_id}")
                    self.run_command(f"docker stop {container_id}")
        
        return True
    
    def start_test_container(self) -> bool:
        """Start the test ArangoDB container"""
        print(f"🚀 Starting test container: {self.container_name}")
        
        # Check if container already exists and is running
        result = self.run_command(f"docker ps --filter name={self.container_name} --format '{{{{.Names}}}}'")
        if result and result.returncode == 0 and self.container_name in result.stdout:
            print(f"✅ Test container is already running: {self.container_name}")
            return True
        
        # Start existing container if it exists
        result = self.run_command(f"docker start {self.container_name}")
        if result and result.returncode == 0:
            print(f"✅ Started existing test container: {self.container_name}")
            return True
        
        # Create new container
        docker_cmd = f"""
        docker run -d \
            --name {self.container_name} \
            -p {self.port}:8529 \
            -e ARANGO_ROOT_PASSWORD={self.password} \
            arangodb/arangodb:latest
        """
        
        result = self.run_command(docker_cmd)
        if result and result.returncode == 0:
            print(f"✅ Created and started test container: {self.container_name}")
            return True
        
        print(f"❌ Failed to start test container")
        return False
    
    def pull_arangodb_image(self) -> bool:
        """Pull the latest ArangoDB image"""
        print("📥 Pulling latest ArangoDB image...")
        
        result = self.run_command("docker pull arangodb/arangodb:latest")
        if result and result.returncode == 0:
            print("✅ Successfully pulled ArangoDB image")
            return True
        
        print("❌ Failed to pull ArangoDB image")
        return False
    
    def wait_for_arangodb(self, max_wait: int = 30) -> bool:
        """Wait for ArangoDB to be ready"""
        print("⏳ Waiting for ArangoDB to be ready...")
        
        for i in range(max_wait):
            if self.check_arango_connection():
                print("✅ ArangoDB is ready!")
                return True
            
            print(f"   Waiting... ({i+1}/{max_wait})")
            time.sleep(1)
        
        print("❌ ArangoDB failed to start within timeout")
        return False
    
    def setup_test_database_and_collections(self) -> bool:
        """Setup test database and collections"""
        print("🗄️  Setting up test database and collections...")
        
        try:
            from arango import ArangoClient
            
            # Connect to system database
            client = ArangoClient(hosts=f"http://localhost:{self.port}")
            sys_db = client.db('_system', username=self.username, password=self.password)
            
            # Create test database if it doesn't exist
            if not sys_db.has_database(self.test_database):
                print(f"📁 Creating test database: {self.test_database}")
                sys_db.create_database(self.test_database)
            else:
                print(f"✅ Test database already exists: {self.test_database}")
            
            # Connect to test database
            test_db = client.db(self.test_database, username=self.username, password=self.password)
            
            # Create collections if they don't exist
            collections = ['customers', 'similarity_pairs', 'clusters', 'golden_records']
            
            for collection_name in collections:
                if not test_db.has_collection(collection_name):
                    print(f"📁 Creating collection: {collection_name}")
                    test_db.create_collection(collection_name)
                else:
                    print(f"✅ Collection already exists: {collection_name}")
            
            # Create test data if collections are empty
            self.create_test_data_if_needed(test_db)
            
            print("✅ Test database and collections setup completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup test database: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_test_data_if_needed(self, db) -> bool:
        """Create test data if collections are empty"""
        print("📊 Creating test data if needed...")
        
        try:
            # Check if customers collection has data
            customers_collection = db.collection('customers')
            if customers_collection.count() == 0:
                print("📝 Creating sample customer data...")
                
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
                    }
                ]
                
                for customer in sample_customers:
                    customers_collection.insert(customer)
                
                print(f"✅ Created {len(sample_customers)} sample customers")
            
            # Check if similarity_pairs collection has data
            similarity_collection = db.collection('similarity_pairs')
            if similarity_collection.count() == 0:
                print("📝 Creating sample similarity pairs...")
                
                # Get customer IDs for similarity pairs
                customers = list(customers_collection.all(limit=3))
                if len(customers) >= 2:
                    pair = {
                        "record_a_id": customers[0]['_id'],
                        "record_b_id": customers[1]['_id'],
                        "similarity_score": 0.85,
                        "blocking_key": "smith",
                        "created_at": time.time()
                    }
                    similarity_collection.insert(pair)
                    print("✅ Created sample similarity pair")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to create test data: {e}")
            return False
    
    def run_setup(self) -> bool:
        """Main setup process"""
        print("=" * 80)
        print("🧪 ENTITY RESOLUTION TEST DATABASE SETUP".center(80))
        print("=" * 80)
        print()
        
        # Step 1: Check what's on port 8529
        port_status = self.check_port_8529()
        
        # Step 2: Check if ArangoDB is already running and accessible
        if self.check_arango_connection():
            print("✅ ArangoDB is already running and accessible!")
            
            # Check if it's the right database for testing
            try:
                from arango import ArangoClient
                client = ArangoClient(hosts=f"http://localhost:{self.port}")
                sys_db = client.db('_system', username=self.username, password=self.password)
                
                # Check if our test database exists
                if sys_db.has_database(self.test_database):
                    print(f"✅ Test database '{self.test_database}' found!")
                    return True
                else:
                    print("⚠️  ArangoDB is running but not configured for testing")
                    print("🔄 Will setup test database and collections...")
                    return self.setup_test_database_and_collections()
                    
            except Exception as e:
                print(f"⚠️  ArangoDB is running but not accessible with our credentials: {e}")
                print("🔄 Will restart with correct configuration...")
        
        # Step 3: Check for existing containers
        container_status = self.check_docker_containers()
        
        # Step 4: Stop conflicting containers
        if container_status.get("exists"):
            self.stop_conflicting_containers()
        
        # Step 5: Start our test container
        if not self.start_test_container():
            print("❌ Failed to start test container, trying to pull fresh image...")
            if not self.pull_arangodb_image():
                print("❌ Failed to pull ArangoDB image")
                return False
            
            # Try starting again with fresh image
            if not self.start_test_container():
                print("❌ Failed to start test container even with fresh image")
                return False
        
        # Step 6: Wait for ArangoDB to be ready
        if not self.wait_for_arangodb():
            print("❌ ArangoDB failed to start")
            return False
        
        # Step 7: Setup test database and collections
        if not self.setup_test_database_and_collections():
            print("❌ Failed to setup test database")
            return False
        
        print()
        print("🎉 TEST DATABASE SETUP COMPLETE!")
        print(f"🌐 ArangoDB Web Interface: http://localhost:{self.port}")
        print(f"👤 Username: {self.username}")
        print(f"🔑 Password: {self.password}")
        print(f"📁 Test Database: {self.test_database}")
        print()
        print("✅ Ready to run entity resolution tests!")
        
        return True


def main():
    """Main entry point"""
    setup = TestDatabaseSetup()
    
    if setup.run_setup():
        print("\n🎯 Test database is ready for testing!")
        sys.exit(0)
    else:
        print("\n❌ Test database setup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
