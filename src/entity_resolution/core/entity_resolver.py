"""
Main Entity Resolution Orchestrator

Coordinates the complete entity resolution pipeline:
1. Data ingestion and validation
2. Blocking and candidate generation
3. Similarity computation
4. Graph-based clustering
5. Golden record generation
"""

import time
from typing import Dict, List, Any, Optional, Union
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    PANDAS_AVAILABLE = False

from ..data.data_manager import DataManager
from ..services.blocking_service import BlockingService
from ..services.similarity_service import SimilarityService
from ..services.clustering_service import ClusteringService
from ..utils.config import Config, get_config
from ..utils.logging import get_logger


class EntityResolutionPipeline:
    """
    Complete entity resolution pipeline
    
    Orchestrates the entire process from raw data to golden records:
    - Data loading and validation
    - Setup of analyzers and views
    - Blocking and candidate generation
    - Similarity computation with Fellegi-Sunter
    - Graph-based clustering with WCC
    - Quality validation and reporting
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.logger = get_logger(__name__)
        
        # Initialize services
        self.data_manager = DataManager(self.config)
        self.blocking_service = BlockingService(self.config)
        self.similarity_service = SimilarityService(self.config)
        self.clustering_service = ClusteringService(self.config)
        
        # Pipeline state
        self.connected = False
        self.pipeline_stats = {}
        
    def connect(self) -> bool:
        """
        Initialize all connections and services
        
        Returns:
            True if all connections successful
        """
        try:
            # Connect data manager
            if not self.data_manager.connect():
                return False
            
            # Connect services
            services = [
                ("blocking", self.blocking_service),
                ("similarity", self.similarity_service), 
                ("clustering", self.clustering_service)
            ]
            
            for name, service in services:
                if hasattr(service, 'connect') and not service.connect():
                    self.logger.error(f"Failed to connect {name} service")
                    return False
            
            self.connected = True
            self.logger.info("Entity resolution pipeline initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize pipeline: {e}")
            return False
    
    def load_data(self, source: Union[str, 'pd.DataFrame'], 
                  collection_name: str = "customers") -> Dict[str, Any]:
        """
        Load data into the system
        
        Args:
            source: File path or DataFrame
            collection_name: Target collection name
            
        Returns:
            Loading results
        """
        if not self.connected:
            return {"success": False, "error": "Pipeline not connected"}
        
        start_time = time.time()
        
        try:
            if isinstance(source, str):
                result = self.data_manager.load_data_from_file(source, collection_name)
            elif PANDAS_AVAILABLE and pd is not None and isinstance(source, pd.DataFrame):
                result = self.data_manager.load_data_from_dataframe(source, collection_name)
            else:
                return {"success": False, "error": "Unsupported source type or pandas not available"}
            
            if result["success"]:
                # Perform data quality analysis
                quality_result = self.data_manager.validate_data_quality(collection_name)
                result["data_quality"] = quality_result
                
                # Update pipeline stats
                self.pipeline_stats["data_loading"] = {
                    "collection": collection_name,
                    "records_loaded": result["inserted_records"],
                    "loading_time": time.time() - start_time,
                    "quality_score": quality_result.get("overall_quality_score", 0)
                }
                
                self.logger.info(f"Data loading completed: {result['inserted_records']} records")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"success": False, "error": str(e)}
    
    def setup_system(self, collections: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Set up analyzers, views, and collections for entity resolution
        
        Args:
            collections: List of collection names to set up
            
        Returns:
            Setup results
        """
        if not self.connected:
            return {"success": False, "error": "Pipeline not connected"}
        
        collections = collections or self.config.er.default_collections
        start_time = time.time()
        
        try:
            # Initialize collections
            init_result = self.data_manager.initialize_test_collections()
            if not init_result["success"]:
                return {"success": False, "error": "Failed to initialize collections", 
                       "details": init_result}
            
            # Set up blocking service (analyzers and views)
            setup_result = self.blocking_service.setup_for_collections(collections)
            
            if setup_result["success"]:
                self.pipeline_stats["setup"] = {
                    "collections": collections,
                    "setup_time": time.time() - start_time,
                    "analyzers_created": len(setup_result.get("analyzers", {})),
                    "views_created": len(setup_result.get("views", {}))
                }
                
                self.logger.info("System setup completed successfully")
            
            return setup_result
            
        except Exception as e:
            self.logger.error(f"Failed to set up system: {e}")
            return {"success": False, "error": str(e)}
    
    def run_entity_resolution(self, collection_name: str = "customers",
                             similarity_threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        Run the complete entity resolution pipeline
        
        Args:
            collection_name: Source collection name
            similarity_threshold: Similarity threshold for clustering
            
        Returns:
            Complete pipeline results
        """
        if not self.connected:
            return {"success": False, "error": "Pipeline not connected"}
        
        threshold = similarity_threshold or self.config.er.similarity_threshold
        pipeline_start = time.time()
        
        try:
            # Get all records from collection
            records = self.data_manager.sample_records(collection_name, limit=10000)  # Adjust limit as needed
            if not records:
                return {"success": False, "error": f"No records found in {collection_name}"}
            
            self.logger.info(f"Starting entity resolution for {len(records)} records")
            
            # Stage 1: Blocking and candidate generation
            blocking_start = time.time()
            blocking_results = self._run_blocking_stage(records, collection_name)
            blocking_time = time.time() - blocking_start
            
            if not blocking_results["success"]:
                return {"success": False, "error": "Blocking stage failed", 
                       "details": blocking_results}
            
            # Stage 2: Similarity computation
            similarity_start = time.time()
            similarity_results = self._run_similarity_stage(blocking_results["candidate_pairs"])
            similarity_time = time.time() - similarity_start
            
            if not similarity_results["success"]:
                return {"success": False, "error": "Similarity stage failed",
                       "details": similarity_results}
            
            # Stage 3: Clustering
            clustering_start = time.time()
            clustering_results = self._run_clustering_stage(similarity_results["scored_pairs"], threshold)
            clustering_time = time.time() - clustering_start
            
            if not clustering_results["success"]:
                return {"success": False, "error": "Clustering stage failed",
                       "details": clustering_results}
            
            # Compile final results
            total_time = time.time() - pipeline_start
            
            pipeline_results = {
                "success": True,
                "collection": collection_name,
                "input_records": len(records),
                "candidate_pairs": len(blocking_results["candidate_pairs"]),
                "scored_pairs": len(similarity_results["scored_pairs"]),
                "entity_clusters": len(clustering_results["clusters"]),
                "performance": {
                    "total_time": total_time,
                    "blocking_time": blocking_time,
                    "similarity_time": similarity_time,
                    "clustering_time": clustering_time
                },
                "stages": {
                    "blocking": blocking_results,
                    "similarity": similarity_results,
                    "clustering": clustering_results
                },
                "configuration": {
                    "similarity_threshold": threshold,
                    "max_candidates": self.config.er.max_candidates_per_record,
                    "ngram_length": self.config.er.ngram_length
                }
            }
            
            # Update pipeline stats
            self.pipeline_stats["entity_resolution"] = pipeline_results["performance"]
            
            self.logger.info(f"Entity resolution completed: {len(clustering_results['clusters'])} clusters found in {total_time:.2f}s")
            
            return pipeline_results
            
        except Exception as e:
            self.logger.error(f"Entity resolution pipeline failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _run_blocking_stage(self, records: List[Dict[str, Any]], 
                           collection_name: str) -> Dict[str, Any]:
        """Run the blocking stage to generate candidate pairs"""
        try:
            self.logger.info("Starting blocking stage...")
            
            # For now, use simple pairwise blocking until Foxx services are working
            candidate_pairs = []
            
            # Generate pairs for each record against a subset of others
            max_candidates = self.config.er.max_candidates_per_record
            
            for i, record_a in enumerate(records):
                candidates_found = 0
                for j, record_b in enumerate(records):
                    if i >= j:  # Skip self and already processed pairs
                        continue
                    
                    if candidates_found >= max_candidates:
                        break
                    
                    # Simple blocking: check if records share any common fields
                    if self._simple_blocking_check(record_a, record_b):
                        candidate_pairs.append({
                            "record_a": record_a,
                            "record_b": record_b,
                            "record_a_id": record_a.get("_id", f"record_{i}"),
                            "record_b_id": record_b.get("_id", f"record_{j}")
                        })
                        candidates_found += 1
            
            self.logger.info(f"Blocking stage completed: {len(candidate_pairs)} candidate pairs generated")
            
            return {
                "success": True,
                "candidate_pairs": candidate_pairs,
                "reduction_ratio": 1 - (len(candidate_pairs) / ((len(records) * (len(records) - 1)) / 2))
            }
            
        except Exception as e:
            self.logger.error(f"Blocking stage failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _simple_blocking_check(self, record_a: Dict[str, Any], 
                              record_b: Dict[str, Any]) -> bool:
        """Simple blocking check based on field similarity"""
        # Check for exact matches in key fields
        key_fields = ["email", "phone"]
        for field in key_fields:
            val_a = record_a.get(field, "").strip().lower()
            val_b = record_b.get(field, "").strip().lower()
            if val_a and val_b and val_a == val_b:
                return True
        
        # Check for name similarity
        name_a = f"{record_a.get('first_name', '')} {record_a.get('last_name', '')}".strip().lower()
        name_b = f"{record_b.get('first_name', '')} {record_b.get('last_name', '')}".strip().lower()
        
        if name_a and name_b:
            # Simple n-gram similarity
            return self._simple_ngram_similarity(name_a, name_b) > 0.6
        
        return False
    
    def _simple_ngram_similarity(self, str1: str, str2: str, n: int = 3) -> float:
        """Simple n-gram similarity calculation"""
        if not str1 or not str2:
            return 0.0
        
        # Generate n-grams
        ngrams1 = set(str1[i:i+n] for i in range(len(str1)-n+1))
        ngrams2 = set(str2[i:i+n] for i in range(len(str2)-n+1))
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = len(ngrams1.intersection(ngrams2))
        union = len(ngrams1.union(ngrams2))
        
        return intersection / union if union > 0 else 0.0
    
    def _run_similarity_stage(self, candidate_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run similarity computation on candidate pairs"""
        try:
            self.logger.info(f"Starting similarity computation for {len(candidate_pairs)} pairs...")
            
            scored_pairs = []
            
            for pair in candidate_pairs:
                record_a = pair["record_a"]
                record_b = pair["record_b"]
                
                # Compute similarity score
                similarity_score = self.similarity_service.compute_similarity(record_a, record_b)
                
                scored_pairs.append({
                    "record_a_id": pair["record_a_id"],
                    "record_b_id": pair["record_b_id"],
                    "similarity_score": similarity_score["total_score"],
                    "is_match": similarity_score["is_match"],
                    "field_scores": similarity_score.get("field_scores", {}),
                    "confidence": similarity_score.get("confidence", 0.0)
                })
            
            self.logger.info(f"Similarity computation completed: {len(scored_pairs)} pairs scored")
            
            return {
                "success": True,
                "scored_pairs": scored_pairs,
                "matches_found": sum(1 for p in scored_pairs if p["is_match"])
            }
            
        except Exception as e:
            self.logger.error(f"Similarity stage failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _run_clustering_stage(self, scored_pairs: List[Dict[str, Any]], 
                             threshold: float) -> Dict[str, Any]:
        """Run clustering on scored pairs"""
        try:
            self.logger.info(f"Starting clustering for {len(scored_pairs)} scored pairs...")
            
            # Filter pairs above threshold
            valid_pairs = [p for p in scored_pairs if p["similarity_score"] >= threshold]
            
            if not valid_pairs:
                self.logger.warning("No pairs above similarity threshold")
                return {"success": True, "clusters": [], "valid_pairs": 0}
            
            # Run clustering
            clustering_result = self.clustering_service.cluster_entities(valid_pairs)
            
            self.logger.info(f"Clustering completed: {len(clustering_result['clusters'])} clusters found")
            
            return {
                "success": True,
                "clusters": clustering_result["clusters"],
                "valid_pairs": len(valid_pairs),
                "clustering_stats": clustering_result.get("statistics", {})
            }
            
        except Exception as e:
            self.logger.error(f"Clustering stage failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get comprehensive pipeline statistics"""
        return {
            "pipeline_stats": self.pipeline_stats,
            "configuration": self.config.to_dict(),
            "system_status": {
                "connected": self.connected,
                "foxx_services_enabled": self.config.er.enable_foxx_services
            }
        }


# Convenience alias
EntityResolver = EntityResolutionPipeline
