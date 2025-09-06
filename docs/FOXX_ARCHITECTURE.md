# Foxx Services Architecture for Entity Resolution

## Overview

This document outlines our mixed Python/Foxx architecture for entity resolution, leveraging the strengths of both environments.

## Architecture Principles

### Python Layer (Orchestration)
- **Testing & Validation**: Comprehensive test suites using pytest
- **ML & Analytics**: Leverage scikit-learn, pandas for advanced processing
- **External Integration**: APIs, file processing, external data sources
- **Configuration Management**: Environment-based configuration
- **Monitoring**: Performance metrics and alerting

### Foxx Layer (Core Processing)
- **Database-Native Operations**: Direct AQL execution without network overhead
- **High-Performance Computing**: Blocking, similarity, clustering algorithms
- **Real-time Processing**: Live entity resolution for streaming data
- **Graph Operations**: Native graph algorithm execution
- **Atomic Transactions**: Complex multi-step operations

## Service Definitions

### 1. Blocking Service (`/foxx/blocking`)
```javascript
// Foxx service for generating candidate pairs
const { query } = require('@arangodb');

function generateCandidates(collectionName, blockingStrategy) {
  const aql = `
    FOR doc IN ${collectionName}
      // Generate blocking keys using ArangoSearch
      FOR candidate IN ${collectionName}_view
        SEARCH candidate._id != doc._id AND 
               ANALYZER(candidate.name, doc.name, "ngram_analyzer")
        LIMIT 100
        RETURN {
          source: doc._id,
          candidate: candidate._id,
          score: BM25(candidate)
        }
  `;
  return query(aql).toArray();
}
```

### 2. Similarity Service (`/foxx/similarity`)
```javascript
// Foxx service for similarity computation
function computeSimilarity(docA, docB, weights) {
  const similarities = {};
  
  // Use ArangoDB's built-in similarity functions
  similarities.name = query(`
    RETURN NGRAM_SIMILARITY(@nameA, @nameB, 3)
  `, { nameA: docA.name, nameB: docB.name }).next();
  
  similarities.address = query(`
    RETURN LEVENSHTEIN_DISTANCE(@addrA, @addrB)
  `, { addrA: docA.address, addrB: docB.address }).next();
  
  // Weighted similarity score
  return Object.keys(weights).reduce((score, field) => {
    return score + (similarities[field] * weights[field]);
  }, 0);
}
```

### 3. Clustering Service (`/foxx/clustering`)
```javascript
// Foxx service for entity clustering using graph algorithms
function clusterEntities(edgeCollection, threshold) {
  const aql = `
    FOR component IN GRAPH_WEAKLY_CONNECTED_COMPONENTS(
      @edgeCollection,
      {
        weightAttribute: "similarity_score",
        threshold: @threshold
      }
    )
    RETURN component
  `;
  
  return query(aql, { 
    edgeCollection: edgeCollection,
    threshold: threshold 
  }).toArray();
}
```

## Python Integration Layer

### API Orchestration
```python
# FastAPI service orchestrating Foxx calls
from fastapi import FastAPI
from arango import ArangoClient

app = FastAPI()
client = ArangoClient(hosts='http://arangodb:8529')

@app.post("/api/entity-resolution/run")
async def run_entity_resolution(dataset_id: str):
    # Step 1: Trigger blocking in Foxx
    blocking_response = requests.post(
        f"{ARANGO_URL}/_db/entity_resolution/_api/foxx/blocking/candidates",
        json={"collection": f"dataset_{dataset_id}"}
    )
    
    # Step 2: Process candidates with similarity service
    candidates = blocking_response.json()
    similarities = []
    
    for candidate_pair in candidates:
        sim_response = requests.post(
            f"{ARANGO_URL}/_db/entity_resolution/_api/foxx/similarity/compute",
            json=candidate_pair
        )
        similarities.append(sim_response.json())
    
    # Step 3: Cluster entities
    cluster_response = requests.post(
        f"{ARANGO_URL}/_db/entity_resolution/_api/foxx/clustering/cluster",
        json={"similarities": similarities}
    )
    
    return {"clusters": cluster_response.json()}
```

### Testing Strategy
```python
# Integration tests for mixed architecture
class TestMixedArchitecture:
    def setup_class(self):
        # Deploy Foxx services for testing
        self.foxx_deployer = FoxxDeployer()
        self.foxx_deployer.deploy_all_services()
        
    def test_blocking_performance(self):
        # Test Foxx blocking service performance
        start_time = time.time()
        result = self.call_foxx_blocking(test_dataset)
        duration = time.time() - start_time
        
        assert duration < 1.0  # Should be fast due to database locality
        assert len(result['candidates']) > 0
        
    def test_python_orchestration(self):
        # Test full Python pipeline using Foxx services
        pipeline = EntityResolutionPipeline()
        result = pipeline.run(test_dataset_id)
        
        assert result['status'] == 'completed'
        assert result['clusters_created'] > 0
```

## Deployment Strategy

### Development Environment
```bash
# Start local development environment
docker-compose -f docker-compose.dev.yml up

# Deploy Foxx services
./scripts/deploy-foxx-dev.sh

# Start Python API
cd src/python && uvicorn main:app --reload
```

### Production Deployment
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  arangodb-cluster:
    image: arangodb:3.12
    deploy:
      replicas: 3
    # ... cluster configuration
    
  foxx-services:
    build: ./deployment/foxx
    depends_on: [arangodb-cluster]
    volumes:
      - ./src/foxx:/services
      
  python-api:
    build: ./src/python
    deploy:
      replicas: 2
    depends_on: [arangodb-cluster, foxx-services]
```

## Performance Considerations

### Foxx Service Optimization
- **Query Optimization**: Use appropriate indexes for AQL queries
- **Memory Management**: Efficient data structures in JavaScript
- **Concurrent Processing**: Leverage ArangoDB's concurrent query execution
- **Caching**: In-memory caching for frequently accessed data

### Python Layer Optimization
- **Async Programming**: Use asyncio for concurrent Foxx service calls
- **Connection Pooling**: Reuse HTTP connections to ArangoDB
- **Batch Processing**: Group operations to minimize API calls
- **Monitoring**: Track performance metrics across both layers

## Development Guidelines

### Code Organization
- **Separation of Concerns**: Clear boundaries between Python and Foxx responsibilities
- **API Contracts**: Well-defined interfaces between layers
- **Error Handling**: Consistent error handling across both environments
- **Documentation**: Comprehensive API documentation for Foxx services

### Testing Requirements
- **Unit Tests**: Separate test suites for Python and Foxx components
- **Integration Tests**: End-to-end testing across both layers
- **Performance Tests**: Benchmarking for critical paths
- **Load Testing**: Stress testing under high concurrency

## Security Considerations

### Authentication & Authorization
- **JWT Tokens**: Secure communication between Python and Foxx layers
- **Role-Based Access**: Different permissions for different operations
- **Input Validation**: Thorough validation in both Python and Foxx
- **Audit Logging**: Track all entity resolution operations

### Data Security
- **PII Handling**: Secure processing of sensitive customer data
- **Encryption**: Data encryption at rest and in transit
- **Access Controls**: Restrict database access to authorized services
- **Compliance**: GDPR, CCPA compliance measures

This mixed architecture provides the best of both worlds: Python's rich ecosystem for orchestration and testing, combined with Foxx's database-native performance for core entity resolution operations.
