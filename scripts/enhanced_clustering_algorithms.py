#!/usr/bin/env python3
"""
Enhanced Clustering Algorithms

This script implements advanced clustering algorithms for better cluster quality
and more sophisticated entity resolution clustering.
"""

import sys
import os
import json
import time
import networkx as nx
from datetime import datetime
from typing import Dict, List, Any, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.services.clustering_service import ClusteringService
from entity_resolution.utils.config import get_config
from entity_resolution.utils.logging import get_logger

@dataclass
class ClusteringAlgorithm:
    """Clustering algorithm configuration."""
    name: str
    description: str
    parameters: Dict[str, Any]
    expected_behavior: str

class EnhancedClusteringAlgorithms:
    """Enhanced clustering algorithms for better entity resolution."""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.clustering_service = ClusteringService()
        
        # Advanced clustering algorithms
        self.algorithms = {
            "weighted_connected_components": ClusteringAlgorithm(
                name="Weighted Connected Components",
                description="Enhanced WCC with similarity score weights",
                parameters={"min_weight": 0.7, "max_cluster_size": 100},
                expected_behavior="Better cluster quality with weight-based connections"
            ),
            
            "hierarchical_clustering": ClusteringAlgorithm(
                name="Hierarchical Clustering",
                description="Agglomerative hierarchical clustering",
                parameters={"linkage": "average", "distance_threshold": 0.3},
                expected_behavior="Hierarchical cluster structure"
            ),
            
            "spectral_clustering": ClusteringAlgorithm(
                name="Spectral Clustering",
                description="Spectral clustering for non-convex clusters",
                parameters={"n_clusters": "auto", "affinity": "rbf"},
                expected_behavior="Handles non-convex cluster shapes"
            ),
            
            "dbscan_clustering": ClusteringAlgorithm(
                name="DBSCAN Clustering",
                description="Density-based clustering",
                parameters={"eps": 0.5, "min_samples": 2},
                expected_behavior="Handles noise and varying cluster densities"
            ),
            
            "community_detection": ClusteringAlgorithm(
                name="Community Detection",
                description="Graph-based community detection",
                parameters={"algorithm": "louvain", "resolution": 1.0},
                expected_behavior="Natural community structure detection"
            )
        }
    
    def weighted_connected_components(self, similarity_pairs: List[Dict[str, Any]], 
                                    min_weight: float = 0.7) -> List[List[str]]:
        """Enhanced WCC with similarity score weights."""
        print("? Running Weighted Connected Components...")
        
        # Create weighted graph
        G = nx.Graph()
        
        for pair in similarity_pairs:
            doc_a_id = pair.get('doc_a', {}).get('_id', '')
            doc_b_id = pair.get('doc_b', {}).get('_id', '')
            weight = pair.get('score', 0.0)
            
            if weight >= min_weight:
                G.add_edge(doc_a_id, doc_b_id, weight=weight)
        
        # Find connected components
        clusters = []
        for component in nx.connected_components(G):
            if len(component) > 1:  # Only clusters with multiple entities
                clusters.append(list(component))
        
        print(f"   ? Generated {len(clusters)} weighted clusters")
        return clusters
    
    def hierarchical_clustering(self, similarity_pairs: List[Dict[str, Any]], 
                               distance_threshold: float = 0.3) -> List[List[str]]:
        """Hierarchical clustering implementation."""
        print("? Running Hierarchical Clustering...")
        
        try:
            from sklearn.cluster import AgglomerativeClustering
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            
            # Create entity list and similarity matrix
            entities = set()
            for pair in similarity_pairs:
                entities.add(pair.get('doc_a', {}).get('_id', ''))
                entities.add(pair.get('doc_b', {}).get('_id', ''))
            
            entities = list(entities)
            n_entities = len(entities)
            
            if n_entities < 2:
                return []
            
            # Create similarity matrix
            similarity_matrix = np.eye(n_entities)
            entity_to_index = {entity: i for i, entity in enumerate(entities)}
            
            for pair in similarity_pairs:
                doc_a_id = pair.get('doc_a', {}).get('_id', '')
                doc_b_id = pair.get('doc_b', {}).get('_id', '')
                score = pair.get('score', 0.0)
                
                if doc_a_id in entity_to_index and doc_b_id in entity_to_index:
                    i = entity_to_index[doc_a_id]
                    j = entity_to_index[doc_b_id]
                    similarity_matrix[i][j] = score
                    similarity_matrix[j][i] = score
            
            # Convert similarity to distance
            distance_matrix = 1 - similarity_matrix
            
            # Perform hierarchical clustering
            clustering = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=distance_threshold,
                linkage='average',
                metric='precomputed'
            )
            
            cluster_labels = clustering.fit_predict(distance_matrix)
            
            # Group entities by cluster
            clusters = defaultdict(list)
            for entity, label in zip(entities, cluster_labels):
                clusters[label].append(entity)
            
            result_clusters = [cluster for cluster in clusters.values() if len(cluster) > 1]
            print(f"   ? Generated {len(result_clusters)} hierarchical clusters")
            return result_clusters
            
        except ImportError:
            print("   [WARN]?  scikit-learn not available, falling back to WCC")
            return self.weighted_connected_components(similarity_pairs)
    
    def spectral_clustering(self, similarity_pairs: List[Dict[str, Any]]) -> List[List[str]]:
        """Spectral clustering implementation."""
        print("? Running Spectral Clustering...")
        
        try:
            from sklearn.cluster import SpectralClustering
            import numpy as np
            
            # Create entity list and similarity matrix
            entities = set()
            for pair in similarity_pairs:
                entities.add(pair.get('doc_a', {}).get('_id', ''))
                entities.add(pair.get('doc_b', {}).get('_id', ''))
            
            entities = list(entities)
            n_entities = len(entities)
            
            if n_entities < 2:
                return []
            
            # Create similarity matrix
            similarity_matrix = np.eye(n_entities)
            entity_to_index = {entity: i for i, entity in enumerate(entities)}
            
            for pair in similarity_pairs:
                doc_a_id = pair.get('doc_a', {}).get('_id', '')
                doc_b_id = pair.get('doc_b', {}).get('_id', '')
                score = pair.get('score', 0.0)
                
                if doc_a_id in entity_to_index and doc_b_id in entity_to_index:
                    i = entity_to_index[doc_a_id]
                    j = entity_to_index[doc_b_id]
                    similarity_matrix[i][j] = score
                    similarity_matrix[j][i] = score
            
            # Determine optimal number of clusters
            n_clusters = min(max(2, n_entities // 3), 10)
            
            # Perform spectral clustering
            clustering = SpectralClustering(
                n_clusters=n_clusters,
                affinity='precomputed',
                random_state=42
            )
            
            cluster_labels = clustering.fit_predict(similarity_matrix)
            
            # Group entities by cluster
            clusters = defaultdict(list)
            for entity, label in zip(entities, cluster_labels):
                clusters[label].append(entity)
            
            result_clusters = [cluster for cluster in clusters.values() if len(cluster) > 1]
            print(f"   ? Generated {len(result_clusters)} spectral clusters")
            return result_clusters
            
        except ImportError:
            print("   [WARN]?  scikit-learn not available, falling back to WCC")
            return self.weighted_connected_components(similarity_pairs)
    
    def dbscan_clustering(self, similarity_pairs: List[Dict[str, Any]], 
                         eps: float = 0.5, min_samples: int = 2) -> List[List[str]]:
        """DBSCAN clustering implementation."""
        print("? Running DBSCAN Clustering...")
        
        try:
            from sklearn.cluster import DBSCAN
            import numpy as np
            
            # Create entity list and similarity matrix
            entities = set()
            for pair in similarity_pairs:
                entities.add(pair.get('doc_a', {}).get('_id', ''))
                entities.add(pair.get('doc_b', {}).get('_id', ''))
            
            entities = list(entities)
            n_entities = len(entities)
            
            if n_entities < 2:
                return []
            
            # Create similarity matrix
            similarity_matrix = np.eye(n_entities)
            entity_to_index = {entity: i for i, entity in enumerate(entities)}
            
            for pair in similarity_pairs:
                doc_a_id = pair.get('doc_a', {}).get('_id', '')
                doc_b_id = pair.get('doc_b', {}).get('_id', '')
                score = pair.get('score', 0.0)
                
                if doc_a_id in entity_to_index and doc_b_id in entity_to_index:
                    i = entity_to_index[doc_a_id]
                    j = entity_to_index[doc_b_id]
                    similarity_matrix[i][j] = score
                    similarity_matrix[j][i] = score
            
            # Convert similarity to distance
            distance_matrix = 1 - similarity_matrix
            
            # Perform DBSCAN clustering
            clustering = DBSCAN(
                eps=eps,
                min_samples=min_samples,
                metric='precomputed'
            )
            
            cluster_labels = clustering.fit_predict(distance_matrix)
            
            # Group entities by cluster
            clusters = defaultdict(list)
            for entity, label in zip(entities, cluster_labels):
                if label != -1:  # Exclude noise points
                    clusters[label].append(entity)
            
            result_clusters = [cluster for cluster in clusters.values() if len(cluster) > 1]
            noise_count = sum(1 for label in cluster_labels if label == -1)
            
            print(f"   ? Generated {len(result_clusters)} DBSCAN clusters")
            print(f"   ? Noise points: {noise_count}")
            return result_clusters
            
        except ImportError:
            print("   [WARN]?  scikit-learn not available, falling back to WCC")
            return self.weighted_connected_components(similarity_pairs)
    
    def community_detection(self, similarity_pairs: List[Dict[str, Any]]) -> List[List[str]]:
        """Community detection using graph algorithms."""
        print("? Running Community Detection...")
        
        try:
            import networkx.algorithms.community as nx_comm
            
            # Create weighted graph
            G = nx.Graph()
            
            for pair in similarity_pairs:
                doc_a_id = pair.get('doc_a', {}).get('_id', '')
                doc_b_id = pair.get('doc_b', {}).get('_id', '')
                weight = pair.get('score', 0.0)
                
                if weight > 0.3:  # Only add edges with reasonable similarity
                    G.add_edge(doc_a_id, doc_b_id, weight=weight)
            
            if len(G.nodes()) < 2:
                return []
            
            # Use Louvain community detection
            communities = nx_comm.louvain_communities(G, weight='weight')
            
            # Convert to list format
            clusters = [list(community) for community in communities if len(community) > 1]
            
            print(f"   ? Generated {len(clusters)} community clusters")
            return clusters
            
        except Exception as e:
            print(f"   [WARN]?  Community detection failed: {e}, falling back to WCC")
            return self.weighted_connected_components(similarity_pairs)
    
    def evaluate_clustering_quality(self, clusters: List[List[str]], 
                                   similarity_pairs: List[Dict[str, Any]]) -> Dict[str, float]:
        """Evaluate clustering quality metrics."""
        if not clusters:
            return {"silhouette_score": 0.0, "modularity": 0.0, "coverage": 0.0}
        
        try:
            from sklearn.metrics import silhouette_score
            import numpy as np
            
            # Create entity-to-cluster mapping
            entity_to_cluster = {}
            for i, cluster in enumerate(clusters):
                for entity in cluster:
                    entity_to_cluster[entity] = i
            
            # Calculate intra-cluster similarity
            intra_cluster_similarities = []
            inter_cluster_similarities = []
            
            for pair in similarity_pairs:
                doc_a_id = pair.get('doc_a', {}).get('_id', '')
                doc_b_id = pair.get('doc_b', {}).get('_id', '')
                score = pair.get('score', 0.0)
                
                cluster_a = entity_to_cluster.get(doc_a_id, -1)
                cluster_b = entity_to_cluster.get(doc_b_id, -1)
                
                if cluster_a == cluster_b and cluster_a != -1:
                    intra_cluster_similarities.append(score)
                elif cluster_a != cluster_b and cluster_a != -1 and cluster_b != -1:
                    inter_cluster_similarities.append(score)
            
            # Calculate metrics
            avg_intra_similarity = np.mean(intra_cluster_similarities) if intra_cluster_similarities else 0.0
            avg_inter_similarity = np.mean(inter_cluster_similarities) if inter_cluster_similarities else 0.0
            
            # Silhouette-like score
            silhouette_score = avg_intra_similarity - avg_inter_similarity
            
            # Coverage (percentage of entities in clusters)
            total_entities = len(set(entity_to_cluster.keys()))
            clustered_entities = len([e for e in entity_to_cluster.values() if e != -1])
            coverage = clustered_entities / total_entities if total_entities > 0 else 0.0
            
            # Modularity (simplified)
            modularity = avg_intra_similarity / (avg_intra_similarity + avg_inter_similarity) if (avg_intra_similarity + avg_inter_similarity) > 0 else 0.0
            
            return {
                "silhouette_score": silhouette_score,
                "modularity": modularity,
                "coverage": coverage,
                "avg_intra_similarity": avg_intra_similarity,
                "avg_inter_similarity": avg_inter_similarity
            }
            
        except ImportError:
            # Fallback metrics without scikit-learn
            total_entities = len(set([pair.get('doc_a', {}).get('_id', '') for pair in similarity_pairs] + 
                                   [pair.get('doc_b', {}).get('_id', '') for pair in similarity_pairs]))
            clustered_entities = sum(len(cluster) for cluster in clusters)
            coverage = clustered_entities / total_entities if total_entities > 0 else 0.0
            
            return {
                "silhouette_score": 0.0,
                "modularity": 0.0,
                "coverage": coverage,
                "avg_intra_similarity": 0.0,
                "avg_inter_similarity": 0.0
            }
    
    def compare_algorithms(self, similarity_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare all clustering algorithms."""
        print("? Comparing Enhanced Clustering Algorithms")
        print("="*60)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "algorithms": {},
            "best_algorithm": None,
            "recommendations": []
        }
        
        algorithm_performances = {}
        
        for algorithm_name, algorithm in self.algorithms.items():
            print(f"\n? Testing {algorithm_name}...")
            print(f"   Description: {algorithm.description}")
            
            start_time = time.time()
            
            try:
                if algorithm_name == "weighted_connected_components":
                    clusters = self.weighted_connected_components(similarity_pairs)
                elif algorithm_name == "hierarchical_clustering":
                    clusters = self.hierarchical_clustering(similarity_pairs)
                elif algorithm_name == "spectral_clustering":
                    clusters = self.spectral_clustering(similarity_pairs)
                elif algorithm_name == "dbscan_clustering":
                    clusters = self.dbscan_clustering(similarity_pairs)
                elif algorithm_name == "community_detection":
                    clusters = self.community_detection(similarity_pairs)
                else:
                    clusters = []
                
                execution_time = time.time() - start_time
                
                # Evaluate quality
                quality_metrics = self.evaluate_clustering_quality(clusters, similarity_pairs)
                
                algorithm_result = {
                    "algorithm": algorithm_name,
                    "description": algorithm.description,
                    "clusters": clusters,
                    "cluster_count": len(clusters),
                    "total_entities": sum(len(cluster) for cluster in clusters),
                    "execution_time": execution_time,
                    "quality_metrics": quality_metrics
                }
                
                results["algorithms"][algorithm_name] = algorithm_result
                
                # Calculate performance score
                performance_score = (
                    quality_metrics["silhouette_score"] * 0.4 +
                    quality_metrics["modularity"] * 0.3 +
                    quality_metrics["coverage"] * 0.3
                )
                algorithm_performances[algorithm_name] = performance_score
                
                print(f"   ? Clusters: {len(clusters)}")
                print(f"   ? Entities: {sum(len(cluster) for cluster in clusters)}")
                print(f"   ? Execution time: {execution_time:.3f}s")
                print(f"   ? Silhouette score: {quality_metrics['silhouette_score']:.3f}")
                print(f"   ? Modularity: {quality_metrics['modularity']:.3f}")
                print(f"   ? Coverage: {quality_metrics['coverage']:.3f}")
                print(f"   ? Performance score: {performance_score:.3f}")
                
            except Exception as e:
                print(f"   [FAIL] Algorithm failed: {e}")
                results["algorithms"][algorithm_name] = {
                    "algorithm": algorithm_name,
                    "error": str(e),
                    "clusters": [],
                    "cluster_count": 0
                }
                algorithm_performances[algorithm_name] = 0.0
        
        # Find best algorithm
        if algorithm_performances:
            best_algorithm = max(algorithm_performances.items(), key=lambda x: x[1])
            results["best_algorithm"] = {
                "name": best_algorithm[0],
                "performance_score": best_algorithm[1],
                "description": self.algorithms[best_algorithm[0]].description
            }
            
            print(f"\n? Best Algorithm: {best_algorithm[0]} (score: {best_algorithm[1]:.3f})")
        
        # Generate recommendations
        recommendations = []
        for algorithm_name, score in algorithm_performances.items():
            if score >= 0.8:
                recommendations.append(f"[PASS] {algorithm_name}: Excellent performance (score: {score:.3f})")
            elif score >= 0.6:
                recommendations.append(f"[PASS] {algorithm_name}: Good performance (score: {score:.3f})")
            elif score >= 0.4:
                recommendations.append(f"[WARN]?  {algorithm_name}: Acceptable performance (score: {score:.3f})")
            else:
                recommendations.append(f"[FAIL] {algorithm_name}: Needs improvement (score: {score:.3f})")
        
        results["recommendations"] = recommendations
        
        return results
    
    def run_enhanced_clustering_analysis(self) -> Dict[str, Any]:
        """Run comprehensive enhanced clustering analysis."""
        print("? ENHANCED CLUSTERING ALGORITHMS ANALYSIS")
        print("="*70)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Test data with various similarity scenarios
        test_similarity_pairs = [
            # High similarity pairs (should cluster together)
            {"doc_a": {"_id": "1", "name": "John Smith"}, "doc_b": {"_id": "2", "name": "Jon Smith"}, "score": 0.9},
            {"doc_a": {"_id": "2", "name": "Jon Smith"}, "doc_b": {"_id": "3", "name": "John Smith"}, "score": 0.9},
            {"doc_a": {"_id": "4", "name": "Jane Doe"}, "doc_b": {"_id": "5", "name": "Jane Doe"}, "score": 0.95},
            
            # Medium similarity pairs
            {"doc_a": {"_id": "6", "name": "Bob Johnson"}, "doc_b": {"_id": "7", "name": "Robert Johnson"}, "score": 0.7},
            {"doc_a": {"_id": "8", "name": "Alice Brown"}, "doc_b": {"_id": "9", "name": "Alice Browne"}, "score": 0.6},
            
            # Low similarity pairs (should not cluster)
            {"doc_a": {"_id": "10", "name": "Charlie Wilson"}, "doc_b": {"_id": "11", "name": "David Miller"}, "score": 0.2},
            {"doc_a": {"_id": "12", "name": "Eve Taylor"}, "doc_b": {"_id": "13", "name": "Frank Davis"}, "score": 0.1}
        ]
        
        # Compare all algorithms
        comparison_results = self.compare_algorithms(test_similarity_pairs)
        
        # Save comprehensive results
        report_file = f"enhanced_clustering_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(comparison_results, f, indent=2, default=str)
        
        print(f"\n? Enhanced clustering analysis report saved: {report_file}")
        
        return comparison_results

def main():
    """Run enhanced clustering algorithms analysis."""
    try:
        analyzer = EnhancedClusteringAlgorithms()
        results = analyzer.run_enhanced_clustering_analysis()
        return 0
    except Exception as e:
        print(f"[FAIL] Enhanced clustering analysis failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
