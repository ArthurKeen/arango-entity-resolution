'use strict';

/**
 * Similarity Routes for Entity Resolution Service
 * 
 * Implements Fellegi-Sunter similarity scoring using ArangoDB's native functions:
 * - NGRAM_SIMILARITY for string matching with n-gram overlap
 * - LEVENSHTEIN_DISTANCE for edit distance computation
 * - Field-specific similarity functions
 * - Configurable weighting strategies
 * - Batch processing for performance
 */

const createRouter = require('@arangodb/foxx/router');
const joi = require('joi');
const { query, db, aql } = require('@arangodb');
const { context } = require('@arangodb/foxx');

const router = createRouter();

// Import utility functions
const { logInfo, logError, logDebug, createTimer } = require('../utils/logger');
const { checkCollectionExists } = require('../lib/setup-utils');

/**
 * Compute similarity score between two documents
 */
router.post('/compute', function (req, res) {
  const timer = createTimer('compute_similarity');
  
  try {
    const {
      docA,
      docB,
      fieldWeights = getDefaultFieldWeights(),
      includeDetails = false
    } = req.body;
    
    // Validate inputs
    if (!docA || !docB) {
      return res.status(400).json({
        success: false,
        error: 'Both docA and docB are required',
        code: 'MISSING_DOCUMENTS'
      });
    }
    
    // Compute aggregate similarity score
    const result = computeAggregateScore(docA, docB, fieldWeights, includeDetails);
    
    timer.log({
      docA_id: docA._id || 'inline',
      docB_id: docB._id || 'inline',
      total_score: result.total_score,
      is_match: result.is_match
    });
    
    res.json({
      success: true,
      similarity: result,
      processing_time_ms: timer.duration(),
      field_weights_used: fieldWeights
    });
    
  } catch (error) {
    logError('Failed to compute similarity: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'SIMILARITY_COMPUTATION_FAILED'
    });
  }
})
.body(joi.object({
  docA: joi.object().required(),
  docB: joi.object().required(), 
  fieldWeights: joi.object().optional(),
  includeDetails: joi.boolean().optional()
}).required(), 'Similarity computation parameters')
.response(200, joi.object({
  success: joi.boolean().required(),
  similarity: joi.object().required()
}).required(), 'Similarity computation result')
.summary('Compute similarity between two documents')
.description('Uses Fellegi-Sunter framework with ArangoDB native functions to compute similarity scores');

/**
 * Batch similarity computation for multiple document pairs
 */
