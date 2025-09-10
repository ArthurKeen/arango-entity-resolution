'use strict';

const createRouter = require('@arangodb/foxx/router');
const router = createRouter();

router.get('/health', function (req, res) {
  res.json({
    status: 'healthy',
    service: 'test-service',
    timestamp: new Date().toISOString()
  });
});

module.context.use(router);
