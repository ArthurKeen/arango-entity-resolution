#!/usr/bin/env python3
"""
Demo Database Setup Script

This script automatically handles ArangoDB setup for the entity resolution demo:
1. Checks if there's a database running on port 8529
2. Verifies if it's the correct database for this project
3. Stops conflicting databases if needed
4. Starts the correct ArangoDB container for entity resolution
5. Falls back to pulling and starting a fresh ArangoDB CE container
"""

import subprocess
import json
import time
import requests
import sys
from pathlib import Path
from typing import Optional, Dict, Any


class DemoDatabaseSetup:
    """Handles automatic ArangoDB setup for entity resolution demos"""
    
    def __init__(self):
        self.project_name = "arango-entity-resolution"
        self.container_name = "arango-entity-resolution"
        self.port = 8529
        self.base_url = f"http://localhost:{self.port}"
        self.username = "root"
        self.password = "testpassword123"
        
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
        
        # Check for our specific container
        result = self.run_command(f"docker ps -a --filter name={self.container_name} --format '{{{{.Names}}}} {{{{.Status}}}}'")
        if result and result.returncode == 0 and result.stdout.strip():
            print(f"📦 Found container '{self.container_name}': {result.stdout.strip()}")
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
    
    def stop_conflicting_containers(self):
        """Stop any containers that might be using port 8529"""
        print("🛑 Stopping conflicting containers...")
        
        # Find containers using port 8529
        result = self.run_command("docker ps --filter publish=8529 --format '{{.Names}}'")
        if result and result.returncode == 0 and result.stdout.strip():
            containers = [name.strip() for name in result.stdout.strip().split('\n') if name.strip()]
            
            for container in containers:
                if container != self.container_name:
                    print(f"🛑 Stopping conflicting container: {container}")
                    self.run_command(f"docker stop {container}", capture_output=False)
                    self.run_command(f"docker rm {container}", capture_output=False)
    
    def start_entity_resolution_container(self) -> bool:
        """Start the entity resolution ArangoDB container"""
        print(f"🚀 Starting {self.container_name} container...")
        
        # Check if container exists
        result = self.run_command(f"docker ps -a --filter name={self.container_name} --format '{{{{.Names}}}}'")
        if result and result.returncode == 0 and result.stdout.strip():
            print(f"📦 Container {self.container_name} exists, starting it...")
            result = self.run_command(f"docker start {self.container_name}", capture_output=False)
            if result and result.returncode == 0:
                print(f"✅ Container {self.container_name} started successfully")
                return True
            else:
                print(f"❌ Failed to start existing container")
                return False
        
        # Container doesn't exist, create it
        print(f"📦 Creating new {self.container_name} container...")
        
        docker_command = f"""
        docker run -d \
            --name {self.container_name} \
            -p {self.port}:8529 \
            -e ARANGO_ROOT_PASSWORD={self.password} \
            -e ARANGO_NO_AUTH=false \
            --restart unless-stopped \
            arangodb:3.12
        """
        
        result = self.run_command(docker_command, capture_output=False)
        if result and result.returncode == 0:
            print(f"✅ Container {self.container_name} created and started")
            return True
        else:
            print(f"❌ Failed to create container")
            return False
    
    def pull_arangodb_image(self) -> bool:
        """Pull the latest ArangoDB Community Edition image"""
        print("📥 Pulling ArangoDB Community Edition image...")
        
        result = self.run_command("docker pull arangodb:3.12", capture_output=False)
        if result and result.returncode == 0:
            print("✅ ArangoDB image pulled successfully")
            return True
        else:
            print("❌ Failed to pull ArangoDB image")
            return False
    
    def wait_for_arangodb(self, max_wait: int = 30) -> bool:
        """Wait for ArangoDB to be ready"""
        print(f"⏳ Waiting for ArangoDB to be ready (max {max_wait}s)...")
        
        for i in range(max_wait):
            if self.check_arango_connection():
                print("✅ ArangoDB is ready!")
                return True
            
            print(f"   Waiting... ({i+1}/{max_wait})")
            time.sleep(1)
        
        print("❌ ArangoDB failed to start within timeout")
        return False
    
    def setup_database_and_collections(self) -> bool:
        """Set up the database and collections for entity resolution"""
        print("🗄️ Setting up database and collections...")
        
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
                print(f"❌ Failed to create database {db_name}")
                return False
            
            print(f"✅ Database '{db_name}' created/verified")
            
            # Initialize data manager and create collections
            data_manager = DataManager()
            if not data_manager.connect():
                print("❌ Failed to connect to database")
                return False
            
            init_result = data_manager.initialize_test_collections()
            
            if not init_result["success"]:
                print(f"❌ Failed to create collections: {init_result.get('errors', [])}")
                return False
            
            print(f"✅ Collections created: {init_result.get('created', [])}")
            
            # Set up the entity resolution pipeline
            pipeline = EntityResolutionPipeline()
            setup_result = pipeline.setup_system()
            
            if not setup_result["success"]:
                print(f"⚠️  Pipeline setup had issues: {setup_result.get('error', 'Unknown error')}")
                # Don't fail completely, collections are created
            
            print("✅ Database and collections setup completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup database: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_setup(self) -> bool:
        """Main setup process"""
        print("=" * 80)
        print("🎯 ENTITY RESOLUTION DEMO DATABASE SETUP".center(80))
        print("=" * 80)
        print()
        
        # Step 1: Check what's on port 8529
        port_status = self.check_port_8529()
        
        # Step 2: Check if ArangoDB is already running and accessible
        if self.check_arango_connection():
            print("✅ ArangoDB is already running and accessible!")
            
            # Check if it's the right database for this project
            try:
                # Try to connect and check for our database
                from arango import ArangoClient
                client = ArangoClient(hosts=f"http://localhost:{self.port}")
                sys_db = client.db('_system', username=self.username, password=self.password)
                
                # Check if our database exists
                if sys_db.has_database('entity_resolution'):
                    print("✅ Entity resolution database found!")
                    return True
                else:
                    print("⚠️  ArangoDB is running but not configured for this project")
                    print("🔄 Will setup database and collections...")
                    return self.setup_database_and_collections()
                    
            except Exception as e:
                print(f"⚠️  ArangoDB is running but not accessible with our credentials: {e}")
                print("🔄 Will restart with correct configuration...")
        
        # Step 3: Check for existing containers
        container_status = self.check_docker_containers()
        
        # Step 4: Stop conflicting containers
        if port_status.get("occupied"):
            self.stop_conflicting_containers()
        
        # Step 5: Start our container
        if not self.start_entity_resolution_container():
            print("❌ Failed to start container, trying to pull fresh image...")
            if not self.pull_arangodb_image():
                print("❌ Failed to pull ArangoDB image")
                return False
            
            # Try starting again with fresh image
            if not self.start_entity_resolution_container():
                print("❌ Failed to start container even with fresh image")
                return False
        
        # Step 6: Wait for ArangoDB to be ready
        if not self.wait_for_arangodb():
            print("❌ ArangoDB failed to start")
            return False
        
        # Step 7: Setup database and collections
        if not self.setup_database_and_collections():
            print("❌ Failed to setup database")
            return False
        
        print()
        print("🎉 DEMO DATABASE SETUP COMPLETE!")
        print(f"🌐 ArangoDB Web Interface: http://localhost:{self.port}")
        print(f"👤 Username: {self.username}")
        print(f"🔑 Password: {self.password}")
        print()
        print("✅ Ready to run the entity resolution demo!")
        
        return True


def main():
    """Main entry point"""
    setup = DemoDatabaseSetup()
    success = setup.run_setup()
    
    if success:
        print("\n🚀 You can now run the demo with:")
        print("   python demo/launch_presentation_demo.py")
        sys.exit(0)
    else:
        print("\n❌ Database setup failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
