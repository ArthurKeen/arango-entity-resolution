'use strict';

/**
 * Setup Routes for Entity Resolution Service
 * 
 * Handles creation and management of:
 * - Custom ArangoSearch analyzers
 * - ArangoSearch views for blocking
 * - Database schema initialization
 */

const createRouter = require('@arangodb/foxx/router');
const joi = require('joi');
const { db } = require('@arangodb');
const { context } = require('@arangodb/foxx');

const router = createRouter();

// Import utility functions
const { createAnalyzer, createView, checkAnalyzerExists, checkViewExists } = require('../lib/setup-utils');
const { logInfo, logError, logDebug } = require('../utils/logger');

/**
 * Create custom analyzers for entity resolution
 */
router.post('/analyzers', function (req, res) {
  const ngramLength = module.context.configuration.ngramLength || 3;
  const enablePhonetic = module.context.configuration.enablePhoneticMatching || true;
  
  try {
    const results = {};
    
    // Create N-gram analyzer for typo tolerance
    const ngramConfig = {
      type: 'text',
      properties: {
        locale: 'en.utf-8',
        case: 'lower',
        accent: false,
        stemming: false,
        stopwords: [],
        ngram: {
          min: ngramLength,
          max: ngramLength,
          preserveOriginal: true,
          streamType: 'utf8'
        }
      },
      features: ['frequency', 'norm', 'position']
    };
    
    results.ngram_analyzer = createAnalyzer('ngram_analyzer', ngramConfig);
    logInfo('Created n-gram analyzer with length: ' + ngramLength);
    
    // Create phonetic analyzer for name variations (if enabled)
    if (enablePhonetic) {
      const phoneticConfig = {
        type: 'text',
        properties: {
          locale: 'en.utf-8',
          case: 'lower',
          accent: false,
          stemming: false,
          stopwords: []
        },
        features: ['frequency', 'norm']
      };
      
      results.phonetic_analyzer = createAnalyzer('phonetic_analyzer', phoneticConfig);
      logInfo('Created phonetic analyzer');
    }
    
    // Create exact match analyzer for structured fields
    const exactConfig = {
      type: 'identity',
      properties: {
        case: 'lower'
      },
      features: ['frequency', 'norm']
    };
    
    results.exact_analyzer = createAnalyzer('exact_analyzer', exactConfig);
    logInfo('Created exact match analyzer');
    
    res.json({
      success: true,
      message: 'Custom analyzers created successfully',
      analyzers: results,
      configuration: {
        ngramLength: ngramLength,
        phoneticEnabled: enablePhonetic
      }
    });
    
  } catch (error) {
    logError('Failed to create analyzers: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'ANALYZER_CREATION_FAILED'
    });
  }
})
.body(joi.object().optional(), 'Optional configuration overrides')
.response(200, joi.object({
  success: joi.boolean().required(),
  message: joi.string().required(),
  analyzers: joi.object().required()
}).required(), 'Analyzer creation results')
.summary('Create custom analyzers for entity resolution')
.description('Creates n-gram, phonetic, and exact match analyzers for blocking operations');

/**
 * Create ArangoSearch views for blocking
 */
