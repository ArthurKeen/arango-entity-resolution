#!/usr/bin/env python3
"""
Foxx Service Deployment using ArangoDB Container Tools

Uses arangosh within the Docker container to deploy Foxx services.
"""

import os
import sys
import json
import argparse
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional

# Add the scripts directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.arango_base import ArangoBaseConnection, add_common_args


class ContainerFoxxDeployer(ArangoBaseConnection):
    """Deploy Foxx services using container tools"""
    
    def __init__(self, host: str = "localhost", port: int = 8529, 
                 username: str = "root", password: Optional[str] = None,
                 database: str = "_system", container_name: str = "arango-entity-resolution"):
        super().__init__(host, port, username, password)
        self.database_name = database
        self.container_name = container_name
        
    def create_service_zip(self, service_path: str) -> str:
        """Create a ZIP file of the Foxx service and copy to container"""
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
        
        # Copy ZIP to container
        container_zip_path = "/tmp/entity-resolution-service.zip"
        try:
            result = subprocess.run([
                'docker', 'cp', temp_file.name, f"{self.container_name}:{container_zip_path}"
            ], capture_output=True, text=True, check=True)
            
            self.print_success(f"Copied service ZIP to container: {container_zip_path}")
            return container_zip_path
            
        finally:
            # Clean up local temp file
            os.unlink(temp_file.name)
    
    def run_arangosh_command(self, js_command: str) -> tuple[bool, str]:
        """Execute JavaScript command in arangosh within the container"""
        try:
            # Escape the JavaScript command for shell
            escaped_command = js_command.replace('"', '\\"').replace('`', '\\`')
            
            cmd = [
                'docker', 'exec', self.container_name,
                'arangosh',
                '--server.endpoint', f'tcp://127.0.0.1:8529',
                '--server.database', self.database_name,
                '--server.username', self.username,
                '--server.password', self.password,
                '--javascript.execute-string', escaped_command
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def install_service(self, service_path: str, mount_path: str, 
                       configuration: Dict[str, Any] = None) -> bool:
        """Install Foxx service using arangosh"""
        try:
            # Create and copy service ZIP to container
            container_zip_path = self.create_service_zip(service_path)
            
            # Prepare configuration JSON
            config_json = json.dumps(configuration or {})
            
            # JavaScript command to install the service
            js_command = f'''
            var fs = require('fs');
            var db = require('@arangodb').db;
            
            // Read the ZIP file
            var zipData = fs.read('{container_zip_path}', true);
            
            // Install the service
            var result = require('@arangodb/foxx/manager').install(
                zipData,
                '{mount_path}',
                {config_json}
            );
            
            print(JSON.stringify(result, null, 2));
            '''
            
            success, output = self.run_arangosh_command(js_command)
            
            if success:
                self.print_success(f"Successfully installed service at {mount_path}")
                self.print_info(f"Output: {output}")
                return True
            else:
                self.print_error(f"Failed to install service: {output}")
                return False
                
        except Exception as e:
            self.print_error(f"Installation failed: {e}")
            return False
    
    def list_services(self) -> bool:
        """List installed Foxx services"""
        try:
            js_command = '''
            var foxxManager = require('@arangodb/foxx/manager');
            var services = foxxManager.list();
            print(JSON.stringify(services, null, 2));
            '''
            
            success, output = self.run_arangosh_command(js_command)
            
            if success:
                try:
                    services = json.loads(output.strip())
                    if not services:
                        self.print_info("No Foxx services installed")
                    else:
                        self.print_success("Installed Foxx services:")
                        for mount_path, service_info in services.items():
                            self.print_info(f"  {mount_path}:")
                            self.print_info(f"    Name: {service_info.get('name', 'Unknown')}")
                            self.print_info(f"    Version: {service_info.get('version', 'Unknown')}")
                            self.print_info(f"    Development: {service_info.get('development', False)}")
                    return True
                except json.JSONDecodeError:
                    self.print_info(f"Raw output: {output}")
                    return True
            else:
                self.print_error(f"Failed to list services: {output}")
                return False
                
        except Exception as e:
            self.print_error(f"Failed to list services: {e}")
            return False
    
    def uninstall_service(self, mount_path: str) -> bool:
        """Uninstall Foxx service"""
        try:
            js_command = f'''
            var foxxManager = require('@arangodb/foxx/manager');
            var result = foxxManager.uninstall('{mount_path}');
            print(JSON.stringify(result, null, 2));
            '''
            
            success, output = self.run_arangosh_command(js_command)
            
            if success:
                self.print_success(f"Successfully uninstalled service from {mount_path}")
                self.print_info(f"Output: {output}")
                return True
            else:
                self.print_error(f"Failed to uninstall service: {output}")
                return False
                
        except Exception as e:
            self.print_error(f"Uninstallation failed: {e}")
            return False
    
    def test_service_health(self, mount_path: str) -> bool:
        """Test service health endpoint"""
        try:
            js_command = f'''
            var request = require('@arangodb/request');
            
            try {{
                var response = request.get({{
                    url: 'http://127.0.0.1:8529/_db/{self.database_name}{mount_path}/health',
                    auth: {{
                        username: '{self.username}',
                        password: '{self.password}'
                    }}
                }});
                
                print(JSON.stringify({{
                    status: response.status,
                    body: response.body
                }}, null, 2));
                
            }} catch (e) {{
                print(JSON.stringify({{
                    error: e.message
                }}, null, 2));
            }}
            '''
            
            success, output = self.run_arangosh_command(js_command)
            
            if success:
                try:
                    result = json.loads(output.strip())
                    if result.get('status') == 200:
                        self.print_success("Service health check passed")
                        self.print_info(f"Health data: {result.get('body', {})}")
                        return True
                    else:
                        self.print_error(f"Health check failed: {result}")
                        return False
                except json.JSONDecodeError:
                    self.print_error(f"Failed to parse health check response: {output}")
                    return False
            else:
                self.print_error(f"Health check command failed: {output}")
                return False
                
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
    parser = argparse.ArgumentParser(description='Deploy Entity Resolution Foxx service using container tools')
    parser.add_argument('action', choices=['install', 'uninstall', 'list', 'health'], 
                       help='Action to perform')
    
    parser.add_argument('--mount-path', '-m', default='/entity-resolution',
                       help='Service mount path (default: /entity-resolution)')
    parser.add_argument('--service-path', '-s', 
                       default='foxx-services/entity-resolution',
                       help='Path to service directory')
    parser.add_argument('--database', '-d', default='_system',
                       help='Database name (default: _system)')
    parser.add_argument('--container', '-c', default='arango-entity-resolution',
                       help='Container name (default: arango-entity-resolution)')
    
    # Add common connection arguments
    add_common_args(parser)
    
    args = parser.parse_args()
    
    # Create deployer
    deployer = ContainerFoxxDeployer(
        args.host, args.port, args.username, args.password, 
        args.database, args.container
    )
    
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
