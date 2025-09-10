'use strict';

/**
 * Configuration Constants for Entity Resolution Service
 * 
 * Centralizes all default values and configuration constants to eliminate
 * hardcoded values throughout the codebase.
 */

// Default configuration values
const DEFAULT_CONFIG = {
  // Similarity and matching thresholds
  SIMILARITY_THRESHOLD: 0.8,
  FALLBACK_THRESHOLD: 0.5,
  HIGH_CONFIDENCE_THRESHOLD: 0.9,
  LOW_CONFIDENCE_THRESHOLD: 0.6,
  
  // Blocking and candidate generation
  MAX_CANDIDATES_PER_RECORD: 100,
  MAX_BATCH_SIZE: 1000,
  BLOCKING_THRESHOLD: 0.1,
  
  // N-gram configuration
  NGRAM_LENGTH: 3,
  NGRAM_MIN_LENGTH: 2,
  NGRAM_MAX_LENGTH: 5,
  
  // Clustering parameters
  MAX_CLUSTER_SIZE: 100,
  MIN_CLUSTER_SIZE: 2,
  CLUSTER_DENSITY_THRESHOLD: 0.3,
  QUALITY_SCORE_THRESHOLD: 0.6,
  
  // Collection and view names
  DEFAULT_COLLECTIONS: ['customers', 'entities', 'persons'],
  EDGE_COLLECTION: 'similarities',
  CLUSTER_COLLECTION: 'entity_clusters',
  GOLDEN_RECORD_COLLECTION: 'golden_records',
  
  // Batch processing limits
  MAX_SCORED_PAIRS_BATCH: 10000,
  MAX_TARGET_DOCS_BATCH: 100,
  
  // Field weights and importance
  DEFAULT_FIELD_IMPORTANCE: 1.0,
  HIGH_IMPORTANCE_MULTIPLIER: 1.2,
  LOW_IMPORTANCE_MULTIPLIER: 0.7,
  
  // Fellegi-Sunter framework defaults
  DEFAULT_M_PROBABILITY: 0.8,
  DEFAULT_U_PROBABILITY: 0.05,
  UPPER_THRESHOLD: 2.0,
  LOWER_THRESHOLD: -1.0,
  
  // Quality validation thresholds
  MIN_AVERAGE_SIMILARITY: 0.7,
  MAX_SCORE_RANGE: 0.5,
  DENSITY_ADEQUATE_THRESHOLD: 0.3,
  
  // Log levels
  LOG_LEVELS: {
    ERROR: 0,
    WARN: 1,
    INFO: 2,
    DEBUG: 3
  }
};

// Error codes for consistent error handling
const ERROR_CODES = {
  // Validation errors
  MISSING_PARAMETERS: 'MISSING_PARAMETERS',
  MISSING_DOCUMENTS: 'MISSING_DOCUMENTS',
  MISSING_SCORED_PAIRS: 'MISSING_SCORED_PAIRS',
  MISSING_CLUSTERS: 'MISSING_CLUSTERS',
  
  // Resource not found
  COLLECTION_NOT_FOUND: 'COLLECTION_NOT_FOUND',
  VIEW_NOT_FOUND: 'VIEW_NOT_FOUND',
  EDGE_COLLECTION_NOT_FOUND: 'EDGE_COLLECTION_NOT_FOUND',
  
  // Size limits exceeded
  BATCH_SIZE_EXCEEDED: 'BATCH_SIZE_EXCEEDED',
  
  // Creation failures
  ANALYZER_CREATION_FAILED: 'ANALYZER_CREATION_FAILED',
  VIEW_CREATION_FAILED: 'VIEW_CREATION_FAILED',
  EDGE_COLLECTION_CREATION_FAILED: 'EDGE_COLLECTION_CREATION_FAILED',
  CLUSTER_COLLECTION_CREATION_FAILED: 'CLUSTER_COLLECTION_CREATION_FAILED',
  
  // Processing failures
  CANDIDATE_GENERATION_FAILED: 'CANDIDATE_GENERATION_FAILED',
  BATCH_CANDIDATE_GENERATION_FAILED: 'BATCH_CANDIDATE_GENERATION_FAILED',
  SIMILARITY_COMPUTATION_FAILED: 'SIMILARITY_COMPUTATION_FAILED',
  BATCH_SIMILARITY_COMPUTATION_FAILED: 'BATCH_SIMILARITY_COMPUTATION_FAILED',
  WCC_CLUSTERING_FAILED: 'WCC_CLUSTERING_FAILED',
  CLUSTER_VALIDATION_FAILED: 'CLUSTER_VALIDATION_FAILED',
  GRAPH_BUILD_FAILED: 'GRAPH_BUILD_FAILED',
  
  // Setup and status
  STATUS_CHECK_FAILED: 'STATUS_CHECK_FAILED',
  INITIALIZATION_FAILED: 'INITIALIZATION_FAILED',
  FUNCTIONS_RETRIEVAL_FAILED: 'FUNCTIONS_RETRIEVAL_FAILED',
  STRATEGIES_RETRIEVAL_FAILED: 'STRATEGIES_RETRIEVAL_FAILED',
  STATS_RETRIEVAL_FAILED: 'STATS_RETRIEVAL_FAILED',
  
  // Generic
  INTERNAL_ERROR: 'INTERNAL_ERROR'
};

