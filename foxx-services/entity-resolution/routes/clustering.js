'use strict';

/**
 * Clustering Routes for Entity Resolution Service
 * 
 * Implements graph-based clustering using ArangoDB's native algorithms:
 * - Build similarity graphs from scored pairs using UPSERT for idempotency
 * - Execute Weakly Connected Components (WCC) clustering
 * - Validate cluster quality and coherence
 * - Generate entity clusters with confidence scores and metadata
 */

const createRouter = require('@arangodb/foxx/router');
const joi = require('joi');
const { query, db } = require('@arangodb');
const { context } = require('@arangodb/foxx');

const router = createRouter();

// Import utility functions
const { logInfo, logError, logDebug, createTimer } = require('../utils/logger');
const { checkCollectionExists } = require('../lib/setup-utils');

/**
 * Build similarity graph from scored pairs
 */
router.post('/build-graph', function (req, res) {
  const timer = createTimer('build_similarity_graph');
  
  try {
    const {
      scoredPairs,
      threshold = module.context.configuration.defaultSimilarityThreshold || 0.8,
      edgeCollection = 'similarities',
      forceUpdate = false
    } = req.body;
    
    // Validate inputs
    if (!scoredPairs || !Array.isArray(scoredPairs)) {
      return res.status(400).json({
        success: false,
        error: 'scoredPairs array is required',
        code: 'MISSING_SCORED_PAIRS'
      });
    }
    
    if (scoredPairs.length > 10000) {
      return res.status(400).json({
        success: false,
        error: 'Maximum 10,000 scored pairs allowed per batch',
        code: 'BATCH_SIZE_EXCEEDED'
      });
    }
    
    // Ensure edge collection exists
    if (!checkCollectionExists(edgeCollection)) {
      try {
        db._createEdgeCollection(edgeCollection);
        logInfo(`Created edge collection: ${edgeCollection}`);
      } catch (error) {
        return res.status(500).json({
          success: false,
          error: `Failed to create edge collection '${edgeCollection}': ${error.message}`,
          code: 'EDGE_COLLECTION_CREATION_FAILED'
        });
      }
    }
    
    // Build similarity graph
    const results = buildSimilarityGraph(scoredPairs, threshold, edgeCollection, forceUpdate);
    
    timer.log({
      scored_pairs: scoredPairs.length,
      threshold: threshold,
      edges_created: results.created_count,
      edges_updated: results.updated_count,
      edges_skipped: results.skipped_count
    });
    
    res.json({
      success: true,
      edge_collection: edgeCollection,
      results: results,
      statistics: {
        input_pairs: scoredPairs.length,
        threshold_used: threshold,
        processing_time_ms: timer.duration()
      }
    });
    
  } catch (error) {
    logError('Failed to build similarity graph: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'GRAPH_BUILD_FAILED'
    });
  }
})
.body(joi.object({
  scoredPairs: joi.array().items(joi.object({
    docA_id: joi.string().required(),
    docB_id: joi.string().required(),
    total_score: joi.number().required(),
    field_scores: joi.object().optional(),
    is_match: joi.boolean().optional()
  })).max(10000).required(),
  threshold: joi.number().min(0).max(10).optional(),
  edgeCollection: joi.string().optional(),
  forceUpdate: joi.boolean().optional()
}).required(), 'Similarity graph building parameters')
.response(200, joi.object({
  success: joi.boolean().required(),
  results: joi.object().required(),
  statistics: joi.object().required()
}).required(), 'Graph building results')
.summary('Build similarity graph from scored pairs')
.description('Creates or updates similarity edges in the graph for clustering operations');

/**
 * Execute Weakly Connected Components clustering
 */
