'use strict';

/**
 * Entity Resolution Foxx Service - Progressive Addition
 */

const createRouter = require('@arangodb/foxx/router');

// Import route modules
const setupRoutes = require('./routes/setup');
const blockingRoutes = require('./routes/blocking');
const similarityRoutes = require('./routes/similarity');
const clusteringRoutes = require('./routes/clustering');

const router = createRouter();

// Health check endpoint
router.get('/health', function (req, res) {
  try {
    res.json({
      status: 'healthy',
      service: 'entity-resolution',
      version: '1.0.0',
      timestamp: new Date().toISOString(),
      mode: 'production',
      active_modules: ['setup', 'blocking', 'similarity', 'clustering']
    });
  } catch (error) {
    res.status(500);
    res.json({
      error: true,
      message: error.message,
      code: 'HEALTH_CHECK_FAILED'
    });
  }
});

// Service info endpoint
router.get('/info', function (req, res) {
  try {
    res.json({
      name: 'Entity Resolution Service',
      description: 'High-performance entity resolution with record blocking',
      version: '1.0.0',
      status: 'production',
      active_endpoints: {
        setup: [
          'POST /setup/analyzers - Create custom analyzers',
          'POST /setup/views - Create ArangoSearch views',
          'GET /setup/status - Check setup status',
          'POST /setup/initialize - Complete setup automation'
        ],
        blocking: [
          'POST /blocking/candidates - Generate candidate pairs',
          'POST /blocking/setup - Setup blocking for collections',
          'GET /blocking/stats - Get blocking performance stats'
        ],
        similarity: [
          'POST /similarity/compute - Compute similarity between documents',
          'POST /similarity/batch - Batch similarity computation',
          'GET /similarity/functions - List available similarity functions'
        ],
        clustering: [
          'POST /clustering/wcc - Weakly Connected Components clustering',
          'POST /clustering/build-graph - Build similarity graph',
          'GET /clustering/analyze - Analyze cluster quality'
        ]
      }
    });
  } catch (error) {
    res.status(500);
    res.json({
      error: true,
      message: error.message,
      code: 'INFO_FAILED'
    });
  }
});

// Mount route modules
try {
  router.use('/setup', setupRoutes);
  router.use('/blocking', blockingRoutes);
  router.use('/similarity', similarityRoutes);
  router.use('/clustering', clusteringRoutes);
  console.log('All routes mounted successfully');
} catch (error) {
  console.error('Failed to mount routes:', error.message);
}

// Export router
module.context.use(router);

console.log('Entity Resolution Foxx Service (production) initialized successfully');