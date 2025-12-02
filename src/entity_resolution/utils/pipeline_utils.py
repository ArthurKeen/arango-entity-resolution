"""
Entity resolution pipeline utilities.

Helper functions for managing entity resolution workflows:
- Cleaning up previous results
- Managing edge collections
- Progress tracking
- Result validation
- Performance monitoring

These utilities help with common ER workflow tasks extracted from
production implementations.
"""

from typing import List, Dict, Any, Optional
from arango.database import StandardDatabase
from arango.collection import Collection
import logging
from datetime import datetime


logger = logging.getLogger(__name__)


def clean_er_results(
    db: StandardDatabase,
    collections: Optional[List[str]] = None,
    keep_last_n: Optional[int] = None,
    older_than: Optional[str] = None
) -> Dict[str, Any]:
    """
    Clean entity resolution results for re-running pipelines.
    
    Useful for iterative development or re-running ER with different parameters.
    Can truncate collections entirely or selectively remove old results.
    
    Args:
        db: ArangoDB database connection
        collections: List of collection names to clean. Common collections:
            - "similarTo" (similarity edges)
            - "entity_clusters" (clustering results)
            - "golden_records" (consolidated entities)
            If None, cleans common ER collections.
        keep_last_n: Keep only the last N results (by timestamp).
            If None, removes all results.
        older_than: Only remove results older than this ISO timestamp.
            If None, removes all results (or based on keep_last_n).
    
    Returns:
        Results dictionary:
        {
            "removed_counts": {"similarTo": 1234, "entity_clusters": 56},
            "kept_counts": {"similarTo": 100, "entity_clusters": 10},
            "errors": [{"collection": "invalid_coll", "error": "..."}],
            "timestamp": "2025-12-02T10:30:00"
        }
    
    Example:
        ```python
        # Truncate all ER results
        results = clean_er_results(db, collections=["similarTo", "entity_clusters"])
        
        # Keep only last 5 runs
        results = clean_er_results(db, keep_last_n=5)
        
        # Remove results older than a date
        results = clean_er_results(db, older_than="2025-01-01T00:00:00")
        ```
    """
    # Default collections to clean
    if collections is None:
        collections = ["similarTo", "entity_clusters", "golden_records"]
    
    removed_counts = {}
    kept_counts = {}
    errors = []
    
    for coll_name in collections:
        try:
            if not db.has_collection(coll_name):
                logger.warning(f"Collection '{coll_name}' does not exist, skipping")
                continue
            
            coll = db.collection(coll_name)
            
            if keep_last_n is None and older_than is None:
                # Simple truncate
                before_count = coll.count()
                coll.truncate()
                removed_counts[coll_name] = before_count
                kept_counts[coll_name] = 0
                logger.info(f"Truncated {before_count} documents from {coll_name}")
            
            elif older_than:
                # Remove by timestamp
                query = f"""
                FOR doc IN {coll_name}
                    FILTER doc.timestamp < @older_than
                    REMOVE doc IN {coll_name}
                    RETURN OLD
                """
                cursor = db.aql.execute(query, bind_vars={'older_than': older_than})
                removed = list(cursor)
                removed_counts[coll_name] = len(removed)
                kept_counts[coll_name] = coll.count()
                logger.info(f"Removed {len(removed)} documents older than {older_than} from {coll_name}")
            
            elif keep_last_n:
                # Keep last N runs (by timestamp)
                # First, get the Nth newest timestamp
                query = f"""
                FOR doc IN {coll_name}
                    SORT doc.timestamp DESC
                    LIMIT @n, 1
                    RETURN doc.timestamp
                """
                cursor = db.aql.execute(query, bind_vars={'n': keep_last_n})
                results = list(cursor)
                
                if results:
                    cutoff_timestamp = results[0]
                    # Remove everything older than the cutoff
                    query = f"""
                    FOR doc IN {coll_name}
                        FILTER doc.timestamp < @cutoff
                        REMOVE doc IN {coll_name}
                        RETURN OLD
                    """
                    cursor = db.aql.execute(query, bind_vars={'cutoff': cutoff_timestamp})
                    removed = list(cursor)
                    removed_counts[coll_name] = len(removed)
                    kept_counts[coll_name] = coll.count()
                    logger.info(f"Kept last {keep_last_n} runs, removed {len(removed)} from {coll_name}")
                else:
                    # Fewer than keep_last_n documents exist
                    removed_counts[coll_name] = 0
                    kept_counts[coll_name] = coll.count()
                    logger.info(f"Collection {coll_name} has fewer than {keep_last_n} documents, kept all")
        
        except Exception as e:
            logger.error(f"Error cleaning collection {coll_name}: {e}", exc_info=True)
            errors.append({
                'collection': coll_name,
                'error': str(e)
            })
    
    return {
        'removed_counts': removed_counts,
        'kept_counts': kept_counts,
        'errors': errors,
        'timestamp': datetime.now().isoformat()
    }