router.post('/wcc', function (req, res) {
  const timer = createTimer('weakly_connected_components');
  
  try {
    const {
      edgeCollection = 'similarities',
      minSimilarity = module.context.configuration.defaultSimilarityThreshold || 0.8,
      maxClusterSize = 100,
      outputCollection = 'entity_clusters'
    } = req.body;
    
    // Validate edge collection exists
    if (!checkCollectionExists(edgeCollection)) {
      return res.status(404).json({
        success: false,
        error: `Edge collection '${edgeCollection}' does not exist`,
        code: 'EDGE_COLLECTION_NOT_FOUND'
      });
    }
    
    // Ensure output collection exists
    if (!checkCollectionExists(outputCollection)) {
      try {
        db._createDocumentCollection(outputCollection);
        logInfo(`Created cluster collection: ${outputCollection}`);
      } catch (error) {
        return res.status(500).json({
          success: false,
          error: `Failed to create cluster collection '${outputCollection}': ${error.message}`,
          code: 'CLUSTER_COLLECTION_CREATION_FAILED'
        });
      }
    }
    
    // Execute Weakly Connected Components
    const clusters = executeWCCClustering(edgeCollection, minSimilarity, maxClusterSize);
    
    // Validate cluster quality
    const validatedClusters = validateClusterQuality(clusters);
    
    // Store clusters in output collection
    const storageResults = storeClusters(validatedClusters, outputCollection);
    
    timer.log({
      edge_collection: edgeCollection,
      clusters_found: clusters.length,
      valid_clusters: validatedClusters.filter(c => c.quality_score > 0.5).length,
      min_similarity: minSimilarity
    });
    
    res.json({
      success: true,
      edge_collection: edgeCollection,
      output_collection: outputCollection,
      clusters: validatedClusters,
      storage_results: storageResults,
      statistics: {
        total_clusters: clusters.length,
        valid_clusters: validatedClusters.filter(c => c.quality_score > 0.5).length,
        average_cluster_size: clusters.length > 0 ? 
          clusters.reduce((sum, c) => sum + c.cluster_size, 0) / clusters.length : 0,
        largest_cluster_size: clusters.length > 0 ? 
          Math.max(...clusters.map(c => c.cluster_size)) : 0,
        processing_time_ms: timer.duration()
      },
      parameters: {
        min_similarity: minSimilarity,
        max_cluster_size: maxClusterSize
      }
    });
    
  } catch (error) {
    logError('Failed to execute WCC clustering: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'WCC_CLUSTERING_FAILED'
    });
  }
})
.body(joi.object({
  edgeCollection: joi.string().optional(),
  minSimilarity: joi.number().min(0).max(10).optional(),
  maxClusterSize: joi.number().integer().min(2).max(1000).optional(),
  outputCollection: joi.string().optional()
}).optional(), 'WCC clustering parameters')
.response(200, joi.object({
  success: joi.boolean().required(),
  clusters: joi.array().required(),
  statistics: joi.object().required()
}).required(), 'WCC clustering results')
.summary('Execute Weakly Connected Components clustering')
.description('Groups entities into clusters using graph connectivity analysis');

/**
 * Validate cluster quality
 */