router.post('/batch', function (req, res) {
  const timer = createTimer('batch_compute_similarity');
  
  try {
    const {
      pairs,
      fieldWeights = getDefaultFieldWeights(),
      includeDetails = false,
      threshold = module.context.configuration.defaultSimilarityThreshold || 0.8
    } = req.body;
    
    // Validate inputs
    if (!pairs || !Array.isArray(pairs)) {
      return res.status(400).json({
        success: false,
        error: 'pairs array is required',
        code: 'MISSING_PAIRS'
      });
    }
    
    if (pairs.length > 1000) {
      return res.status(400).json({
        success: false,
        error: 'Maximum 1000 pairs allowed per batch',
        code: 'BATCH_SIZE_EXCEEDED'
      });
    }
    
    // Process each pair
    const results = [];
    let matchCount = 0;
    let totalScore = 0;
    
    for (let i = 0; i < pairs.length; i++) {
      const pair = pairs[i];
      
      try {
        if (!pair.docA || !pair.docB) {
          results.push({
            index: i,
            success: false,
            error: 'Missing docA or docB',
            similarity: null
          });
          continue;
        }
        
        const similarity = computeAggregateScore(pair.docA, pair.docB, fieldWeights, includeDetails);
        
        results.push({
          index: i,
          success: true,
          docA_id: pair.docA._id || `inline_${i}_A`,
          docB_id: pair.docB._id || `inline_${i}_B`,
          similarity: similarity
        });
        
        totalScore += similarity.total_score;
        if (similarity.is_match) {
          matchCount++;
        }
        
      } catch (error) {
        logError(`Failed to compute similarity for pair ${i}: ${error.message}`);
        results.push({
          index: i,
          success: false,
          error: error.message,
          similarity: null
        });
      }
    }
    
    // Calculate batch statistics
    const successCount = results.filter(r => r.success).length;
    const averageScore = successCount > 0 ? totalScore / successCount : 0;
    
    timer.log({
      batch_size: pairs.length,
      successful_computations: successCount,
      matches_found: matchCount,
      average_score: averageScore
    });
    
    res.json({
      success: true,
      batch_size: pairs.length,
      results: results,
      statistics: {
        successful_computations: successCount,
        failed_computations: pairs.length - successCount,
        matches_found: matchCount,
        match_rate: successCount > 0 ? matchCount / successCount : 0,
        average_score: averageScore,
        processing_time_ms: timer.duration()
      },
      threshold_used: threshold,
      field_weights_used: fieldWeights
    });
    
  } catch (error) {
    logError('Failed to compute batch similarities: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'BATCH_SIMILARITY_COMPUTATION_FAILED'
    });
  }
})
.body(joi.object({
  pairs: joi.array().items(joi.object({
    docA: joi.object().required(),
    docB: joi.object().required()
  })).max(1000).required(),
  fieldWeights: joi.object().optional(),
  includeDetails: joi.boolean().optional(),
  threshold: joi.number().min(0).max(1).optional()
}).required(), 'Batch similarity computation parameters')
.response(200, joi.object({
  success: joi.boolean().required(),
  results: joi.array().required(),
  statistics: joi.object().required()
}).required(), 'Batch similarity computation results')
.summary('Compute similarities for multiple document pairs')
.description('Efficiently processes multiple document pairs for similarity computation in a single batch');

/**
 * Get available similarity functions
 */
router.get('/functions', function (req, res) {
  try {
    const functions = {
      ngram_similarity: {
        name: 'N-gram Similarity',
        description: 'Computes similarity based on n-gram overlap',
        function: 'NGRAM_SIMILARITY(str1, str2, n)',
        parameters: ['string1', 'string2', 'ngram_length'],
        return_type: 'number (0.0 to 1.0)',
        best_for: 'Text fields with potential typos',
        example: 'NGRAM_SIMILARITY("John Smith", "Jon Smith", 3) → 0.75'
      },
      levenshtein_distance: {
        name: 'Levenshtein Distance',
        description: 'Computes edit distance between strings',
        function: 'LEVENSHTEIN_DISTANCE(str1, str2)',
        parameters: ['string1', 'string2'],
        return_type: 'number (0 to max_string_length)',
        best_for: 'Measuring exact differences between strings',
        example: 'LEVENSHTEIN_DISTANCE("kitten", "sitting") → 3'
      },
      exact_match: {
        name: 'Exact Match',
        description: 'Boolean exact string comparison',
        function: 'str1 == str2',
        parameters: ['string1', 'string2'],
        return_type: 'boolean',
        best_for: 'Structured fields like IDs, emails',
        example: '"john@example.com" == "john@example.com" → true'
      },
      normalized_levenshtein: {
        name: 'Normalized Levenshtein',
        description: 'Levenshtein distance normalized to 0-1 range',
        function: '1 - (LEVENSHTEIN_DISTANCE(str1, str2) / MAX(LENGTH(str1), LENGTH(str2)))',
        parameters: ['string1', 'string2'],
        return_type: 'number (0.0 to 1.0)',
        best_for: 'Similarity scoring with consistent range',
        example: 'Normalized distance between "cat" and "hat" → 0.67'
      }
    };
    
    const fieldStrategies = {
      names: {
        recommended_functions: ['ngram_similarity', 'normalized_levenshtein'],
        typical_threshold: 0.7,
        considerations: 'Names often have variations, nicknames, and cultural differences'
      },
      addresses: {
        recommended_functions: ['ngram_similarity'],
        typical_threshold: 0.6,
        considerations: 'Addresses may have abbreviations and format differences'
      },
      emails: {
        recommended_functions: ['exact_match'],
        typical_threshold: 1.0,
        considerations: 'Emails should match exactly or not at all'
      },
      phones: {
        recommended_functions: ['exact_match', 'normalized_levenshtein'],
        typical_threshold: 0.9,
        considerations: 'Phone numbers may have different formatting'
      },
      companies: {
        recommended_functions: ['ngram_similarity'],
        typical_threshold: 0.8,
        considerations: 'Company names may have legal suffixes and abbreviations'
      }
    };
    
    res.json({
      success: true,
      similarity_functions: functions,
      field_strategies: fieldStrategies,
      default_configuration: getDefaultFieldWeights(),
      implementation_notes: {
        performance: 'ArangoDB native functions are optimized for large datasets',
        accuracy: 'Combine multiple functions for robust similarity scoring',
        tuning: 'Adjust thresholds based on data quality and business requirements'
      }
    });
    
  } catch (error) {
    logError('Failed to get similarity functions: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'FUNCTIONS_RETRIEVAL_FAILED'
    });
  }
})
.response(200, joi.object({
  success: joi.boolean().required(),
  similarity_functions: joi.object().required(),
  field_strategies: joi.object().required()
}).required(), 'Available similarity functions and strategies')
.summary('Get available similarity functions')
.description('Returns information about available similarity functions and recommended usage strategies');

