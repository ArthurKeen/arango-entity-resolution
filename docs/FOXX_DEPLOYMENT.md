# Foxx Service Deployment

This document provides comprehensive instructions for deploying the Entity Resolution Foxx service to ArangoDB.

## Quick Start

### Automated Deployment

The easiest method for deployment:

```bash
python3 scripts/foxx/automated_deploy.py
```

This script will:
- Package the service as a ZIP file
- Deploy to ArangoDB
- Verify the installation
- Test all endpoints

### Manual Deployment via Web Interface

If automated deployment encounters issues, use the ArangoDB web interface:

#### Step 1: Access ArangoDB Web Interface

1. Open your web browser
2. Navigate to: `http://localhost:8529`
3. Login with your credentials (default: root/testpassword123)

#### Step 2: Navigate to Services

1. Click on "Services" in the left sidebar
2. You should see the Services management interface

#### Step 3: Install the Service

1. Click "Add Service" or the "+" button
2. Choose "Upload" as the installation method
3. Upload the file: `entity-resolution-service.zip` (created in project root)
4. Set mount point to: `/entity-resolution`
5. Click "Install"

#### Step 4: Verify Installation

The service should now be installed and running. You can verify by:

1. Checking the Services list shows "entity-resolution" with status "Running"
2. Running the test script: `python3 scripts/foxx/test_foxx_deployment.py`

## Expected Results After Deployment

Once deployed, you should see:

### Service Status
- Service Name: Entity Resolution Service
- Status: production
- Active Modules: setup, blocking, similarity, clustering
- Mount Point: /entity-resolution

### Available Endpoints

#### Health and Info
- `GET /entity-resolution/health` - Service health check
- `GET /entity-resolution/info` - Service information and endpoints

#### Setup Module
- `POST /entity-resolution/setup/analyzers` - Create custom analyzers
- `POST /entity-resolution/setup/views` - Create ArangoSearch views
- `GET /entity-resolution/setup/status` - Check setup status
- `POST /entity-resolution/setup/initialize` - Complete setup automation

#### Similarity Module
- `POST /entity-resolution/similarity/compute` - Compute similarity between documents
- `POST /entity-resolution/similarity/batch` - Batch similarity computation
- `GET /entity-resolution/similarity/functions` - List available similarity functions

#### Blocking Module
- `POST /entity-resolution/blocking/candidates` - Generate candidate pairs
- `POST /entity-resolution/blocking/setup` - Setup blocking for collections
- `GET /entity-resolution/blocking/stats` - Get blocking performance stats

#### Clustering Module
- `POST /entity-resolution/clustering/wcc` - Weakly Connected Components clustering
- `POST /entity-resolution/clustering/build-graph` - Build similarity graph
- `GET /entity-resolution/clustering/analyze` - Analyze cluster quality

## Performance Benefits

Once deployed, the Foxx service provides:

- **5-6x Performance Improvement**: Native ArangoDB processing vs Python
- **Reduced Latency**: Direct database access without network overhead
- **Better Scalability**: Leverages ArangoDB's native optimization
- **Memory Efficiency**: In-database processing reduces data movement

## Testing the Deployment

### Quick Test with CURL

```bash
# Test health endpoint
curl -u root:testpassword123 "http://localhost:8529/_db/_system/entity-resolution/health" | jq .

# Test similarity computation
curl -u root:testpassword123 -H "Content-Type: application/json" \
  -d '{"docA":{"first_name":"John","last_name":"Smith"},"docB":{"first_name":"Jon","last_name":"Smith"}}' \
  "http://localhost:8529/_db/_system/entity-resolution/similarity/compute" | jq .

# List available similarity functions
curl -u root:testpassword123 "http://localhost:8529/_db/_system/entity-resolution/similarity/functions" | jq .
```

### Comprehensive Test Suite

Run the full test script to verify all endpoints:

```bash
python3 scripts/foxx/test_foxx_deployment.py
```

Expected output:
```
Testing Foxx service deployment
Health check: healthy
Active modules: ['setup', 'blocking', 'similarity', 'clustering']
Service: Entity Resolution Service
Status: production
Similarity test: True
Similarity functions endpoint accessible
FOXX SERVICE TEST RESULTS:
  health: PASS (OK)
  info: PASS (OK) 
  similarity: PASS (OK)
  similarity_functions: PASS (OK)
  blocking_stats: PASS (OK)
  clustering_analyze: PASS (OK)
ALL TESTS PASSED - Foxx service is working correctly
```

## Next Steps After Deployment

1. **Update Python Services**: Configure Python fallbacks to use Foxx endpoints
2. **Performance Benchmarking**: Compare before/after performance metrics
3. **Production Configuration**: Tune service parameters for your dataset
4. **Monitoring Setup**: Add performance monitoring and alerting

## Troubleshooting

### Service Won't Install

**Problem**: Service fails to install via web interface or script

**Solutions**:
- Check that `entity-resolution-service.zip` exists in project root
- Verify ArangoDB is running and accessible: `docker-compose ps`
- Check ArangoDB logs for error details: `docker-compose logs arangodb`
- Ensure proper permissions on service files
- Try restarting ArangoDB: `docker-compose restart arangodb`

