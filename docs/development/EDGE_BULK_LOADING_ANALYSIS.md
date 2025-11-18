# Edge Bulk Loading Analysis - AddressERService

**Date**: January 3, 2025  
**Issue**: Performance bottleneck when creating millions of edges  
**Context**: `dnb_er` project creating ~4M edges from 285K blocks

---

## Problem Analysis

### Current Implementation

The `AddressERService._create_edges()` method currently:

1. **Processes blocks one at a time**
   - 285,504 blocks = 285,504 separate `insert_many()` calls
   - Each block creates edges for all pairs within that block
   - Network round trip for every block

2. **Performance Characteristics**
   ```python
   # Current approach (per block)
   for block_key, addresses in blocks.items():
       edge_docs = []
       # Generate all pairs for this block
       for i, addr1_id in enumerate(addresses):
           for addr2_id in addresses[i + 1:]:
               edge_docs.append({...})
       
       # Insert this block's edges
       edge_collection.insert_many(edge_docs)  # 285K+ API calls!
   ```

3. **Estimated Performance**
   - **Network overhead**: 285,504 calls × ~10ms = ~2,855 seconds (48 minutes)
   - **Insert time**: ~4M edges × ~0.001s = ~4,000 seconds (67 minutes)
   - **Total estimated**: ~115 minutes (1.9 hours) ⚠️

### The Problem

For **~4 million edges**, the current approach is inefficient because:
- ❌ Too many network round trips (285K+ calls)
- ❌ No batching across blocks
- ❌ Python overhead for each block
- ❌ No ability to resume if interrupted

---

## Solution: CSV Export + arangoimport

### Why arangoimport is Better

**arangoimport** is ArangoDB's native bulk import tool:
- ✅ **10-50x faster** than API inserts
- ✅ **Single file import** (no network overhead)
- ✅ **Server-side optimization** (direct database writes)
- ✅ **Resumable** (can retry failed imports)
- ✅ **Memory efficient** (streaming import)

### Performance Comparison

| Method | Time (4M edges) | Network Calls | Notes |
|--------|------------------|---------------|-------|
| **Current (insert_many per block)** | ~115 min | 285K+ | Too many API calls |
| **Improved (batched insert_many)** | ~40 min | ~4K | Better, but still slow |
| **arangoimport (CSV)** | **~5-10 min** | 1 | **10-20x faster** ✅ |

---

## Recommended Implementation

### Option 1: Add CSV Export Method (Recommended)

Add a new method to `AddressERService` that exports edges to CSV:

```python
def _create_edges_via_csv(
    self, 
    blocks: Dict[str, List[str]], 
    csv_path: Optional[str] = None
) -> int:
    """
    Create edges by exporting to CSV and using arangoimport.
    
    Much faster for large edge sets (>100K edges).
    
    Args:
        blocks: Dictionary mapping block keys to lists of address IDs
        csv_path: Path to CSV file (auto-generated if None)
    
    Returns:
        Number of edges created
    """
    import csv
    import tempfile
    import subprocess
    import os
    
    # Generate CSV path
    if csv_path is None:
        csv_path = tempfile.mktemp(suffix='.csv', prefix='address_edges_')
    
    self.logger.info(f"Exporting edges to CSV: {csv_path}")
    
    # Calculate total edges
    total_edges = sum(
        (len(addrs) * (len(addrs) - 1)) // 2
        for addrs in blocks.values()
    )
    
    self.logger.info(f"Will export ~{total_edges:,} edges to CSV")
    
    # Export to CSV
    edges_written = 0
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow(['_from', '_to', 'block_key', 'timestamp', 'type'])
        
        # Write edges
        timestamp = datetime.now().isoformat()
        for block_key, addresses in blocks.items():
            for i, addr1_id in enumerate(addresses):
                for addr2_id in addresses[i + 1:]:
                    writer.writerow([
                        addr1_id,
                        addr2_id,
                        block_key,
                        timestamp,
                        'address_sameAs'
                    ])
                    edges_written += 1
                    
                    # Progress logging
                    if edges_written % 100000 == 0:
                        self.logger.info(f"  Exported {edges_written:,} edges...")
    
    self.logger.info(f"✓ Exported {edges_written:,} edges to CSV")
    
    # Import using arangoimport
    self.logger.info("Importing edges using arangoimport...")
    
    # Get database connection info
    db_name = self.db.name
    host = self.db.connection.host
    port = self.db.connection.port
    username = self.db.connection.username
    password = self.db.connection.password
    
    # Ensure collection exists
    if not self.db.has_collection(self.edge_collection):
        self.logger.info(f"Creating {self.edge_collection} edge collection...")
        self.db.create_collection(self.edge_collection, edge=True)
    else:
        self.logger.info(f"Truncating existing {self.edge_collection} collection...")
        self.db.collection(self.edge_collection).truncate()
    
    # Build arangoimport command
    cmd = [
        'arangoimport',
        '--server.endpoint', f'http://{host}:{port}',
        '--server.username', username,
        '--server.password', password,
        '--server.database', db_name,
        '--collection', self.edge_collection,
        '--type', 'csv',
        '--file', csv_path,
        '--create-collection', 'false',
        '--create-collection-type', 'edge'
    ]
    
    # Run arangoimport
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse output to get number imported
        # arangoimport outputs: "created: 3973489"
        import re
        match = re.search(r'created:\s*(\d+)', result.stdout)
        if match:
            edges_imported = int(match.group(1))
        else:
            edges_imported = edges_written  # Fallback
        
        self.logger.info(f"✓ Imported {edges_imported:,} edges via arangoimport")
        
        # Clean up CSV file
        if os.path.exists(csv_path):
            os.remove(csv_path)
            self.logger.debug(f"Cleaned up temporary CSV: {csv_path}")
        
        return edges_imported
        
    except subprocess.CalledProcessError as e:
        self.logger.error(f"arangoimport failed: {e}")
        self.logger.error(f"stdout: {e.stdout}")
        self.logger.error(f"stderr: {e.stderr}")
        raise
    except FileNotFoundError:
        self.logger.error("arangoimport not found. Install ArangoDB client tools.")
        self.logger.info("Falling back to standard insert_many method...")
        return self._create_edges(blocks)  # Fallback
```

