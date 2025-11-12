# Graph Algorithms in Entity Resolution: UPSERT-based Edge Creation and WCC Clustering

## Overview

This document explains why our entity resolution system uses graph-based algorithms and how they solve fundamental challenges in record linkage and deduplication.

## The Entity Resolution Challenge

Entity resolution is fundamentally a **connectivity problem**. When we determine that two records are similar (e.g., "John Smith" and "Jon Smith"), we're not just making a binary decision - we're establishing a **relationship** that has broader implications for the entire dataset.

### The Transitive Relationship Problem

Consider this real-world scenario:
- **Record A**: "John Smith, 123 Main St"
- **Record B**: "Jon Smith, 123 Main Street" 
- **Record C**: "J. Smith, 123 Main St"

Traditional pairwise matching might find:
- A ↔ B (similar names, same address) → Score: 0.85
- A ↔ C (similar names, same address) → Score: 0.75
- B ↔ C (different name format) → Score: 0.65

If our threshold is 0.7, traditional approaches would miss the B ↔ C connection, resulting in two separate clusters: {A, B} and {A, C}, which doesn't make sense since A appears in both.

## The Graph Solution

### Why Graphs?

**Graph-based entity resolution** treats similarity relationships as edges in a graph, where:
- **Vertices** = Individual records
- **Edges** = Similarity relationships above threshold
- **Connected Components** = Entity clusters

This approach handles **transitive closure**: If A connects to B, and A connects to C, then A, B, and C should all be in the same entity cluster, even if B and C don't directly match well.

## UPSERT-based Edge Creation Strategy

### The Problem with Simple Edge Creation

Traditional approaches create edges with simple INSERT operations:
```sql
INSERT INTO similarities (_from, _to, score) VALUES (@from, @to, @score)
```

**Problems:**
1. **Duplicate edges** when processing runs multiple times
2. **No score evolution** when algorithms improve
3. **No historical context** about confidence
4. **Pipeline fragility** - failures mean starting over

### Our UPSERT Solution

```javascript
UPSERT { _from: @from, _to: @to }
INSERT {
  _from: @from,
  _to: @to,
  similarity_score: @score,
  field_scores: @fieldScores,
  is_match: @isMatch,
  algorithm: "fellegi_sunter",
  created_at: DATE_NOW(),
  update_count: 1
}
UPDATE {
  similarity_score: @forceUpdate ? @score : AVERAGE([OLD.similarity_score, @score]),
  field_scores: @forceUpdate ? @fieldScores : OLD.field_scores,
  is_match: @forceUpdate ? @isMatch : (OLD.is_match || @isMatch),
  updated_at: DATE_NOW(),
  update_count: OLD.update_count + 1
}
```

### Benefits of UPSERT Approach

#### 1. **Idempotency**
- Running the same similarity computation multiple times doesn't create duplicates
- Safe to re-run processing on failures or data updates
- Essential for production systems with incremental processing

#### 2. **Score Evolution**
```javascript
similarity_score: AVERAGE([OLD.similarity_score, @score])
```
- New similarity scores are averaged with existing ones
- Improves accuracy over time as algorithms are refined
- Provides confidence through multiple computations

#### 3. **Robust Pipeline**
- **Partial failures** don't require complete restart
- **Incremental updates** when new records arrive
- **A/B testing** of different similarity algorithms
- **Historical tracking** with update counts and timestamps

#### 4. **Metadata Preservation**
- Tracks which algorithm generated the score
- Maintains field-level similarity details
- Records creation and update timestamps
- Counts how many times each edge has been updated

## Weakly Connected Components (WCC) Clustering

### The Algorithm

```javascript
GRAPH_WEAKLY_CONNECTED_COMPONENTS(
  @@edgeCollection,
  {
    weightAttribute: "similarity_score",
    threshold: @minSimilarity
  }
)
```

### Real-World Example

Consider these similarity relationships:
- Record A ↔ Record B: 0.85 similarity
- Record A ↔ Record C: 0.75 similarity  
- Record D ↔ Record E: 0.90 similarity
- Record B ↔ Record F: 0.80 similarity

With threshold 0.7, WCC creates:
- **Cluster 1**: [A, B, C, F] - all connected through A and B
- **Cluster 2**: [D, E] - connected directly

### Why WCC vs Simple Clustering?

#### 1. **Transitive Closure**
- If A → B and B → C, then A, B, C are in same cluster
- Even if A ↔ C similarity is below threshold individually
- Handles **chain connections**: A→B→C→D

