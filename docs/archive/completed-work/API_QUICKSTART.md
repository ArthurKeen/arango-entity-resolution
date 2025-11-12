# API Quick Start Guide

Get started with the Entity Resolution API in under 5 minutes.

## Prerequisites

- ArangoDB 3.12+ running (Docker or native)
- Python 3.8+ installed
- Access credentials for ArangoDB

## Quick Setup

### 1. Start ArangoDB

```bash
# Using Docker
docker-compose up -d

# Check health
curl http://localhost:8529/_api/version
```

### 2. Deploy Foxx Service

```bash
# Deploy entity resolution service
cd /path/to/arango-entity-resolution
python3 scripts/foxx/deploy_foxx.py
```

### 3. Verify Installation

```bash
# Check service health
curl -u root:your_password http://localhost:8529/_db/entity_resolution/entity-resolution/health

# Should return:
# {
#   "status": "healthy",
#   "service": "entity-resolution",
#   "version": "1.0.0"
# }
```

## REST API Quick Start

### Initialize Setup

```bash
# Base configuration
BASE_URL="http://localhost:8529/_db/entity_resolution/entity-resolution"
AUTH="root:your_password"

# Initialize analyzers and views
curl -u $AUTH -X POST "$BASE_URL/setup/initialize" \
  -H "Content-Type: application/json" \
  -d '{"collections": ["customers"]}'
```

### Find Duplicates

```bash
# Generate candidate duplicates for a record
curl -u $AUTH -X POST "$BASE_URL/blocking/candidates" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "customers",
    "targetDocId": "customers/12345",
    "strategies": ["ngram", "exact"],
    "limit": 100
  }' | jq '.'
```

### Compute Similarity

```bash
# Check if two records are the same entity
curl -u $AUTH -X POST "$BASE_URL/similarity/compute" \
  -H "Content-Type: application/json" \
  -d '{
    "docA": {
      "first_name": "John",
      "last_name": "Smith",
      "email": "john.smith@example.com"
    },
    "docB": {
      "first_name": "Jon",
      "last_name": "Smith",
      "email": "j.smith@example.com"
    }
  }' | jq '.similarity.decision'
```

## Python API Quick Start

### Basic Usage

```python
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

# Initialize
pipeline = EntityResolutionPipeline()
pipeline.connect()

# Load data
pipeline.load_data("customers.csv", collection_name="customers")

# Run entity resolution
results = pipeline.run_complete_pipeline(
    collection_name="customers",
    similarity_threshold=0.8
)

# View results
print(f"Found {results['clustering']['total_clusters']} entity clusters")
```

### Real-Time Matching

```python
from entity_resolution.services.blocking_service import BlockingService
from entity_resolution.services.similarity_service import SimilarityService

# Initialize services
blocking = BlockingService()
similarity = SimilarityService()

blocking.connect()
similarity.connect()

# New customer record
new_customer = {
    "first_name": "John",
    "last_name": "Smith",
    "email": "john.smith@example.com"
}

# Find matches
candidates = blocking.generate_candidates(
    collection="customers",
    target_record_id="customers/new",
    strategies=["ngram", "exact"],
    limit=50
)

# Check similarity
for candidate in candidates['candidates'][:5]:
    result = similarity.compute_similarity(
        doc_a=new_customer,
        doc_b=candidate['candidate']
    )
    
    if result['similarity']['is_match']:
        print(f"Match found: {candidate['candidateId']} "
              f"(confidence: {result['similarity']['confidence']:.2%})")
```

## Common Tasks

### Task 1: Deduplicate Customer Database

```python
# Complete deduplication workflow
pipeline = EntityResolutionPipeline()
pipeline.connect()

# Load and process
pipeline.load_data("customers.csv", "customers")
results = pipeline.run_complete_pipeline(
    collection_name="customers",
    strategies=["ngram", "exact"],
    similarity_threshold=0.85
)

# Results
print(f"Original records: {results['overall']['records_processed']}")
print(f"Unique entities: {results['clustering']['total_clusters']}")
print(f"Duplicates removed: {results['overall']['records_processed'] - results['clustering']['total_clusters']}")
```

