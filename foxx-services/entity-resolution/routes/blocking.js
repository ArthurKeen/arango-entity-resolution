'use strict';

/**
 * Blocking Routes for Entity Resolution Service
 * 
 * Handles multi-strategy record blocking using ArangoSearch:
 * - N-gram blocking for typo tolerance
 * - Exact matching for structured fields
 * - Phonetic matching for name variations
 * - Candidate pair generation with BM25 scoring
 */

const createRouter = require('@arangodb/foxx/router');
const joi = require('joi');
const { query, db } = require('@arangodb');
const { context } = require('@arangodb/foxx');

const router = createRouter();

// Import utility functions
const { logInfo, logError, logDebug, createTimer } = require('../utils/logger');
const { checkViewExists, checkCollectionExists } = require('../lib/setup-utils');

/**
 * Generate candidate pairs using ArangoSearch blocking
 */
router.post('/candidates', function (req, res) {
  const timer = createTimer('generate_candidates');
  
  try {
    const {
      collection,
      targetDocId,
      strategies = ['ngram', 'exact'],
      limit = module.context.configuration.maxCandidatesPerRecord || 100,
      threshold = 0.1
    } = req.body;
    
    // Validate inputs
    if (!collection || !targetDocId) {
      return res.status(400).json({
        success: false,
        error: 'collection and targetDocId are required',
        code: 'MISSING_PARAMETERS'
      });
    }
    
    // Check if collection and view exist
    if (!checkCollectionExists(collection)) {
      return res.status(404).json({
        success: false,
        error: `Collection '${collection}' does not exist`,
        code: 'COLLECTION_NOT_FOUND'
      });
    }
    
    const viewName = `${collection}_blocking_view`;
    if (!checkViewExists(viewName)) {
      return res.status(404).json({
        success: false,
        error: `ArangoSearch view '${viewName}' does not exist. Run setup first.`,
        code: 'VIEW_NOT_FOUND'
      });
    }
    
    // Generate candidates using the appropriate strategy
    const candidates = generateCandidatesWithArangoSearch(
      collection,
      targetDocId,
      strategies,
      limit,
      threshold
    );
    
    // Calculate blocking performance metrics
    const totalPossiblePairs = getTotalRecordCount(collection) - 1; // Exclude target record
    const reductionRatio = totalPossiblePairs > 0 ? 
      (totalPossiblePairs - candidates.length) / totalPossiblePairs : 0;
    
    timer.log({
      collection: collection,
      targetDocId: targetDocId,
      candidates_found: candidates.length,
      reduction_ratio: reductionRatio,
      strategies: strategies
    });
    
    res.json({
      success: true,
      collection: collection,
      targetDocId: targetDocId,
      candidates: candidates,
      statistics: {
        candidate_count: candidates.length,
        total_possible_pairs: totalPossiblePairs,
        reduction_ratio: reductionRatio,
        processing_time_ms: timer.duration()
      },
      strategies_used: strategies,
      parameters: {
        limit: limit,
        threshold: threshold
      }
    });
    
  } catch (error) {
    logError('Failed to generate candidates: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'CANDIDATE_GENERATION_FAILED'
    });
  }
})
.body(joi.object({
  collection: joi.string().required(),
  targetDocId: joi.string().required(),
  strategies: joi.array().items(joi.string().valid('ngram', 'exact', 'phonetic')).optional(),
  limit: joi.number().integer().min(1).max(1000).optional(),
  threshold: joi.number().min(0).max(1).optional()
}).required(), 'Candidate generation parameters')
.response(200, joi.object({
  success: joi.boolean().required(),
  candidates: joi.array().required(),
  statistics: joi.object().required()
}).required(), 'Generated candidate pairs with statistics')
.summary('Generate candidate pairs using ArangoSearch blocking')
.description('Uses multi-strategy blocking to find candidate record pairs for entity resolution');

/**
 * Batch candidate generation for multiple target records
 */
