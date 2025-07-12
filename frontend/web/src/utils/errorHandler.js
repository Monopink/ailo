/**
 * Unified error handling system
 * Separates user-facing messages (Chinese toast) from developer logs (English)
 */

import { useToast } from 'vue-toastification';
import { errorLogger } from './logger.js';
import { UI_CONFIG, ERROR_CONFIG } from '../config/constants.js';

// Error types for categorization
export const ERROR_TYPES = {
  NETWORK: 'network',
  AUTHENTICATION: 'authentication',
  VALIDATION: 'validation',
  PERMISSION: 'permission',
  NOT_FOUND: 'not_found',
  SERVER: 'server',
  CLIENT: 'client',
  UNKNOWN: 'unknown',
};

// User-friendly error messages in Chinese
const USER_MESSAGES = {
  [ERROR_TYPES.NETWORK]: '网络连接失败，请检查网络设置',
  [ERROR_TYPES.AUTHENTICATION]: '登录已过期，请重新登录',
  [ERROR_TYPES.VALIDATION]: '输入信息有误，请检查后重试',
  [ERROR_TYPES.PERMISSION]: '权限不足，无法执行此操作',
  [ERROR_TYPES.NOT_FOUND]: '请求的资源不存在',
  [ERROR_TYPES.SERVER]: '服务器暂时无法响应，请稍后重试',
  [ERROR_TYPES.CLIENT]: '操作失败，请重试',
  [ERROR_TYPES.UNKNOWN]: '发生未知错误，请重试',
};

// Specific operation error messages
const OPERATION_MESSAGES = {
  'login': '登录失败',
  'register': '注册失败',
  'send_message': '消息发送失败',
  'load_contacts': '联系人加载失败',
  'add_contact': '添加联系人失败',
  'search_contacts': '搜索联系人失败',
  'load_chat': '聊天记录加载失败',
  'upload_file': '文件上传失败',
  'update_profile': '资料更新失败',
  'delete_message': '消息删除失败',
};

/**
 * Error handler class
 */
class ErrorHandler {
  constructor() {
    this.toast = null;
    this.errorQueue = [];
    this.lastErrorTime = 0;
  }

  /**
   * Initialize toast instance
   */
  init() {
    try {
      this.toast = useToast();
    } catch (error) {
      errorLogger.warn('Toast not available, falling back to console', error);
    }
  }

  /**
   * Determine error type from error object
   */
  getErrorType(error) {
    if (!error) return ERROR_TYPES.UNKNOWN;

    // Network errors
    if (error.code === 'NETWORK_ERROR' || error.message?.includes('Network Error')) {
      return ERROR_TYPES.NETWORK;
    }

    // HTTP status code based classification
    if (error.response?.status) {
      const status = error.response.status;
      if (status === 401 || status === 403) {
        return ERROR_TYPES.AUTHENTICATION;
      }
      if (status === 404) {
        return ERROR_TYPES.NOT_FOUND;
      }
      if (status >= 400 && status < 500) {
        return ERROR_TYPES.CLIENT;
      }
      if (status >= 500) {
        return ERROR_TYPES.SERVER;
      }
    }

    // Validation errors
    if (error.name === 'ValidationError' || error.message?.includes('validation')) {
      return ERROR_TYPES.VALIDATION;
    }

    return ERROR_TYPES.UNKNOWN;
  }

  /**
   * Get user-friendly message for error
   */
  getUserMessage(errorType, operation = null) {
    let message = USER_MESSAGES[errorType] || USER_MESSAGES[ERROR_TYPES.UNKNOWN];
    
    // Add operation-specific prefix if available
    if (operation && OPERATION_MESSAGES[operation]) {
      message = `${OPERATION_MESSAGES[operation]}：${message}`;
    }
    
    return message;
  }

  /**
   * Show toast notification to user
   */
  showToast(message, type = 'error') {
    if (this.toast) {
      this.toast[type](message, {
        timeout: UI_CONFIG.TOAST_DURATION,
        position: 'top-center',
        hideProgressBar: false,
        closeOnClick: true,
        pauseOnHover: true,
      });
    } else {
      // Fallback to alert if toast is not available
      alert(message);
    }
  }

  /**
   * Log detailed error information for developers
   */
  logError(error, context = null, operation = null) {
    const errorInfo = {
      message: error.message || 'Unknown error',
      stack: error.stack,
      context,
      operation,
      timestamp: new Date().toISOString(),
      url: window.location.href,
      userAgent: navigator.userAgent,
    };

    // Add response data if available
    if (error.response) {
      errorInfo.response = {
        status: error.response.status,
        statusText: error.response.statusText,
        data: error.response.data,
      };
    }

    errorLogger.error('Application error occurred', errorInfo);
  }

  /**
   * Handle error with both user notification and developer logging
   */
  handle(error, options = {}) {
    const {
      operation = null,
      context = null,
      showToast = true,
      customMessage = null,
    } = options;

    // Prevent spam by rate limiting
    const now = Date.now();
    if (now - this.lastErrorTime < ERROR_CONFIG.REPORT_COOLDOWN) {
      errorLogger.debug('Error handling rate limited', { error: error.message });
      return;
    }
    this.lastErrorTime = now;

    // Determine error type
    const errorType = this.getErrorType(error);

    // Log detailed error for developers
    this.logError(error, context, operation);

    // Show user-friendly message
    if (showToast) {
      const userMessage = customMessage || this.getUserMessage(errorType, operation);
      this.showToast(userMessage);
    }

    // Queue error for potential reporting
    this.queueError(error, errorType, operation, context);
  }

  /**
   * Queue error for potential backend reporting
   */
  queueError(error, errorType, operation, context) {
    if (!ERROR_CONFIG.ENABLE_REPORTING) {
      return;
    }

    const errorReport = {
      type: errorType,
      message: error.message,
      operation,
      context,
      timestamp: new Date().toISOString(),
      url: window.location.href,
    };

    this.errorQueue.push(errorReport);

    // Limit queue size
    if (this.errorQueue.length > ERROR_CONFIG.MAX_ERROR_QUEUE) {
      this.errorQueue.shift();
    }

    // TODO: Implement backend error reporting
    errorLogger.debug('Error queued for reporting', errorReport);
  }

  /**
   * Handle API errors specifically
   */
  handleApiError(error, operation = null) {
    this.handle(error, {
      operation,
      context: 'API',
      showToast: true,
    });
  }

  /**
   * Handle validation errors
   */
  handleValidationError(error, field = null) {
    this.handle(error, {
      operation: 'validation',
      context: field,
      showToast: true,
    });
  }

  /**
   * Handle authentication errors
   */
  handleAuthError(error) {
    this.handle(error, {
      operation: 'authentication',
      context: 'AUTH',
      showToast: true,
    });

    // Redirect to login if needed
    // TODO: Implement auth redirect logic
  }
}

// Create singleton instance
const errorHandler = new ErrorHandler();

// Export convenience functions
export function handleError(error, options = {}) {
  return errorHandler.handle(error, options);
}

export function handleApiError(error, operation = null) {
  return errorHandler.handleApiError(error, operation);
}

export function handleValidationError(error, field = null) {
  return errorHandler.handleValidationError(error, field);
}

export function handleAuthError(error) {
  return errorHandler.handleAuthError(error);
}

export function initErrorHandler() {
  errorHandler.init();
}

export default errorHandler;