/**
 * Core function: Compute aggregate similarity score using Fellegi-Sunter framework
 */
function computeAggregateScore(docA, docB, fieldWeights, includeDetails = false) {
  // Use ArangoDB's native similarity functions for performance
  const aqlQuery = `
    LET docA = @docA
    LET docB = @docB
    
    RETURN {
      name_ngram: NGRAM_SIMILARITY(
        CONCAT(docA.first_name || "", " ", docA.last_name || ""), 
        CONCAT(docB.first_name || "", " ", docB.last_name || ""), 
        3
      ),
      first_name_ngram: NGRAM_SIMILARITY(docA.first_name || "", docB.first_name || "", 3),
      last_name_ngram: NGRAM_SIMILARITY(docA.last_name || "", docB.last_name || "", 3),
      address_ngram: NGRAM_SIMILARITY(docA.address || "", docB.address || "", 3),
      city_ngram: NGRAM_SIMILARITY(docA.city || "", docB.city || "", 3),
      company_ngram: NGRAM_SIMILARITY(docA.company || "", docB.company || "", 3),
      
      email_exact: (docA.email || "") == (docB.email || "") ? 1.0 : 0.0,
      phone_exact: (docA.phone || "") == (docB.phone || "") ? 1.0 : 0.0,
      
      first_name_levenshtein: LENGTH(docA.first_name || "") > 0 AND LENGTH(docB.first_name || "") > 0 ? 
        1 - (LEVENSHTEIN_DISTANCE(docA.first_name, docB.first_name) / 
             (LENGTH(docA.first_name) > LENGTH(docB.first_name) ? LENGTH(docA.first_name) : LENGTH(docB.first_name))) : 0.0,
      last_name_levenshtein: LENGTH(docA.last_name || "") > 0 AND LENGTH(docB.last_name || "") > 0 ? 
        1 - (LEVENSHTEIN_DISTANCE(docA.last_name, docB.last_name) / 
             (LENGTH(docA.last_name) > LENGTH(docB.last_name) ? LENGTH(docA.last_name) : LENGTH(docB.last_name))) : 0.0
    }
  `;
  
  try {
    const result = db._query(aqlQuery, { docA, docB });
    const similarities = result.toArray()[0];
    
    // Apply Fellegi-Sunter framework with field-specific weights
    return computeFellegiSunterScore(similarities, fieldWeights, includeDetails);
    
  } catch (error) {
    logError(`Similarity computation query failed: ${error.message}`);
    throw new Error(`Similarity computation failed: ${error.message}`);
  }
}