router.post('/candidates/batch', function (req, res) {
  const timer = createTimer('batch_generate_candidates');
  
  try {
    const {
      collection,
      targetDocIds,
      strategies = ['ngram', 'exact'],
      limit = module.context.configuration.maxCandidatesPerRecord || 100,
      threshold = 0.1
    } = req.body;
    
    // Validate inputs
    if (!collection || !targetDocIds || !Array.isArray(targetDocIds)) {
      return res.status(400).json({
        success: false,
        error: 'collection and targetDocIds array are required',
        code: 'MISSING_PARAMETERS'
      });
    }
    
    if (targetDocIds.length > 100) {
      return res.status(400).json({
        success: false,
        error: 'Maximum 100 target documents allowed per batch',
        code: 'BATCH_SIZE_EXCEEDED'
      });
    }
    
    // Check if collection and view exist
    if (!checkCollectionExists(collection)) {
      return res.status(404).json({
        success: false,
        error: `Collection '${collection}' does not exist`,
        code: 'COLLECTION_NOT_FOUND'
      });
    }
    
    const viewName = `${collection}_blocking_view`;
    if (!checkViewExists(viewName)) {
      return res.status(404).json({
        success: false,
        error: `ArangoSearch view '${viewName}' does not exist. Run setup first.`,
        code: 'VIEW_NOT_FOUND'
      });
    }
    
    // Generate candidates for each target document
    const results = [];
    let totalCandidates = 0;
    
    for (const targetDocId of targetDocIds) {
      try {
        const candidates = generateCandidatesWithArangoSearch(
          collection,
          targetDocId,
          strategies,
          limit,
          threshold
        );
        
        results.push({
          targetDocId: targetDocId,
          candidates: candidates,
          candidate_count: candidates.length,
          success: true
        });
        
        totalCandidates += candidates.length;
        
      } catch (error) {
        logError(`Failed to generate candidates for ${targetDocId}: ${error.message}`);
        results.push({
          targetDocId: targetDocId,
          candidates: [],
          candidate_count: 0,
          success: false,
          error: error.message
        });
      }
    }
    
    // Calculate batch statistics
    const successCount = results.filter(r => r.success).length;
    const totalPossiblePairs = getTotalRecordCount(collection) * targetDocIds.length;
    const reductionRatio = totalPossiblePairs > 0 ? 
      (totalPossiblePairs - totalCandidates) / totalPossiblePairs : 0;
    
    timer.log({
      collection: collection,
      batch_size: targetDocIds.length,
      successful_targets: successCount,
      total_candidates: totalCandidates,
      reduction_ratio: reductionRatio
    });
    
    res.json({
      success: true,
      collection: collection,
      batch_size: targetDocIds.length,
      results: results,
      statistics: {
        successful_targets: successCount,
        failed_targets: targetDocIds.length - successCount,
        total_candidates: totalCandidates,
        average_candidates_per_target: totalCandidates / Math.max(successCount, 1),
        reduction_ratio: reductionRatio,
        processing_time_ms: timer.duration()
      },
      strategies_used: strategies,
      parameters: {
        limit: limit,
        threshold: threshold
      }
    });
    
  } catch (error) {
    logError('Failed to generate batch candidates: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'BATCH_CANDIDATE_GENERATION_FAILED'
    });
  }
})
.body(joi.object({
  collection: joi.string().required(),
  targetDocIds: joi.array().items(joi.string()).max(100).required(),
  strategies: joi.array().items(joi.string().valid('ngram', 'exact', 'phonetic')).optional(),
  limit: joi.number().integer().min(1).max(1000).optional(),
  threshold: joi.number().min(0).max(1).optional()
}).required(), 'Batch candidate generation parameters')
.response(200, joi.object({
  success: joi.boolean().required(),
  results: joi.array().required(),
  statistics: joi.object().required()
}).required(), 'Batch candidate generation results')
.summary('Generate candidates for multiple target records')
.description('Efficiently processes multiple target documents for candidate generation in a single batch');

/**
 * Get available blocking strategies
 */
