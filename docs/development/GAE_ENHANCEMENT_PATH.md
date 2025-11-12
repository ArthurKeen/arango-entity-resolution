# GAE Enhancement Path for WCC Clustering

**Date:** November 12, 2025  
**Status:** Future Enhancement Documentation

---

## Overview

This document outlines the path for adding GAE (Graph Analytics Engine) support to `WCCClusteringService` as a future enhancement for handling extremely large graphs.

### Current Implementation

**AQL Graph Traversal (Primary)**
- Server-side processing
- Works on all ArangoDB 3.11+
- Efficient for graphs up to millions of edges
- No additional backend requirements

### Why GAE?

**Graph Analytics Engine (GAE)** is ArangoDB's optimized graph analytics engine designed for:
- Very large graphs (millions to billions of edges)
- Complex graph algorithms
- Distributed processing
- Enhanced performance for large-scale analytics

---

## When to Add GAE Support

### Triggers for Implementation

1. **User Demand**
   - Multiple users report performance issues with large graphs
   - Users specifically request GAE support
   - Community feedback indicates need

2. **Performance Requirements**
   - Graphs exceeding 10 million edges
   - Clustering time exceeds acceptable thresholds
   - Memory constraints with current approach

3. **ArangoDB Adoption**
   - GAE becomes widely available in target environments
   - Backend capabilities commonly enabled
   - Enterprise deployments standard

### Current Assessment

**As of November 2025:**
- AQL implementation handles typical use cases efficiently
- Most ER graphs are < 1 million edges
- GAE requires additional backend configuration
- **Recommendation:** Wait for user demand

---

## GAE Requirements

### Technical Requirements

1. **ArangoDB Version**
   - ArangoDB 3.11+ with GAE capabilities enabled
   - Enterprise Edition (GAE may be enterprise-only)

2. **Backend Configuration**
   - Graph Analytics Engine backend enabled
   - Sufficient memory allocation for GAE
   - Proper permissions configured

3. **Python Driver**
   - python-arango 8.0+ with GAE support
   - Access to GAE API methods

### Detection Code

```python
def _is_gae_available(self) -> bool:
    """
    Check if GAE is available in this ArangoDB instance.
    
    Returns:
        True if GAE is available and enabled
    """
    try:
        # Check ArangoDB version
        server_version = self.db.version()
        version_number = server_version.get('version', '')
        
        # GAE available in 3.11+
        if not version_number.startswith('3.11') and not version_number.startswith('3.12'):
            return False
        
        # Check if GAE endpoint exists
        # (Specific check depends on GAE API)
        # This is placeholder - actual implementation depends on GAE API
        
        return True
    except Exception:
        return False
```

---

## Implementation Plan

### Phase 1: API Design

Add GAE support as an optional enhancement:

```python
class WCCClusteringService:
    def __init__(
        self,
        db: StandardDatabase,
        edge_collection: str = "similarTo",
        cluster_collection: str = "entity_clusters",
        vertex_collection: Optional[str] = None,
        min_cluster_size: int = 2,
        graph_name: Optional[str] = None,
        prefer_gae: bool = False  # NEW: Use GAE if available
    ):
        """
        prefer_gae: If True, use GAE when available. Falls back to AQL
            if GAE not available. Default False (always use AQL).
        """
        self.prefer_gae = prefer_gae
        ...
```

### Phase 2: GAE Implementation

Add GAE clustering method:

```python
def _find_connected_components_gae(self) -> List[List[str]]:
    """
    Use GAE (Graph Analytics Engine) WCC algorithm.
    
    GAE is ArangoDB's optimized graph analytics engine for
    large graphs. Requires additional backend capabilities.
    
    Returns:
        List of clusters (each cluster is a list of document keys)
    
    Raises:
        RuntimeError: If GAE not available
    """
    # Check GAE availability
    if not self._is_gae_available():
        raise RuntimeError(
            "GAE not available. Requires ArangoDB 3.11+ Enterprise "
            "with Graph Analytics Engine enabled."
        )
    
    # Create temporary graph if needed
    graph_name = self.graph_name or f"_temp_graph_{int(time.time())}"
    
    try:
        # Use GAE WCC algorithm
        # Note: Exact API depends on final GAE implementation
        
        # Example (placeholder - actual API may differ):
        result = self.db.execute_graph_analytics(
            algorithm='weakly_connected_components',
            graph=graph_name,
            edge_collections=[self.edge_collection_name],
            options={
                'min_component_size': self.min_cluster_size
            }
        )
        
        # Parse GAE results into cluster format
        clusters = self._parse_gae_results(result)
        
        return clusters
    
    finally:
        # Clean up temporary graph if created
        if not self.graph_name and graph_name.startswith('_temp_'):
            try:
                self.db.delete_graph(graph_name)
            except Exception:
                pass

def _parse_gae_results(self, gae_result: Any) -> List[List[str]]:
    """
    Parse GAE WCC results into standard cluster format.
    
    Args:
        gae_result: Result from GAE WCC algorithm
    
    Returns:
        List of clusters
    """
    # Implementation depends on GAE result format
    # This is a placeholder
    pass
```

### Phase 3: Algorithm Selection

Update cluster() method to support GAE:

