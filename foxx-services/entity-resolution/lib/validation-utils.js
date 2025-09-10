'use strict';

/**
 * Validation Utility Functions
 * 
 * Centralizes common validation logic to eliminate duplicate validation
 * patterns across route handlers.
 */

const { checkCollectionExists, checkViewExists, checkAnalyzerExists } = require('./setup-utils');
const { DEFAULT_CONFIG, ERROR_CODES } = require('./constants');
const { sendValidationError, sendNotFoundError, sendBatchSizeError } = require('./response-utils');

/**
 * Validate collection existence and related view
 */
function validateCollectionAndView(res, collection) {
  // Check if collection exists
  if (!checkCollectionExists(collection)) {
    sendNotFoundError(res, 'Collection', collection);
    return false;
  }
  
  // Check if blocking view exists
  const viewName = `${collection}_blocking_view`;
  if (!checkViewExists(viewName)) {
    sendNotFoundError(res, 'ArangoSearch view', `${viewName}. Run setup first`);
    return false;
  }
  
  return true;
}

/**
 * Validate edge collection existence for clustering operations
 */
function validateEdgeCollection(res, edgeCollection) {
  if (!checkCollectionExists(edgeCollection)) {
    sendNotFoundError(res, 'Edge collection', edgeCollection);
    return false;
  }
  
  return true;
}

/**
 * Validate blocking parameters
 */
function validateBlockingParams(res, params) {
  const { collection, targetDocId, limit, threshold } = params;
  
  // Required parameters
  if (!collection || !targetDocId) {
    sendValidationError(res, 'collection and targetDocId are required', ['collection', 'targetDocId']);
    return false;
  }
  
  // Validate collection and view
  if (!validateCollectionAndView(res, collection)) {
    return false;
  }
  
  // Validate optional parameters
  if (limit !== undefined && (limit < 1 || limit > DEFAULT_CONFIG.MAX_BATCH_SIZE)) {
    sendValidationError(res, `limit must be between 1 and ${DEFAULT_CONFIG.MAX_BATCH_SIZE}`);
    return false;
  }
  
  if (threshold !== undefined && (threshold < 0 || threshold > 1)) {
    sendValidationError(res, 'threshold must be between 0 and 1');
    return false;
  }
  
  return true;
}

/**
 * Validate batch blocking parameters
 */
function validateBatchBlockingParams(res, params) {
  const { collection, targetDocIds, limit, threshold } = params;
  
  // Required parameters
  if (!collection || !targetDocIds || !Array.isArray(targetDocIds)) {
    sendValidationError(res, 'collection and targetDocIds array are required', ['collection', 'targetDocIds']);
    return false;
  }
  
  // Validate collection and view
  if (!validateCollectionAndView(res, collection)) {
    return false;
  }
  
  // Validate batch size
  if (targetDocIds.length > DEFAULT_CONFIG.MAX_TARGET_DOCS_BATCH) {
    sendBatchSizeError(res, targetDocIds.length, DEFAULT_CONFIG.MAX_TARGET_DOCS_BATCH, 'target documents');
    return false;
  }
  
  // Validate optional parameters
  if (limit !== undefined && (limit < 1 || limit > DEFAULT_CONFIG.MAX_BATCH_SIZE)) {
    sendValidationError(res, `limit must be between 1 and ${DEFAULT_CONFIG.MAX_BATCH_SIZE}`);
    return false;
  }
  
  if (threshold !== undefined && (threshold < 0 || threshold > 1)) {
    sendValidationError(res, 'threshold must be between 0 and 1');
    return false;
  }
  
  return true;
}

/**
 * Validate similarity computation parameters
 */
function validateSimilarityParams(res, params) {
  const { docA, docB } = params;
  
  if (!docA || !docB) {
    sendValidationError(res, 'Both docA and docB are required', ['docA', 'docB']);
    return false;
  }
  
  return true;
}

/**
 * Validate batch similarity parameters
 */
function validateBatchSimilarityParams(res, params) {
  const { pairs, threshold } = params;
  
  if (!pairs || !Array.isArray(pairs)) {
    sendValidationError(res, 'pairs array is required', ['pairs']);
    return false;
  }
  
  if (pairs.length > DEFAULT_CONFIG.MAX_BATCH_SIZE) {
    sendBatchSizeError(res, pairs.length, DEFAULT_CONFIG.MAX_BATCH_SIZE, 'pairs');
    return false;
  }
  
  // Validate each pair has required fields
  for (let i = 0; i < pairs.length; i++) {
    const pair = pairs[i];
    if (!pair.docA || !pair.docB) {
      sendValidationError(res, `Pair at index ${i} is missing docA or docB`);
      return false;
    }
  }
  
  if (threshold !== undefined && (threshold < 0 || threshold > 1)) {
    sendValidationError(res, 'threshold must be between 0 and 1');
    return false;
  }
  
  return true;
}