router.get('/strategies', function (req, res) {
  try {
    const ngramLength = module.context.configuration.ngramLength || 3;
    const phoneticEnabled = module.context.configuration.enablePhoneticMatching || false;
    
    const strategies = {
      ngram: {
        name: 'N-gram Blocking',
        description: 'Uses n-gram tokens for typo-tolerant blocking',
        analyzer: 'ngram_analyzer',
        ngram_length: ngramLength,
        fields: ['first_name', 'last_name', 'full_name', 'address', 'company'],
        advantages: ['Typo tolerance', 'Character-level matching', 'Language independent'],
        best_for: 'Names and addresses with potential spelling variations'
      },
      exact: {
        name: 'Exact Blocking',
        description: 'Uses exact string matching with normalization',
        analyzer: 'exact_analyzer',
        fields: ['email', 'phone', 'ssn', 'id_number'],
        advantages: ['High precision', 'Fast processing', 'No false positives'],
        best_for: 'Structured fields like emails, phone numbers, IDs'
      }
    };
    
    if (phoneticEnabled) {
      strategies.phonetic = {
        name: 'Phonetic Blocking',
        description: 'Uses phonetic algorithms for name variations',
        analyzer: 'phonetic_analyzer',
        fields: ['first_name', 'last_name', 'full_name'],
        advantages: ['Pronunciation variations', 'Cultural name differences', 'Nickname matching'],
        best_for: 'Person names with phonetic variations'
      };
    }
    
    res.json({
      success: true,
      strategies: strategies,
      configuration: {
        ngram_length: ngramLength,
        phonetic_enabled: phoneticEnabled,
        default_limit: module.context.configuration.maxCandidatesPerRecord
      },
      recommended_combinations: [
        {
          name: 'Standard Person Matching',
          strategies: ['ngram', 'exact'],
          description: 'Good for person records with names and contact info'
        },
        {
          name: 'Enhanced Person Matching',
          strategies: phoneticEnabled ? ['ngram', 'exact', 'phonetic'] : ['ngram', 'exact'],
          description: 'Comprehensive matching including phonetic variations'
        },
        {
          name: 'High Precision Matching',
          strategies: ['exact'],
          description: 'Conservative matching for high-quality data'
        }
      ]
    });
    
  } catch (error) {
    logError('Failed to get blocking strategies: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'STRATEGIES_RETRIEVAL_FAILED'
    });
  }
})
.response(200, joi.object({
  success: joi.boolean().required(),
  strategies: joi.object().required(),
  configuration: joi.object().required()
}).required(), 'Available blocking strategies')
.summary('Get available blocking strategies')
.description('Returns information about available blocking strategies and their configurations');

/**
 * Get blocking performance statistics
 */
router.get('/stats/:collection', function (req, res) {
  try {
    const { collection } = req.pathParams;
    
    if (!checkCollectionExists(collection)) {
      return res.status(404).json({
        success: false,
        error: `Collection '${collection}' does not exist`,
        code: 'COLLECTION_NOT_FOUND'
      });
    }
    
    const viewName = `${collection}_blocking_view`;
    if (!checkViewExists(viewName)) {
      return res.status(404).json({
        success: false,
        error: `ArangoSearch view '${viewName}' does not exist`,
        code: 'VIEW_NOT_FOUND'
      });
    }
    
    // Get collection statistics
    const collectionObj = db._collection(collection);
    const recordCount = collectionObj.count();
    const totalPossiblePairs = recordCount * (recordCount - 1) / 2; // Combinations, not permutations
    
    // Get view statistics (if available)
    const viewObj = db._view(viewName);
    const viewStats = viewObj.properties();
    
    res.json({
      success: true,
      collection: collection,
      view: viewName,
      statistics: {
        record_count: recordCount,
        total_possible_pairs: totalPossiblePairs,
        view_properties: viewStats,
        complexity_note: `Without blocking, ${totalPossiblePairs.toLocaleString()} comparisons would be needed`,
        blocking_benefit: 'Reduces comparisons by 90-99% typically'
      },
      performance_estimates: {
        pairs_with_10_percent_blocking: Math.round(totalPossiblePairs * 0.1),
        pairs_with_5_percent_blocking: Math.round(totalPossiblePairs * 0.05),
        pairs_with_1_percent_blocking: Math.round(totalPossiblePairs * 0.01)
      }
    });
    
  } catch (error) {
    logError('Failed to get blocking stats: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'STATS_RETRIEVAL_FAILED'
    });
  }
})
.pathParam('collection', joi.string().required(), 'Collection name')
.response(200, joi.object({
  success: joi.boolean().required(),
  statistics: joi.object().required()
}).required(), 'Blocking performance statistics')
.summary('Get blocking performance statistics for a collection')
.description('Returns statistics about record count, potential comparisons, and blocking efficiency');

