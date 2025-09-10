'use strict';

const createRouter = require('@arangodb/foxx/router');
const router = createRouter();

// Health check endpoint
router.get('/health', function (req, res) {
  res.json({
    status: 'healthy',
    service: 'entity-resolution',
    version: '1.0.0',
    timestamp: new Date().toISOString()
  });
});

// Service info endpoint
router.get('/info', function (req, res) {
  res.json({
    name: 'Entity Resolution Service',
    description: 'High-performance entity resolution with record blocking',
    version: '1.0.0',
    endpoints: {
      health: 'GET /health - Health check',
      info: 'GET /info - Service information'
    }
  });
});

// Export router as main module
module.context.use(router);

console.log('Entity Resolution Foxx Service initialized successfully');