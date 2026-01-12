# Docker Testing Setup

**Last Updated**: November 17, 2025 
**Version**: 3.0.0

## ArangoDB Container Setup

**ArangoDB CE container setup and testing verified**

**Container Details:**
- **Name**: `arangodb-test`
- **Image**: `arangodb/arangodb:latest`
- **Version**: ArangoDB 3.12.4-3 (Community Edition)
- **Port**: `8529` (mapped to host)
- **Volume Mount**: `~/data` -> `/data` (in container)
- **Password**: `testpassword123` (test environment only)

## Container Management

### Check Container Status
```bash
docker ps | grep arangodb
```

### View Container Logs
```bash
docker logs arangodb-test
```

### Stop Container
```bash
docker stop arangodb-test
```

### Start Container (if stopped)
```bash
docker start arangodb-test
```

### Remove Container (when done)
```bash
docker stop arangodb-test
docker rm arangodb-test
```

## Environment Variables for Testing

Set these environment variables before running tests:

```bash
export ARANGO_ROOT_PASSWORD=testpassword123
export USE_DEFAULT_PASSWORD=true
export ARANGO_HOST=localhost
export ARANGO_PORT=8529
export ARANGO_DATABASE=entity_resolution_test
```

## Running Round-Trip Tests

### Option 1: Simple Test Script (No pytest required)

```bash
# Set environment variables
export ARANGO_ROOT_PASSWORD=testpassword123
export USE_DEFAULT_PASSWORD=true
export ARANGO_HOST=localhost
export ARANGO_PORT=8529
export ARANGO_DATABASE=entity_resolution_test

# Run simple test
python3 test_round_trip_simple.py
```

### Option 2: Full Integration Tests (with pytest)

```bash
# Set environment variables (same as above)
export ARANGO_ROOT_PASSWORD=testpassword123
export USE_DEFAULT_PASSWORD=true
export ARANGO_HOST=localhost
export ARANGO_PORT=8529
export ARANGO_DATABASE=entity_resolution_test

# Run full round-trip tests
pytest tests/test_round_trip_v3.py -v -s

# Or run specific test class
pytest tests/test_round_trip_v3.py::TestWeightedFieldSimilarityRoundTrip -v -s
```

### Option 3: Existing Integration Tests

```bash
# Run existing integration tests
pytest tests/test_integration_and_performance.py -v -s -m integration
```

## Test Coverage

The round-trip tests verify:

1. **WeightedFieldSimilarity** - Standalone similarity computation
2. **BatchSimilarityService** - Batch similarity with database
3. **AddressERService** - Complete address ER pipeline
4. **WCCClusteringService** - Python DFS clustering algorithm
5. **Complete Pipeline** - End-to-end ER workflow

## Verifying Database Connection

Test the connection manually:

```bash
curl -u root:testpassword123 http://localhost:8529/_api/version
```

Expected response:
```json
{
"server": "arango",
"license": "community",
"version": "3.12.4-3"
}
```

## Troubleshooting

### Container Not Running
```bash
docker ps -a | grep arangodb
# If stopped, start it:
docker start arangodb-test
```

### Port Already in Use
If port 8529 is already in use, stop the existing container or use a different port:
```bash
docker stop arangodb-test
docker rm arangodb-test
docker run -d --name arangodb-test -p 8529:8529 \
-e ARANGO_ROOT_PASSWORD=testpassword123 \
-v ~/data:/data \
arangodb/arangodb:latest
```

### Database Connection Errors
1. Verify container is running: `docker ps | grep arangodb`
2. Check logs: `docker logs arangodb-test`
3. Verify port: `curl http://localhost:8529/_api/version`
4. Check environment variables are set correctly

## Data Persistence

The `~/data` directory is mounted to `/data` in the container, so:
- Database files persist between container restarts
- Data is stored in `~/data` on your host machine
- To start fresh, remove `~/data` and restart container

## Next Steps

1. Install dependencies (if not already installed):
```bash
pip install -e ".[test]"
```

2. Run tests:
```bash
python3 test_round_trip_simple.py
```

3. Review test results and verify all components work correctly

