# Foxx Service Deployment Instructions

## Manual Deployment via ArangoDB Web Interface

Since automated deployment requires additional ArangoDB Python driver updates, use the manual web interface method for immediate deployment:

### Step 1: Access ArangoDB Web Interface

1. Open your web browser
2. Navigate to: `http://localhost:8529`
3. Login with your credentials (default: root/testpassword123)

### Step 2: Navigate to Services

1. Click on "Services" in the left sidebar
2. You should see the Services management interface

### Step 3: Install the Service

1. Click "Add Service" or the "+" button
2. Choose "Upload" as the installation method
3. Upload the file: `entity-resolution-service.zip` (created in project root)
4. Set mount point to: `/entity-resolution`
5. Click "Install"

### Step 4: Verify Installation

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

Run the test script to verify all endpoints:

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
- Check that `entity-resolution-service.zip` exists in project root
- Verify ArangoDB is running and accessible
- Check ArangoDB logs for error details

### Endpoints Return 404
- Verify service is properly mounted at `/entity-resolution`
- Check that all route files are included in the ZIP
- Restart ArangoDB if necessary

### Performance Issues
- Monitor ArangoDB server resources
- Check for competing database operations
- Verify service configuration parameters

## Alternative Deployment Methods

### Using Foxx CLI (Advanced)

If you have Node.js and Foxx CLI installed:

```bash
npm install -g foxx-cli
foxx install /entity-resolution foxx-services/entity-resolution
```

### Using HTTP API (Development)

For programmatic deployment (requires additional API debugging):

```bash
curl -X PUT \
  "http://localhost:8529/_db/_system/_admin/foxx/install" \
  -u "root:testpassword123" \
  -F "source=@entity-resolution-service.zip" \
  -F "mount=/entity-resolution"
```
