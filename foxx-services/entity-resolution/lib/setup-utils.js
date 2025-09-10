'use strict';

/**
 * Setup Utility Functions
 * 
 * Helper functions for creating and managing:
 * - Custom analyzers
 * - ArangoSearch views
 * - Database schema validation
 */

const { db } = require('@arangodb');
const { logInfo, logError, logDebug } = require('../utils/logger');

/**
 * Create a custom analyzer
 */
function createAnalyzer(name, config) {
  try {
    logDebug(`Creating analyzer: ${name}`);
    
    // Check if analyzer already exists
    if (checkAnalyzerExists(name)) {
      logInfo(`Analyzer '${name}' already exists, skipping creation`);
      return { name: name, status: 'exists', created: false };
    }
    
    // Create the analyzer
    const result = db._createAnalyzer(name, config.type, config.properties, config.features);
    
    logInfo(`Successfully created analyzer: ${name}`);
    return { 
      name: name, 
      status: 'created', 
      created: true,
      type: config.type,
      properties: config.properties
    };
    
  } catch (error) {
    logError(`Failed to create analyzer '${name}': ${error.message}`);
    
    // If analyzer already exists, that's not really an error for our purposes
    if (error.message.includes('already exists') || error.message.includes('duplicate')) {
      logInfo(`Analyzer '${name}' already exists`);
      return { name: name, status: 'exists', created: false };
    }
    
    throw new Error(`Failed to create analyzer '${name}': ${error.message}`);
  }
}

/**
 * Create an ArangoSearch view
 */
function createView(name, config) {
  try {
    logDebug(`Creating view: ${name}`);
    
    // Check if view already exists
    if (checkViewExists(name)) {
      logInfo(`View '${name}' already exists, updating configuration`);
      
      // Update existing view
      const view = db._view(name);
      view.properties(config);
      
      return { 
        name: name, 
        status: 'updated', 
        created: false,
        links: Object.keys(config.links || {})
      };
    }
    
    // Create new view
    const view = db._createView(name, 'arangosearch', config);
    
    logInfo(`Successfully created view: ${name}`);
    return { 
      name: name, 
      status: 'created', 
      created: true,
      type: 'arangosearch',
      links: Object.keys(config.links || {})
    };
    
  } catch (error) {
    logError(`Failed to create view '${name}': ${error.message}`);
    throw new Error(`Failed to create view '${name}': ${error.message}`);
  }
}

/**
 * Check if an analyzer exists
 */
function checkAnalyzerExists(name) {
  try {
    const analyzer = db._analyzer(name);
    return analyzer !== null;
  } catch (error) {
    // If analyzer doesn't exist, _analyzer throws an error
    return false;
  }
}

/**
 * Check if a view exists
 */
function checkViewExists(name) {
  try {
    const view = db._view(name);
    return view !== null;
  } catch (error) {
    // If view doesn't exist, _view throws an error
    return false;
  }
}

/**
 * Check if a collection exists
 */
function checkCollectionExists(name) {
  try {
    const collection = db._collection(name);
    return collection !== null;
  } catch (error) {
    return false;
  }
}

/**
 * Get analyzer configuration
 */
function getAnalyzerConfig(name) {
  try {
    if (!checkAnalyzerExists(name)) {
      return null;
    }
    
    const analyzer = db._analyzer(name);
    return {
      name: analyzer.name(),
      type: analyzer.type(),
      properties: analyzer.properties(),
      features: analyzer.features()
    };
  } catch (error) {
    logError(`Failed to get analyzer config for '${name}': ${error.message}`);
    return null;
  }
}

/**
 * Get view configuration
 */
function getViewConfig(name) {
  try {
    if (!checkViewExists(name)) {
      return null;
    }
    
    const view = db._view(name);
    return {
      name: view.name(),
      type: view.type(),
      properties: view.properties()
    };
  } catch (error) {
    logError(`Failed to get view config for '${name}': ${error.message}`);
    return null;
  }
}

/**
 * Remove analyzer (for cleanup/testing)
 */
function removeAnalyzer(name, force = false) {
  try {
    if (!checkAnalyzerExists(name)) {
      logInfo(`Analyzer '${name}' does not exist, nothing to remove`);
      return { name: name, status: 'not_found', removed: false };
    }
    
    db._dropAnalyzer(name, force);
    logInfo(`Successfully removed analyzer: ${name}`);
    return { name: name, status: 'removed', removed: true };
    
  } catch (error) {
    logError(`Failed to remove analyzer '${name}': ${error.message}`);
    throw new Error(`Failed to remove analyzer '${name}': ${error.message}`);
  }
}

/**
 * Remove view (for cleanup/testing)
 */
function removeView(name) {
  try {
    if (!checkViewExists(name)) {
      logInfo(`View '${name}' does not exist, nothing to remove`);
      return { name: name, status: 'not_found', removed: false };
    }
    
    db._dropView(name);
    logInfo(`Successfully removed view: ${name}`);
    return { name: name, status: 'removed', removed: true };
    
  } catch (error) {
    logError(`Failed to remove view '${name}': ${error.message}`);
    throw new Error(`Failed to remove view '${name}': ${error.message}`);
  }
}

/**
 * Validate setup completeness
 */
function validateSetup(requiredAnalyzers = ['ngram_analyzer', 'exact_analyzer'], requiredViews = []) {
  const validation = {
    analyzers: {},
    views: {},
    valid: true,
    errors: []
  };
  
  // Check required analyzers
  for (const analyzer of requiredAnalyzers) {
    const exists = checkAnalyzerExists(analyzer);
    validation.analyzers[analyzer] = exists;
    
    if (!exists) {
      validation.valid = false;
      validation.errors.push(`Required analyzer '${analyzer}' is missing`);
    }
  }
  
  // Check required views
  for (const view of requiredViews) {
    const exists = checkViewExists(view);
    validation.views[view] = exists;
    
    if (!exists) {
      validation.valid = false;
      validation.errors.push(`Required view '${view}' is missing`);
    }
  }
  
  return validation;
}

/**
 * Get system information for debugging
 */
function getSystemInfo() {
  try {
    return {
      database: db._name(),
      version: db._version(),
      analyzers: db._analyzers().map(a => ({
        name: a.name(),
        type: a.type(),
        features: a.features()
      })),
      views: db._views().map(v => ({
        name: v.name(),
        type: v.type()
      })),
      collections: db._collections().map(c => ({
        name: c.name(),
        type: c.type(),
        count: c.count()
      }))
    };
  } catch (error) {
    logError(`Failed to get system info: ${error.message}`);
    return { error: error.message };
  }
}

module.exports = {
  createAnalyzer,
  createView,
  checkAnalyzerExists,
  checkViewExists,
  checkCollectionExists,
  getAnalyzerConfig,
  getViewConfig,
  removeAnalyzer,
  removeView,
  validateSetup,
  getSystemInfo
};
