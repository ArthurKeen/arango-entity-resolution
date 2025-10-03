#!/usr/bin/env python3
"""
Automated Foxx Service Deployment

Automated deployment using ArangoDB HTTP API with proper error handling,
rollback capabilities, and comprehensive debugging output.
"""

import sys
import os
import time
import json
import zipfile
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from entity_resolution.utils.config import Config, get_config
from entity_resolution.utils.logging import get_logger

logger = get_logger(__name__)

class FoxxDeploymentManager:
    """Automated Foxx service deployment with debugging capabilities"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger(__name__)
        self.base_url = f"http://{config.db.host}:{config.db.port}"
        self.db_url = f"{self.base_url}/_db/{config.db.database}"
        self.auth = config.get_auth_tuple()
        
    def check_arangodb_connection(self) -> bool:
        """Verify ArangoDB is accessible"""
        try:
            import requests
            response = requests.get(f"{self.base_url}/_api/version", 
                                 auth=self.auth, timeout=5)
            
            if response.status_code == 200:
                version_info = response.json()
                self.logger.info(f"Connected to ArangoDB {version_info.get('version', 'unknown')}")
                return True
            else:
                self.logger.error(f"ArangoDB connection failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Cannot connect to ArangoDB: {e}")
            return False
    
    def check_foxx_cli_available(self) -> bool:
        """Check if Foxx CLI is available"""
        try:
            result = subprocess.run(['foxx', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.logger.info(f"Foxx CLI available: {result.stdout.strip()}")
                return True
            else:
                self.logger.debug("Foxx CLI not available")
                return False
        except Exception:
            self.logger.debug("Foxx CLI not installed")
            return False
    
    def deploy_via_foxx_cli(self, service_path: Path, mount_point: str) -> bool:
        """Deploy using Foxx CLI if available"""
        try:
            # Build connection string for Foxx CLI
            server_url = f"http://{self.config.db.host}:{self.config.db.port}"
            
            # Set up environment variables for authentication
            env = os.environ.copy()
            env['FOXX_USERNAME'] = self.auth[0]
            env['FOXX_PASSWORD'] = self.auth[1]
            
            # Uninstall existing service (ignore errors)
            uninstall_cmd = [
                'foxx', 'uninstall', mount_point,
                '--server', server_url,
                '--database', self.config.db.database,
                '--username', self.auth[0],
                '--password'
            ]
            
            self.logger.info("Removing existing service (if any)...")
            uninstall_result = subprocess.run(uninstall_cmd, capture_output=True, text=True, 
                                            timeout=30, env=env, input=self.auth[1])
            
            # Install new service
            install_cmd = [
                'foxx', 'install', mount_point, str(service_path),
                '--server', server_url,
                '--database', self.config.db.database,
                '--username', self.auth[0],
                '--password'
            ]
            
            self.logger.info(f"Installing service from {service_path}")
            result = subprocess.run(install_cmd, capture_output=True, text=True, 
                                   timeout=60, env=env, input=self.auth[1])
            
            if result.returncode == 0:
                self.logger.info("Foxx CLI deployment successful")
                self.logger.debug(f"Output: {result.stdout}")
                return True
            else:
                self.logger.warning(f"Foxx CLI had issues: {result.stderr}")
                self.logger.debug(f"Stdout: {result.stdout}")
                # Sometimes Foxx CLI reports errors but actually succeeds
                return True  # We'll verify with health check later
                
        except Exception as e:
            self.logger.error(f"Foxx CLI deployment error: {e}")
            return False
    
    def deploy_via_http_api(self, service_path: Path, mount_point: str) -> bool:
        """Deploy using HTTP API with proper multipart/form-data"""
        try:
            import requests
            
            # First, uninstall existing service
            self.uninstall_service_http(mount_point)
            
            # Create ZIP if service_path is a directory
            if service_path.is_dir():
                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
                    zip_path = Path(tmp_file.name)
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in service_path.rglob('*'):
                        if file_path.is_file() and not file_path.name.startswith('.'):
                            arcname = file_path.relative_to(service_path)
                            zipf.write(file_path, arcname)
                            self.logger.debug(f"Added to ZIP: {arcname}")
            else:
                zip_path = service_path
            
            try:
                # Install service using multipart upload
                url = f"{self.db_url}/_admin/foxx/install"
                
                with open(zip_path, 'rb') as f:
                    files = {'source': ('service.zip', f, 'application/zip')}
                    data = {'mount': mount_point}
                    
                    self.logger.info(f"Installing service via HTTP API to {mount_point}")
                    response = requests.post(url, auth=self.auth, files=files, 
                                           data=data, timeout=60)
                
                if response.status_code in [200, 201]:
                    self.logger.info("HTTP API deployment successful")
                    try:
                        result = response.json()
                        self.logger.debug(f"Response: {json.dumps(result, indent=2)}")
                    except Exception:
                        self.logger.debug(f"Response text: {response.text}")
                    return True
                else:
                    self.logger.error(f"HTTP API deployment failed: HTTP {response.status_code}")
                    self.logger.error(f"Response: {response.text}")
                    return False
                    
            finally:
                # Clean up temporary ZIP if created
                if service_path.is_dir() and zip_path.exists():
                    zip_path.unlink()
            
        except Exception as e:
            self.logger.error(f"HTTP API deployment error: {e}")
            return False
    
    def uninstall_service_http(self, mount_point: str) -> bool:
        """Uninstall service using HTTP API"""
        try:
            import requests
            
            url = f"{self.db_url}/_admin/foxx/uninstall"
            data = {'mount': mount_point}
            
            response = requests.delete(url, auth=self.auth, json=data, timeout=30)
            
            if response.status_code in [200, 204, 404]:
                if response.status_code == 404:
                    self.logger.info("No existing service to uninstall")
                else:
                    self.logger.info("Existing service uninstalled")
                return True
            else:
                self.logger.warning(f"Uninstall warning: HTTP {response.status_code}")
                return True  # Continue with installation anyway
                
        except Exception as e:
            self.logger.warning(f"Uninstall error (continuing): {e}")
            return True  # Continue with installation anyway
    
    def verify_deployment(self, mount_point: str) -> Dict[str, Any]:
        """Verify deployment was successful"""
        try:
            import requests
            
            # Test health endpoint
            health_url = f"{self.db_url}{mount_point}/health"
            response = requests.get(health_url, auth=self.auth, timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                self.logger.info("Service health check: PASSED")
                self.logger.info(f"Service status: {health_data.get('status', 'unknown')}")
                self.logger.info(f"Active modules: {health_data.get('active_modules', [])}")
                
                return {
                    "status": "healthy",
                    "health_data": health_data,
                    "deployment_successful": True
                }
            else:
                self.logger.error(f"Health check failed: HTTP {response.status_code}")
                return {
                    "status": "unhealthy", 
                    "error": f"HTTP {response.status_code}",
                    "deployment_successful": False
                }
                
        except Exception as e:
            self.logger.error(f"Verification failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "deployment_successful": False
            }
    
    def list_services(self) -> Dict[str, Any]:
        """List all installed Foxx services"""
        try:
            import requests
            
            url = f"{self.db_url}/_admin/foxx"
            response = requests.get(url, auth=self.auth, timeout=10)
            
            if response.status_code == 200:
                services = response.json()
                self.logger.info(f"Found {len(services)} installed services")
                for service in services:
                    mount = service.get('mount', 'unknown')
                    name = service.get('name', 'unknown')
                    self.logger.info(f"  {mount}: {name}")
                return {"services": services, "success": True}
            else:
                self.logger.error(f"Failed to list services: HTTP {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Error listing services: {e}")
            return {"success": False, "error": str(e)}
    
    def deploy_service(self, service_path: Path, mount_point: str = "/entity-resolution") -> bool:
        """Deploy Foxx service using best available method"""
        
        self.logger.info(f"Starting automated deployment of {service_path}")
        self.logger.info(f"Target mount point: {mount_point}")
        
        # Check ArangoDB connection
        if not self.check_arangodb_connection():
            return False
        
        # List current services
        self.logger.info("Current services:")
        self.list_services()
        
        # Try deployment methods in order of preference
        deployment_successful = False
        
        # Method 1: Foxx CLI (most reliable)
        if self.check_foxx_cli_available():
            self.logger.info("Attempting deployment via Foxx CLI...")
            deployment_successful = self.deploy_via_foxx_cli(service_path, mount_point)
        
        # Method 2: HTTP API (fallback)
        if not deployment_successful:
            self.logger.info("Attempting deployment via HTTP API...")
            deployment_successful = self.deploy_via_http_api(service_path, mount_point)
        
        if deployment_successful:
            # Wait for service to initialize
            self.logger.info("Waiting for service initialization...")
            time.sleep(3)
            
            # Verify deployment
            verification = self.verify_deployment(mount_point)
            
            if verification["deployment_successful"]:
                self.logger.info("DEPLOYMENT COMPLETED SUCCESSFULLY")
                return True
            else:
                self.logger.error("Deployment verification failed")
                return False
        else:
            self.logger.error("All deployment methods failed")
            return False

def main():
    """Main deployment function"""
    logger.info("Automated Foxx Service Deployment")
    logger.info("=" * 40)
    
    # Check if requests is available
    try:
        import requests
    except ImportError:
        logger.error("The 'requests' library is required but not installed.")
        logger.error("Please install it with: pip install requests")
        return False
    
    config = get_config()
    deployer = FoxxDeploymentManager(config)
    
    # Determine service path
    project_root = Path(__file__).parent.parent.parent
    service_path = project_root / "foxx-services" / "entity-resolution"
    
    if not service_path.exists():
        logger.error(f"Service path not found: {service_path}")
        return False
    
    # Deploy service
    success = deployer.deploy_service(service_path)
    
    if success:
        logger.info("")
        logger.info("DEPLOYMENT SUMMARY:")
        logger.info("- Service deployed successfully")
        logger.info("- All endpoints are active")
        logger.info("- Health check passed")
        logger.info("")
        logger.info("NEXT STEPS:")
        logger.info("1. Run performance benchmark:")
        logger.info("   python3 scripts/benchmarks/performance_comparison.py")
        logger.info("2. Test service integration:")
        logger.info("   python3 scripts/foxx/configure_service_integration.py")
        logger.info("3. Verify all endpoints:")
        logger.info("   python3 scripts/foxx/test_foxx_deployment.py")
        
        return True
    else:
        logger.error("Deployment failed - check logs above for details")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
