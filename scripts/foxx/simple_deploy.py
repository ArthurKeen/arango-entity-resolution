#!/usr/bin/env python3
"""
Simple Foxx Service Deployment Script

Uses ArangoDB's HTTP API directly to deploy Foxx services.
"""

import os
import sys
import json
import argparse
import zipfile
import tempfile
import urllib.request
import urllib.parse
import base64
from pathlib import Path
from typing import Dict, Any, Optional

# Add the scripts directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.arango_base import ArangoBaseConnection, add_common_args


class SimpleFoxxDeployer(ArangoBaseConnection):
    """Simple Foxx deployer using HTTP API"""
    
    def __init__(self, host: str = "localhost", port: int = 8529, 
                 username: str = "root", password: Optional[str] = None,
                 database: str = "_system"):
        super().__init__(host, port, username, password)
        self.database_name = database
        self.base_url = f"http://{self.host}:{self.port}/_db/{self.database_name}"
        
    def _make_request(self, method: str, url: str, data: bytes = None, 
                     headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Make HTTP request to ArangoDB"""
        # Create authorization header
        auth_string = f"{self.username}:{self.password}"
        auth_bytes = auth_string.encode('ascii')
        auth_header = base64.b64encode(auth_bytes).decode('ascii')
        
        # Default headers
        req_headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/json'
        }
        if headers:
            req_headers.update(headers)
        
        # Create request
        request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        
        try:
            with urllib.request.urlopen(request) as response:
                response_data = response.read()
                if response_data:
                    return json.loads(response_data.decode('utf-8'))
                return {}
        except urllib.error.HTTPError as e:
            error_data = e.read().decode('utf-8')
            try:
                error_json = json.loads(error_data)
                raise Exception(f"HTTP {e.code}: {error_json.get('errorMessage', error_data)}")
            except json.JSONDecodeError:
                raise Exception(f"HTTP {e.code}: {error_data}")
    
    def create_service_zip(self, service_path: str) -> bytes:
        """Create ZIP bytes of the Foxx service"""
        service_dir = Path(service_path)
        if not service_dir.exists():
            raise FileNotFoundError(f"Service directory not found: {service_path}")
        
        # Create in-memory ZIP
        from io import BytesIO
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in service_dir.rglob('*'):
                if file_path.is_file():
                    # Skip hidden files and directories
                    if any(part.startswith('.') for part in file_path.parts):
                        continue
                    
                    # Add file to ZIP with relative path
                    arcname = file_path.relative_to(service_dir)
                    zipf.write(file_path, arcname)
                    self.print_info(f"Added to ZIP: {arcname}")
        
        zip_bytes = zip_buffer.getvalue()
        self.print_success(f"Created service ZIP ({len(zip_bytes)} bytes)")
        return zip_bytes
    
    def install_service(self, service_path: str, mount_path: str, 
                       configuration: Dict[str, Any] = None) -> bool:
        """Install Foxx service"""
        try:
            # Create service ZIP
            zip_data = self.create_service_zip(service_path)
            
            # Prepare URL and headers
            url = f"{self.base_url}/_api/foxx/service"
            params = {'mount': mount_path}
            if configuration:
                params['configuration'] = json.dumps(configuration)
            
            query_string = urllib.parse.urlencode(params)
            full_url = f"{url}?{query_string}"
            
            headers = {
                'Authorization': f'Basic {base64.b64encode(f"{self.username}:{self.password}".encode()).decode()}',
                'Content-Type': 'application/zip'
            }
            
            # Make request
            request = urllib.request.Request(full_url, data=zip_data, headers=headers, method='POST')
            
            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            self.print_success(f"Successfully installed service at {mount_path}")
            self.print_info(f"Service info: {json.dumps(result, indent=2)}")
            return True
            
        except Exception as e:
            self.print_error(f"Failed to install service: {e}")
            return False
    
    def list_services(self) -> bool:
        """List installed Foxx services"""
        try:
            url = f"{self.base_url}/_api/foxx/service"
            result = self._make_request('GET', url)
            
            if not result:
                self.print_info("No Foxx services installed")
                return True
            
            self.print_success("Installed Foxx services:")
            for service in result:
                mount = service.get('mount', 'Unknown')
                name = service.get('name', 'Unknown')
                version = service.get('version', 'Unknown')
                development = service.get('development', False)
                
                self.print_info(f"  {mount}:")
                self.print_info(f"    Name: {name}")
                self.print_info(f"    Version: {version}")
                self.print_info(f"    Development: {development}")
            
            return True
        except Exception as e:
            self.print_error(f"Failed to list services: {e}")
            return False
    
    def uninstall_service(self, mount_path: str) -> bool:
        """Uninstall Foxx service"""
        try:
            url = f"{self.base_url}/_api/foxx/service"
            params = {'mount': mount_path}
            query_string = urllib.parse.urlencode(params)
            full_url = f"{url}?{query_string}"
            
            self._make_request('DELETE', full_url)
            self.print_success(f"Successfully uninstalled service from {mount_path}")
            return True
        except Exception as e:
            self.print_error(f"Failed to uninstall service: {e}")
            return False
    
    def test_service_health(self, mount_path: str) -> bool:
        """Test service health"""
        try:
            url = f"{self.base_url}{mount_path}/health"
            result = self._make_request('GET', url)
            
            self.print_success("Service health check passed")
            self.print_info(f"Health data: {json.dumps(result, indent=2)}")
            return True
        except Exception as e:
            self.print_error(f"Health check failed: {e}")
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
    parser = argparse.ArgumentParser(description='Deploy Entity Resolution Foxx service')
    parser.add_argument('action', choices=['install', 'uninstall', 'list', 'health'], 
                       help='Action to perform')
    
    parser.add_argument('--mount-path', '-m', default='/entity-resolution',
                       help='Service mount path (default: /entity-resolution)')
    parser.add_argument('--service-path', '-s', 
                       default='foxx-services/entity-resolution',
                       help='Path to service directory')
    parser.add_argument('--database', '-d', default='_system',
                       help='Database name (default: _system)')
    
    # Add common connection arguments
    add_common_args(parser)
    
    args = parser.parse_args()
    
    # Create deployer
    deployer = SimpleFoxxDeployer(args.host, args.port, args.username, args.password, args.database)
    
    # Execute action
    success = False
    
    if args.action == 'install':
        configuration = get_default_configuration()
        success = deployer.install_service(args.service_path, args.mount_path, configuration)
        if success:
            # Test health
            import time
            time.sleep(2)
            deployer.test_service_health(args.mount_path)
    
    elif args.action == 'uninstall':
        success = deployer.uninstall_service(args.mount_path)
    
    elif args.action == 'list':
        success = deployer.list_services()
    
    elif args.action == 'health':
        success = deployer.test_service_health(args.mount_path)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
