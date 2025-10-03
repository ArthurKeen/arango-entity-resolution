#!/usr/bin/env python3
config.database.password"
Test Database Setup Script

This script provides resilient database management for the test system, similar to
the demo database setup but optimized for testing scenarios:

1. Checks if there's a database running on port config.database.port
2. Verifies if it's the correct database for testing
3. Stops conflicting databases if needed
4. Starts the correct ArangoDB container for testing
5. Falls back to pulling and starting a fresh ArangoDB CE container
6. Creates test database and collections
7. Provides test data if needed
config.database.password"

import subprocess
import json
import time
import requests
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, List


class TestDatabaseSetup:
    config.database.password"Handles automatic ArangoDB setup for entity resolution testingconfig.database.password"
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.project_name = "arango-entity-resolution-test"
        self.container_name = "arango-entity-resolution-test"
        self.port = config.database.port
        self.base_url = f"http://config.database.host:{self.port}"
        self.username = config.database.username
        self.password = config.db.password
        self.test_database = "entity_resolution_test"
        
    def run_command(self, command: str, capture_output: bool = True) -> subprocess.CompletedProcess:
        config.database.password"Run a shell command and return the resultconfig.database.password"
        try:
            if capture_output:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
            else:
                result = subprocess.run(command, shell=True)
            return result
        except Exception as e:
            self.logger.error(r"Error running command '{command}': {e}")
            return None
    
    def check_port_config.database.port(self) -> Optional[Dict[str, Any]]:
        config.database.password"Check what's running on port config.database.portconfig.database.password"
        self.logger.debug(r"Checking what's running on port config.database.port...")
        
        # Check if anything is listening on port config.database.port
        result = self.run_command(f"lsof -i :{self.port}")
        if result and result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # More than just the header
                self.logger.info(f"📊 Found processes on port {self.port}:")
                for line in lines[1:]:  # Skip header
                    self.logger.info(f"   {line}")
                return {"occupied": True, "processes": lines[1:]}
        
        self.logger.success(r"Port {self.port} is available")
        return {"occupied": False, "processes": []}
    
    def check_arango_connection(self) -> bool:
        config.database.password"Check if we can connect to ArangoDB on port config.database.portconfig.database.password"
        self.logger.info("🔗 Testing ArangoDB connection...")
        
        try:
            # Test basic connectivity
            response = requests.get(f"{self.base_url}/_api/version", timeout=5)
            if response.status_code == 200:
                version_info = response.json()
                self.logger.success(r"ArangoDB is running - Version: {version_info.get('version', 'Unknown')}")
                return True
        except requests.exceptions.RequestException as e:
            self.logger.error(r"Cannot connect to ArangoDB: {e}")
            return False
        
        return False
    
    def check_docker_containers(self) -> Dict[str, Any]:
        config.database.password"Check for existing Docker containersconfig.database.password"
        self.logger.info("🐳 Checking Docker containers...")
        
        # Check for our specific test container
        result = self.run_command(f"docker ps -a --filter name={self.container_name} --format '{{{{.Names}}}} {{{{.Status}}}}'")
        if result and result.returncode == 0 and result.stdout.strip():
            self.logger.info(f"📦 Found test container '{self.container_name}': {result.stdout.strip()}")
            return {"exists": True, "status": result.stdout.strip()}
        
        # Check for any ArangoDB containers
        result = self.run_command("docker ps -a --filter ancestor=arangodb --format '{{.Names}} {{.Status}}'")
        if result and result.returncode == 0 and result.stdout.strip():
            self.logger.info(f"📦 Found ArangoDB containers:")
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    self.logger.info(f"   {line}")
            return {"exists": True, "containers": result.stdout.strip().split('\n')}
        
        self.logger.success(r"No existing ArangoDB containers found")
        return {"exists": False}
    
    def stop_conflicting_containers(self) -> bool:
        config.database.password"Stop any conflicting ArangoDB containersconfig.database.password"
        self.logger.info("🛑 Stopping conflicting containers...")
        
        # Stop our test container if it exists
        result = self.run_command(f"docker stop {self.container_name}")
        if result and result.returncode == 0:
            self.logger.success(r"Stopped test container: {self.container_name}")
        
        # Stop any other ArangoDB containers that might conflict
        result = self.run_command("docker ps -q --filter ancestor=arangodb")
        if result and result.returncode == 0 and result.stdout.strip():
            container_ids = result.stdout.strip().split('\n')
            for container_id in container_ids:
                if container_id.strip():
                    self.logger.info(f"🛑 Stopping conflicting container: {container_id}")
                    self.run_command(f"docker stop {container_id}")
        
        return True
    
    def start_test_container(self) -> bool:
        config.database.password"Start the test ArangoDB containerconfig.database.password"
        self.logger.info(f"🚀 Starting test container: {self.container_name}")
        
        # Check if container already exists and is running
        result = self.run_command(f"docker ps --filter name={self.container_name} --format '{{{{.Names}}}}'")
        if result and result.returncode == 0 and self.container_name in result.stdout:
            self.logger.success(r"Test container is already running: {self.container_name}")
            return True
        
        # Start existing container if it exists
        result = self.run_command(f"docker start {self.container_name}")
        if result and result.returncode == 0:
            self.logger.success(r"Started existing test container: {self.container_name}")
            return True
        
        # Create new container
        docker_cmd = fconfig.database.password"
        docker run -d \
            --name {self.container_name} \
            -p {self.port}:config.database.port \
            -e ARANGO_ROOT_PASSWORD={self.password} \
            arangodb/arangodb:latest
        config.database.password"
        
        result = self.run_command(docker_cmd)
        if result and result.returncode == 0:
            self.logger.success(r"Created and started test container: {self.container_name}")
            return True
        
        self.logger.error(r"Failed to start test container")
        return False
    
    def pull_arangodb_image(self) -> bool:
        config.database.password"Pull the latest ArangoDB imageconfig.database.password"
        self.logger.info("📥 Pulling latest ArangoDB image...")
        
        result = self.run_command("docker pull arangodb/arangodb:latest")
        if result and result.returncode == 0:
            self.logger.success(r"Successfully pulled ArangoDB image")
            return True
        
        self.logger.error(r"Failed to pull ArangoDB image")
        return False
    
    def wait_for_arangodb(self, max_wait: int = 30) -> bool:
        config.database.password"Wait for ArangoDB to be readyconfig.database.password"
        self.logger.info("⏳ Waiting for ArangoDB to be ready...")
        
        for i in range(max_wait):
            if self.check_arango_connection():
                self.logger.success(r"ArangoDB is ready!")
                return True
            
            self.logger.info(f"   Waiting... ({i+1}/{max_wait})")
            time.sleep(1)
        
        self.logger.error(r"ArangoDB failed to start within timeout")
        return False
    
    def setup_test_database_and_collections(self) -> bool:
        config.database.password"Setup test database and collectionsconfig.database.password"
        self.logger.info("🗄️  Setting up test database and collections...")
        
        try:
            from arango import ArangoClient
            
            # Connect to system database
            client = ArangoClient(hosts=f"http://config.database.host:{self.port}")
            sys_db = client.db('_system', username=self.username, password=self.password)
            
            # Create test database if it doesn't exist
            if not sys_db.has_database(self.test_database):
                self.logger.info(f"📁 Creating test database: {self.test_database}")
                sys_db.create_database(self.test_database)
            else:
                self.logger.success(r"Test database already exists: {self.test_database}")
            
            # Connect to test database
            test_db = client.db(self.test_database, username=self.username, password=self.password)
            
            # Create collections if they don't exist
            collections = ['customers', 'similarity_pairs', 'clusters', 'golden_records']
            
            for collection_name in collections:
                if not test_db.has_collection(collection_name):
                    self.logger.info(f"📁 Creating collection: {collection_name}")
                    test_db.create_collection(collection_name)
                else:
                    self.logger.success(r"Collection already exists: {collection_name}")
            
            # Create test data if collections are empty
            self.create_test_data_if_needed(test_db)
            
            self.logger.success(r"Test database and collections setup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(r"Failed to setup test database: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_test_data_if_needed(self, db) -> bool:
        config.database.password"Create test data if collections are emptyconfig.database.password"
        self.logger.info("📊 Creating test data if needed...")
        
        try:
            # Check if customers collection has data
            customers_collection = db.collection('customers')
            if customers_collection.count() == 0:
                self.logger.info("📝 Creating sample customer data...")
                
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
                
                self.logger.success(r"Created {len(sample_customers)} sample customers")
            
            # Check if similarity_pairs collection has data
            similarity_collection = db.collection('similarity_pairs')
            if similarity_collection.count() == 0:
                self.logger.info("📝 Creating sample similarity pairs...")
                
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
                    self.logger.success(r"Created sample similarity pair")
            
            return True
            
        except Exception as e:
            self.logger.error(r"Failed to create test data: {e}")
            return False
    
    def run_setup(self) -> bool:
        config.database.password"Main setup processconfig.database.password"
        self.logger.info("=" * 80)
        self.logger.info("🧪 ENTITY RESOLUTION TEST DATABASE SETUP".center(80))
        self.logger.info("=" * 80)
        print()
        
        # Step 1: Check what's on port config.database.port
        port_status = self.check_port_config.database.port()
        
        # Step 2: Check if ArangoDB is already running and accessible
        if self.check_arango_connection():
            self.logger.success(r"ArangoDB is already running and accessible!")
            
            # Check if it's the right database for testing
            try:
                from arango import ArangoClient
from entity_resolution.utils.logging import get_logger
from entity_resolution.utils.enhanced_config import get_config
                client = ArangoClient(hosts=f"http://config.database.host:{self.port}")
                sys_db = client.db('_system', username=self.username, password=self.password)
                
                # Check if our test database exists
                if sys_db.has_database(self.test_database):
                    self.logger.success(r"Test database '{self.test_database}' found!")
                    return True
                else:
                    self.logger.warning(r"ArangoDB is running but not configured for testing")
                    self.logger.info("🔄 Will setup test database and collections...")
                    return self.setup_test_database_and_collections()
                    
            except Exception as e:
                self.logger.warning(r"ArangoDB is running but not accessible with our credentials: {e}")
                self.logger.info("🔄 Will restart with correct configuration...")
        
        # Step 3: Check for existing containers
        container_status = self.check_docker_containers()
        
        # Step 4: Stop conflicting containers
        if container_status.get("exists"):
            self.stop_conflicting_containers()
        
        # Step 5: Start our test container
        if not self.start_test_container():
            self.logger.error(r"Failed to start test container, trying to pull fresh image...")
            if not self.pull_arangodb_image():
                self.logger.error(r"Failed to pull ArangoDB image")
                return False
            
            # Try starting again with fresh image
            if not self.start_test_container():
                self.logger.error(r"Failed to start test container even with fresh image")
                return False
        
        # Step 6: Wait for ArangoDB to be ready
        if not self.wait_for_arangodb():
            self.logger.error(r"ArangoDB failed to start")
            return False
        
        # Step 7: Setup test database and collections
        if not self.setup_test_database_and_collections():
            self.logger.error(r"Failed to setup test database")
            return False
        
        print()
        self.logger.info("🎉 TEST DATABASE SETUP COMPLETE!")
        self.logger.info(f"🌐 ArangoDB Web Interface: http://config.database.host:{self.port}")
        self.logger.info(f"👤 Username: {self.username}")
        self.logger.info(f"🔑 Password: {self.password}")
        self.logger.info(f"📁 Test Database: {self.test_database}")
        print()
        self.logger.success(r"Ready to run entity resolution tests!")
        
        return True


def main():
    config.database.password"Main entry pointconfig.database.password"
    setup = TestDatabaseSetup()
    
    if setup.run_setup():
        self.logger.info("\n🎯 Test database is ready for testing!")
        sys.exit(0)
    else:
        self.logger.info("\n❌ Test database setup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
