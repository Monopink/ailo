/**
 * Logger utility
 * Provides structured logging with different log levels
 */

import { LOG_LEVEL } from './env';

const LOG_LEVELS = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3,
  NONE: 4  // No logging
};

// Current log level (configured from environment)
let currentLogLevel = LOG_LEVELS[LOG_LEVEL] || LOG_LEVELS.NONE;

/**
 * Set log level
 * @param {string} level - Log level (DEBUG, INFO, WARN, ERROR)
 */
export function setLogLevel(level) {
  if (LOG_LEVELS[level] !== undefined) {
    currentLogLevel = LOG_LEVELS[level];
  }
}

/**
 * Format log message
 * @param {string} level - Log level
 * @param {string} tag - Log tag
 * @param {string} message - Log message
 * @param {Object} data - Additional data
 * @returns {string} Formatted log message
 */
function formatLog(level, tag, message, data) {
  const timestamp = new Date().toISOString();
  const dataStr = data ? ` ${JSON.stringify(data)}` : '';
  return `[${timestamp}] [${level}] [${tag}] ${message}${dataStr}`;
}

/**
 * Log message
 * @param {string} level - Log level
 * @param {string} tag - Log tag
 * @param {string} message - Log message
 * @param {Object} data - Additional data
 */
function log(level, tag, message, data) {
  const logLevel = LOG_LEVELS[level];

  if (logLevel < currentLogLevel) {
    return;
  }

  const formattedLog = formatLog(level, tag, message, data);

  switch (level) {
    case 'DEBUG':
    case 'INFO':
      console.log(formattedLog);
      break;
    case 'WARN':
      console.warn(formattedLog);
      break;
    case 'ERROR':
      console.error(formattedLog);
      break;
  }
}

/**
 * Create logger instance
 * @param {string} tag - Logger tag
 * @returns {Object} Logger instance
 */
export function getLogger(tag) {
  return {
    debug: (message, data) => log('DEBUG', tag, message, data),
    info: (message, data) => log('INFO', tag, message, data),
    warn: (message, data) => log('WARN', tag, message, data),
    error: (message, data) => log('ERROR', tag, message, data)
  };
}

// Default logger instance for backward compatibility
const defaultLogger = {
  debug: (message, data) => log('DEBUG', 'App', message, data),
  info: (message, data) => log('INFO', 'App', message, data),
  warn: (message, data) => log('WARN', 'App', message, data),
  error: (message, data) => log('ERROR', 'App', message, data),
  getLogger,
  setLogLevel
};

export default defaultLogger;

