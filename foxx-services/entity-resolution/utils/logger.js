'use strict';

/**
 * Logging Utilities
 * 
 * Centralized logging functions for the entity resolution service
 */

const { context } = require('@arangodb/foxx');

/**
 * Get current log level from configuration
 */
function getLogLevel() {
  return module.context.configuration.logLevel || 'info';
}

/**
 * Log levels (in order of verbosity)
 */
const LOG_LEVELS = {
  'error': 0,
  'warn': 1,
  'info': 2,
  'debug': 3
};

/**
 * Check if message should be logged at current level
 */
function shouldLog(level) {
  const currentLevel = getLogLevel();
  return LOG_LEVELS[level] <= LOG_LEVELS[currentLevel];
}

/**
 * Format log message with timestamp and level
 */
function formatMessage(level, message, data = null) {
  const timestamp = new Date().toISOString();
  const prefix = `[${timestamp}] [${level.toUpperCase()}] [EntityResolution]`;
  
  if (data) {
    return `${prefix} ${message} | Data: ${JSON.stringify(data)}`;
  }
  
  return `${prefix} ${message}`;
}

/**
 * Log error message
 */
function logError(message, data = null) {
  if (shouldLog('error')) {
    console.error(formatMessage('error', message, data));
  }
}

/**
 * Log warning message
 */
function logWarn(message, data = null) {
  if (shouldLog('warn')) {
    console.warn(formatMessage('warn', message, data));
  }
}

/**
 * Log info message
 */
function logInfo(message, data = null) {
  if (shouldLog('info')) {
    console.log(formatMessage('info', message, data));
  }
}

/**
 * Log debug message
 */
function logDebug(message, data = null) {
  if (shouldLog('debug')) {
    console.log(formatMessage('debug', message, data));
  }
}

/**
 * Log performance metrics
 */
function logPerformance(operation, startTime, additionalData = {}) {
  const duration = Date.now() - startTime;
  const message = `${operation} completed in ${duration}ms`;
  
  logInfo(message, {
    operation: operation,
    duration_ms: duration,
    ...additionalData
  });
}

/**
 * Log API request
 */
function logRequest(req, additionalData = {}) {
  if (shouldLog('debug')) {
    logDebug(`API Request: ${req.method} ${req.path}`, {
      method: req.method,
      path: req.path,
      query: req.queryParams,
      headers: req.headers,
      ...additionalData
    });
  }
}

/**
 * Log API response
 */
function logResponse(req, res, startTime, additionalData = {}) {
  const duration = Date.now() - startTime;
  
  if (shouldLog('info')) {
    logInfo(`API Response: ${req.method} ${req.path} - ${res.statusCode}`, {
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration_ms: duration,
      ...additionalData
    });
  }
}

/**
 * Create a performance timer
 */
function createTimer(operation) {
  const startTime = Date.now();
  
  return {
    start: startTime,
    log: function(additionalData = {}) {
      logPerformance(operation, startTime, additionalData);
    },
    duration: function() {
      return Date.now() - startTime;
    }
  };
}

module.exports = {
  logError,
  logWarn,
  logInfo,
  logDebug,
  logPerformance,
  logRequest,
  logResponse,
  createTimer,
  getLogLevel,
  shouldLog
};