router.post('/views', function (req, res) {
  // Get collections from request body or configuration
  let collections = req.body.collections;
  if (!collections || collections.length === 0) {
    const defaultColl = module.context.configuration.defaultCollections || '';
    collections = defaultColl ? defaultColl.split(',').map(c => c.trim()).filter(Boolean) : [];
  }
  
  // Validate collections were provided
  if (!collections || collections.length === 0) {
    const availableCollections = db._collections()
      .filter(c => !c.name().startsWith('_'))
      .map(c => c.name());
    
    res.status(400);
    return res.json({
      success: false,
      error: 'No collections specified',
      message: 'Provide collections in request body or configure defaultCollections service setting',
      available_collections: availableCollections,
      example: {
        collections: availableCollections.slice(0, 3),
        fields: {
          [availableCollections[0]]: ['field1', 'field2']
        }
      }
    });
  }
  
  const { fields = {} } = req.body;
  const autoDiscover = module.context.configuration.autoDiscoverFields !== false;
  
  try {
    const results = {};
    
    for (const collection of collections) {
      const viewName = `${collection}_blocking_view`;
      
      // Check if collection exists
      const coll = db._collection(collection);
      if (!coll) {
        const availableCollections = db._collections()
          .filter(c => !c.name().startsWith('_'))
          .map(c => c.name());
        throw new Error(`Collection '${collection}' does not exist. Available collections: ${availableCollections.join(', ')}`);
      }
      
      // Define view configuration
      const viewConfig = {
        type: 'arangosearch',
        links: {}
      };
      
      // Configure collection link with multiple analyzers
      viewConfig.links[collection] = {
        analyzers: [
          'identity',        // Exact matches
          'ngram_analyzer',  // Typo tolerance
          'exact_analyzer'   // Normalized exact matches
        ],
        includeAllFields: autoDiscover,
        fields: {}
      };
      
      // Configure specific fields if provided
      if (fields[collection] && Array.isArray(fields[collection])) {
        for (const field of fields[collection]) {
          viewConfig.links[collection].fields[field] = {
            analyzers: ['ngram_analyzer', 'exact_analyzer']
          };
        }
        logInfo(`Configured ${fields[collection].length} specific fields for ${collection}`);
      } else if (autoDiscover) {
        logInfo(`Auto-discovery enabled for ${collection} - all fields will be indexed`);
      }
      
      // Add phonetic analyzer if enabled
      if (module.context.configuration.enablePhoneticMatching && 
          checkAnalyzerExists('phonetic_analyzer')) {
        viewConfig.links[collection].analyzers.push('phonetic_analyzer');
      }
      
      results[viewName] = createView(viewName, viewConfig);
      logInfo(`Created ArangoSearch view: ${viewName}`);
    }
    
    res.json({
      success: true,
      message: 'ArangoSearch views created successfully',
      views: results,
      collections: collections,
      configuration: {
        autoDiscoverFields: autoDiscover,
        fieldsConfigured: Object.keys(fields).length > 0
      }
    });
    
  } catch (error) {
    logError('Failed to create views: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'VIEW_CREATION_FAILED'
    });
  }
})
.body(joi.object({
  collections: joi.array().items(joi.string()).optional(),
  fields: joi.object().pattern(/.*/, joi.array().items(joi.string())).optional()
}).optional(), 'Collections and optional field mappings')
.response(200, joi.object({
  success: joi.boolean().required(),
  message: joi.string().required(),
  views: joi.object().required()
}).required(), 'View creation results')
.summary('Create ArangoSearch views for blocking')
.description('Creates optimized ArangoSearch views with custom analyzers. Supports custom collections and field mappings. Example: {"collections": ["duns"], "fields": {"duns": ["DUNS_NAME", "NAME_CHIEF_EXECUTIVE"]}}');

/**
 * Check setup status
 */
router.get('/status', function (req, res) {
  try {
    const status = {
      analyzers: {
        ngram_analyzer: checkAnalyzerExists('ngram_analyzer'),
        phonetic_analyzer: checkAnalyzerExists('phonetic_analyzer'),
        exact_analyzer: checkAnalyzerExists('exact_analyzer')
      },
      views: {},
      collections: {}
    };
    
    // Check common collections and their views
    const commonCollections = ['customers', 'entities', 'persons'];
    for (const collection of commonCollections) {
      const collectionExists = !!db._collection(collection);
      status.collections[collection] = collectionExists;
      
      if (collectionExists) {
        const viewName = `${collection}_blocking_view`;
        status.views[viewName] = checkViewExists(viewName);
      }
    }
    
    // Calculate overall readiness
    const analyzerCount = Object.values(status.analyzers).filter(Boolean).length;
    const viewCount = Object.values(status.views).filter(Boolean).length;
    const collectionCount = Object.values(status.collections).filter(Boolean).length;
    
    const readiness = {
      analyzers_ready: analyzerCount >= 2, // At least ngram and exact
      views_configured: viewCount > 0,
      collections_available: collectionCount > 0,
      overall_ready: analyzerCount >= 2 && viewCount > 0 && collectionCount > 0
    };
    
    res.json({
      success: true,
      status: status,
      readiness: readiness,
      summary: {
        analyzers: `${analyzerCount}/3 created`,
        views: `${viewCount} configured`,
        collections: `${collectionCount} available`
      }
    });
    
  } catch (error) {
    logError('Failed to check setup status: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'STATUS_CHECK_FAILED'
    });
  }
})
.response(200, joi.object({
  success: joi.boolean().required(),
  status: joi.object().required(),
  readiness: joi.object().required()
}).required(), 'Setup status information')
.summary('Check entity resolution setup status')
.description('Returns the current status of analyzers, views, and collections required for entity resolution');

/**
 * Initialize complete setup
 */