/**
 * Validate clustering parameters
 */
function validateClusteringParams(res, params) {
  const { edgeCollection, minSimilarity, maxClusterSize } = params;
  
  // Validate edge collection
  if (edgeCollection && !validateEdgeCollection(res, edgeCollection)) {
    return false;
  }
  
  // Validate similarity threshold
  if (minSimilarity !== undefined && (minSimilarity < 0 || minSimilarity > 10)) {
    sendValidationError(res, 'minSimilarity must be between 0 and 10');
    return false;
  }
  
  // Validate cluster size
  if (maxClusterSize !== undefined && (maxClusterSize < 2 || maxClusterSize > 1000)) {
    sendValidationError(res, 'maxClusterSize must be between 2 and 1000');
    return false;
  }
  
  return true;
}

/**
 * Validate graph building parameters
 */
function validateGraphBuildParams(res, params) {
  const { scoredPairs, threshold } = params;
  
  if (!scoredPairs || !Array.isArray(scoredPairs)) {
    sendValidationError(res, 'scoredPairs array is required', ['scoredPairs']);
    return false;
  }
  
  if (scoredPairs.length > DEFAULT_CONFIG.MAX_SCORED_PAIRS_BATCH) {
    sendBatchSizeError(res, scoredPairs.length, DEFAULT_CONFIG.MAX_SCORED_PAIRS_BATCH, 'scored pairs');
    return false;
  }
  
  // Validate each scored pair has required fields
  for (let i = 0; i < scoredPairs.length; i++) {
    const pair = scoredPairs[i];
    if (!pair.docA_id || !pair.docB_id || pair.total_score === undefined) {
      sendValidationError(res, `Scored pair at index ${i} is missing required fields (docA_id, docB_id, total_score)`);
      return false;
    }
  }
  
  if (threshold !== undefined && (threshold < 0 || threshold > 10)) {
    sendValidationError(res, 'threshold must be between 0 and 10');
    return false;
  }
  
  return true;
}

/**
 * Validate cluster validation parameters
 */
function validateClusterValidationParams(res, params) {
  const { clusters } = params;
  
  if (!clusters || !Array.isArray(clusters)) {
    sendValidationError(res, 'clusters array is required', ['clusters']);
    return false;
  }
  
  return true;
}

/**
 * Validate setup parameters for analyzer creation
 */
function validateAnalyzerParams(res, params) {
  // All parameters are optional for analyzer creation
  // Validation happens within the analyzer creation logic
  return true;
}

/**
 * Validate setup parameters for view creation
 */
function validateViewParams(res, params) {
  const { collections } = params;
  
  if (collections && !Array.isArray(collections)) {
    sendValidationError(res, 'collections must be an array');
    return false;
  }
  
  return true;
}

/**
 * Validate setup parameters for initialization
 */
function validateInitParams(res, params) {
  const { collections, force } = params;
  
  if (collections && !Array.isArray(collections)) {
    sendValidationError(res, 'collections must be an array');
    return false;
  }
  
  if (force !== undefined && typeof force !== 'boolean') {
    sendValidationError(res, 'force must be a boolean');
    return false;
  }
  
  return true;
}

/**
 * Validate blocking strategies
 */
function validateBlockingStrategies(strategies) {
  const validStrategies = ['ngram', 'exact', 'phonetic'];
  
  if (!Array.isArray(strategies)) {
    return false;
  }
  
  return strategies.every(strategy => validStrategies.includes(strategy));
}

/**
 * Get validation error for invalid strategies
 */
function getStrategyValidationError() {
  return 'strategies must be an array containing only: ngram, exact, phonetic';
}

module.exports = {
  validateCollectionAndView,
  validateEdgeCollection,
  validateBlockingParams,
  validateBatchBlockingParams,
  validateSimilarityParams,
  validateBatchSimilarityParams,
  validateClusteringParams,
  validateGraphBuildParams,
  validateClusterValidationParams,
  validateAnalyzerParams,
  validateViewParams,
  validateInitParams,
  validateBlockingStrategies,
  getStrategyValidationError
};