router.post('/validate', function (req, res) {
  const timer = createTimer('validate_clusters');
  
  try {
    const {
      clusters,
      qualityThresholds = getDefaultQualityThresholds()
    } = req.body;
    
    // Validate inputs
    if (!clusters || !Array.isArray(clusters)) {
      return res.status(400).json({
        success: false,
        error: 'clusters array is required',
        code: 'MISSING_CLUSTERS'
      });
    }
    
    // Validate each cluster
    const validationResults = clusters.map(cluster => validateSingleCluster(cluster, qualityThresholds));
    
    // Calculate overall statistics
    const validClusters = validationResults.filter(r => r.quality_score >= qualityThresholds.min_quality_score);
    const invalidClusters = validationResults.filter(r => r.quality_score < qualityThresholds.min_quality_score);
    
    const overallQuality = validationResults.length > 0 ? 
      validationResults.reduce((sum, r) => sum + r.quality_score, 0) / validationResults.length : 0;
    
    timer.log({
      total_clusters: clusters.length,
      valid_clusters: validClusters.length,
      invalid_clusters: invalidClusters.length,
      overall_quality: overallQuality
    });
    
    res.json({
      success: true,
      validation_results: validationResults,
      statistics: {
        total_clusters: clusters.length,
        valid_clusters: validClusters.length,
        invalid_clusters: invalidClusters.length,
        overall_quality_score: overallQuality,
        validation_pass_rate: clusters.length > 0 ? validClusters.length / clusters.length : 0,
        processing_time_ms: timer.duration()
      },
      quality_thresholds: qualityThresholds,
      recommendations: generateQualityRecommendations(validationResults)
    });
    
  } catch (error) {
    logError('Failed to validate clusters: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'CLUSTER_VALIDATION_FAILED'
    });
  }
})
.body(joi.object({
  clusters: joi.array().required(),
  qualityThresholds: joi.object().optional()
}).required(), 'Cluster validation parameters')
.response(200, joi.object({
  success: joi.boolean().required(),
  validation_results: joi.array().required(),
  statistics: joi.object().required()
}).required(), 'Cluster validation results')
.summary('Validate cluster quality and coherence')
.description('Analyzes clusters for quality metrics and identifies potential issues');

/**
 * Get clustering statistics for a similarity graph
 */
router.get('/stats/:edgeCollection', function (req, res) {
  try {
    const { edgeCollection } = req.pathParams;
    
    if (!checkCollectionExists(edgeCollection)) {
      return res.status(404).json({
        success: false,
        error: `Edge collection '${edgeCollection}' does not exist`,
        code: 'EDGE_COLLECTION_NOT_FOUND'
      });
    }
    
    const stats = getGraphStatistics(edgeCollection);
    
    res.json({
      success: true,
      edge_collection: edgeCollection,
      statistics: stats
    });
    
  } catch (error) {
    logError('Failed to get clustering stats: ' + error.message);
    res.status(500);
    res.json({
      success: false,
      error: error.message,
      code: 'STATS_RETRIEVAL_FAILED'
    });
  }
})
.pathParam('edgeCollection', joi.string().required(), 'Edge collection name')
.response(200, joi.object({
  success: joi.boolean().required(),
  statistics: joi.object().required()
}).required(), 'Clustering statistics')
.summary('Get clustering statistics for similarity graph')
.description('Returns metrics about the similarity graph structure and clustering potential');

/**
 * Core function: Build similarity graph from scored pairs
 */
function buildSimilarityGraph(scoredPairs, threshold, edgeCollection, forceUpdate) {
  const results = {
    created_count: 0,
    updated_count: 0,
    skipped_count: 0,
    errors: []
  };
  
  // Filter pairs above threshold
  const validPairs = scoredPairs.filter(pair => pair.total_score >= threshold);
  
  for (const pair of validPairs) {
    try {
      // Use UPSERT for idempotent edge creation
      const aql = `
        UPSERT { _from: @from, _to: @to }
        INSERT {
          _from: @from,
          _to: @to,
          similarity_score: @score,
          field_scores: @fieldScores,
          is_match: @isMatch,
          algorithm: "fellegi_sunter",
          created_at: DATE_NOW(),
          update_count: 1
        }
        UPDATE {
          similarity_score: @forceUpdate ? @score : AVERAGE([OLD.similarity_score, @score]),
          field_scores: @forceUpdate ? @fieldScores : OLD.field_scores,
          is_match: @forceUpdate ? @isMatch : (OLD.is_match || @isMatch),
          updated_at: DATE_NOW(),
          update_count: OLD.update_count + 1
        }
        IN @@edgeCollection
        RETURN { created: NEW._rev == OLD._rev ? false : true, updated: NEW._rev != OLD._rev }
      `;
      
      const result = query(aql, {
        from: pair.docA_id,
        to: pair.docB_id,
        score: pair.total_score,
        fieldScores: pair.field_scores || {},
        isMatch: pair.is_match || false,
        forceUpdate: forceUpdate,
        '@edgeCollection': edgeCollection
      }).next();
      
      if (result.created) {
        results.created_count++;
      } else if (result.updated) {
        results.updated_count++;
      } else {
        results.skipped_count++;
      }
      
    } catch (error) {
      logError(`Failed to create/update edge for pair ${pair.docA_id}-${pair.docB_id}: ${error.message}`);
      results.errors.push({
        pair: `${pair.docA_id}-${pair.docB_id}`,
        error: error.message
      });
    }
  }
  
  logInfo(`Graph building completed: ${results.created_count} created, ${results.updated_count} updated, ${results.skipped_count} skipped`);
  return results;
}