### Task 2: Real-Time Duplicate Detection

```python
def check_for_duplicates(new_record, collection="customers"):
    """Check if new record is a duplicate"""
    blocking = BlockingService()
    similarity = SimilarityService()
    
    blocking.connect()
    similarity.connect()
    
    # Find candidates
    candidates = blocking.generate_candidates(
        collection=collection,
        target_record_id=f"{collection}/temp",
        limit=50
    )
    
    # Check similarities
    matches = []
    for candidate in candidates['candidates']:
        result = similarity.compute_similarity(
            doc_a=new_record,
            doc_b=candidate['candidate']
        )
        
        if result['similarity']['is_match']:
            matches.append({
                'id': candidate['candidateId'],
                'confidence': result['similarity']['confidence']
            })
    
    return matches

# Usage
new_customer = {"first_name": "John", "last_name": "Smith", ...}
duplicates = check_for_duplicates(new_customer)

if duplicates:
    print(f"WARNING: {len(duplicates)} potential duplicates found")
else:
    print("No duplicates - safe to insert")
```

### Task 3: Batch Processing

```python
# Process large dataset in batches
from entity_resolution.services.blocking_service import BlockingService

blocking = BlockingService()
blocking.connect()

# Get all record IDs
record_ids = [...] # Load from database

# Process in batches
BATCH_SIZE = 100
for i in range(0, len(record_ids), BATCH_SIZE):
    batch = record_ids[i:i+BATCH_SIZE]
    
    results = blocking.generate_candidates_batch(
        collection="customers",
        target_record_ids=batch,
        limit=100
    )
    
    print(f"Processed batch {i//BATCH_SIZE + 1}: "
          f"{results['statistics']['total_candidates']} candidates")
```

## Configuration

### Environment Variables

```bash
# .env file
ARANGO_HOST=localhost
ARANGO_PORT=8529
ARANGO_USERNAME=root
ARANGO_PASSWORD=your_password
ARANGO_DATABASE=entity_resolution

# Foxx service configuration
FOXX_SERVICE_MOUNT=/entity-resolution
FOXX_TIMEOUT=30
```

### Python Configuration

```python
from entity_resolution.utils.config import Config

config = Config(
    arango_host="localhost",
    arango_port=8529,
    arango_username="root",
    arango_password="your_password",
    arango_database="entity_resolution"
)

# Use custom config
pipeline = EntityResolutionPipeline(config=config)
```

## Troubleshooting

### Service Not Available

```bash
# Check if service is deployed
curl -u root:password http://localhost:8529/_db/entity_resolution/_api/foxx

# Redeploy if needed
python3 scripts/foxx/deploy_foxx.py
```

### View Not Found

```bash
# Initialize setup
curl -u root:password -X POST \
  http://localhost:8529/_db/entity_resolution/entity-resolution/setup/initialize \
  -H "Content-Type: application/json" \
  -d '{"collections": ["customers"]}'
```

### Connection Refused

```bash
# Check ArangoDB is running
docker ps | grep arangodb

# Start if not running
docker-compose up -d
```

## Performance Tips

1. **Use batch operations** for processing large datasets
2. **Optimize blocking strategies** based on your data quality
3. **Tune similarity thresholds** for your precision/recall requirements
4. **Use Foxx services** for better performance in production
5. **Monitor and adjust** based on performance metrics

## Next Steps

- [Complete API Reference](./API_REFERENCE.md) - Full endpoint documentation
- [Python API Guide](./API_PYTHON.md) - Detailed Python SDK reference
- [API Examples](./API_EXAMPLES.md) - Practical usage examples
- [OpenAPI Spec](./openapi.yaml) - REST API schema

## Support

- **Documentation**: `/docs` directory
- **Examples**: `/examples` directory
- **Issues**: GitHub Issues
- **Contact**: support@example.com

