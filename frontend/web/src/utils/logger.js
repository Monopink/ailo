/**
 * Centralized logging system with environment-aware log levels
 * Provides structured logging for development and production environments
 */

import { DEV_CONFIG } from '../config/constants.js';

// Log levels
export const LOG_LEVELS = {
  ERROR: 0,
  WARN: 1,
  INFO: 2,
  DEBUG: 3,
};

// Log level names for display
const LOG_LEVEL_NAMES = {
  [LOG_LEVELS.ERROR]: 'ERROR',
  [LOG_LEVELS.WARN]: 'WARN',
  [LOG_LEVELS.INFO]: 'INFO',
  [LOG_LEVELS.DEBUG]: 'DEBUG',
};

// Current log level based on environment
const CURRENT_LOG_LEVEL = DEV_CONFIG.ENABLE_DEBUG ? LOG_LEVELS.DEBUG : LOG_LEVELS.WARN;

/**
 * Format log message with timestamp and context
 */
function formatLogMessage(level, message, context = null) {
  const timestamp = new Date().toISOString();
  const levelName = LOG_LEVEL_NAMES[level];
  const contextStr = context ? ` [${context}]` : '';
  
  return `[${timestamp}] ${levelName}${contextStr}: ${message}`;
}

/**
 * Check if log level should be output
 */
function shouldLog(level) {
  return level <= CURRENT_LOG_LEVEL;
}

/**
 * Core logging function
 */
function log(level, message, data = null, context = null) {
  if (!shouldLog(level)) {
    return;
  }

  const formattedMessage = formatLogMessage(level, message, context);
  
  switch (level) {
    case LOG_LEVELS.ERROR:
      if (data) {
        console.error(formattedMessage, data);
      } else {
        console.error(formattedMessage);
      }
      break;
      
    case LOG_LEVELS.WARN:
      if (data) {
        console.warn(formattedMessage, data);
      } else {
        console.warn(formattedMessage);
      }
      break;
      
    case LOG_LEVELS.INFO:
      if (data) {
        console.info(formattedMessage, data);
      } else {
        console.info(formattedMessage);
      }
      break;
      
    case LOG_LEVELS.DEBUG:
      if (data) {
        console.log(formattedMessage, data);
      } else {
        console.log(formattedMessage);
      }
      break;
      
    default:
      console.log(formattedMessage, data);
  }
}

/**
 * Logger class with context support
 */
class Logger {
  constructor(context = null) {
    this.context = context;
  }

  /**
   * Log error messages (always shown)
   */
  error(message, data = null) {
    log(LOG_LEVELS.ERROR, message, data, this.context);
  }

  /**
   * Log warning messages
   */
  warn(message, data = null) {
    log(LOG_LEVELS.WARN, message, data, this.context);
  }

  /**
   * Log info messages
   */
  info(message, data = null) {
    log(LOG_LEVELS.INFO, message, data, this.context);
  }

  /**
   * Log debug messages (development only)
   */
  debug(message, data = null) {
    log(LOG_LEVELS.DEBUG, message, data, this.context);
  }

  /**
   * Create a child logger with additional context
   */
  child(childContext) {
    const newContext = this.context ? `${this.context}:${childContext}` : childContext;
    return new Logger(newContext);
  }
}

// Default logger instance
export const logger = new Logger();

// Specialized loggers for different modules
export const apiLogger = new Logger('API');
export const chatLogger = new Logger('CHAT');
export const authLogger = new Logger('AUTH');
export const uiLogger = new Logger('UI');
export const errorLogger = new Logger('ERROR');

/**
 * Performance logging utilities
 */
export const performance = {
  /**
   * Start a performance timer
   */
  start(label) {
    if (DEV_CONFIG.ENABLE_PERFORMANCE) {
      console.time(label);
    }
  },

  /**
   * End a performance timer
   */
  end(label) {
    if (DEV_CONFIG.ENABLE_PERFORMANCE) {
      console.timeEnd(label);
    }
  },

  /**
   * Log performance mark
   */
  mark(label, data = null) {
    if (DEV_CONFIG.ENABLE_PERFORMANCE) {
      const message = `Performance mark: ${label}`;
      log(LOG_LEVELS.DEBUG, message, data, 'PERF');
    }
  },
};

/**
 * API request/response logging
 */
export const apiLog = {
  /**
   * Log API request
   */
  request(method, url, data = null) {
    if (DEV_CONFIG.ENABLE_API_LOGGING) {
      apiLogger.debug(`${method.toUpperCase()} ${url}`, data);
    }
  },

  /**
   * Log API response
   */
  response(method, url, status, data = null) {
    if (DEV_CONFIG.ENABLE_API_LOGGING) {
      const message = `${method.toUpperCase()} ${url} - ${status}`;
      if (status >= 400) {
        apiLogger.warn(message, data);
      } else {
        apiLogger.debug(message, data);
      }
    }
  },

  /**
   * Log API error
   */
  error(method, url, error) {
    apiLogger.error(`${method.toUpperCase()} ${url} - ERROR`, {
      message: error.message,
      stack: error.stack,
    });
  },
};

/**
 * Create logger for specific component or module
 */
export function createLogger(context) {
  return new Logger(context);
}

export default logger;
