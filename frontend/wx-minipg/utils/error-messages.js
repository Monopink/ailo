/**
 * Error Message Mapping
 * Maps technical error codes to user-friendly messages
 */

const ERROR_MESSAGES = {
  MESSAGE_SERVICE_DISCONNECTED: '消息服务未连接，请稍后重试',
  CONVERSATION_NOT_FOUND: '会话信息异常，请返回重新进入',
  NETWORK_ERROR: '网络连接失败，请检查网络',
  SEND_FAILED: '发送失败，请重试',
  UNKNOWN_ERROR: '系统错误，请稍后重试'
};

/**
 * Get user-friendly error message
 * @param {Error|string} error - Error object or error code
 * @returns {string} User-friendly error message
 */
export function getUserFriendlyError(error) {
  if (!error) {
    return ERROR_MESSAGES.UNKNOWN_ERROR;
  }

  const errorCode = typeof error === 'string' ? error : error.message;

  // Check if it's a known error code
  if (ERROR_MESSAGES[errorCode]) {
    return ERROR_MESSAGES[errorCode];
  }

  // Check for network errors
  if (errorCode && (
    errorCode.includes('network') ||
    errorCode.includes('timeout') ||
    errorCode.includes('连接')
  )) {
    return ERROR_MESSAGES.NETWORK_ERROR;
  }

  // Default to generic error
  return ERROR_MESSAGES.UNKNOWN_ERROR;
}

export default {
  getUserFriendlyError,
  ERROR_MESSAGES
};