// Field configuration for analyzers and views
const FIELD_CONFIG = {
  // Name fields - use n-gram and phonetic analyzers
  NAME_FIELDS: ['first_name', 'last_name', 'full_name'],
  
  // Address fields - use n-gram analyzer
  ADDRESS_FIELDS: ['address', 'company'],
  
  // City fields - use both n-gram and exact analyzers
  CITY_FIELDS: ['city'],
  
  // Exact match fields - use exact analyzer only
  EXACT_FIELDS: ['email', 'phone'],
  
  // Analyzer assignments
  ANALYZERS: {
    IDENTITY: 'identity',
    NGRAM: 'ngram_analyzer',
    PHONETIC: 'phonetic_analyzer',
    EXACT: 'exact_analyzer'
  }
};

// Blocking strategies configuration
const BLOCKING_STRATEGIES = {
  NGRAM: 'ngram',
  EXACT: 'exact',
  PHONETIC: 'phonetic'
};

// Quality thresholds for different field types
const FIELD_QUALITY_THRESHOLDS = {
  NAMES: 0.7,
  ADDRESSES: 0.6,
  PHONES: 0.9,
  EMAILS: 1.0,
  COMPANIES: 0.8
};

/**
 * Get configuration value with fallback to service configuration
 */
function getConfigValue(key, context = null, defaultValue = null) {
  if (context && context.configuration && context.configuration[key] !== undefined) {
    return context.configuration[key];
  }
  
  if (DEFAULT_CONFIG[key] !== undefined) {
    return DEFAULT_CONFIG[key];
  }
  
  return defaultValue;
}

/**
 * Get all configuration with service overrides
 */
function getFullConfig(context = null) {
  const config = { ...DEFAULT_CONFIG };
  
  if (context && context.configuration) {
    // Override with service configuration
    if (context.configuration.defaultSimilarityThreshold !== undefined) {
      config.SIMILARITY_THRESHOLD = context.configuration.defaultSimilarityThreshold;
    }
    if (context.configuration.maxCandidatesPerRecord !== undefined) {
      config.MAX_CANDIDATES_PER_RECORD = context.configuration.maxCandidatesPerRecord;
    }
    if (context.configuration.ngramLength !== undefined) {
      config.NGRAM_LENGTH = context.configuration.ngramLength;
    }
    if (context.configuration.enablePhoneticMatching !== undefined) {
      config.PHONETIC_ENABLED = context.configuration.enablePhoneticMatching;
    }
    if (context.configuration.logLevel !== undefined) {
      config.LOG_LEVEL = context.configuration.logLevel;
    }
  }
  
  return config;
}

module.exports = {
  DEFAULT_CONFIG,
  ERROR_CODES,
  FIELD_CONFIG,
  BLOCKING_STRATEGIES,
  FIELD_QUALITY_THRESHOLDS,
  getConfigValue,
  getFullConfig
};