### Endpoints Return 404

**Problem**: Deployed service endpoints return 404 errors

**Solutions**:
- Verify service is properly mounted at `/entity-resolution`
- Check Services list in web interface for correct mount point
- Verify all route files are included in the ZIP
- Check service manifest.json for correct route configuration
- Restart ArangoDB if necessary

### Authentication Errors (401)

**Problem**: Endpoints return 401 Unauthorized

**Solutions**:
- Verify credentials are correct (default: root/testpassword123)
- Check authentication is enabled in docker-compose.yml
- Use `-u username:password` with curl commands
- Verify ARANGO_PASSWORD environment variable is set

### Performance Issues

**Problem**: Service responds slowly or times out

**Solutions**:
- Monitor ArangoDB server resources: `docker stats`
- Check for competing database operations
- Verify service configuration parameters
- Ensure adequate memory allocated to Docker
- Check ArangoDB logs for performance warnings

### JavaScript Errors in Service

**Problem**: Service returns JavaScript runtime errors

**Solutions**:
- Check ArangoDB logs for detailed error messages
- Verify AQL queries syntax in service code
- Test queries directly in ArangoDB web interface
- Use curl for rapid debugging (see Testing section)
- Check that all required dependencies are in manifest.json

## Alternative Deployment Methods

### Using Foxx CLI (Advanced)

If you have Node.js and Foxx CLI installed:

```bash
# Install Foxx CLI globally
npm install -g foxx-cli

# Deploy service
foxx install /entity-resolution foxx-services/entity-resolution
```

### Using HTTP API (Development)

For programmatic deployment (requires debugging):

```bash
curl -X PUT \
  "http://localhost:8529/_db/_system/_admin/foxx/install" \
  -u "root:testpassword123" \
  -F "source=@entity-resolution-service.zip" \
  -F "mount=/entity-resolution"
```

### Using Python Deployment Script

```bash
# Deploy to specific database
python3 scripts/foxx/automated_deploy.py --database _system

# Redeploy (replace existing service)
python3 scripts/foxx/automated_deploy.py --redeploy

# Deploy with custom mount point
python3 scripts/foxx/automated_deploy.py --mount /custom-entity-resolution
```

## Service Configuration

### Runtime Configuration

Configure the service via ArangoDB web interface:

1. Go to Services > entity-resolution
2. Click "Settings" or "Configuration"
3. Adjust parameters:
   - `defaultSimilarityThreshold`: Default threshold for matching (default: 0.8)
   - `maxCandidatesPerRecord`: Max candidates per record (default: 100)
   - `ngramLength`: N-gram length for blocking (default: 3)
   - `enablePhoneticMatching`: Enable phonetic matching (default: true)
   - `logLevel`: Logging level (default: info)

### Environment-Specific Configuration

For different environments (dev/staging/prod), create separate configuration profiles:

```javascript
// In manifest.json
"configuration": {
  "environment": {
    "type": "string",
    "default": "development"
  },
  "similarityThreshold": {
    "type": "number",
    "default": 0.8,
    "description": "Minimum similarity score for matches"
  }
}
```

## Updating the Service

### Redeployment

To update an existing service:

```bash
# Using automated script
python3 scripts/foxx/automated_deploy.py --redeploy

# Or via web interface:
# 1. Go to Services
# 2. Click on entity-resolution service
# 3. Click "Replace"
# 4. Upload new ZIP file
```

### Rolling Updates

For production environments with minimal downtime:

1. Deploy new version to different mount point
2. Test new version thoroughly
3. Update application to use new endpoint
4. Remove old version once confirmed stable

## Best Practices

### Development
- Use automated deployment script for rapid iteration
- Test with curl immediately after each change
- Check ArangoDB logs for errors
- Version control your service code

### Production
- Test thoroughly in staging environment first
- Use environment-specific configuration
- Monitor service performance and health
- Keep backups of working service versions
- Document any custom configurations

### Security
- Change default ArangoDB password
- Use environment variables for sensitive data
- Restrict network access to ArangoDB
- Enable authentication on all endpoints
- Regular security updates for ArangoDB

## Monitoring and Maintenance

### Health Checks

Set up regular health checks:

```bash
# Add to monitoring system
curl -u username:password \
  "http://localhost:8529/_db/_system/entity-resolution/health"
```

### Performance Monitoring

Monitor key metrics:
- Response times per endpoint
- Throughput (requests/second)
- Error rates
- Memory usage
- Query execution times

### Log Management

Configure appropriate log levels:
- **debug**: Development only
- **info**: Normal operations (default)
- **warn**: Production recommended
- **error**: Critical issues only

Access logs via:
- ArangoDB web interface (Logs section)
- Docker: `docker-compose logs arangodb`
- Log files in mounted data directory

## Additional Resources

- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Foxx Architecture](FOXX_ARCHITECTURE.md) - Service architecture details
- [Testing Guide](TESTING.md) - Comprehensive testing strategies
- [ArangoDB Foxx Documentation](https://www.arangodb.com/docs/stable/foxx.html) - Official Foxx docs

---

For additional help or issues not covered here, please check the project issues on GitHub or consult the ArangoDB community forums.

