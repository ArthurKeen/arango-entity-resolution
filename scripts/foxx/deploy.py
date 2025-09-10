#!/usr/bin/env python3
"""
Foxx Service Deployment Script

Deploys and manages the Entity Resolution Foxx service in ArangoDB.
Handles service installation, configuration, and health checks.
"""

import os
import sys
import json
import argparse
import time
import zipfile
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

# Add the scripts directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.arango_base import ArangoBaseConnection, add_common_args


class FoxxServiceDeployer(ArangoBaseConnection):
    """Deploys and manages Foxx services in ArangoDB"""
    
    def __init__(self, host: str = "localhost", port: int = 8529, 
                 username: str = "root", password: Optional[str] = None,
                 database: str = "_system"):
        super().__init__(host, port, username, password)
        self.database_name = database
        self.db = None
        
    def connect(self) -> bool:
        """Establish connection to database"""
        try:
            self.db = self.client.db(self.database_name, username=self.username, password=self.password)
            # Test connection
            self.db.properties()
            self.print_success(f"Connected to database: {self.database_name}")
            return True
        except Exception as e:
            self.print_error(f"Failed to connect to database {self.database_name}: {e}")
            return False
    
    def create_service_zip(self, service_path: str) -> str:
        """Create a ZIP file of the Foxx service"""
        service_dir = Path(service_path)
        if not service_dir.exists():
            raise FileNotFoundError(f"Service directory not found: {service_path}")
        
        # Create temporary ZIP file
        temp_file = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
        temp_file.close()
        
        with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in service_dir.rglob('*'):
                if file_path.is_file():
                    # Skip hidden files and directories
                    if any(part.startswith('.') for part in file_path.parts):
                        continue
                    
                    # Add file to ZIP with relative path
                    arcname = file_path.relative_to(service_dir)
                    zipf.write(file_path, arcname)
                    self.print_info(f"Added to ZIP: {arcname}")
        
        self.print_success(f"Created service ZIP: {temp_file.name}")
        return temp_file.name
    
    def install_service(self, service_path: str, mount_path: str, 
                       configuration: Dict[str, Any] = None) -> bool:
        """Install Foxx service from local directory"""
        try:
            # Create service ZIP
            zip_path = self.create_service_zip(service_path)
            
            try:
                # Read ZIP file
                with open(zip_path, 'rb') as zip_file:
                    zip_data = zip_file.read()
                
                # Install service using ArangoDB Python driver
                service_info = self.db.install_service(
                    mount_point=mount_path,
                    source=zip_data,
                    configuration=configuration or {}
                )
                
                self.print_success(f"Successfully installed service at {mount_path}")
                self.print_info(f"Service info: {json.dumps(service_info, indent=2)}")
                return True
                
            finally:
                # Clean up temporary ZIP file
                os.unlink(zip_path)
                
        except Exception as e:
            self.print_error(f"Failed to install service: {e}")
            return False
    
    def update_service(self, mount_path: str, service_path: str,
                      configuration: Dict[str, Any] = None) -> bool:
        """Update existing Foxx service"""
        try:
            # Create service ZIP
            zip_path = self.create_service_zip(service_path)
            
            try:
                # Read ZIP file
                with open(zip_path, 'rb') as zip_file:
                    zip_data = zip_file.read()
                
                # Update service
                service_info = self.db.update_service(
                    mount_point=mount_path,
                    source=zip_data,
                    configuration=configuration or {}
                )
                
                self.print_success(f"Successfully updated service at {mount_path}")
                self.print_info(f"Service info: {json.dumps(service_info, indent=2)}")
                return True
                
            finally:
                # Clean up temporary ZIP file
                os.unlink(zip_path)
                
        except Exception as e:
            self.print_error(f"Failed to update service: {e}")
            return False
    
    def uninstall_service(self, mount_path: str) -> bool:
        """Uninstall Foxx service"""
        try:
            self.db.uninstall_service(mount_point=mount_path)
            self.print_success(f"Successfully uninstalled service from {mount_path}")
            return True
        except Exception as e:
            self.print_error(f"Failed to uninstall service: {e}")
            return False
    
    def list_services(self) -> bool:
        """List all installed Foxx services"""
        try:
            services = self.db.services()
            
            if not services:
                self.print_info("No Foxx services installed")
                return True
            
            self.print_success("Installed Foxx services:")
            for mount_path, service_info in services.items():
                self.print_info(f"  {mount_path}:")
                self.print_info(f"    Name: {service_info.get('name', 'Unknown')}")
                self.print_info(f"    Version: {service_info.get('version', 'Unknown')}")
                self.print_info(f"    Status: {service_info.get('status', 'Unknown')}")
                self.print_info(f"    Development: {service_info.get('development', False)}")
            
            return True
        except Exception as e:
            self.print_error(f"Failed to list services: {e}")
            return False
    
    def get_service_info(self, mount_path: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific service"""
        try:
            service_info = self.db.service(mount_point=mount_path)
            self.print_success(f"Service info for {mount_path}:")
            self.print_info(json.dumps(service_info, indent=2))
            return service_info
        except Exception as e:
            self.print_error(f"Failed to get service info: {e}")
            return None
    
    def test_service_health(self, mount_path: str) -> bool:
        """Test service health by calling health endpoint"""
        try:
            import requests
            
            url = f"http://{self.host}:{self.port}/_db/{self.database_name}{mount_path}/health"
            
            self.print_info(f"Testing service health: {url}")
            
            response = requests.get(url, auth=(self.username, self.password), timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                self.print_success("Service health check passed")
                self.print_info(f"Health data: {json.dumps(health_data, indent=2)}")
                return True
            else:
                self.print_error(f"Health check failed with status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.print_error(f"Failed to test service health: {e}")
            return False
    
    def configure_service(self, mount_path: str, configuration: Dict[str, Any]) -> bool:
        """Update service configuration"""
        try:
            self.db.update_service_configuration(mount_point=mount_path, configuration=configuration)
            self.print_success(f"Successfully updated configuration for {mount_path}")
            self.print_info(f"New configuration: {json.dumps(configuration, indent=2)}")
            return True
        except Exception as e:
            self.print_error(f"Failed to update service configuration: {e}")
            return False


def get_default_configuration() -> Dict[str, Any]:
    """Get default configuration for entity resolution service"""
    return {
        "defaultSimilarityThreshold": 0.8,
        "maxCandidatesPerRecord": 100,
        "ngramLength": 3,
        "enablePhoneticMatching": True,
        "logLevel": "info"
    }


def main():
    parser = argparse.ArgumentParser(description='Deploy and manage Entity Resolution Foxx service')
    parser.add_argument('action', choices=[
        'install', 'update', 'uninstall', 'list', 'info', 'health', 'configure'
    ], help='Action to perform')
    
    parser.add_argument('--mount-path', '-m', default='/entity-resolution',
                       help='Service mount path (default: /entity-resolution)')
    parser.add_argument('--service-path', '-s', 
                       default='foxx-services/entity-resolution',
                       help='Path to service directory (default: foxx-services/entity-resolution)')
    parser.add_argument('--config-file', '-c',
                       help='JSON configuration file')
    parser.add_argument('--database', '-d', default='_system',
                       help='Database name (default: _system)')
    
    # Add common connection arguments
    add_common_args(parser)
    
    args = parser.parse_args()
    
    # Load configuration if provided
    configuration = get_default_configuration()
    if args.config_file:
        try:
            with open(args.config_file, 'r') as f:
                file_config = json.load(f)
                configuration.update(file_config)
            print(f"✓ Loaded configuration from {args.config_file}")
        except Exception as e:
            print(f"✗ Failed to load configuration file: {e}")
            return 1
    
    # Create deployer and connect
    deployer = FoxxServiceDeployer(args.host, args.port, args.username, args.password, args.database)
    if not deployer.connect():
        return 1
    
    # Execute requested action
    success = False
    
    if args.action == 'install':
        success = deployer.install_service(args.service_path, args.mount_path, configuration)
        if success:
            # Test health after installation
            time.sleep(2)  # Give service time to start
            deployer.test_service_health(args.mount_path)
    
    elif args.action == 'update':
        success = deployer.update_service(args.mount_path, args.service_path, configuration)
        if success:
            # Test health after update
            time.sleep(2)
            deployer.test_service_health(args.mount_path)
    
    elif args.action == 'uninstall':
        success = deployer.uninstall_service(args.mount_path)
    
    elif args.action == 'list':
        success = deployer.list_services()
    
    elif args.action == 'info':
        service_info = deployer.get_service_info(args.mount_path)
        success = service_info is not None
    
    elif args.action == 'health':
        success = deployer.test_service_health(args.mount_path)
    
    elif args.action == 'configure':
        success = deployer.configure_service(args.mount_path, configuration)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