router.post('/initialize', function (req, res) {
  // Get collections from request body or configuration
  let collections = req.body.collections;
  if (!collections || collections.length === 0) {
    const defaultColl = module.context.configuration.defaultCollections || '';
    collections = defaultColl ? defaultColl.split(',').map(c => c.trim()).filter(Boolean) : [];
  }
  
  const { force = false, fields = {} } = req.body;
  const autoDiscover = module.context.configuration.autoDiscoverFields !== false;
  
  try {
    const results = {
      analyzers: {},
      views: {},
      collections: {},
      warnings: []
    };
    
    // Step 1: Create analyzers
    logInfo('Initializing analyzers...');
    const ngramLength = module.context.configuration.ngramLength || 3;
    
    if (!checkAnalyzerExists('ngram_analyzer') || force) {
      const ngramConfig = {
        type: 'text',
        properties: {
          locale: 'en.utf-8',
          case: 'lower',
          accent: false,
          stemming: false,
          stopwords: [],
          ngram: {
            min: ngramLength,
            max: ngramLength,
            preserveOriginal: true
          }
        },
        features: ['frequency', 'norm', 'position']
      };
      results.analyzers.ngram_analyzer = createAnalyzer('ngram_analyzer', ngramConfig);
    }
    
    if (!checkAnalyzerExists('exact_analyzer') || force) {
      const exactConfig = {
        type: 'identity',
        properties: { case: 'lower' },
        features: ['frequency', 'norm']
      };
      results.analyzers.exact_analyzer = createAnalyzer('exact_analyzer', exactConfig);
    }
    
    // Step 2: Verify collections exist
    logInfo('Checking collections...');
    if (!collections || collections.length === 0) {
      const availableCollections = db._collections()
        .filter(c => !c.name().startsWith('_'))
        .map(c => c.name());
      
      results.warnings.push('No collections specified. Available collections: ' + availableCollections.join(', '));
      results.warnings.push('Provide collections in request body or configure defaultCollections service setting');
      
      return res.json({
        success: false,
        message: 'Cannot initialize without collections',
        results: results,
        available_collections: availableCollections,
        example: {
          collections: availableCollections.slice(0, 2),
          fields: {
            [availableCollections[0]]: ['field1', 'field2']
          }
        }
      });
    }
    
    for (const collection of collections) {
      if (!db._collection(collection)) {
        results.warnings.push(`Collection '${collection}' does not exist - skipping view creation`);
        results.collections[collection] = false;
      } else {
        results.collections[collection] = true;
      }
    }
    
    // Step 3: Create views for existing collections
    logInfo('Creating views...');
    for (const collection of collections) {
      if (results.collections[collection]) {
        const viewName = `${collection}_blocking_view`;
        
        if (!checkViewExists(viewName) || force) {
          const viewConfig = {
            type: 'arangosearch',
            links: {}
          };
          
          viewConfig.links[collection] = {
            analyzers: ['identity', 'ngram_analyzer', 'exact_analyzer'],
            includeAllFields: autoDiscover,
            fields: {}
          };
          
          // Configure specific fields if provided
          if (fields[collection] && Array.isArray(fields[collection])) {
            for (const field of fields[collection]) {
              viewConfig.links[collection].fields[field] = {
                analyzers: ['ngram_analyzer', 'exact_analyzer']
              };
            }
            logInfo(`Configured ${fields[collection].length} specific fields for ${collection}`);
          } else if (autoDiscover) {
            logInfo(`Auto-discovery enabled for ${collection} - all fields will be indexed`);
          }
          
          results.views[viewName] = createView(viewName, viewConfig);
        } else {
          results.warnings.push(`View '${viewName}' already exists - use force=true to recreate`);
        }
      }
    }
    
    logInfo('Entity resolution setup initialization completed');
    
    res.json({
      success: true,
      message: 'Entity resolution setup initialized successfully',
      results: results,
      configuration: {
        ngramLength: ngramLength,
        collections: collections,
        force: force,
        autoDiscoverFields: autoDiscover,
        fieldsConfigured: Object.keys(fields).length > 0
      }
    });
    
  } catch (error) {
    logError('Failed to initialize setup: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'INITIALIZATION_FAILED'
    });
  }
})
.body(joi.object({
  collections: joi.array().items(joi.string()).optional(),
  fields: joi.object().pattern(/.*/, joi.array().items(joi.string())).optional(),
  force: joi.boolean().optional()
}).optional(), 'Initialization configuration with optional field mappings')
.response(200, joi.object({
  success: joi.boolean().required(),
  message: joi.string().required(),
  results: joi.object().required()
}).required(), 'Initialization results')
.summary('Initialize complete entity resolution setup')
.description('Creates all required analyzers and views for entity resolution. Supports custom collections and field mappings. Example: {"collections": ["duns", "regs"], "fields": {"duns": ["DUNS_NAME", "NAME_CHIEF_EXECUTIVE"], "regs": ["REGISTRATION_NAME"]}}');

module.exports = router;