/**
 * Core function: Execute Weakly Connected Components clustering
 */
function executeWCCClustering(edgeCollection, minSimilarity, maxClusterSize) {
  const aql = `
    FOR component IN GRAPH_WEAKLY_CONNECTED_COMPONENTS(
      @@edgeCollection,
      {
        weightAttribute: "similarity_score",
        threshold: @minSimilarity
      }
    )
    
    LET clusterSize = LENGTH(component.vertices)
    FILTER clusterSize >= 2 AND clusterSize <= @maxClusterSize
    
    LET avgScore = AVERAGE(
      FOR edge IN component.edges
        RETURN edge.similarity_score
    )
    
    LET minScore = MIN(
      FOR edge IN component.edges
        RETURN edge.similarity_score
    )
    
    LET maxScore = MAX(
      FOR edge IN component.edges
        RETURN edge.similarity_score
    )
    
    RETURN {
      cluster_id: CONCAT("cluster_", MD5(TO_STRING(SORTED(component.vertices)))),
      member_ids: component.vertices,
      cluster_size: clusterSize,
      edge_count: LENGTH(component.edges),
      average_similarity: avgScore,
      min_similarity: minScore,
      max_similarity: maxScore,
      density: LENGTH(component.edges) / (clusterSize * (clusterSize - 1) / 2),
      created_at: DATE_NOW()
    }
  `;
  
  try {
    logDebug(`Executing WCC clustering on ${edgeCollection} with min similarity ${minSimilarity}`);
    
    const clusters = query(aql, {
      '@edgeCollection': edgeCollection,
      minSimilarity: minSimilarity,
      maxClusterSize: maxClusterSize
    }).toArray();
    
    logInfo(`WCC clustering found ${clusters.length} clusters`);
    return clusters;
    
  } catch (error) {
    logError(`WCC clustering query failed: ${error.message}`);
    throw new Error(`WCC clustering failed: ${error.message}`);
  }
}

/**
 * Core function: Validate cluster quality
 */
function validateClusterQuality(clusters) {
  return clusters.map(cluster => validateSingleCluster(cluster, getDefaultQualityThresholds()));
}

/**
 * Validate a single cluster
 */
function validateSingleCluster(cluster, thresholds) {
  const qualityMetrics = {
    size_appropriate: cluster.cluster_size >= thresholds.min_cluster_size && 
                     cluster.cluster_size <= thresholds.max_cluster_size,
    similarity_coherent: cluster.average_similarity >= thresholds.min_avg_similarity,
    density_adequate: cluster.density >= thresholds.min_density,
    score_range_reasonable: (cluster.max_similarity - cluster.min_similarity) <= thresholds.max_score_range
  };
  
  const passedMetrics = Object.values(qualityMetrics).filter(Boolean).length;
  const totalMetrics = Object.keys(qualityMetrics).length;
  const qualityScore = passedMetrics / totalMetrics;
  
  return {
    ...cluster,
    quality_metrics: qualityMetrics,
    quality_score: qualityScore,
    quality_issues: Object.entries(qualityMetrics)
      .filter(([_, passed]) => !passed)
      .map(([metric, _]) => metric),
    is_valid: qualityScore >= thresholds.min_quality_score
  };
}