/**
 * Core function: Apply Fellegi-Sunter probabilistic framework
 */
function computeFellegiSunterScore(similarities, fieldWeights, includeDetails = false) {
  let totalScore = 0;
  const fieldScores = {};
  
  for (const [field, simValue] of Object.entries(similarities)) {
    if (fieldWeights[field]) {
      const weights = fieldWeights[field];
      const agreement = simValue > (weights.threshold || 0.5);
      
      // Fellegi-Sunter log-likelihood ratio
      const weight = agreement ? 
        Math.log(weights.m_prob / weights.u_prob) :
        Math.log((1 - weights.m_prob) / (1 - weights.u_prob));
      
      fieldScores[field] = {
        similarity: simValue,
        agreement: agreement,
        weight: weight,
        threshold: weights.threshold || 0.5
      };
      
      // Add field importance multiplier
      const importance = weights.importance || 1.0;
      totalScore += weight * importance;
    }
  }
  
  // Calculate confidence and match decision
  const globalWeights = fieldWeights.global || {
    upper_threshold: 2.0,
    lower_threshold: -2.0
  };
  
  const isMatch = totalScore > globalWeights.upper_threshold;
  const isPossibleMatch = totalScore > globalWeights.lower_threshold && 
                         totalScore <= globalWeights.upper_threshold;
  
  const confidence = Math.min(Math.max(
    (totalScore - globalWeights.lower_threshold) / 
    (globalWeights.upper_threshold - globalWeights.lower_threshold), 
    0
  ), 1);
  
  const result = {
    total_score: totalScore,
    is_match: isMatch,
    is_possible_match: isPossibleMatch,
    confidence: confidence,
    decision: isMatch ? 'match' : (isPossibleMatch ? 'possible_match' : 'non_match')
  };
  
  if (includeDetails) {
    result.field_scores = fieldScores;
    result.thresholds = globalWeights;
  }
  
  return result;
}

/**
 * Get default field weights configuration
 */
function getDefaultFieldWeights() {
  return {
    // Name fields
    name_ngram: {
      m_prob: 0.9,
      u_prob: 0.01,
      threshold: 0.7,
      importance: 1.0
    },
    first_name_ngram: {
      m_prob: 0.85,
      u_prob: 0.02,
      threshold: 0.7,
      importance: 0.8
    },
    last_name_ngram: {
      m_prob: 0.9,
      u_prob: 0.015,
      threshold: 0.7,
      importance: 1.0
    },
    first_name_levenshtein: {
      m_prob: 0.8,
      u_prob: 0.05,
      threshold: 0.6,
      importance: 0.7
    },
    last_name_levenshtein: {
      m_prob: 0.85,
      u_prob: 0.03,
      threshold: 0.6,
      importance: 0.9
    },
    
    // Address fields
    address_ngram: {
      m_prob: 0.8,
      u_prob: 0.03,
      threshold: 0.6,
      importance: 0.8
    },
    city_ngram: {
      m_prob: 0.9,
      u_prob: 0.05,
      threshold: 0.8,
      importance: 0.6
    },
    
    // Exact match fields
    email_exact: {
      m_prob: 0.95,
      u_prob: 0.001,
      threshold: 1.0,
      importance: 1.2
    },
    phone_exact: {
      m_prob: 0.9,
      u_prob: 0.005,
      threshold: 1.0,
      importance: 1.1
    },
    
    // Company field
    company_ngram: {
      m_prob: 0.8,
      u_prob: 0.02,
      threshold: 0.7,
      importance: 0.7
    },
    
    // Global thresholds
    global: {
      upper_threshold: 2.0,   // Clear match
      lower_threshold: -1.0   // Clear non-match
    }
  };
}

module.exports = router;
