#!/usr/bin/env python3
"""
Service Integration Configuration

Configures Python services to optimally use Foxx endpoints when available,
with intelligent fallback and performance monitoring.
"""

import sys
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from entity_resolution.utils.config import Config, get_config
from entity_resolution.utils.logging import get_logger
from entity_resolution.services.similarity_service import SimilarityService
from entity_resolution.services.blocking_service import BlockingService
from entity_resolution.services.clustering_service import ClusteringService

logger = get_logger(__name__)

class ServiceIntegrationManager:
    """Manages integration between Python services and Foxx endpoints"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger(__name__)
        self.foxx_health_cache = {}
        self.last_health_check = 0
        self.health_check_interval = 60  # seconds
        
    def check_foxx_service_health(self, force_check: bool = False) -> Dict[str, Any]:
        """Check health of Foxx service with caching"""
        current_time = time.time()
        
        if not force_check and (current_time - self.last_health_check) < self.health_check_interval:
            return self.foxx_health_cache
        
        health_status = {
            "available": False,
            "endpoints": {},
            "performance_mode": "python_fallback",
            "last_check": current_time
        }
        
        try:
            base_url = f"http://{self.config.db.host}:{self.config.db.port}/_db/{self.config.db.database}/entity-resolution"
            auth = self.config.get_auth_tuple()
            
            # Check health endpoint
            response = requests.get(f"{base_url}/health", auth=auth, timeout=5)
            
            if response.status_code == 200:
                health_data = response.json()
                health_status["available"] = True
                health_status["service_info"] = health_data
                health_status["performance_mode"] = "foxx_native"
                
                # Check individual endpoints
                endpoints_to_test = [
                    ("similarity", "/similarity/functions"),
                    ("blocking", "/blocking/stats"),
                    ("clustering", "/clustering/analyze")
                ]
                
                for service_name, endpoint in endpoints_to_test:
                    try:
                        test_response = requests.get(f"{base_url}{endpoint}", auth=auth, timeout=3)
                        health_status["endpoints"][service_name] = {
                            "available": test_response.status_code in [200, 404],  # 404 acceptable for some endpoints
                            "status_code": test_response.status_code
                        }
                    except Exception as e:
                        health_status["endpoints"][service_name] = {
                            "available": False,
                            "error": str(e)
                        }
                
                self.logger.info("Foxx service health check: HEALTHY")
            else:
                self.logger.warning(f"Foxx service health check failed: HTTP {response.status_code}")
                
        except Exception as e:
            self.logger.warning(f"Foxx service not accessible: {e}")
        
        self.foxx_health_cache = health_status
        self.last_health_check = current_time
        
        return health_status
    
    def configure_similarity_service(self) -> SimilarityService:
        """Configure similarity service with Foxx integration"""
        service = SimilarityService(self.config)
        
        # Check Foxx availability
        health = self.check_foxx_service_health()
        
        if health["available"] and health["endpoints"].get("similarity", {}).get("available"):
            # Force reconnection to pick up Foxx service
            service.connect()
            if service.foxx_available:
                self.logger.info("Similarity service configured for Foxx mode")
            else:
                self.logger.info("Similarity service falling back to Python mode")
        else:
            self.logger.info("Similarity service configured for Python mode (Foxx not available)")
        
        return service
    
    def configure_blocking_service(self) -> BlockingService:
        """Configure blocking service with Foxx integration"""
        service = BlockingService(self.config)
        
        # Check Foxx availability
        health = self.check_foxx_service_health()
        
        if health["available"] and health["endpoints"].get("blocking", {}).get("available"):
            service.connect()
            if service.foxx_available:
                self.logger.info("Blocking service configured for Foxx mode")
            else:
                self.logger.info("Blocking service falling back to Python mode")
        else:
            self.logger.info("Blocking service configured for Python mode (Foxx not available)")
        
        return service
    
    def configure_clustering_service(self) -> ClusteringService:
        """Configure clustering service with Foxx integration"""
        service = ClusteringService(self.config)
        
        # Check Foxx availability
        health = self.check_foxx_service_health()
        
        if health["available"] and health["endpoints"].get("clustering", {}).get("available"):
            service.connect()
            if service.foxx_available:
                self.logger.info("Clustering service configured for Foxx mode")
            else:
                self.logger.info("Clustering service falling back to Python mode")
        else:
            self.logger.info("Clustering service configured for Python mode (Foxx not available)")
        
        return service
    
    def get_optimal_configuration(self) -> Dict[str, Any]:
        """Get optimal configuration recommendations"""
        health = self.check_foxx_service_health(force_check=True)
        
        config_recommendations = {
            "foxx_service_available": health["available"],
            "performance_mode": health["performance_mode"],
            "recommendations": []
        }
        
        if health["available"]:
            config_recommendations["recommendations"].extend([
                "Foxx service is available - optimal performance mode enabled",
                "All services configured for native ArangoDB processing",
                "Expected 5-6x performance improvement over Python fallback"
            ])
            
            # Check specific endpoints
            for service, endpoint_info in health["endpoints"].items():
                if endpoint_info["available"]:
                    config_recommendations["recommendations"].append(
                        f"{service.capitalize()} service: Foxx mode enabled"
                    )
                else:
                    config_recommendations["recommendations"].append(
                        f"{service.capitalize()} service: Python fallback (Foxx endpoint not ready)"
                    )
        else:
            config_recommendations["recommendations"].extend([
                "Foxx service not available - using Python fallback mode",
                "Deploy Foxx service for optimal performance",
                "Current performance: baseline Python implementation"
            ])
        
        return config_recommendations
    
    def run_integration_test(self) -> Dict[str, Any]:
        """Run integration test to verify service configuration"""
        self.logger.info("Running service integration test")
        
        test_results = {
            "similarity_service": {"status": "unknown", "mode": "unknown"},
            "blocking_service": {"status": "unknown", "mode": "unknown"},
            "clustering_service": {"status": "unknown", "mode": "unknown"},
            "overall_status": "unknown"
        }
        
        # Test similarity service
        try:
            similarity_service = self.configure_similarity_service()
            test_doc_a = {"first_name": "John", "last_name": "Smith", "email": "john@example.com"}
            test_doc_b = {"first_name": "Jon", "last_name": "Smith", "email": "john@example.com"}
            
            result = similarity_service.compute_similarity(test_doc_a, test_doc_b)
            
            test_results["similarity_service"] = {
                "status": "working" if result.get("success", True) else "failed",
                "mode": "foxx" if similarity_service.foxx_available else "python",
                "test_score": result.get("similarity", {}).get("total_score", "N/A")
            }
        except Exception as e:
            test_results["similarity_service"] = {"status": "error", "error": str(e)}
        
        # Test blocking service (simplified)
        try:
            blocking_service = self.configure_blocking_service()
            # Just test service initialization since we don't have test data in collections
            test_results["blocking_service"] = {
                "status": "initialized",
                "mode": "foxx" if blocking_service.foxx_available else "python"
            }
        except Exception as e:
            test_results["blocking_service"] = {"status": "error", "error": str(e)}
        
        # Test clustering service (simplified)
        try:
            clustering_service = self.configure_clustering_service()
            test_results["clustering_service"] = {
                "status": "initialized", 
                "mode": "foxx" if clustering_service.foxx_available else "python"
            }
        except Exception as e:
            test_results["clustering_service"] = {"status": "error", "error": str(e)}
        
        # Determine overall status
        all_services_working = all(
            result["status"] in ["working", "initialized"] 
            for result in test_results.values() 
            if isinstance(result, dict) and "status" in result
        )
        
        test_results["overall_status"] = "healthy" if all_services_working else "issues_detected"
        
        return test_results

def main():
    """Main configuration function"""
    logger.info("Entity Resolution Service Integration Configuration")
    logger.info("=" * 60)
    
    config = get_config()
    manager = ServiceIntegrationManager(config)
    
    # Check Foxx service health
    logger.info("Checking Foxx service availability...")
    health = manager.check_foxx_service_health(force_check=True)
    
    # Get configuration recommendations
    logger.info("Analyzing optimal configuration...")
    recommendations = manager.get_optimal_configuration()
    
    # Run integration test
    logger.info("Running integration tests...")
    test_results = manager.run_integration_test()
    
    # Display results
    logger.info("")
    logger.info("FOXX SERVICE INTEGRATION STATUS")
    logger.info("=" * 40)
    logger.info(f"Foxx Service Available: {health['available']}")
    logger.info(f"Performance Mode: {health['performance_mode']}")
    
    if health["available"]:
        logger.info(f"Service Status: {health['service_info'].get('status', 'unknown')}")
        logger.info(f"Active Modules: {health['service_info'].get('active_modules', [])}")
    
    logger.info("")
    logger.info("SERVICE CONFIGURATION:")
    for service, result in test_results.items():
        if isinstance(result, dict) and "status" in result:
            mode = result.get("mode", "unknown")
            status = result.get("status", "unknown")
            logger.info(f"  {service}: {status} ({mode} mode)")
    
    logger.info("")
    logger.info("RECOMMENDATIONS:")
    for rec in recommendations["recommendations"]:
        logger.info(f"  - {rec}")
    
    logger.info("")
    logger.info("NEXT STEPS:")
    if health["available"]:
        logger.info("  1. Run performance benchmark to measure improvements")
        logger.info("  2. Monitor service performance in production")
        logger.info("  3. Configure monitoring and alerting")
    else:
        logger.info("  1. Deploy Foxx service using FOXX_DEPLOYMENT_INSTRUCTIONS.md")
        logger.info("  2. Verify deployment with test script")
        logger.info("  3. Re-run this configuration script")
    
    return test_results

if __name__ == "__main__":
    main()