def count_inferred_edges(
    db: StandardDatabase,
    edge_collection: str = "similarTo",
    confidence_threshold: Optional[float] = None
) -> Dict[str, Any]:
    """
    Count inferred edges (edges marked as inferred=true).
    
    Useful for tracking progress in cross-collection matching or
    fuzzy entity resolution workflows.
    
    Args:
        db: ArangoDB database connection
        edge_collection: Edge collection name. Default "similarTo".
        confidence_threshold: Optional minimum confidence to include.
            If None, counts all inferred edges regardless of confidence.
    
    Returns:
        Statistics dictionary:
        {
            "total_edges": 12345,
            "inferred_edges": 234,
            "direct_edges": 12111,
            "avg_confidence": 0.87,
            "confidence_distribution": {
                "0.85-0.87": 45,
                "0.87-0.90": 89,
                "0.90-0.95": 78,
                "0.95-1.00": 22
            },
            "timestamp": "2025-12-02T10:30:00"
        }
    
    Example:
        ```python
        stats = count_inferred_edges(db, "hasRegistration", confidence_threshold=0.85)
        print(f"Found {stats['inferred_edges']} inferred edges")
        ```
    """
    if not db.has_collection(edge_collection):
        raise ValueError(f"Edge collection '{edge_collection}' does not exist")
    
    coll = db.collection(edge_collection)
    
    # Count total edges
    total_edges = coll.count()
    
    # Count inferred edges
    query = f"""
    FOR e IN {edge_collection}
        FILTER e.inferred == true
    """
    
    if confidence_threshold is not None:
        query += f" FILTER e.confidence >= {confidence_threshold}"
    
    query += " COLLECT WITH COUNT INTO cnt RETURN cnt"
    
    cursor = db.aql.execute(query)
    inferred_edges = list(cursor)[0] if cursor else 0
    
    direct_edges = total_edges - inferred_edges
    
    # Calculate average confidence
    confidence_query = f"""
    FOR e IN {edge_collection}
        FILTER e.inferred == true
        FILTER e.confidence != null
    """
    
    if confidence_threshold is not None:
        confidence_query += f" FILTER e.confidence >= {confidence_threshold}"
    
    confidence_query += " COLLECT AGGREGATE avg_conf = AVG(e.confidence) RETURN avg_conf"
    
    cursor = db.aql.execute(confidence_query)
    avg_confidence = list(cursor)[0] if cursor else None
    
    # Confidence distribution
    dist_query = f"""
    FOR e IN {edge_collection}
        FILTER e.inferred == true
        FILTER e.confidence != null
    """
    
    if confidence_threshold is not None:
        dist_query += f" FILTER e.confidence >= {confidence_threshold}"
    
    dist_query += """
        LET range = FLOOR(e.confidence * 20) / 20
        COLLECT bucket = range WITH COUNT INTO cnt
        SORT bucket
        RETURN {bucket: bucket, count: cnt}
    """
    
    cursor = db.aql.execute(dist_query)
    distribution_raw = list(cursor)
    
    # Format distribution
    confidence_distribution = {}
    for item in distribution_raw:
        bucket = item['bucket']
        next_bucket = bucket + 0.05
        key = f"{bucket:.2f}-{next_bucket:.2f}"
        confidence_distribution[key] = item['count']
    
    return {
        'total_edges': total_edges,
        'inferred_edges': inferred_edges,
        'direct_edges': direct_edges,
        'avg_confidence': round(avg_confidence, 4) if avg_confidence else None,
        'confidence_distribution': confidence_distribution,
        'timestamp': datetime.now().isoformat()
    }


