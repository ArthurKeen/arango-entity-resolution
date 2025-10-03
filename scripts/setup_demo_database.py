#!/usr/bin/env python3
config.database.password"
Demo Database Setup Script

This script automatically handles ArangoDB setup for the entity resolution demo:
1. Checks if there's a database running on port config.database.port
2. Verifies if it's the correct database for this project
3. Stops conflicting databases if needed
4. Starts the correct ArangoDB container for entity resolution
5. Falls back to pulling and starting a fresh ArangoDB CE container
config.database.password"

import subprocess
import json
import time
import requests
import sys
from pathlib import Path
from typing import Optional, Dict, Any


class DemoDatabaseSetup:
    config.database.password"Handles automatic ArangoDB setup for entity resolution demosconfig.database.password"
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.project_name = "arango-entity-resolution"
        self.container_name = "arango-entity-resolution"
        self.port = config.database.port
        self.base_url = f"http://config.database.host:{self.port}"
        self.username = config.database.username
        self.password = config.db.password
        
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
        
        # Check for our specific container
        result = self.run_command(f"docker ps -a --filter name={self.container_name} --format '{{{{.Names}}}} {{{{.Status}}}}'")
        if result and result.returncode == 0 and result.stdout.strip():
            self.logger.info(f"📦 Found container '{self.container_name}': {result.stdout.strip()}")
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
    
    def stop_conflicting_containers(self):
        config.database.password"Stop any containers that might be using port config.database.portconfig.database.password"
        self.logger.info("🛑 Stopping conflicting containers...")
        
        # Find containers using port config.database.port
        result = self.run_command("docker ps --filter publish=config.database.port --format '{{.Names}}'")
        if result and result.returncode == 0 and result.stdout.strip():
            containers = [name.strip() for name in result.stdout.strip().split('\n') if name.strip()]
            
            for container in containers:
                if container != self.container_name:
                    self.logger.info(f"🛑 Stopping conflicting container: {container}")
                    self.run_command(f"docker stop {container}", capture_output=False)
                    self.run_command(f"docker rm {container}", capture_output=False)
    
    def start_entity_resolution_container(self) -> bool:
        config.database.password"Start the entity resolution ArangoDB containerconfig.database.password"
        self.logger.info(f"🚀 Starting {self.container_name} container...")
        
        # Check if container exists
        result = self.run_command(f"docker ps -a --filter name={self.container_name} --format '{{{{.Names}}}}'")
        if result and result.returncode == 0 and result.stdout.strip():
            self.logger.info(f"📦 Container {self.container_name} exists, starting it...")
            result = self.run_command(f"docker start {self.container_name}", capture_output=False)
            if result and result.returncode == 0:
                self.logger.success(r"Container {self.container_name} started successfully")
                return True
            else:
                self.logger.error(r"Failed to start existing container")
                return False
        
        # Container doesn't exist, create it
        self.logger.info(f"📦 Creating new {self.container_name} container...")
        
        docker_command = fconfig.database.password"
        docker run -d \
            --name {self.container_name} \
            -p {self.port}:config.database.port \
            -e ARANGO_ROOT_PASSWORD={self.password} \
            -e ARANGO_NO_AUTH=false \
            --restart unless-stopped \
            arangodb:3.12
        config.database.password"
        
        result = self.run_command(docker_command, capture_output=False)
        if result and result.returncode == 0:
            self.logger.success(r"Container {self.container_name} created and started")
            return True
        else:
            self.logger.error(r"Failed to create container")
            return False
    
    def pull_arangodb_image(self) -> bool:
        config.database.password"Pull the latest ArangoDB Community Edition imageconfig.database.password"
        self.logger.info("📥 Pulling ArangoDB Community Edition image...")
        
        result = self.run_command("docker pull arangodb:3.12", capture_output=False)
        if result and result.returncode == 0:
            self.logger.success(r"ArangoDB image pulled successfully")
            return True
        else:
            self.logger.error(r"Failed to pull ArangoDB image")
            return False
    
    def wait_for_arangodb(self, max_wait: int = 30) -> bool:
        config.database.password"Wait for ArangoDB to be readyconfig.database.password"
        self.logger.info(f"⏳ Waiting for ArangoDB to be ready (max {max_wait}s)...")
        
        for i in range(max_wait):
            if self.check_arango_connection():
                self.logger.success(r"ArangoDB is ready!")
                return True
            
            self.logger.info(f"   Waiting... ({i+1}/{max_wait})")
            time.sleep(1)
        
        self.logger.error(r"ArangoDB failed to start within timeout")
        return False
    
    def setup_database_and_collections(self) -> bool:
        config.database.password"Set up the database and collections for entity resolutionconfig.database.password"
        self.logger.info("🗄️ Setting up database and collections...")
        
        try:
            # Import the database setup
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from src.entity_resolution.utils.database import DatabaseManager
            from src.entity_resolution.data.data_manager import DataManager
            from src.entity_resolution.core.entity_resolver import EntityResolutionPipeline
            
            # Initialize database manager
            db_manager = DatabaseManager()
            
            # Create the entity resolution database
            db_name = "entity_resolution"
            if not db_manager.create_database_if_not_exists(db_name):
                self.logger.error(r"Failed to create database {db_name}")
                return False
            
            self.logger.success(r"Database '{db_name}' created/verified")
            
            # Initialize data manager and create collections
            data_manager = DataManager()
            if not data_manager.connect():
                self.logger.error(r"Failed to connect to database")
                return False
            
            init_result = data_manager.initialize_test_collections()
            
            if not init_result["success"]:
                self.logger.error(r"Failed to create collections: {init_result.get('errors', [])}")
                return False
            
            self.logger.success(r"Collections created: {init_result.get('created', [])}")
            
            # Set up the entity resolution pipeline
            pipeline = EntityResolutionPipeline()
            setup_result = pipeline.setup_system()
            
            if not setup_result["success"]:
                self.logger.warning(r"Pipeline setup had issues: {setup_result.get('error', 'Unknown error')}")
                # Don't fail completely, collections are created
            
            self.logger.success(r"Database and collections setup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(r"Failed to setup database: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_setup(self) -> bool:
        config.database.password"Main setup processconfig.database.password"
        self.logger.info("=" * 80)
        self.logger.info("🎯 ENTITY RESOLUTION DEMO DATABASE SETUP".center(80))
        self.logger.info("=" * 80)
        print()
        
        # Step 1: Check what's on port config.database.port
        port_status = self.check_port_config.database.port()
        
        # Step 2: Check if ArangoDB is already running and accessible
        if self.check_arango_connection():
            self.logger.success(r"ArangoDB is already running and accessible!")
            
            # Check if it's the right database for this project
            try:
                # Try to connect and check for our database
                from arango import ArangoClient
from entity_resolution.utils.logging import get_logger
from entity_resolution.utils.enhanced_config import get_config
                client = ArangoClient(hosts=f"http://config.database.host:{self.port}")
                sys_db = client.db('_system', username=self.username, password=self.password)
                
                # Check if our database exists
                if sys_db.has_database('entity_resolution'):
                    self.logger.success(r"Entity resolution database found!")
                    return True
                else:
                    self.logger.warning(r"ArangoDB is running but not configured for this project")
                    self.logger.info("🔄 Will setup database and collections...")
                    return self.setup_database_and_collections()
                    
            except Exception as e:
                self.logger.warning(r"ArangoDB is running but not accessible with our credentials: {e}")
                self.logger.info("🔄 Will restart with correct configuration...")
        
        # Step 3: Check for existing containers
        container_status = self.check_docker_containers()
        
        # Step 4: Stop conflicting containers
        if port_status.get("occupied"):
            self.stop_conflicting_containers()
        
        # Step 5: Start our container
        if not self.start_entity_resolution_container():
            self.logger.error(r"Failed to start container, trying to pull fresh image...")
            if not self.pull_arangodb_image():
                self.logger.error(r"Failed to pull ArangoDB image")
                return False
            
            # Try starting again with fresh image
            if not self.start_entity_resolution_container():
                self.logger.error(r"Failed to start container even with fresh image")
                return False
        
        # Step 6: Wait for ArangoDB to be ready
        if not self.wait_for_arangodb():
            self.logger.error(r"ArangoDB failed to start")
            return False
        
        # Step 7: Setup database and collections
        if not self.setup_database_and_collections():
            self.logger.error(r"Failed to setup database")
            return False
        
        print()
        self.logger.info("🎉 DEMO DATABASE SETUP COMPLETE!")
        self.logger.info(f"🌐 ArangoDB Web Interface: http://config.database.host:{self.port}")
        self.logger.info(f"👤 Username: {self.username}")
        self.logger.info(f"🔑 Password: {self.password}")
        print()
        self.logger.success(r"Ready to run the entity resolution demo!")
        
        return True


def main():
    config.database.password"Main entry pointconfig.database.password"
    setup = DemoDatabaseSetup()
    success = setup.run_setup()
    
    if success:
        self.logger.info("\n🚀 You can now run the demo with:")
        self.logger.info("   python demo/launch_presentation_demo.py")
        sys.exit(0)
    else:
        self.logger.info("\n❌ Database setup failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