```python
def cluster(
    self,
    store_results: bool = True,
    truncate_existing: bool = True
) -> List[List[str]]:
    """
    Run WCC clustering.
    
    Automatically selects best available algorithm:
    - GAE if prefer_gae=True and GAE available
    - AQL otherwise (fallback, works everywhere)
    """
    start_time = time.time()
    
    # Select algorithm
    if self.prefer_gae and self._is_gae_available():
        clusters = self._find_connected_components_gae()
        algorithm_used = 'gae'
    else:
        clusters = self._find_connected_components_aql()
        algorithm_used = 'aql_graph_traversal'
    
    # Filter and store
    filtered_clusters = [
        cluster for cluster in clusters
        if len(cluster) >= self.min_cluster_size
    ]
    
    if store_results:
        if truncate_existing:
            self.cluster_collection.truncate()
        self._store_clusters(filtered_clusters, algorithm_used)
    
    # Update statistics
    execution_time = time.time() - start_time
    self._stats['algorithm_used'] = algorithm_used
    self._update_statistics(filtered_clusters, execution_time)
    
    return filtered_clusters
```

---

## Testing Strategy

### Unit Tests

```python
def test_gae_availability_detection():
    """Test GAE availability detection."""
    service = WCCClusteringService(db, prefer_gae=True)
    is_available = service._is_gae_available()
    # Assert based on environment

def test_gae_fallback_to_aql():
    """Test fallback to AQL when GAE unavailable."""
    service = WCCClusteringService(db, prefer_gae=True)
    clusters = service.cluster()
    stats = service.get_statistics()
    # Should use AQL if GAE not available
    assert stats['algorithm_used'] in ['aql_graph_traversal', 'gae']

def test_gae_clustering(skip_if_unavailable=True):
    """Test GAE clustering if available."""
    service = WCCClusteringService(db, prefer_gae=True)
    if not service._is_gae_available() and skip_if_unavailable:
        pytest.skip("GAE not available")
    
    clusters = service.cluster()
    stats = service.get_statistics()
    assert stats['algorithm_used'] == 'gae'
    assert len(clusters) > 0
```

### Performance Benchmarks

Compare AQL vs GAE for various graph sizes:

```python
def benchmark_aql_vs_gae():
    """
    Compare performance of AQL vs GAE for different graph sizes.
    
    Graph sizes tested:
    - Small: 1K nodes, 5K edges
    - Medium: 100K nodes, 500K edges
    - Large: 1M nodes, 5M edges
    - Very Large: 10M nodes, 50M edges
    """
    results = {
        'aql': {},
        'gae': {}
    }
    
    for size in ['small', 'medium', 'large', 'very_large']:
        # Test AQL
        service_aql = WCCClusteringService(db, prefer_gae=False)
        start = time.time()
        clusters = service_aql.cluster()
        aql_time = time.time() - start
        results['aql'][size] = aql_time
        
        # Test GAE (if available)
        service_gae = WCCClusteringService(db, prefer_gae=True)
        if service_gae._is_gae_available():
            start = time.time()
            clusters = service_gae.cluster()
            gae_time = time.time() - start
            results['gae'][size] = gae_time
    
    return results
```

---

## Migration Path

### For Existing Users

When GAE support is added:

1. **Default Behavior: No Change**
   - `prefer_gae=False` by default
   - Existing code continues using AQL
   - No breaking changes

2. **Opt-In GAE**
   - Users can set `prefer_gae=True`
   - Automatic fallback to AQL if unavailable
   - Clear messaging in logs

3. **Documentation**
   - When to use GAE (very large graphs)
   - How to enable GAE in ArangoDB
   - Performance comparison

### Example Migration

```python
# Before (current)
service = WCCClusteringService(
    db=db,
    edge_collection="similarTo"
)
clusters = service.cluster()

# After (with GAE support)
service = WCCClusteringService(
    db=db,
    edge_collection="similarTo",
    prefer_gae=True  # New parameter, optional
)
clusters = service.cluster()
# Uses GAE if available, falls back to AQL otherwise
```

---

## Documentation Requirements

### API Documentation

Update `WCCClusteringService` docstring:

```python
"""
Weakly Connected Components clustering.

Supports two algorithms:
1. AQL graph traversal (default, works everywhere)
   - Server-side, efficient
   - Works on all ArangoDB 3.11+
   - Good for graphs up to millions of edges

2. GAE (Graph Analytics Engine) - optional
   - Optimized for very large graphs
   - Requires GAE backend capabilities
   - Best for graphs > 10M edges
   - Set prefer_gae=True to enable

The service automatically falls back to AQL if GAE unavailable.
"""
```

### User Guide

Add section: "When to Use GAE"

```markdown
## When to Use GAE for Clustering

### Use AQL (Default)
- Most use cases
- Graphs < 10M edges
- Standard ArangoDB installations
- When backend setup is limited

### Use GAE (Optional)
- Very large graphs (> 10M edges)
- Performance-critical applications
- Enterprise deployments with GAE enabled
- When clustering time is a bottleneck

### Enabling GAE

1. Check ArangoDB version (3.11+ required)
2. Enable GAE in ArangoDB configuration
3. Verify GAE backend is running
4. Set `prefer_gae=True` in service initialization
```

---

## Reference Implementation

See `~/code/dnb_gae` for GAE WCC reference implementation (if available in customer environment).

---

## Decision Timeline

### Review Points

1. **6 Months (May 2026)**
   - Review user feedback
   - Assess GAE adoption in community
   - Evaluate performance reports

2. **1 Year (November 2026)**
   - Decide on GAE implementation
   - If proceeding, assign to roadmap
   - Create detailed implementation spec

3. **Ongoing**
   - Monitor ArangoDB GAE development
   - Track enterprise adoption
   - Respond to user requests

---

## Conclusion

**Current Status:** AQL implementation is sufficient for current needs

**GAE Addition:** Future enhancement based on:
- User demand
- Performance requirements
- GAE ecosystem maturity
- Enterprise adoption

**Recommendation:** Document this path, implement when triggered by above factors

---

**Document Version:** 1.0  
**Created:** November 12, 2025  
**Next Review:** May 2026