/**
 * Core function: Generate candidates using ArangoSearch
 */
function generateCandidatesWithArangoSearch(collection, targetDocId, strategies, limit, threshold) {
  const viewName = `${collection}_blocking_view`;
  
  // Build the search conditions based on strategies
  const searchConditions = [];
  
  if (strategies.includes('ngram')) {
    searchConditions.push(`
      ANALYZER(PHRASE(candidate.first_name, targetDoc.first_name, "ngram_analyzer"), "ngram_analyzer") OR
      ANALYZER(PHRASE(candidate.last_name, targetDoc.last_name, "ngram_analyzer"), "ngram_analyzer") OR
      ANALYZER(PHRASE(candidate.full_name, targetDoc.full_name, "ngram_analyzer"), "ngram_analyzer") OR
      ANALYZER(PHRASE(candidate.address, targetDoc.address, "ngram_analyzer"), "ngram_analyzer") OR
      ANALYZER(PHRASE(candidate.company, targetDoc.company, "ngram_analyzer"), "ngram_analyzer")
    `);
  }
  
  if (strategies.includes('exact')) {
    searchConditions.push(`
      candidate.email == targetDoc.email OR
      candidate.phone == targetDoc.phone OR
      ANALYZER(candidate.city, "exact_analyzer") == ANALYZER(targetDoc.city, "exact_analyzer")
    `);
  }
  
  if (strategies.includes('phonetic') && checkAnalyzerExists('phonetic_analyzer')) {
    searchConditions.push(`
      ANALYZER(PHRASE(candidate.first_name, targetDoc.first_name, "phonetic_analyzer"), "phonetic_analyzer") OR
      ANALYZER(PHRASE(candidate.last_name, targetDoc.last_name, "phonetic_analyzer"), "phonetic_analyzer")
    `);
  }
  
  if (searchConditions.length === 0) {
    throw new Error('No valid blocking strategies specified');
  }
  
  const searchCondition = searchConditions.join(' OR ');
  
  const aql = `
    LET targetDoc = DOCUMENT(@targetDocId)
    
    FOR candidate IN ${viewName}
      SEARCH candidate._id != targetDoc._id AND (
        ${searchCondition}
      )
      LET bm25Score = BM25(candidate)
      FILTER bm25Score >= @threshold
      SORT bm25Score DESC
      LIMIT @limit
      
      RETURN {
        candidateId: candidate._id,
        targetId: targetDoc._id,
        score: bm25Score,
        matchedFields: [
          candidate.email == targetDoc.email ? "email" : null,
          candidate.phone == targetDoc.phone ? "phone" : null,
          ANALYZER(candidate.city, "exact_analyzer") == ANALYZER(targetDoc.city, "exact_analyzer") ? "city" : null
        ],
        candidate: {
          first_name: candidate.first_name,
          last_name: candidate.last_name,
          email: candidate.email,
          phone: candidate.phone,
          city: candidate.city
        }
      }
  `;
  
  try {
    logDebug(`Executing blocking query for ${targetDocId} with strategies: ${strategies.join(', ')}`);
    
    const result = query(aql, {
      targetDocId: targetDocId,
      limit: limit,
      threshold: threshold
    }).toArray();
    
    logDebug(`Found ${result.length} candidates for ${targetDocId}`);
    return result;
    
  } catch (error) {
    logError(`AQL blocking query failed: ${error.message}`);
    throw new Error(`Blocking query failed: ${error.message}`);
  }
}

/**
 * Helper function: Get total record count for a collection
 */
function getTotalRecordCount(collection) {
  try {
    const collectionObj = db._collection(collection);
    return collectionObj.count();
  } catch (error) {
    logError(`Failed to get record count for ${collection}: ${error.message}`);
    return 0;
  }
}

/**
 * Helper function: Check if analyzer exists
 */
function checkAnalyzerExists(name) {
  try {
    const analyzer = db._analyzer(name);
    return analyzer !== null;
  } catch (error) {
    return false;
  }
}

module.exports = router;
