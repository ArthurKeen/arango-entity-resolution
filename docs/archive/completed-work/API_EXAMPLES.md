# API Usage Examples

This document provides practical examples for common entity resolution scenarios using both REST and Python APIs.

## Table of Contents

- [REST API Examples](#rest-api-examples)
- [Python API Examples](#python-api-examples)
- [Integration Patterns](#integration-patterns)
- [Industry-Specific Examples](#industry-specific-examples)

---

## REST API Examples

### Example 1: Complete Setup and Initialization

Initialize the entity resolution system from scratch.

```bash
# Base URL
BASE_URL="http://localhost:8529/_db/entity_resolution/entity-resolution"
AUTH="root:your_password"

# 1. Check health
curl -u $AUTH "$BASE_URL/health"

# 2. Initialize complete setup (creates analyzers + views)
curl -u $AUTH -X POST "$BASE_URL/setup/initialize" \
  -H "Content-Type: application/json" \
  -d '{
    "collections": ["customers"],
    "force": false
  }'

# 3. Check setup status
curl -u $AUTH "$BASE_URL/setup/status"
```

### Example 2: Generate Candidates for Duplicate Detection

Find potential duplicates for a specific customer record.

```bash
# Generate candidates using multiple strategies
curl -u $AUTH -X POST "$BASE_URL/blocking/candidates" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "customers",
    "targetDocId": "customers/12345",
    "strategies": ["ngram", "exact"],
    "limit": 100,
    "threshold": 0.1
  }' | jq '.'

# Response shows candidates with BM25 scores
# {
#   "success": true,
#   "candidates": [
#     {
#       "candidateId": "customers/67890",
#       "score": 8.5,
#       "matchedFields": ["email", "phone"],
#       "candidate": { ... }
#     }
#   ],
#   "statistics": {
#     "candidate_count": 15,
#     "reduction_ratio": 0.9985
#   }
# }
```

### Example 3: Compute Similarity Scores

Compare two customer records to determine if they're the same entity.

```bash
# Compute similarity with detailed field scores
curl -u $AUTH -X POST "$BASE_URL/similarity/compute" \
  -H "Content-Type: application/json" \
  -d '{
    "docA": {
      "first_name": "John",
      "last_name": "Smith",
      "email": "john.smith@example.com",
      "phone": "555-1234",
      "address": "123 Main St",
      "city": "New York"
    },
    "docB": {
      "first_name": "Jon",
      "last_name": "Smith",
      "email": "j.smith@example.com",
      "phone": "555-1234",
      "address": "123 Main Street",
      "city": "New York"
    },
    "includeDetails": true
  }' | jq '.similarity'

# Response shows match decision and confidence
# {
#   "total_score": 3.45,
#   "is_match": true,
#   "confidence": 0.89,
#   "decision": "match",
#   "field_scores": { ... }
# }
```

### Example 4: Batch Processing

Process multiple records efficiently in batch mode.

```bash
# Generate candidates for multiple customers
curl -u $AUTH -X POST "$BASE_URL/blocking/candidates/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "customers",
    "targetDocIds": [
      "customers/123",
      "customers/456",
      "customers/789"
    ],
    "strategies": ["ngram", "exact"],
    "limit": 100
  }' | jq '.statistics'

# Compute similarities for multiple pairs
curl -u $AUTH -X POST "$BASE_URL/similarity/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "pairs": [
      {
        "docA": { "first_name": "John", "last_name": "Smith" },
        "docB": { "first_name": "Jon", "last_name": "Smith" }
      },
      {
        "docA": { "first_name": "Mary", "last_name": "Jones" },
        "docB": { "first_name": "Marie", "last_name": "Jones" }
      }
    ],
    "includeDetails": false,
    "threshold": 0.8
  }' | jq '.statistics'
```

### Example 5: Graph-Based Clustering

Build similarity graph and execute clustering.

```bash
# 1. Build similarity graph from scored pairs
curl -u $AUTH -X POST "$BASE_URL/clustering/build-graph" \
  -H "Content-Type: application/json" \
  -d '{
    "scoredPairs": [
      {
        "docA_id": "customers/123",
        "docB_id": "customers/456",
        "total_score": 3.5,
        "is_match": true
      },
      {
        "docA_id": "customers/123",
        "docB_id": "customers/789",
        "total_score": 2.8,
        "is_match": true
      }
    ],
    "threshold": 0.8,
    "edgeCollection": "similarities"
  }'

# 2. Execute Weakly Connected Components clustering
curl -u $AUTH -X POST "$BASE_URL/clustering/wcc" \
  -H "Content-Type: application/json" \
  -d '{
    "edgeCollection": "similarities",
    "minSimilarity": 0.8,
    "maxClusterSize": 100,
    "outputCollection": "entity_clusters"
  }' | jq '.statistics'

# 3. Get clustering statistics
curl -u $AUTH "$BASE_URL/clustering/stats/similarities" | jq '.statistics'
```

### Example 6: Complete Workflow via REST API

End-to-end entity resolution using REST endpoints.

```bash
#!/bin/bash

BASE_URL="http://localhost:8529/_db/entity_resolution/entity-resolution"
AUTH="root:your_password"

echo "[1/5] Initializing setup..."
curl -u $AUTH -X POST "$BASE_URL/setup/initialize" \
  -H "Content-Type: application/json" \
  -d '{"collections": ["customers"]}'

echo "\n[2/5] Generating candidates for all records..."
# Assume you have a list of customer IDs
IDS='["customers/1", "customers/2", "customers/3"]'

CANDIDATES=$(curl -s -u $AUTH -X POST "$BASE_URL/blocking/candidates/batch" \
  -H "Content-Type: application/json" \
  -d "{\"collection\": \"customers\", \"targetDocIds\": $IDS}")

echo "\n[3/5] Computing similarities..."
# Extract candidate pairs and compute similarities
# (This would typically be done programmatically)

echo "\n[4/5] Building similarity graph..."
curl -u $AUTH -X POST "$BASE_URL/clustering/build-graph" \
  -H "Content-Type: application/json" \
  -d @scored_pairs.json

echo "\n[5/5] Executing clustering..."
curl -u $AUTH -X POST "$BASE_URL/clustering/wcc" \
  -H "Content-Type: application/json" \
  -d '{
    "edgeCollection": "similarities",
    "minSimilarity": 0.8
  }'

echo "\n[COMPLETE] Entity resolution finished!"
```

---

## Python API Examples

### Example 1: Basic Entity Resolution

Simple entity resolution for a customer dataset.

```python
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

# Initialize and connect
pipeline = EntityResolutionPipeline()
if not pipeline.connect():
    print("Connection failed")
    exit(1)

# Load data
result = pipeline.load_data("customers.csv", collection_name="customers")
print(f"Loaded {result['records_imported']} records")

# Run complete pipeline
results = pipeline.run_complete_pipeline(
    collection_name="customers",
    strategies=["ngram", "exact"],
    similarity_threshold=0.8,
    max_candidates=100
)

# Display results
print(f"\n[RESULTS]")
print(f"Processing time: {results['overall']['total_time']:.2f}s")
print(f"Entity clusters: {results['clustering']['total_clusters']}")
print(f"Duplicate rate: {(1 - results['clustering']['total_clusters'] / result['records_imported']) * 100:.1f}%")
```

### Example 2: Custom Similarity Scoring

Use custom Fellegi-Sunter weights for your specific data.

```python
from entity_resolution.services.similarity_service import SimilarityService

# Initialize service
similarity = SimilarityService()
similarity.connect()

# Define custom field weights
custom_weights = {
    # High-value identifier (email)
    "email_exact": {
        "m_prob": 0.98,      # Very likely to match if same entity
        "u_prob": 0.001,     # Very unlikely to match randomly
        "threshold": 1.0,
        "importance": 2.0    # Double weight
    },
    
    # Names (moderate tolerance)
    "first_name_ngram": {
        "m_prob": 0.85,
        "u_prob": 0.05,
        "threshold": 0.7,
        "importance": 1.0
    },
    "last_name_ngram": {
        "m_prob": 0.90,
        "u_prob": 0.03,
        "threshold": 0.7,
        "importance": 1.2
    },
    
    # Address (lower tolerance)
    "address_ngram": {
        "m_prob": 0.75,
        "u_prob": 0.10,
        "threshold": 0.6,
        "importance": 0.8
    },
    
    # Global thresholds
    "global": {
        "upper_threshold": 3.0,   # Stricter match threshold
        "lower_threshold": -2.0
    }
}

# Compare two records
doc_a = {
    "first_name": "John",
    "last_name": "Smith",
    "email": "john.smith@company.com",
    "address": "123 Main St"
}

doc_b = {
    "first_name": "Jon",
    "last_name": "Smith",
    "email": "john.smith@company.com",
    "address": "123 Main Street"
}

result = similarity.compute_similarity(
    doc_a=doc_a,
    doc_b=doc_b,
    field_weights=custom_weights,
    include_details=True
)

# Analyze results
print(f"Decision: {result['similarity']['decision']}")
print(f"Confidence: {result['similarity']['confidence']:.2%}")
print(f"Total score: {result['similarity']['total_score']:.2f}")

if result['similarity']['decision'] == 'match':
    print("\n[MATCH CONFIRMED]")
    print("Field contributions:")
    for field, scores in result['similarity']['field_scores'].items():
        if scores['agreement']:
            print(f"  {field}: {scores['similarity']:.2f} (weight: {scores['weight']:.2f})")
```

### Example 3: Progressive Entity Resolution for Large Datasets

Process large datasets efficiently in batches.

```python
from entity_resolution.services.blocking_service import BlockingService
from entity_resolution.services.similarity_service import SimilarityService
from entity_resolution.services.clustering_service import ClusteringService
import time

# Initialize services
blocking = BlockingService()
similarity = SimilarityService()
clustering = ClusteringService()

# Connect all services
for service in [blocking, similarity, clustering]:
    service.connect()

# Get all record IDs (pagination for very large datasets)
collection = "customers"
record_ids = []  # Load from database query

# Configuration
BATCH_SIZE = 100
CANDIDATE_LIMIT = 100
SIMILARITY_THRESHOLD = 0.8

print(f"Processing {len(record_ids)} records in batches of {BATCH_SIZE}")

# Track progress
total_candidates = 0
total_matches = 0
all_scored_pairs = []

# Process in batches
for i in range(0, len(record_ids), BATCH_SIZE):
    batch_num = i // BATCH_SIZE + 1
    batch = record_ids[i:i+BATCH_SIZE]
    
    print(f"\n[BATCH {batch_num}] Processing {len(batch)} records...")
    
    # 1. Generate candidates
    start_time = time.time()
    candidates_result = blocking.generate_candidates_batch(
        collection=collection,
        target_record_ids=batch,
        strategies=["ngram", "exact"],
        limit=CANDIDATE_LIMIT
    )
    
    # Extract candidate pairs
    candidate_pairs = []
    for result in candidates_result['results']:
        if result['success']:
            for candidate in result['candidates']:
                candidate_pairs.append({
                    'docA': {'_id': result['targetDocId']},
                    'docB': {'_id': candidate['candidateId']}
                })
    
    total_candidates += len(candidate_pairs)
    
    # 2. Compute similarities
    if candidate_pairs:
        similarity_result = similarity.compute_batch_similarity(
            pairs=candidate_pairs,
            include_details=False
        )
        
        # Filter matches above threshold
        for result in similarity_result['results']:
            if result['success'] and result['similarity']['is_match']:
                all_scored_pairs.append({
                    'docA_id': result['docA_id'],
                    'docB_id': result['docB_id'],
                    'total_score': result['similarity']['total_score'],
                    'is_match': True
                })
                total_matches += 1
    
    elapsed = time.time() - start_time
    print(f"  Candidates: {len(candidate_pairs)}")
    print(f"  Matches: {len([r for r in similarity_result['results'] if r.get('similarity', {}).get('is_match')])}")
    print(f"  Time: {elapsed:.2f}s")

print(f"\n[PHASE 1 COMPLETE]")
print(f"Total candidates: {total_candidates}")
print(f"Total matches: {total_matches}")

# 3. Build similarity graph
print(f"\n[PHASE 2] Building similarity graph...")
graph_result = clustering.build_similarity_graph(
    scored_pairs=all_scored_pairs,
    threshold=SIMILARITY_THRESHOLD,
    edge_collection="similarities"
)

print(f"Edges created: {graph_result['results']['created_count']}")

# 4. Execute clustering
print(f"\n[PHASE 3] Executing WCC clustering...")
cluster_result = clustering.execute_wcc_clustering(
    edge_collection="similarities",
    min_similarity=SIMILARITY_THRESHOLD,
    max_cluster_size=100
)

print(f"\n[COMPLETE]")
print(f"Total clusters: {cluster_result['statistics']['total_clusters']}")
print(f"Valid clusters: {cluster_result['statistics']['valid_clusters']}")
print(f"Average cluster size: {cluster_result['statistics']['average_cluster_size']:.1f}")

# 5. Analyze clusters
print(f"\n[TOP 10 LARGEST CLUSTERS]")
sorted_clusters = sorted(
    cluster_result['clusters'],
    key=lambda c: c['cluster_size'],
    reverse=True
)

for cluster in sorted_clusters[:10]:
    print(f"Cluster {cluster['cluster_id']}")
    print(f"  Size: {cluster['cluster_size']} members")
    print(f"  Avg similarity: {cluster['average_similarity']:.2f}")
    print(f"  Density: {cluster['density']:.2f}")
    print(f"  Quality: {cluster['quality_score']:.2f}")
```

### Example 4: Real-Time Entity Matching

Match incoming records against existing database in real-time.

```python
from entity_resolution.services.blocking_service import BlockingService
from entity_resolution.services.similarity_service import SimilarityService

class RealTimeEntityMatcher:
    def __init__(self):
        self.blocking = BlockingService()
        self.similarity = SimilarityService()
        
        # Connect services
        self.blocking.connect()
        self.similarity.connect()
    
    def find_matches(self, new_record, collection="customers", confidence_threshold=0.85):
        """
        Find matching entities for a new record in real-time
        
        Returns:
            List of matches with confidence scores
        """
        # Step 1: Import new record temporarily
        temp_id = f"{collection}/temp_{int(time.time())}"
        # (In practice, insert into temp collection)
        
        # Step 2: Generate candidates using blocking
        candidates_result = self.blocking.generate_candidates(
            collection=collection,
            target_record_id=temp_id,
            strategies=["ngram", "exact"],
            limit=50  # Fewer candidates for real-time
        )
        
        if not candidates_result['success']:
            return []
        
        # Step 3: Compute similarities for candidates
        pairs = []
        for candidate in candidates_result['candidates']:
            pairs.append({
                'docA': new_record,
                'docB': candidate['candidate']
            })
        
        if not pairs:
            return []
        
        similarity_result = self.similarity.compute_batch_similarity(
            pairs=pairs,
            include_details=True
        )
        
        # Step 4: Filter and rank matches
        matches = []
        for i, result in enumerate(similarity_result['results']):
            if result['success']:
                sim = result['similarity']
                confidence = sim['confidence']
                
                if confidence >= confidence_threshold:
                    candidate = candidates_result['candidates'][i]
                    matches.append({
                        'candidate_id': candidate['candidateId'],
                        'confidence': confidence,
                        'decision': sim['decision'],
                        'total_score': sim['total_score'],
                        'candidate_data': candidate['candidate'],
                        'field_details': sim.get('field_scores', {})
                    })
        
        # Sort by confidence
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        return matches

# Usage
matcher = RealTimeEntityMatcher()

# Incoming customer record
new_customer = {
    "first_name": "John",
    "last_name": "Smith",
    "email": "john.smith@example.com",
    "phone": "555-1234",
    "company": "Acme Corp"
}

# Find matches
matches = matcher.find_matches(new_customer, confidence_threshold=0.85)

if matches:
    print(f"Found {len(matches)} potential matches:")
    for match in matches:
        print(f"\n  Match ID: {match['candidate_id']}")
        print(f"  Confidence: {match['confidence']:.2%}")
        print(f"  Decision: {match['decision']}")
        
        # Show matching fields
        strong_matches = [
            field for field, scores in match['field_details'].items()
            if scores.get('agreement', False) and scores.get('similarity', 0) > 0.9
        ]
        if strong_matches:
            print(f"  Strong field matches: {', '.join(strong_matches)}")
else:
    print("No matches found - this appears to be a new entity")
```

### Example 5: Data Quality Monitoring

Monitor entity resolution quality metrics over time.

```python
from entity_resolution.core.entity_resolver import EntityResolutionPipeline
import json
from datetime import datetime

class EntityResolutionMonitor:
    def __init__(self):
        self.pipeline = EntityResolutionPipeline()
        self.pipeline.connect()
    
    def run_quality_assessment(self, collection="customers"):
        """
        Run entity resolution and collect quality metrics
        """
        start_time = datetime.now()
        
        # Run pipeline
        results = self.pipeline.run_complete_pipeline(
            collection_name=collection,
            strategies=["ngram", "exact"],
            similarity_threshold=0.8
        )
        
        # Calculate quality metrics
        stats = self.pipeline.get_pipeline_stats()
        
        quality_report = {
            "timestamp": start_time.isoformat(),
            "collection": collection,
            "metrics": {
                # Efficiency metrics
                "blocking_efficiency": {
                    "reduction_ratio": stats['blocking']['reduction_ratio'],
                    "avg_candidates": stats['blocking']['avg_candidates_per_record'],
                    "processing_time": stats['blocking']['processing_time']
                },
                
                # Matching metrics
                "matching_quality": {
                    "match_rate": stats['similarity']['match_rate'],
                    "avg_score": stats['similarity']['avg_similarity_score'],
                    "processing_time": stats['similarity']['processing_time']
                },
                
                # Clustering metrics
                "clustering_quality": {
                    "total_clusters": stats['clustering']['total_clusters'],
                    "valid_clusters": stats['clustering']['valid_clusters'],
                    "validation_pass_rate": stats['clustering']['validation_pass_rate'],
                    "avg_cluster_size": stats['clustering']['avg_cluster_size'],
                    "processing_time": stats['clustering']['processing_time']
                },
                
                # Overall metrics
                "overall": {
                    "total_records": stats['overall']['total_records'],
                    "total_time": stats['overall']['total_time_seconds'],
                    "records_per_second": stats['overall']['total_records'] / stats['overall']['total_time_seconds']
                }
            },
            
            # Quality flags
            "quality_flags": []
        }
        
        # Add quality warnings
        if stats['blocking']['reduction_ratio'] < 0.95:
            quality_report['quality_flags'].append({
                "type": "WARNING",
                "message": "Blocking efficiency below 95% - consider reviewing strategies"
            })
        
        if stats['similarity']['match_rate'] > 0.5:
            quality_report['quality_flags'].append({
                "type": "WARNING",
                "message": "High match rate suggests potential over-matching"
            })
        
        if stats['clustering']['validation_pass_rate'] < 0.9:
            quality_report['quality_flags'].append({
                "type": "WARNING",
                "message": "Low cluster validation rate - review quality thresholds"
            })
        
        return quality_report
    
    def save_report(self, report, filename=None):
        """Save quality report to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"er_quality_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Quality report saved to {filename}")

# Usage
monitor = EntityResolutionMonitor()

# Run quality assessment
report = monitor.run_quality_assessment("customers")

# Display summary
print("\n[ENTITY RESOLUTION QUALITY REPORT]")
print(f"Collection: {report['collection']}")
print(f"Timestamp: {report['timestamp']}")

print(f"\n[EFFICIENCY]")
print(f"  Blocking reduction: {report['metrics']['blocking_efficiency']['reduction_ratio']:.2%}")
print(f"  Avg candidates: {report['metrics']['blocking_efficiency']['avg_candidates']:.1f}")
print(f"  Processing rate: {report['metrics']['overall']['records_per_second']:.0f} records/sec")

print(f"\n[QUALITY]")
print(f"  Match rate: {report['metrics']['matching_quality']['match_rate']:.2%}")
print(f"  Cluster validation: {report['metrics']['clustering_quality']['validation_pass_rate']:.2%}")
print(f"  Valid clusters: {report['metrics']['clustering_quality']['valid_clusters']}")

if report['quality_flags']:
    print(f"\n[WARNINGS]")
    for flag in report['quality_flags']:
        print(f"  {flag['type']}: {flag['message']}")

# Save report
monitor.save_report(report)
```

---

## Integration Patterns

### Pattern 1: ETL Pipeline Integration

Integrate entity resolution into data pipeline.

```python
# etl_pipeline.py
from entity_resolution.core.entity_resolver import EntityResolutionPipeline
import pandas as pd

def extract_data(source):
    """Extract data from source system"""
    return pd.read_csv(source)

def transform_data(df):
    """Apply data transformations"""
    # Normalize fields
    df['email'] = df['email'].str.lower().str.strip()
    df['phone'] = df['phone'].str.replace(r'[^0-9]', '', regex=True)
    return df

def resolve_entities(df):
    """Perform entity resolution"""
    pipeline = EntityResolutionPipeline()
    pipeline.connect()
    
    # Load data
    pipeline.load_data(df, collection_name="staging_customers")
    
    # Run entity resolution
    results = pipeline.run_complete_pipeline(
        collection_name="staging_customers",
        similarity_threshold=0.85
    )
    
    return results

def load_data(results):
    """Load deduplicated data to target system"""
    # Export golden records
    # Load to data warehouse
    pass

# Main ETL workflow
if __name__ == "__main__":
    # Extract
    raw_data = extract_data("sources/customers.csv")
    
    # Transform
    clean_data = transform_data(raw_data)
    
    # Entity Resolution
    er_results = resolve_entities(clean_data)
    
    # Load
    load_data(er_results)
```

### Pattern 2: Microservice API

Expose entity resolution as a REST microservice.

```python
# api_service.py
from flask import Flask, request, jsonify
from entity_resolution.services.blocking_service import BlockingService
from entity_resolution.services.similarity_service import SimilarityService

app = Flask(__name__)

# Initialize services
blocking = BlockingService()
similarity = SimilarityService()

@app.route('/api/v1/match', methods=['POST'])
def match_entity():
    """Find matches for an incoming entity"""
    data = request.json
    
    # Generate candidates
    candidates = blocking.generate_candidates(
        collection=data.get('collection', 'customers'),
        target_record_id=data['target_id'],
        strategies=data.get('strategies', ['ngram', 'exact']),
        limit=data.get('limit', 50)
    )
    
    if not candidates['success']:
        return jsonify({"error": "Candidate generation failed"}), 500
    
    # Compute similarities
    pairs = [
        {'docA': data['target_record'], 'docB': c['candidate']}
        for c in candidates['candidates']
    ]
    
    similarities = similarity.compute_batch_similarity(
        pairs=pairs,
        threshold=data.get('threshold', 0.8)
    )
    
    # Return matches
    matches = [
        {
            'candidate_id': candidates['candidates'][i]['candidateId'],
            'confidence': r['similarity']['confidence'],
            'decision': r['similarity']['decision']
        }
        for i, r in enumerate(similarities['results'])
        if r['success'] and r['similarity']['is_match']
    ]
    
    return jsonify({
        "matches": matches,
        "count": len(matches)
    })

@app.route('/api/v1/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    # Connect services
    blocking.connect()
    similarity.connect()
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000)
```

---

## Industry-Specific Examples

### Healthcare: Patient Record Matching

```python
# Configure for high-precision patient matching
custom_weights = {
    # Critical identifiers
    "ssn_exact": {
        "m_prob": 0.99,
        "u_prob": 0.0001,
        "importance": 3.0  # Very high weight
    },
    "medical_record_number": {
        "m_prob": 0.98,
        "u_prob": 0.001,
        "importance": 2.5
    },
    
    # Demographics
    "first_name_ngram": {"m_prob": 0.90, "u_prob": 0.05, "importance": 1.0},
    "last_name_ngram": {"m_prob": 0.95, "u_prob": 0.03, "importance": 1.2},
    "date_of_birth": {"m_prob": 0.95, "u_prob": 0.01, "importance": 1.5},
    
    # Strict thresholds for patient safety
    "global": {
        "upper_threshold": 4.0,  # Very strict
        "lower_threshold": -1.0
    }
}

# Run with strict parameters
results = pipeline.run_complete_pipeline(
    collection_name="patients",
    strategies=["exact"],  # Use exact matching only
    similarity_threshold=0.95  # Very high threshold
)
```

### Finance: KYC/Customer Deduplication

```python
# Financial services entity resolution
kyc_weights = {
    # Regulatory identifiers
    "tax_id_exact": {"m_prob": 0.99, "u_prob": 0.0001, "importance": 3.0},
    "national_id_exact": {"m_prob": 0.99, "u_prob": 0.0001, "importance": 3.0},
    
    # Customer data
    "full_name_ngram": {"m_prob": 0.85, "u_prob": 0.05, "importance": 1.0},
    "address_ngram": {"m_prob": 0.80, "u_prob": 0.10, "importance": 0.8},
    "date_of_birth": {"m_prob": 0.95, "u_prob": 0.01, "importance": 1.5},
    
    # Balanced thresholds for compliance
    "global": {
        "upper_threshold": 3.5,
        "lower_threshold": -1.5
    }
}

results = pipeline.run_complete_pipeline(
    collection_name="kyc_customers",
    strategies=["ngram", "exact"],
    similarity_threshold=0.90
)
```

### E-commerce: Customer 360 View

```python
# E-commerce customer deduplication
ecommerce_weights = {
    # Digital identifiers
    "email_exact": {"m_prob": 0.95, "u_prob": 0.001, "importance": 2.0},
    "phone_exact": {"m_prob": 0.90, "u_prob": 0.01, "importance": 1.5},
    
    # Personal information
    "name_ngram": {"m_prob": 0.80, "u_prob": 0.05, "importance": 0.8},
    "address_ngram": {"m_prob": 0.75, "u_prob": 0.10, "importance": 0.7},
    
    # Moderate thresholds for marketing use case
    "global": {
        "upper_threshold": 2.5,
        "lower_threshold": -1.0
    }
}

results = pipeline.run_complete_pipeline(
    collection_name="customers",
    strategies=["ngram", "exact", "phonetic"],  # More lenient
    similarity_threshold=0.80  # Lower threshold
)
```

---

## Next Steps

- Review [API Reference](./API_REFERENCE.md) for complete endpoint documentation
- Check [Python API Documentation](./API_PYTHON.md) for detailed SDK reference
- See [OpenAPI Specification](./openapi.yaml) for REST API schema
- Try [Quick Start Guide](../README.md#getting-started) for hands-on tutorial

