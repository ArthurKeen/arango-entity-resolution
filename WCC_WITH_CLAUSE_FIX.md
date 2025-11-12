# WCC Clustering Service - Missing WITH Clause Fix

## Issue
The WCC clustering service was generating AQL graph traversal queries without the required `WITH` clause. This caused errors when ArangoDB attempted to traverse collections that weren't explicitly declared.

### Error Message
```
[HTTP 400] [ERR 1521] AQL: collection not known to traversal: 'duns'. 
please add 'WITH duns' as the first line in your AQL
```

## Root Cause
In `src/entity_resolution/services/wcc_clustering_service.py`, the `_find_connected_components_aql()` method was generating graph traversal queries like:

```aql
FOR v IN 0..999999 ANY @start_vertex similarTo
    RETURN DISTINCT v._id
```

This query lacks the `WITH` clause that declares which vertex collection(s) will be traversed.

## Solution
Added automatic detection and inclusion of the `WITH` clause in graph traversal queries.

### Changes Made

1. **Added `_get_vertex_collections()` helper method** (lines 387-425)
   - Auto-detects vertex collections from edge `_from` and `_to` fields
   - Falls back to explicitly provided `vertex_collection` parameter
   - Samples up to 10 edges to determine all vertex collections in use
   - Returns sorted list of unique collection names

2. **Updated `_find_connected_components_aql()` method** (lines 303-356)
   - Calls `_get_vertex_collections()` to determine collections
   - Builds `WITH` clause from detected collections
   - Adds `WITH` clause to the graph traversal query
   - Now generates proper AQL:

```aql
WITH duns
FOR v IN 0..999999 ANY @start_vertex similarTo
    RETURN DISTINCT v._id
```

## Benefits
- **Fixes production error**: Resolves the "collection not known to traversal" error
- **Handles multiple collections**: Automatically detects and includes all vertex collections
- **Backward compatible**: Works with both explicitly provided and auto-detected collections
- **Robust error handling**: Gracefully handles cases with no edges or detection failures

## Testing Recommendations
1. Test with single vertex collection (e.g., `companies`)
2. Test with multiple vertex collections (e.g., edges between different entity types)
3. Test with explicitly provided `vertex_collection` parameter
4. Test with auto-detection (no `vertex_collection` provided)
5. Test with empty edge collection

## Example Usage

```python
# Auto-detection (recommended)
service = WCCClusteringService(
    db=db,
    edge_collection="similarTo",
    cluster_collection="entity_clusters"
)

# Explicit vertex collection
service = WCCClusteringService(
    db=db,
    edge_collection="similarTo",
    cluster_collection="entity_clusters",
    vertex_collection="duns"  # Explicitly specify
)

clusters = service.cluster(store_results=True)
```

## Files Modified
- `src/entity_resolution/services/wcc_clustering_service.py`
  - Added `_get_vertex_collections()` method
  - Updated `_find_connected_components_aql()` to include WITH clause

## Date
November 12, 2025