### Option 2: Improve Current Batching

If arangoimport is not available, improve the current approach:

```python
def _create_edges(self, blocks: Dict[str, List[str]]) -> int:
    """
    Create sameAs edges for duplicate addresses.
    Improved version with better batching.
    """
    # ... existing collection setup ...
    
    # Calculate total edges
    total_edges = sum(
        (len(addrs) * (len(addrs) - 1)) // 2
        for addrs in blocks.values()
    )
    
    self.logger.info(f"Will create ~{total_edges:,} edges from {len(blocks):,} blocks")
    
    # Create edges in larger batches (across blocks)
    edge_collection: EdgeCollection = self.db.collection(self.edge_collection)
    edges_created = 0
    batch = []
    batch_size = 10000  # Larger batches
    
    timestamp = datetime.now().isoformat()
    
    for block_key, addresses in blocks.items():
        # Generate all pairs for this block
        for i, addr1_id in enumerate(addresses):
            for addr2_id in addresses[i + 1:]:
                batch.append({
                    '_from': addr1_id,
                    '_to': addr2_id,
                    'block_key': block_key,
                    'timestamp': timestamp,
                    'type': 'address_sameAs'
                })
                
                # Insert when batch is full
                if len(batch) >= batch_size:
                    edge_collection.insert_many(batch)
                    edges_created += len(batch)
                    batch = []
                    
                    # Progress logging
                    if edges_created % 100000 == 0:
                        self.logger.info(f"  Created {edges_created:,} edges...")
    
    # Insert remaining edges
    if batch:
        edge_collection.insert_many(batch)
        edges_created += len(batch)
    
    self.logger.info(f"✓ Created {edges_created:,} sameAs edges")
    return edges_created
```

**Improvement**: Reduces API calls from 285K to ~400 (100x reduction)

---

## Implementation Plan

### Phase 1: Add CSV Export Method (Recommended)

1. **Add `_create_edges_via_csv()` method** to `AddressERService`
2. **Add configuration option** to choose method:
   ```python
   service.run(
       create_edges=True,
       use_csv_import=True,  # New option
       csv_path=None  # Auto-generate if None
   )
   ```
3. **Auto-detect arangoimport availability**
4. **Fallback to improved batching** if arangoimport not available

### Phase 2: Make it the Default for Large Datasets

- Auto-select CSV method when edge count > 100K
- Keep current method for smaller datasets (< 10K edges)

---

## Performance Estimates

### For 4M Edges (285K blocks)

| Method | Time | API Calls | Notes |
|--------|------|-----------|-------|
| **Current** | ~115 min | 285K | Too slow |
| **Improved Batching** | ~40 min | ~400 | Better |
| **CSV + arangoimport** | **~5-10 min** | 1 | **Best** ✅ |

### For 100K Edges (10K blocks)

| Method | Time | API Calls | Notes |
|--------|------|-----------|-------|
| **Current** | ~3 min | 10K | Acceptable |
| **Improved Batching** | ~1 min | ~10 | Good |
| **CSV + arangoimport** | **~30 sec** | 1 | **Best** ✅ |

---

## Recommendations

### Immediate (High Priority)

1. ✅ **Add CSV export method** - 10-20x performance improvement
2. ✅ **Improve current batching** - 3-4x improvement as fallback
3. ✅ **Auto-select method** based on edge count

### Short Term

4. Add progress callbacks for CSV export
5. Add resume capability (checkpoint CSV writing)
6. Add validation (verify imported edge count)

### Long Term

7. Consider AQL-based edge creation (single query)
8. Add streaming support for very large datasets
9. Add parallel import support

---

## Code Changes Required

### File: `src/entity_resolution/services/address_er_service.py`

1. Add `_create_edges_via_csv()` method
2. Improve `_create_edges()` batching
3. Add `use_csv_import` parameter to `run()` method
4. Add auto-detection logic

### Dependencies

- `arangoimport` must be in PATH (part of ArangoDB client tools)
- Or provide installation instructions

---

## Conclusion

**Yes, using CSV + arangoimport is significantly better** for large edge sets:

- ✅ **10-20x faster** than current approach
- ✅ **Single import operation** vs 285K+ API calls
- ✅ **Server-side optimization**
- ✅ **Resumable and reliable**

**Recommendation**: Implement CSV export method as primary approach for large datasets (>100K edges), with improved batching as fallback.

---

**Next Steps**: 
1. Implement `_create_edges_via_csv()` method
2. Add configuration option
3. Test with dnb_er dataset
4. Update documentation

