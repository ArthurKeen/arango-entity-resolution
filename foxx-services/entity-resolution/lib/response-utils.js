'use strict';

/**
 * Response Utility Functions
 * 
 * Standardizes HTTP responses across all route handlers to eliminate
 * duplicate response formatting code.
 */

const { ERROR_CODES } = require('./constants');
const { logError } = require('../utils/logger');

/**
 * Send standardized success response
 */
function sendSuccess(res, data, message = null, statusCode = 200) {
  const response = {
    success: true,
    ...data
  };
  
  if (message) {
    response.message = message;
  }
  
  res.status(statusCode);
  res.json(response);
}

/**
 * Send standardized error response
 */
function sendError(res, errorCode, message, statusCode = 500, additionalData = null) {
  const response = {
    success: false,
    error: message,
    code: errorCode,
    timestamp: new Date().toISOString()
  };
  
  if (additionalData) {
    Object.assign(response, additionalData);
  }
  
  res.status(statusCode);
  res.json(response);
}

/**
 * Send validation error response
 */
function sendValidationError(res, message, missingFields = null) {
  const additionalData = missingFields ? { missing_fields: missingFields } : null;
  sendError(res, ERROR_CODES.MISSING_PARAMETERS, message, 400, additionalData);
}

/**
 * Send not found error response
 */
function sendNotFoundError(res, resourceType, resourceName) {
  const message = `${resourceType} '${resourceName}' does not exist`;
  let errorCode;
  
  switch (resourceType.toLowerCase()) {
    case 'collection':
      errorCode = ERROR_CODES.COLLECTION_NOT_FOUND;
      break;
    case 'view':
      errorCode = ERROR_CODES.VIEW_NOT_FOUND;
      break;
    case 'edge collection':
      errorCode = ERROR_CODES.EDGE_COLLECTION_NOT_FOUND;
      break;
    default:
      errorCode = ERROR_CODES.INTERNAL_ERROR;
  }
  
  sendError(res, errorCode, message, 404);
}

/**
 * Send batch size exceeded error
 */
function sendBatchSizeError(res, currentSize, maxSize, resourceType = 'items') {
  const message = `Maximum ${maxSize} ${resourceType} allowed per batch, received ${currentSize}`;
  sendError(res, ERROR_CODES.BATCH_SIZE_EXCEEDED, message, 400);
}

/**
 * Handle service errors with standardized logging and response
 */
function handleServiceError(res, error, operation, errorCode = null) {
  const code = errorCode || ERROR_CODES.INTERNAL_ERROR;
  const message = `Failed to ${operation}: ${error.message}`;
  
  logError(message);
  sendError(res, code, error.message, 500);
}

/**
 * Send processing results with statistics
 */
function sendProcessingResults(res, results, statistics, operation, processingTimeMs) {
  const response = {
    success: true,
    results: results,
    statistics: {
      ...statistics,
      processing_time_ms: processingTimeMs
    },
    operation: operation
  };
  
  res.json(response);
}

/**
 * Send batch processing results
 */
function sendBatchResults(res, results, statistics, operation, processingTimeMs, parameters = null) {
  const response = {
    success: true,
    batch_size: Array.isArray(results) ? results.length : statistics.total_items || 0,
    results: results,
    statistics: {
      ...statistics,
      processing_time_ms: processingTimeMs
    },
    operation: operation
  };
  
  if (parameters) {
    response.parameters = parameters;
  }
  
  res.json(response);
}

/**
 * Middleware to wrap route handlers with standardized error handling
 */
function wrapRouteHandler(handler, operation) {
  return async function(req, res) {
    try {
      await handler(req, res);
    } catch (error) {
      handleServiceError(res, error, operation);
    }
  };
}

/**
 * Validate required fields in request body
 */
function validateRequiredFields(body, requiredFields) {
  const missingFields = [];
  
  for (const field of requiredFields) {
    if (body[field] === undefined || body[field] === null) {
      missingFields.push(field);
    }
  }
  
  return missingFields.length > 0 ? missingFields : null;
}

/**
 * Create standardized timer response
 */
function createTimerResponse(timer, additionalData = {}) {
  return {
    processing_time_ms: timer.duration(),
    ...additionalData
  };
}

module.exports = {
  sendSuccess,
  sendError,
  sendValidationError,
  sendNotFoundError,
  sendBatchSizeError,
  handleServiceError,
  sendProcessingResults,
  sendBatchResults,
  wrapRouteHandler,
  validateRequiredFields,
  createTimerResponse
};
