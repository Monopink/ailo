/**
 * Simplified error handling system
 * Focuses on business-specific error messages, minimal default handling
 */

import { useToast } from 'vue-toastification';
import { errorLogger } from './logger.js';
import { UI_CONFIG } from '../config/constants.js';

// Business operation error messages (user-friendly)
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
 * Simplified error handler class
 */
class ErrorHandler {
  constructor() {
    this.toast = null;
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
      // Fallback to console if toast is not available
      console.error('Toast message:', message);
    }
  }

  /**
   * Log detailed error information for developers
   */
  logError(error, context = null) {
    const errorInfo = {
      message: error.message || 'Unknown error',
      stack: error.stack,
      context,
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
   * Handle error with business operation context
   * Supports both custom messages and operation-based messages
   */
  handle(error, options = {}) {
    const {
      context = null,
      operation = null,
      showToast = true,
      customMessage = null,
    } = options;

    // Log detailed error for developers
    this.logError(error, context);

    // Show user message
    if (showToast) {
      let message = customMessage;

      // If no custom message, try to get operation-specific message
      if (!message && operation && OPERATION_MESSAGES[operation]) {
        message = OPERATION_MESSAGES[operation];
      }

      if (message) {
        this.showToast(message);
      }
    }
  }

  /**
   * Handle API errors - extract backend message if available
   */
  handleApiError(error, operation = null, customMessage = null) {
    // Try to get user-friendly message from backend
    const backendMessage = error.response?.data?.detail;
    const message = customMessage || backendMessage;

    this.handle(error, {
      context: 'API',
      operation,
      showToast: true,
      customMessage: message,
    });
  }
}

// Create singleton instance
const errorHandler = new ErrorHandler();

// Export convenience functions
export function handleError(error, options = {}) {
  return errorHandler.handle(error, options);
}

export function handleApiError(error, operation = null, customMessage = null) {
  return errorHandler.handleApiError(error, operation, customMessage);
}

export function initErrorHandler() {
  errorHandler.init();
}

export default errorHandler;