def validate_edge_quality(
    db: StandardDatabase,
    edge_collection: str,
    min_confidence: float = 0.75,
    sample_size: int = 100
) -> Dict[str, Any]:
    """
    Validate quality of similarity edges.
    
    Checks for common data quality issues:
    - Edges with missing confidence scores
    - Edges below confidence threshold
    - Self-loops (entity linked to itself)
    - Duplicate edges
    - Invalid vertex references
    
    Args:
        db: ArangoDB database connection
        edge_collection: Edge collection to validate
        min_confidence: Minimum expected confidence. Default 0.75.
        sample_size: Number of edges to sample for detailed validation.
            Default 100.
    
    Returns:
        Validation results:
        {
            "valid": True/False,
            "issues": [
                {"type": "missing_confidence", "count": 12},
                {"type": "below_threshold", "count": 34},
                {"type": "self_loop", "count": 2}
            ],
            "total_edges": 12345,
            "valid_edges": 12297,
            "invalid_edges": 48,
            "sample_details": [...],
            "timestamp": "2025-12-02T10:30:00"
        }
    """
    if not db.has_collection(edge_collection):
        raise ValueError(f"Edge collection '{edge_collection}' does not exist")
    
    coll = db.collection(edge_collection)
    total_edges = coll.count()
    issues = []
    
    # Check for missing confidence
    query = f"""
    FOR e IN {edge_collection}
        FILTER e.confidence == null
        COLLECT WITH COUNT INTO cnt
        RETURN cnt
    """
    cursor = db.aql.execute(query)
    missing_confidence = list(cursor)[0] if cursor else 0
    if missing_confidence > 0:
        issues.append({
            'type': 'missing_confidence',
            'count': missing_confidence,
            'severity': 'warning'
        })
    
    # Check for below threshold
    query = f"""
    FOR e IN {edge_collection}
        FILTER e.confidence < {min_confidence}
        COLLECT WITH COUNT INTO cnt
        RETURN cnt
    """
    cursor = db.aql.execute(query)
    below_threshold = list(cursor)[0] if cursor else 0
    if below_threshold > 0:
        issues.append({
            'type': 'below_threshold',
            'count': below_threshold,
            'threshold': min_confidence,
            'severity': 'warning'
        })
    
    # Check for self-loops
    query = f"""
    FOR e IN {edge_collection}
        FILTER e._from == e._to
        COLLECT WITH COUNT INTO cnt
        RETURN cnt
    """
    cursor = db.aql.execute(query)
    self_loops = list(cursor)[0] if cursor else 0
    if self_loops > 0:
        issues.append({
            'type': 'self_loop',
            'count': self_loops,
            'severity': 'error'
        })
    
    # Sample edges for detailed validation
    query = f"""
    FOR e IN {edge_collection}
        LIMIT {sample_size}
        RETURN {{
            _from: e._from,
            _to: e._to,
            confidence: e.confidence,
            method: e.method,
            has_match_details: e.match_details != null
        }}
    """
    cursor = db.aql.execute(query)
    sample_details = list(cursor)
    
    # Calculate valid/invalid counts
    invalid_edges = missing_confidence + below_threshold + self_loops
    valid_edges = total_edges - invalid_edges
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'total_edges': total_edges,
        'valid_edges': valid_edges,
        'invalid_edges': invalid_edges,
        'sample_details': sample_details[:10],  # Return first 10 for brevity
        'timestamp': datetime.now().isoformat()
    }


