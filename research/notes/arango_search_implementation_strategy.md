# ArangoSearch Implementation Strategy for Entity Resolution

## Overview

Entity blocking is a crucial technique in entity resolution (ER) that drastically reduces the number of comparisons needed to find duplicate records. Instead of comparing every record against every other record (an O(N²) problem), blocking groups similar records into "blocks" using a common key, limiting comparisons to only the records within each block.

Using ArangoDB, the best way to implement blocking is by leveraging **ArangoSearch**, the built-in full-text search and ranking engine. Its powerful Analyzers and Views are specifically designed to create the kind of inverted indexes needed for efficient blocking.

## Implementing Entity Blocking in ArangoDB

Here's a step-by-step guide to adapting the blocking technique for ArangoDB, with a focus on practical implementation. For this example, let's assume you have a collection of person data named `Person`.

### 1. Data Ingestion: The Correct Starting Point

Your assumption is correct. The best practice is to load the raw source data "as is" into an ArangoDB document collection (e.g., `Person`). This allows you to work with the data in its native form without loss of information. Use `arangoimport` for large datasets for maximum efficiency.

### 2. The Blocking Strategy

Before you write any code, you must define a blocking strategy. A good blocking key is one that is likely to be similar for records representing the same real-world entity.

For people data, common blocking keys include:

- **Prefixes of names**: The first three letters of a last name (SMI for Smith)
- **Normalized values**: Lowercased and sanitized city names
- **N-grams**: Overlapping sequences of characters (e.g., "joh" "ohn" "hn " for "john"). This is particularly effective for catching typos

### 3. Implementation with ArangoSearch

This is the core of the ArangoDB blocking process. You'll create an ArangoSearch View that uses a custom Analyzer to generate your blocking keys.

#### a. Create a Custom Analyzer

The analyzer will tokenize your data according to your blocking strategy. A text analyzer with a ngram tokenizer is an excellent choice for a robust blocking strategy. It handles misspellings and variations naturally.

```javascript
// Create a custom analyzer for n-grams
// It will convert names to lowercase and generate n-grams of length 3
// e.g., "John Doe" -> ["joh", "ohn", "hn ", " do", "doe"]
db._create("my_ngram_analyzer", "text", {
  locale: "en.utf-8",
  stopwords: [],
  case: "lower",
  accent: false,
  stemming: false,
  ngram: {
    min: 3,
    max: 3,
    preserveOriginal: true
  }
});
```

#### b. Create an ArangoSearch View

Next, create a view that links to your Person collection and uses the analyzer on the properties you want to block on (e.g., `fullName`, `address`).

```javascript
// Create an ArangoSearch view for blocking
db._create("person_blocking_view", "arangosearch", {
  links: {
    Person: {
      analyzers: [
        "identity", // keeps the original document searchable
        "my_ngram_analyzer" // for creating the n-gram index used for blocking
      ],
      includeAllFields: true,
      fields: {
        fullName: {},
        address: {}
      }
    }
  }
});
```

#### c. Generate Blocks and Candidate Pairs

Now you can use a single AQL query with the `SEARCH` operation to find records that share one or more n-grams, effectively placing them in the same block.

The following query finds all Person documents that have at least a 3-gram match in their `fullName` or `address` to the document with key `1234567`.

```aql
LET targetDoc = DOCUMENT("Person/1234567")

FOR candidate IN person_blocking_view
  // Search for candidates with matching n-grams, exclude the target document
  SEARCH candidate._id != targetDoc._id AND (
    ANALYZER(PHRASE(candidate.fullName, targetDoc.fullName, "my_ngram_analyzer"), "my_ngram_analyzer") OR
    ANALYZER(PHRASE(candidate.address, targetDoc.address, "my_ngram_analyzer"), "my_ngram_analyzer")
  )
  LIMIT 100 // To limit the number of candidates for a single document
  RETURN {
    candidateId: candidate._id,
    targetId: targetDoc._id,
    score: BM25(candidate) // Optional: Use BM25 to rank the candidates
  }
```

This query returns a list of candidate pairs that are likely duplicates of `Person/1234567`.

### 4. Record Comparison & Entity Resolution

Once you have your candidate pairs, you can perform the final comparison using ArangoDB's fuzzy matching functions to assign a definitive match score.

```aql
// Let's assume you have a candidate pair from the previous step
LET docA = DOCUMENT("Person/1234567")
LET docB = DOCUMENT("Person/8910111")

// Calculate the similarity score using multiple properties
LET fullNameScore = NGRAM_SIMILARITY(docA.fullName, docB.fullName, 3)
LET addressScore = NGRAM_SIMILARITY(docA.address, docB.address, 3)

// Calculate a weighted average for the aggregate score
LET aggregateScore = (fullNameScore * 0.6) + (addressScore * 0.4)

// Return the score and a decision based on a threshold
RETURN {
  docA: docA._key,
  docB: docB._key,
  aggregateScore: aggregateScore,
  isMatch: aggregateScore > 0.8 // A simple threshold
}
```

## Evaluation of Your Proposed Approach & Improvements

Your proposed approach—load raw data → perform blocking/ER → export → reload into a knowledge graph—is a viable and logical starting point, but it's not the most efficient or idiomatic way to use ArangoDB's capabilities.

### Recommended Improvement: A Native Graph-Based Workflow

A much better approach is to keep the entire process within ArangoDB. This leverages its unique multi-model capabilities, avoiding the overhead of exporting and re-importing data.

1. **Load Raw Data**: As you suggested, load all raw source records into a `Person` document collection.

2. **Generate a Similarity Graph**: Instead of just generating a list of candidate pairs, your next step should be to create a graph.
   - For every pair of records identified by your blocking step with a high aggregate score, create a directed or undirected edge in a new `sameAs` edge collection. These edges represent a "similarity link" between two records.
   - You can use `UPSERT` statements in AQL to make this process robust and idempotent, ensuring a single edge between any two documents, regardless of how many properties match.

3. **Cluster with Weakly Connected Components (WCC)**: Now that you have a similarity graph, use ArangoDB's `GRAPH_WEAKLY_CONNECTED_COMPONENTS()` graph algorithm.
   - This algorithm will traverse the `sameAs` graph and group all records that are directly or indirectly connected into clusters. Each cluster represents a single real-world entity.

4. **Create Golden Records & Final Knowledge Graph**: The final step is to process these clusters (the WCC results) to create a definitive set of "golden records" and the final knowledge graph.
   - Using AQL, for each cluster, select or synthesize a master record (the "golden record"). You can use a `FOR` loop to iterate through the cluster members and apply logic (e.g., pick the record from the most trusted source, or combine non-conflicting attributes).
   - The golden records can be placed in a new `Entities` collection. You can then add edges from the original raw records to their corresponding golden record, finalizing your knowledge graph.

### Why this is a better approach:

- **Avoids Export/Import Overhead**: Keeps the entire process within a single database, which is far more performant and less prone to data loss or corruption.
- **Leverages Graph Power**: The graph-based approach is a natural fit for ER. It visually and programmatically represents the relationships between your data, making it easier to debug and understand.
- **Robustness**: WCC is highly effective at handling complex, indirect relationships (e.g., if A is linked to B, and B is linked to C, then A, B, and C are all part of the same community).

This native ArangoDB workflow for entity resolution is more sophisticated and scalable, making it a better choice for a robust software solution and an excellent foundation for your PRD.

