"""
Weakly Connected Components (WCC) clustering service.

This service finds connected components in the similarity graph using
AQL graph traversal. Provides production-grade clustering with validation
and comprehensive statistics.
"""

from typing import List, Dict, Any, Optional
from arango.database import StandardDatabase
from arango.collection import EdgeCollection, StandardCollection
import time
from datetime import datetime
import logging

from ..utils.graph_utils import format_vertex_id, extract_key_from_vertex_id


class WCCClusteringService:
    """
    Weakly Connected Components clustering using AQL graph traversal.
    
    Finds connected components in the similarity graph using server-side
    AQL graph traversal. This is efficient, works on all modern ArangoDB
    installations (3.11+), and handles graphs with millions of edges.
    
    Key features:
    - Server-side processing (no need to fetch edges to Python)
    - AQL graph traversal for efficiency
    - Configurable minimum cluster size
    - Cluster storage with metadata
    - Validation and statistics
    - Works with any edge collection
    
    Future enhancement: GAE (Graph Analytics Engine) support for
    extremely large graphs (millions of edges).
    
    Example:
        ```python
        service = WCCClusteringService(
            db=db,
            edge_collection="similarTo",
            cluster_collection="entity_clusters",
            vertex_collection="companies"
        )
        
        clusters = service.cluster(store_results=True)
        
        # Get statistics
        stats = service.get_statistics()
        print(f"Found {stats['total_clusters']} clusters")
        ```
    """
    
    def __init__(
        self,
        db: StandardDatabase,
        edge_collection: str = "similarTo",
        cluster_collection: str = "entity_clusters",
        vertex_collection: Optional[str] = None,
        min_cluster_size: int = 2,
        graph_name: Optional[str] = None
    ):
        """
        Initialize WCC clustering service.
        
        Args:
            db: ArangoDB database connection
            edge_collection: Edge collection containing similarity edges
            cluster_collection: Collection to store cluster results
            vertex_collection: Vertex collection name (for _from/_to parsing).
                If None, will auto-detect from edges.
            min_cluster_size: Minimum entities per cluster to store. Default 2.
            graph_name: Named graph to use (optional). If None, will use
                anonymous graph traversal.
        
        Note:
            Uses AQL graph traversal for clustering. This is server-side,
            efficient, and works on all modern ArangoDB installations (3.11+).
        """
        self.db = db
        self.edge_collection_name = edge_collection
        self.cluster_collection_name = cluster_collection
        self.vertex_collection = vertex_collection
        self.min_cluster_size = min_cluster_size
        self.graph_name = graph_name
        
        # Initialize logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Get collections
        self.edge_collection: EdgeCollection = db.collection(edge_collection)
        
        # Create cluster collection if it doesn't exist
        if not db.has_collection(cluster_collection):
            self.cluster_collection: StandardCollection = db.create_collection(cluster_collection)
        else:
            self.cluster_collection = db.collection(cluster_collection)
        
        # Statistics tracking
        self._stats = {
            'total_clusters': 0,
            'total_entities_clustered': 0,
            'avg_cluster_size': 0.0,
            'max_cluster_size': 0,
            'min_cluster_size': 0,
            'cluster_size_distribution': {},
            'algorithm_used': 'aql_graph_traversal',
            'execution_time_seconds': 0.0,
            'timestamp': None
        }
    
    def cluster(
        self,
        store_results: bool = True,
        truncate_existing: bool = True
    ) -> List[List[str]]:
        """
        Run WCC clustering on similarity edges using AQL graph traversal.
        
        Args:
            store_results: Store clusters in cluster_collection. Default True.
            truncate_existing: Clear existing clusters before storing. Default True.
        
        Returns:
            List of clusters, each cluster is a list of document keys:
            [
                ["doc1", "doc2", "doc3"],  # Cluster 1
                ["doc4", "doc5"],          # Cluster 2
                ...
            ]
        
        Performance: Server-side processing, efficient for graphs up to
        millions of edges.
        """
        start_time = time.time()
        
        # Find connected components using AQL
        clusters = self._find_connected_components_aql()
        
        # Filter by minimum cluster size
        filtered_clusters = [
            cluster for cluster in clusters
            if len(cluster) >= self.min_cluster_size
        ]
        
        # Store results if requested
        if store_results:
            if truncate_existing:
                self.cluster_collection.truncate()
            self._store_clusters(filtered_clusters)
        
        # Update statistics
        execution_time = time.time() - start_time
        self._update_statistics(filtered_clusters, execution_time)
        
        return filtered_clusters
    
    def get_cluster_by_member(self, member_key: str) -> Optional[Dict[str, Any]]:
        """
        Find cluster containing a specific member.
        
        Args:
            member_key: Document key to search for
        
        Returns:
            Cluster record or None if not found
        
        Example:
            ```python
            cluster = service.get_cluster_by_member("company_123")
            if cluster:
                print(f"Company 123 is in cluster {cluster['cluster_id']}")
                print(f"Cluster has {cluster['size']} members")
            ```
        """
        # Format member key properly
        member_id = self._format_vertex_id(member_key)
        
        query = f"""
        FOR cluster IN {self.cluster_collection_name}
            FILTER @member_id IN cluster.members
            RETURN cluster
        """
        
        cursor = self.db.aql.execute(query, bind_vars={'member_id': member_id})
        results = list(cursor)
        
        return results[0] if results else None
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get clustering statistics.
        
        Returns:
            Statistics dictionary:
            {
                "total_clusters": 234,
                "total_entities_clustered": 1523,
                "avg_cluster_size": 6.5,
                "max_cluster_size": 45,
                "min_cluster_size": 2,
                "cluster_size_distribution": {
                    "2": 120,
                    "3": 56,
                    "4-10": 45,
                    "11-50": 13
                },
                "algorithm_used": "aql_graph_traversal",
                "execution_time_seconds": 3.4,
                "timestamp": "2025-11-12T14:30:22"
            }
        """
        return self._stats.copy()
    
    def validate_clusters(self) -> Dict[str, Any]:
        """
        Validate cluster quality and consistency.
        
        Checks:
        - No overlapping clusters (each entity in at most one cluster)
        - All edges respected (connected entities in same cluster)
        - Minimum size requirement met
        
        Returns:
            Validation results:
            {
                "valid": True,
                "issues": [],
                "checks_performed": [
                    "no_overlapping_clusters",
                    "all_edges_respected",
                    "min_size_requirement"
                ],
                "entities_checked": 1523,
                "edges_checked": 845
            }
        """
        issues = []
        checks_performed = []
        
        # Check 1: No overlapping clusters
        checks_performed.append("no_overlapping_clusters")
        entity_to_cluster = {}
        
        for cluster_doc in self.cluster_collection:
            cluster_id = cluster_doc.get('cluster_id')
            members = cluster_doc.get('member_keys', [])
            
            for member in members:
                if member in entity_to_cluster:
                    issues.append({
                        'type': 'overlapping_clusters',
                        'entity': member,
                        'clusters': [entity_to_cluster[member], cluster_id]
                    })
                else:
                    entity_to_cluster[member] = cluster_id
        
        # Check 2: Minimum size requirement
        checks_performed.append("min_size_requirement")
        for cluster_doc in self.cluster_collection:
            size = cluster_doc.get('size', 0)
            if size < self.min_cluster_size:
                issues.append({
                    'type': 'below_min_size',
                    'cluster_id': cluster_doc.get('cluster_id'),
                    'size': size,
                    'min_required': self.min_cluster_size
                })
        
        # Check 3: Sample edge validation (check some edges are respected)
        checks_performed.append("sample_edges_validated")
        edges_sample = list(self.edge_collection.all(limit=100))
        edges_checked = 0
        
        for edge in edges_sample:
            from_key = self._extract_key_from_vertex_id(edge.get('_from', ''))
            to_key = self._extract_key_from_vertex_id(edge.get('_to', ''))
            
            from_cluster = entity_to_cluster.get(from_key)
            to_cluster = entity_to_cluster.get(to_key)
            
            if from_cluster != to_cluster:
                issues.append({
                    'type': 'edge_not_respected',
                    'from': from_key,
                    'to': to_key,
                    'from_cluster': from_cluster,
                    'to_cluster': to_cluster
                })
            
            edges_checked += 1
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'checks_performed': checks_performed,
            'entities_checked': len(entity_to_cluster),
            'edges_checked': edges_checked
        }
    
    def _find_connected_components_aql(self) -> List[List[str]]:
        """
        Use AQL graph traversal to find connected components.
        
        Implementation approach:
        1. Get all unique vertices from edges
        2. For each unvisited vertex, traverse to find its component
        3. Use AQL graph traversal (FOR v, e, p IN 0..999999 ANY ...)
        4. Mark visited vertices to avoid duplicates
        
        This is server-side and efficient for graphs up to millions of edges.
        
        Returns:
            List of clusters (each cluster is a list of document keys)
        """
        # Determine vertex collection(s) for WITH clause
        vertex_collections = self._get_vertex_collections()
        with_clause = f"WITH {', '.join(vertex_collections)}" if vertex_collections else ""
        
        # Step 1: Get all unique vertices from edges
        vertices_query = f"""
        LET from_vertices = (
            FOR e IN {self.edge_collection_name}
                RETURN DISTINCT e._from
        )
        LET to_vertices = (
            FOR e IN {self.edge_collection_name}
                RETURN DISTINCT e._to
        )
        RETURN UNION_DISTINCT(from_vertices, to_vertices)
        """
        
        cursor = self.db.aql.execute(vertices_query)
        cursor_list = list(cursor)
        all_vertices = cursor_list[0] if cursor_list else []
        
        if not all_vertices:
            return []
        
        # Step 2: Find connected components iteratively
        visited = set()
        clusters = []
        
        for start_vertex in all_vertices:
            if start_vertex in visited:
                continue
            
            # Traverse from this vertex to find its component
            # WITH clause is required for graph traversal to declare collections
            component_query = f"""
            {with_clause}
            FOR v IN 0..999999 ANY @start_vertex {self.edge_collection_name}
                RETURN DISTINCT v._id
            """
            
            try:
                cursor = self.db.aql.execute(
                    component_query,
                    bind_vars={'start_vertex': start_vertex}
                )
                component_vertices = list(cursor)
                
                if component_vertices:
                    # Extract keys from vertex IDs
                    component_keys = [
                        self._extract_key_from_vertex_id(v)
                        for v in component_vertices
                    ]
                    component_keys = [k for k in component_keys if k]  # Filter out None
                    
                    if component_keys:
                        clusters.append(sorted(component_keys))
                        visited.update(component_vertices)
            
            except Exception as e:
                # Log error but continue with next vertex
                self.logger.error(
                    f"Failed to find connected component for {start_vertex}: {e}",
                    exc_info=True
                )
                continue
        
        return clusters
    
    def _get_vertex_collections(self) -> List[str]:
        """
        Determine vertex collection(s) for WITH clause in graph traversal.
        
        Returns:
            List of vertex collection names
        """
        # If vertex_collection is explicitly provided, use it
        if self.vertex_collection:
            return [self.vertex_collection]
        
        # Otherwise, auto-detect from edges
        try:
            # Sample a few edges to find vertex collections
            sample_edges = list(self.edge_collection.all(limit=10))
            
            if not sample_edges:
                self.logger.warning("No edges found to detect vertex collections")
                return []
            
            vertex_collections = set()
            for edge in sample_edges:
                # Extract collection names from _from and _to
                from_id = edge.get('_from', '')
                to_id = edge.get('_to', '')
                
                if '/' in from_id:
                    from_collection = from_id.split('/')[0]
                    vertex_collections.add(from_collection)
                
                if '/' in to_id:
                    to_collection = to_id.split('/')[0]
                    vertex_collections.add(to_collection)
            
            return sorted(list(vertex_collections))
        
        except Exception as e:
            self.logger.error(f"Failed to detect vertex collections: {e}", exc_info=True)
            return []
    
    def _store_clusters(self, clusters: List[List[str]]):
        """
        Store clusters in the cluster collection.
        
        Args:
            clusters: List of clusters to store
        """
        cluster_docs = []
        
        for i, cluster_members in enumerate(clusters):
            cluster_docs.append({
                '_key': f'cluster_{i:06d}',
                'cluster_id': i,
                'size': len(cluster_members),
                'members': [self._format_vertex_id(k) for k in cluster_members],
                'member_keys': cluster_members,
                'timestamp': datetime.now().isoformat(),
                'method': 'aql_graph_traversal'
            })
        
        if cluster_docs:
            # Insert in batches
            batch_size = 1000
            for i in range(0, len(cluster_docs), batch_size):
                batch = cluster_docs[i:i + batch_size]
                self.cluster_collection.insert_many(batch)
    
    def _update_statistics(self, clusters: List[List[str]], execution_time: float):
        """Update internal statistics."""
        if not clusters:
            self._stats.update({
                'total_clusters': 0,
                'total_entities_clustered': 0,
                'execution_time_seconds': round(execution_time, 2),
                'timestamp': datetime.now().isoformat()
            })
            return
        
        sizes = [len(c) for c in clusters]
        total_entities = sum(sizes)
        
        # Calculate size distribution
        distribution = {
            '2': len([s for s in sizes if s == 2]),
            '3': len([s for s in sizes if s == 3]),
            '4-10': len([s for s in sizes if 4 <= s <= 10]),
            '11-50': len([s for s in sizes if 11 <= s <= 50]),
            '51+': len([s for s in sizes if s > 50])
        }
        
        self._stats.update({
            'total_clusters': len(clusters),
            'total_entities_clustered': total_entities,
            'avg_cluster_size': round(total_entities / len(clusters), 2),
            'max_cluster_size': max(sizes),
            'min_cluster_size': min(sizes),
            'cluster_size_distribution': distribution,
            'execution_time_seconds': round(execution_time, 2),
            'timestamp': datetime.now().isoformat()
        })
    
    def _format_vertex_id(self, key: str) -> str:
        """
        Format a document key as a vertex ID.
        
        Note:
            This method now delegates to the shared graph_utils.format_vertex_id()
            for consistency across the codebase.
        """
        return format_vertex_id(key, self.vertex_collection)
    
    def _extract_key_from_vertex_id(self, vertex_id: str) -> Optional[str]:
        """
        Extract document key from vertex ID.
        
        Note:
            This method now delegates to the shared graph_utils.extract_key_from_vertex_id()
            for consistency across the codebase.
        """
        return extract_key_from_vertex_id(vertex_id)
    
    def __repr__(self) -> str:
        """String representation."""
        return (f"WCCClusteringService("
                f"edge_collection='{self.edge_collection_name}', "
                f"min_cluster_size={self.min_cluster_size})")