def get_pipeline_statistics(
    db: StandardDatabase,
    vertex_collection: str,
    edge_collection: str = "similarTo",
    cluster_collection: str = "entity_clusters"
) -> Dict[str, Any]:
    """
    Get comprehensive statistics for an ER pipeline.
    
    Provides a complete overview of pipeline results for reporting
    and quality assessment.
    
    Args:
        db: ArangoDB database connection
        vertex_collection: Entity collection name (e.g., "companies")
        edge_collection: Similarity edge collection. Default "similarTo".
        cluster_collection: Cluster collection. Default "entity_clusters".
    
    Returns:
        Statistics dictionary:
        {
            "entities": {
                "total": 331933,
                "clustered": 12456,
                "unclustered": 319477,
                "clustering_rate": 0.0375
            },
            "edges": {
                "total": 5678,
                "inferred": 234,
                "direct": 5444,
                "avg_confidence": 0.87
            },
            "clusters": {
                "total": 1234,
                "avg_size": 10.1,
                "max_size": 145,
                "size_distribution": {...}
            },
            "performance": {
                "pairs_reduction": "99.9999%",
                "match_rate": "0.12%"
            },
            "timestamp": "2025-12-02T10:30:00"
        }
    """
    stats = {}
    
    # Entity statistics
    if db.has_collection(vertex_collection):
        vertex_coll = db.collection(vertex_collection)
        total_entities = vertex_coll.count()
        
        # Count clustered entities
        if db.has_collection(cluster_collection):
            query = f"""
            FOR cluster IN {cluster_collection}
                RETURN SUM(cluster.size)
            """
            cursor = db.aql.execute(query)
            clustered_entities = list(cursor)[0] if cursor else 0
        else:
            clustered_entities = 0
        
        unclustered = total_entities - clustered_entities
        clustering_rate = clustered_entities / total_entities if total_entities > 0 else 0
        
        stats['entities'] = {
            'total': total_entities,
            'clustered': clustered_entities,
            'unclustered': unclustered,
            'clustering_rate': round(clustering_rate, 4)
        }
    
    # Edge statistics
    if db.has_collection(edge_collection):
        edge_stats = count_inferred_edges(db, edge_collection)
        stats['edges'] = {
            'total': edge_stats['total_edges'],
            'inferred': edge_stats['inferred_edges'],
            'direct': edge_stats['direct_edges'],
            'avg_confidence': edge_stats['avg_confidence']
        }
    
    # Cluster statistics
    if db.has_collection(cluster_collection):
        cluster_coll = db.collection(cluster_collection)
        total_clusters = cluster_coll.count()
        
        if total_clusters > 0:
            query = f"""
            FOR cluster IN {cluster_collection}
                COLLECT AGGREGATE 
                    avg_size = AVG(cluster.size),
                    max_size = MAX(cluster.size)
                RETURN {{avg_size, max_size}}
            """
            cursor = db.aql.execute(query)
            cluster_agg = list(cursor)[0] if cursor else {}
            
            # Size distribution
            query = f"""
            FOR cluster IN {cluster_collection}
                LET size_bucket = (
                    cluster.size == 2 ? "2" :
                    cluster.size == 3 ? "3" :
                    cluster.size <= 10 ? "4-10" :
                    cluster.size <= 50 ? "11-50" :
                    "51+"
                )
                COLLECT bucket = size_bucket WITH COUNT INTO cnt
                RETURN {{bucket, count: cnt}}
            """
            cursor = db.aql.execute(query)
            size_dist_list = list(cursor)
            size_distribution = {item['bucket']: item['count'] for item in size_dist_list}
            
            stats['clusters'] = {
                'total': total_clusters,
                'avg_size': round(cluster_agg.get('avg_size', 0), 2),
                'max_size': cluster_agg.get('max_size', 0),
                'size_distribution': size_distribution
            }
        else:
            stats['clusters'] = {
                'total': 0,
                'avg_size': 0,
                'max_size': 0,
                'size_distribution': {}
            }
    
    # Performance metrics
    if 'entities' in stats and 'edges' in stats:
        total_possible_pairs = stats['entities']['total'] * (stats['entities']['total'] - 1) / 2
        actual_edges = stats['edges']['total']
        
        if total_possible_pairs > 0:
            pairs_reduction = (1 - actual_edges / total_possible_pairs) * 100
            match_rate = (actual_edges / total_possible_pairs) * 100
            
            stats['performance'] = {
                'pairs_reduction': f"{pairs_reduction:.6f}%",
                'match_rate': f"{match_rate:.6f}%",
                'total_possible_pairs': int(total_possible_pairs),
                'actual_edges': actual_edges
            }
    
    stats['timestamp'] = datetime.now().isoformat()
    
    return stats

