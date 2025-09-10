'use strict';

/**
 * Entity Resolution Foxx Service
 * 
 * High-performance entity resolution with record blocking using ArangoSearch.
 */

const createRouter = require('@arangodb/foxx/router');

// Create main router
const router = createRouter();

// Health check endpoint
router.get('/health', function (req, res) {
  try {
    res.json({
      status: 'healthy',
      service: 'entity-resolution',
      version: '1.0.0',
      timestamp: new Date().toISOString(),
      configuration: {
        similarityThreshold: module.context.configuration.defaultSimilarityThreshold || 0.8,
        maxCandidates: module.context.configuration.maxCandidatesPerRecord || 100,
        ngramLength: module.context.configuration.ngramLength || 3,
        phoneticEnabled: module.context.configuration.enablePhoneticMatching || true
      }
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
      status: 'active',
      endpoints: {
        health: 'GET /health - Health check',
        info: 'GET /info - Service information',
        setup: 'POST /setup/* - Setup operations (coming soon)',
        blocking: 'POST /blocking/* - Blocking operations (coming soon)',
        similarity: 'POST /similarity/* - Similarity operations (coming soon)',
        clustering: 'POST /clustering/* - Clustering operations (coming soon)'
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

// Test endpoint to debug imports
router.get('/test', function (req, res) {
  try {
    // Test if we can import utilities
    const { logInfo } = require('./utils/logger');
    logInfo('Test endpoint called');
    
    res.json({
      status: 'test_passed',
      message: 'Logger import successful',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(500);
    res.json({
      error: true,
      message: 'Test failed: ' + error.message,
      stack: error.stack,
      code: 'TEST_FAILED'
    });
  }
});

// Export router as main module
module.context.use(router);

// Error handling middleware
module.context.use(function (err, req, res, next) {
  console.error(`[Entity Resolution Error] ${err.message}`, err.stack);
  
  if (!res.headersSent) {
    res.status(err.statusCode || 500);
    res.json({
      error: true,
      message: err.message || 'Internal server error',
      code: err.code || 'INTERNAL_ERROR',
      timestamp: new Date().toISOString()
    });
  }
});

console.log('Entity Resolution Foxx Service (minimal) initialized successfully');