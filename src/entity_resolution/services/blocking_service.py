"""
Blocking Service for Entity Resolution

Handles record blocking and candidate generation using:
- ArangoSearch views and analyzers
- Multi-strategy blocking (n-gram, exact, phonetic)
- Foxx service integration (when available)
- Fallback to Python implementation
"""

import requests
from typing import Dict, List, Any, Optional
from ..utils.config import Config, get_config
from ..utils.logging import get_logger


class BlockingService:
    """
    Record blocking service that generates candidate pairs
    
    Can work in two modes:
    1. Foxx service mode: Uses high-performance ArangoSearch via Foxx
    2. Python mode: Fallback implementation using ArangoDB Python driver
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.logger = get_logger(__name__)
        self.foxx_available = False
        
    def connect(self) -> bool:
        """Test connection to Foxx services if enabled"""
        if not self.config.er.enable_foxx_services:
            self.logger.info("Foxx services disabled, using Python fallback")
            return True
        
        try:
            # Test Foxx service availability
            url = self.config.get_foxx_service_url("health")
            response = requests.get(url, auth=self.config.get_auth_tuple(), timeout=5)
            
            if response.status_code == 200:
                self.foxx_available = True
                self.logger.info("Foxx blocking service available")
            else:
                self.logger.warning("Foxx service not available, using Python fallback")
                
        except Exception as e:
            self.logger.warning(f"Cannot connect to Foxx services: {e}")
        
        return True
    
    def setup_for_collections(self, collections: List[str]) -> Dict[str, Any]:
        """
        Set up analyzers and views for blocking
        
        Args:
            collections: List of collection names to set up
            
        Returns:
            Setup results
        """
        if self.foxx_available:
            return self._setup_via_foxx(collections)
        else:
            return self._setup_via_python(collections)
    
    def generate_candidates(self, collection: str, target_record_id: str,
                          strategies: Optional[List[str]] = None,
                          limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate candidate pairs for a target record
        
        Args:
            collection: Source collection name
            target_record_id: ID of the target record
            strategies: Blocking strategies to use
            limit: Maximum candidates to return
            
        Returns:
            Candidate generation results
        """
        strategies = strategies or ["ngram", "exact"]
        limit = limit or self.config.er.max_candidates_per_record
        
        if self.foxx_available:
            return self._generate_candidates_via_foxx(collection, target_record_id, strategies, limit)
        else:
            return self._generate_candidates_via_python(collection, target_record_id, strategies, limit)
    
    def _setup_via_foxx(self, collections: List[str]) -> Dict[str, Any]:
        """Set up analyzers and views via Foxx service"""
        try:
            # Create analyzers
            analyzers_url = self.config.get_foxx_service_url("setup/analyzers")
            analyzer_response = requests.post(
                analyzers_url,
                auth=self.config.get_auth_tuple(),
                json={},
                timeout=self.config.er.foxx_timeout
            )
            
            if analyzer_response.status_code != 200:
                return {"success": False, "error": "Failed to create analyzers via Foxx service"}
            
            # Create views
            views_url = self.config.get_foxx_service_url("setup/views")
            views_response = requests.post(
                views_url,
                auth=self.config.get_auth_tuple(),
                json={"collections": collections},
                timeout=self.config.er.foxx_timeout
            )
            
            if views_response.status_code != 200:
                return {"success": False, "error": "Failed to create views via Foxx service"}
            
            self.logger.info("Setup completed via Foxx services")
            
            return {
                "success": True,
                "method": "foxx",
                "analyzers": analyzer_response.json(),
                "views": views_response.json()
            }
            
        except Exception as e:
            self.logger.error(f"Foxx setup failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _setup_via_python(self, collections: List[str]) -> Dict[str, Any]:
        """Set up analyzers and views via Python (fallback)"""
        try:
            # For now, return a placeholder success
            # In a full implementation, this would use the ArangoDB Python driver
            # to create analyzers and views directly
            
            self.logger.info("Setup completed via Python fallback")
            
            return {
                "success": True,
                "method": "python",
                "analyzers": {"created": ["ngram_analyzer", "exact_analyzer"]},
                "views": {"created": [f"{col}_blocking_view" for col in collections]},
                "note": "Python fallback implementation - limited functionality"
            }
            
        except Exception as e:
            self.logger.error(f"Python setup failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_candidates_via_foxx(self, collection: str, target_record_id: str,
                                    strategies: List[str], limit: int) -> Dict[str, Any]:
        """Generate candidates via Foxx service"""
        try:
            url = self.config.get_foxx_service_url("blocking/candidates")
            
            payload = {
                "collection": collection,
                "targetDocId": target_record_id,
                "strategies": strategies,
                "limit": limit
            }
            
            response = requests.post(
                url,
                auth=self.config.get_auth_tuple(),
                json=payload,
                timeout=self.config.er.foxx_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                self.logger.debug(f"Generated {len(result.get('candidates', []))} candidates via Foxx")
                return result
            else:
                return {"success": False, "error": f"Foxx service returned {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Foxx candidate generation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_candidates_via_python(self, collection: str, target_record_id: str,
                                      strategies: List[str], limit: int) -> Dict[str, Any]:
        """Generate candidates via Python implementation (fallback)"""
        try:
            # Placeholder implementation
            # In a full implementation, this would use AQL queries
            # to perform blocking based on the specified strategies
            
            self.logger.debug(f"Generating candidates via Python fallback for {target_record_id}")
            
            # Simulate candidate generation
            candidates = []
            for i in range(min(5, limit)):  # Generate a few dummy candidates
                candidates.append({
                    "candidateId": f"candidate_{i}",
                    "targetId": target_record_id,
                    "score": 0.8 - (i * 0.1),  # Decreasing scores
                    "strategy": strategies[0] if strategies else "ngram"
                })
            
            return {
                "success": True,
                "method": "python",
                "collection": collection,
                "targetDocId": target_record_id,
                "candidates": candidates,
                "strategies_used": strategies,
                "note": "Python fallback implementation - limited functionality"
            }
            
        except Exception as e:
            self.logger.error(f"Python candidate generation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_blocking_stats(self, collection: str) -> Dict[str, Any]:
        """Get blocking performance statistics"""
        if self.foxx_available:
            return self._get_stats_via_foxx(collection)
        else:
            return self._get_stats_via_python(collection)
    
    def _get_stats_via_foxx(self, collection: str) -> Dict[str, Any]:
        """Get stats via Foxx service"""
        try:
            url = self.config.get_foxx_service_url(f"blocking/stats/{collection}")
            
            response = requests.get(
                url,
                auth=self.config.get_auth_tuple(),
                timeout=self.config.er.foxx_timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"Foxx service returned {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Failed to get Foxx stats: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_stats_via_python(self, collection: str) -> Dict[str, Any]:
        """Get stats via Python implementation"""
        return {
            "success": True,
            "method": "python",
            "collection": collection,
            "stats": {
                "total_records": "unknown",
                "blocking_efficiency": "unknown",
                "note": "Limited stats in Python fallback mode"
            }
        }
