"""
Clustering Service for Entity Resolution

Handles graph-based entity clustering using:
- Weakly Connected Components (WCC) algorithm
- Quality validation and coherence checking
- Foxx service integration (when available)
- Fallback to Python graph implementation
"""

import requests
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict
from .base_service import BaseEntityResolutionService, Config


class ClusteringService(BaseEntityResolutionService):
    """
    Entity clustering service using graph-based algorithms
    
    Can work in two modes:
    1. Foxx service mode: Uses ArangoDB native graph algorithms
    2. Python mode: Fallback implementation with NetworkX-style clustering
    """
    
    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)
        
    def _get_service_name(self) -> str:
        return "clustering"
    
    def _test_service_endpoints(self) -> bool:
        """Test if clustering Foxx endpoints are available"""
        try:
            result = self._make_foxx_request("clustering/wcc", method="GET")
            return result.get("success", False) or "error" not in result or "404" not in str(result.get("error", ""))
        except Exception:
            return False
    
    def build_similarity_graph(self, scored_pairs: List[Dict[str, Any]],
                              threshold: Optional[float] = None,
                              edge_collection: str = "similarities") -> Dict[str, Any]:
        """
        Build similarity graph from scored pairs
        
        Args:
            scored_pairs: List of scored document pairs
            threshold: Similarity threshold for edge creation
            edge_collection: Target edge collection name
            
        Returns:
            Graph building results
        """
        threshold = threshold or self.config.er.similarity_threshold
        
        if self.foxx_available:
            return self._build_graph_via_foxx(scored_pairs, threshold, edge_collection)
        else:
            return self._build_graph_via_python(scored_pairs, threshold, edge_collection)
    
    def cluster_entities(self, scored_pairs: List[Dict[str, Any]],
                        min_similarity: Optional[float] = None,
                        max_cluster_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Perform entity clustering using Weakly Connected Components
        
        Args:
            scored_pairs: List of scored document pairs
            min_similarity: Minimum similarity threshold for clustering
            max_cluster_size: Maximum allowed cluster size
            
        Returns:
            Clustering results with entity clusters
        """
        min_similarity = min_similarity or self.config.er.similarity_threshold
        max_cluster_size = max_cluster_size or self.config.er.max_cluster_size
        
        if self.foxx_available:
            return self._cluster_via_foxx(scored_pairs, min_similarity, max_cluster_size)
        else:
            return self._cluster_via_python(scored_pairs, min_similarity, max_cluster_size)
    
    def validate_cluster_quality(self, clusters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate cluster quality and coherence
        
        Args:
            clusters: List of entity clusters to validate
            
        Returns:
            Validation results with quality metrics
        """
        if self.foxx_available:
            return self._validate_via_foxx(clusters)
        else:
            return self._validate_via_python(clusters)
    
    def _build_graph_via_foxx(self, scored_pairs: List[Dict[str, Any]],
                             threshold: float, edge_collection: str) -> Dict[str, Any]:
        """Build similarity graph via Foxx service"""
        try:
            url = self.config.get_foxx_service_url("clustering/build-graph")
            
            payload = {
                "scoredPairs": scored_pairs,
                "threshold": threshold,
                "edgeCollection": edge_collection
            }
            
            response = requests.post(
                url,
                auth=self.config.get_auth_tuple(),
                json=payload,
                timeout=self.config.er.foxx_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"Built similarity graph: {result.get('results', {}).get('created_count', 0)} edges created")
                return result
            else:
                return {"success": False, "error": f"Foxx service returned {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Foxx graph building failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_graph_via_python(self, scored_pairs: List[Dict[str, Any]],
                               threshold: float, edge_collection: str) -> Dict[str, Any]:
        """Build similarity graph via Python implementation"""
        try:
            # Filter pairs above threshold
            valid_pairs = [pair for pair in scored_pairs if pair.get("similarity_score", 0) >= threshold]
            
            self.logger.info(f"Building graph with {len(valid_pairs)} valid pairs (threshold: {threshold})")
            
            # For Python fallback, we don't actually store in ArangoDB
            # Instead, we keep the edges in memory for clustering
            edges = []
            vertices = set()
            
            for pair in valid_pairs:
                doc_a_id = pair.get("record_a_id") or pair.get("docA_id")
                doc_b_id = pair.get("record_b_id") or pair.get("docB_id")
                score = pair.get("similarity_score", 0)
                
                if doc_a_id and doc_b_id:
                    edges.append({
                        "_from": doc_a_id,
                        "_to": doc_b_id,
                        "similarity_score": score,
                        "is_match": pair.get("is_match", False)
                    })
                    vertices.add(doc_a_id)
                    vertices.add(doc_b_id)
            
            return {
                "success": True,
                "method": "python",
                "edge_collection": edge_collection,
                "results": {
                    "created_count": len(edges),
                    "updated_count": 0,
                    "skipped_count": 0,
                    "edges": edges,  # Store edges for clustering
                    "vertices": list(vertices)
                },
                "statistics": {
                    "input_pairs": len(scored_pairs),
                    "threshold_used": threshold,
                    "valid_pairs": len(valid_pairs)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Python graph building failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _cluster_via_foxx(self, scored_pairs: List[Dict[str, Any]],
                         min_similarity: float, max_cluster_size: int) -> Dict[str, Any]:
        """Perform clustering via Foxx service"""
        try:
            # First build the graph
            graph_result = self._build_graph_via_foxx(
                scored_pairs, min_similarity, self.config.er.edge_collection)
            
            if not graph_result.get("success"):
                return {"success": False, "error": "Failed to build similarity graph"}
            
            # Then perform WCC clustering
            url = self.config.get_foxx_service_url("clustering/wcc")
            
            payload = {
                "edgeCollection": self.config.er.edge_collection,
                "minSimilarity": min_similarity,
                "maxClusterSize": max_cluster_size,
                "outputCollection": self.config.er.cluster_collection
            }
            
            response = requests.post(
                url,
                auth=self.config.get_auth_tuple(),
                json=payload,
                timeout=self.config.er.foxx_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                clusters = result.get("clusters", [])
                self.logger.info(f"WCC clustering completed: {len(clusters)} clusters found")
                return result
            else:
                return {"success": False, "error": f"Foxx service returned {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Foxx clustering failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _cluster_via_python(self, scored_pairs: List[Dict[str, Any]],
                           min_similarity: float, max_cluster_size: int) -> Dict[str, Any]:
        """Perform clustering via Python implementation using Weakly Connected Components"""
        try:
            import time
            start_time = time.time()
            
            # Build graph first
            graph_result = self._build_graph_via_python(
                scored_pairs, min_similarity, self.config.er.edge_collection)
            
            if not graph_result.get("success"):
                return {"success": False, "error": "Failed to build similarity graph"}
            
            edges = graph_result["results"]["edges"]
            vertices = graph_result["results"]["vertices"]
            
            # Perform weakly connected components clustering
            clusters = self._find_connected_components(edges, vertices)
            
            # Filter by cluster size
            valid_clusters = [c for c in clusters if len(c["member_ids"]) <= max_cluster_size]
            
            # Calculate cluster statistics
            cluster_list = []
            for i, cluster in enumerate(valid_clusters):
                cluster_edges = [e for e in edges if 
                               e["_from"] in cluster["member_ids"] and e["_to"] in cluster["member_ids"]]
                
                if cluster_edges:
                    avg_similarity = sum(e["similarity_score"] for e in cluster_edges) / len(cluster_edges)
                    min_similarity_score = min(e["similarity_score"] for e in cluster_edges)
                    max_similarity_score = max(e["similarity_score"] for e in cluster_edges)
                else:
                    avg_similarity = 0
                    min_similarity_score = 0
                    max_similarity_score = 0
                
                cluster_size = len(cluster["member_ids"])
                density = len(cluster_edges) / (cluster_size * (cluster_size - 1) / 2) if cluster_size > 1 else 0
                
                cluster_list.append({
                    "cluster_id": f"cluster_{i}",
                    "member_ids": cluster["member_ids"],
                    "cluster_size": cluster_size,
                    "edge_count": len(cluster_edges),
                    "average_similarity": avg_similarity,
                    "min_similarity": min_similarity_score,
                    "max_similarity": max_similarity_score,
                    "density": density,
                    "quality_score": self._calculate_cluster_quality(cluster_size, density, avg_similarity)
                })
            
            self.logger.info(f"Python clustering completed: {len(cluster_list)} clusters found")
            
            return {
                "success": True,
                "method": "python",
                "clusters": cluster_list,
                "statistics": {
                    "total_clusters": len(cluster_list),
                    "valid_clusters": len([c for c in cluster_list if c["quality_score"] > 0.5]),
                    "average_cluster_size": sum(c["cluster_size"] for c in cluster_list) / len(cluster_list) if cluster_list else 0,
                    "largest_cluster_size": max(c["cluster_size"] for c in cluster_list) if cluster_list else 0
                },
                "parameters": {
                    "min_similarity": min_similarity,
                    "max_cluster_size": max_cluster_size
                }
            }
            
        except Exception as e:
            self.logger.error(f"Python clustering failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _find_connected_components(self, edges: List[Dict[str, Any]], 
                                  vertices: List[str]) -> List[Dict[str, Any]]:
        """Find connected components using Union-Find algorithm"""
        # Build adjacency list
        graph = defaultdict(set)
        for edge in edges:
            from_node = edge["_from"]
            to_node = edge["_to"]
            graph[from_node].add(to_node)
            graph[to_node].add(from_node)
        
        visited = set()
        components = []
        
        def dfs(node: str, component: Set[str]):
            """Depth-first search to find connected component"""
            if node in visited:
                return
            
            visited.add(node)
            component.add(node)
            
            for neighbor in graph[node]:
                if neighbor not in visited:
                    dfs(neighbor, component)
        
        # Find all connected components
        for vertex in vertices:
            if vertex not in visited:
                component = set()
                dfs(vertex, component)
                if len(component) > 1:  # Only include components with multiple nodes
                    components.append({
                        "member_ids": list(component),
                        "size": len(component)
                    })
        
        return components
    
    def _calculate_cluster_quality(self, cluster_size: int, density: float, 
                                  avg_similarity: float) -> float:
        """Calculate cluster quality score"""
        # Quality factors
        size_factor = 1.0 if cluster_size >= self.config.er.min_cluster_size else 0.5
        density_factor = density if density >= self.config.er.cluster_density_threshold else density * 0.5
        similarity_factor = avg_similarity
        
        # Penalize very large clusters
        if cluster_size > 20:
            size_factor *= 0.8
        
        # Weighted quality score
        quality_score = (size_factor * 0.3 + density_factor * 0.4 + similarity_factor * 0.3)
        
        return min(quality_score, 1.0)
    
    def _validate_via_foxx(self, clusters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate clusters via Foxx service"""
        try:
            url = self.config.get_foxx_service_url("clustering/validate")
            
            payload = {
                "clusters": clusters,
                "qualityThresholds": self._get_quality_thresholds()
            }
            
            response = requests.post(
                url,
                auth=self.config.get_auth_tuple(),
                json=payload,
                timeout=self.config.er.foxx_timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"Foxx service returned {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Foxx cluster validation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _validate_via_python(self, clusters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate clusters via Python implementation"""
        try:
            validation_results = []
            quality_thresholds = self._get_quality_thresholds()
            
            for cluster in clusters:
                validation_result = self._validate_single_cluster(cluster, quality_thresholds)
                validation_results.append(validation_result)
            
            # Generate summary statistics
            valid_clusters = [r for r in validation_results if r["is_valid"]]
            quality_scores = [r["quality_score"] for r in validation_results]
            
            summary = {
                "total_clusters": len(clusters),
                "valid_clusters": len(valid_clusters),
                "invalid_clusters": len(clusters) - len(valid_clusters),
                "average_quality_score": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
                "validation_rate": len(valid_clusters) / len(clusters) if clusters else 0
            }
            
            return {
                "success": True,
                "method": "python",
                "validation_results": validation_results,
                "summary": summary,
                "quality_thresholds": quality_thresholds
            }
            
        except Exception as e:
            self.logger.error(f"Python cluster validation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _validate_single_cluster(self, cluster: Dict[str, Any], 
                                thresholds: Dict[str, float]) -> Dict[str, Any]:
        """Validate a single cluster against quality thresholds"""
        cluster_size = cluster.get("cluster_size", 0)
        density = cluster.get("density", 0)
        avg_similarity = cluster.get("average_similarity", 0)
        min_similarity = cluster.get("min_similarity", 0)
        max_similarity = cluster.get("max_similarity", 0)
        
        # Quality checks
        quality_metrics = {
            "size_adequate": cluster_size >= thresholds["min_cluster_size"] and cluster_size <= thresholds["max_cluster_size"],
            "density_adequate": density >= thresholds["min_density"],
            "similarity_adequate": avg_similarity >= thresholds["min_avg_similarity"],
            "score_range_reasonable": (max_similarity - min_similarity) <= thresholds["max_score_range"]
        }
        
        # Calculate overall quality score
        passed_metrics = sum(quality_metrics.values())
        total_metrics = len(quality_metrics)
        quality_score = passed_metrics / total_metrics
        
        is_valid = quality_score >= thresholds["min_quality_score"]
        
        return {
            "cluster_id": cluster.get("cluster_id"),
            "is_valid": is_valid,
            "quality_score": quality_score,
            "quality_metrics": quality_metrics,
            "cluster_size": cluster_size,
            "density": density,
            "average_similarity": avg_similarity
        }
    
    def _get_quality_thresholds(self) -> Dict[str, float]:
        """Get quality thresholds for cluster validation"""
        return {
            "min_cluster_size": self.config.er.min_cluster_size,
            "max_cluster_size": self.config.er.max_cluster_size,
            "min_avg_similarity": self.config.er.min_average_similarity,
            "min_density": self.config.er.density_adequate_threshold,
            "max_score_range": self.config.er.max_score_range,
            "min_quality_score": self.config.er.quality_score_threshold
        }