#### 2. **Complex Relationship Patterns**
- **Star patterns**: A connects to B, C, D, E (A is the "hub")
- **Dense clusters**: Everyone connected to everyone  
- **Bridge connections**: Records that link separate groups

#### 3. **Natural Community Detection**
- Finds **meaningful groups** not just pairwise matches
- Handles **different similarity patterns** (some records might be "bridges")
- Discovers **hierarchical relationships** automatically

### Quality Validation

The system validates each cluster with multiple metrics:

```javascript
{
  cluster_id: "cluster_abc123",
  member_ids: [vertex_ids],
  cluster_size: 4,
  edge_count: 5,
  average_similarity: 0.82,
  min_similarity: 0.71,
  max_similarity: 0.95,
  density: 0.83,  // How interconnected the cluster is
  quality_score: 0.89
}
```

**Quality Metrics:**
- **Density**: `edge_count / (cluster_size * (cluster_size - 1) / 2)`
- **Size limits**: Prevents massive clusters (likely false positives)
- **Score coherence**: Ensures similar records are grouped together
- **Range validation**: Checks similarity score consistency

## Implementation Architecture

### Data Flow

```
Similarity Scores → UPSERT Edges → WCC Clustering → Quality Validation → Entity Clusters
      ↓                 ↓              ↓                    ↓               ↓
 Fellegi-Sunter    Graph Building   Community        Coherence      Final Clusters
   Framework         (idempotent)    Detection        Checking      + Metadata
```

### Performance Optimizations

1. **Database-Native Processing**: All operations within ArangoDB
2. **Efficient Graph Algorithms**: Native WCC implementation
3. **Batch Operations**: Process thousands of edges efficiently
4. **Incremental Updates**: Only process new/changed relationships
5. **Quality Thresholds**: Filter out low-quality clusters early

### Configuration Parameters

From our centralized configuration:

```javascript
// Clustering parameters
MAX_CLUSTER_SIZE: 100,           // Prevent runaway clusters
MIN_CLUSTER_SIZE: 2,             // At least a pair
CLUSTER_DENSITY_THRESHOLD: 0.3,  // Minimum interconnectedness
QUALITY_SCORE_THRESHOLD: 0.6,    // Overall quality threshold

// Graph building
MAX_SCORED_PAIRS_BATCH: 10000,   // Batch processing limit
UPPER_THRESHOLD: 2.0,            // Fellegi-Sunter upper bound
LOWER_THRESHOLD: -1.0,           // Fellegi-Sunter lower bound
```

## Advantages Over Traditional Approaches

### 1. **Mathematical Rigor**
- Based on established graph theory algorithms
- Proven scalability and performance characteristics
- Well-understood complexity: O(V + E) for WCC

### 2. **Handles Complex Cases**
- **Ambiguous matches**: Records that could belong to multiple entities
- **Partial information**: Missing fields don't break clustering
- **Data quality issues**: Robust to inconsistent similarity scores

### 3. **Production Ready**
- **Incremental processing**: Add new records without full recomputation
- **Fault tolerance**: UPSERT ensures recovery from failures
- **Monitoring**: Rich metadata for observability
- **Tunable**: Many parameters for different data quality scenarios

### 4. **Scalability**
- **Native database operations**: Leverages ArangoDB's optimizations
- **Parallel processing**: Graph algorithms can be parallelized
- **Memory efficient**: Streaming results for large datasets

## Use Cases and Examples

### E-commerce Customer Deduplication
```
Customer A: "John Doe, john.doe@email.com, 555-1234"
Customer B: "J. Doe, john.doe@gmail.com, 555-1234"  
Customer C: "John D., jdoe@email.com, 555-1234"
```
→ WCC clusters all three despite different email formats

### Healthcare Patient Matching
```
Patient A: "Smith, Mary, DOB: 1985-01-15, SSN: ***-**-1234"
Patient B: "Mary Smith, DOB: 01/15/1985, Insurance: ABC123"
Patient C: "M. Smith, DOB: 1/15/85, Phone: 555-9876"
```
→ WCC connects through partial information overlap

### Business Entity Resolution
```
Company A: "ABC Corp, 123 Business St, New York"
Company B: "ABC Corporation, 123 Business Street, NY"
Company C: "ABC Co., Tax ID: 12-3456789"
```
→ WCC handles name variations and incomplete data

This graph-based approach with UPSERT edge creation and WCC clustering provides a robust, scalable foundation for production entity resolution systems that can handle the complexity and ambiguity of real-world data.