/**
 * Store clusters in collection
 */
function storeClusters(clusters, outputCollection) {
  const results = {
    stored_count: 0,
    errors: []
  };
  
  for (const cluster of clusters) {
    try {
      const aql = `
        UPSERT { cluster_id: @clusterId }
        INSERT @cluster
        UPDATE @cluster
        IN @@outputCollection
        RETURN NEW
      `;
      
      query(aql, {
        clusterId: cluster.cluster_id,
        cluster: cluster,
        '@outputCollection': outputCollection
      }).next();
      
      results.stored_count++;
      
    } catch (error) {
      logError(`Failed to store cluster ${cluster.cluster_id}: ${error.message}`);
      results.errors.push({
        cluster_id: cluster.cluster_id,
        error: error.message
      });
    }
  }
  
  return results;
}

/**
 * Get graph statistics
 */
function getGraphStatistics(edgeCollection) {
  const aql = `
    LET edgeStats = (
      FOR edge IN @@edgeCollection
        COLLECT AGGREGATE 
          totalEdges = COUNT(),
          avgSimilarity = AVERAGE(edge.similarity_score),
          minSimilarity = MIN(edge.similarity_score),
          maxSimilarity = MAX(edge.similarity_score)
        RETURN {
          total_edges: totalEdges,
          average_similarity: avgSimilarity,
          min_similarity: minSimilarity,
          max_similarity: maxSimilarity
        }
    )[0]
    
    LET vertexStats = (
      FOR edge IN @@edgeCollection
        FOR vertex IN [edge._from, edge._to]
          COLLECT v = vertex WITH COUNT INTO degree
          COLLECT AGGREGATE
            uniqueVertices = COUNT(),
            avgDegree = AVERAGE(degree),
            maxDegree = MAX(degree)
          RETURN {
            unique_vertices: uniqueVertices,
            average_degree: avgDegree,
            max_degree: maxDegree
          }
    )[0]
    
    RETURN MERGE(edgeStats, vertexStats)
  `;
  
  try {
    const result = db._query(aql, { '@edgeCollection': edgeCollection });
    const stats = result.toArray()[0];
    return stats || {};
  } catch (error) {
    logError(`Failed to get graph statistics: ${error.message}`);
    return { error: error.message };
  }
}

/**
 * Get default quality thresholds
 */
function getDefaultQualityThresholds() {
  return {
    min_cluster_size: 2,
    max_cluster_size: 50,
    min_avg_similarity: 0.7,
    min_density: 0.3,
    max_score_range: 0.5,
    min_quality_score: 0.6
  };
}

/**
 * Generate quality recommendations
 */
function generateQualityRecommendations(validationResults) {
  const recommendations = [];
  
  const invalidClusters = validationResults.filter(r => !r.is_valid);
  if (invalidClusters.length > 0) {
    recommendations.push({
      type: 'quality_improvement',
      message: `${invalidClusters.length} clusters failed quality validation`,
      suggestion: 'Review similarity thresholds and clustering parameters'
    });
  }
  
  const largeClusters = validationResults.filter(r => r.cluster_size > 20);
  if (largeClusters.length > 0) {
    recommendations.push({
      type: 'large_clusters',
      message: `${largeClusters.length} clusters are unusually large`,
      suggestion: 'Consider increasing similarity thresholds or reviewing data quality'
    });
  }
  
  const lowDensityClusters = validationResults.filter(r => r.density < 0.3);
  if (lowDensityClusters.length > 0) {
    recommendations.push({
      type: 'low_density',
      message: `${lowDensityClusters.length} clusters have low edge density`,
      suggestion: 'Review blocking strategies and similarity computation'
    });
  }
  
  return recommendations;
}

module.exports = router;
