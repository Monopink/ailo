/**
 * Error Message Mapping
 * Maps technical error codes to user-friendly messages
 *
 * Error categories:
 * - Network errors: Connection issues, timeouts
 * - Service errors: Backend service unavailable
 * - Business errors: Message blocked, not friends
 */

const ERROR_MESSAGES = {
  // Network layer errors
  NETWORK_ERROR: '网络连接失败，请检查网络',
  TIMEOUT_ERROR: '网络连接失败，请检查网络',

  // Service layer errors
  MESSAGE_SERVICE_DISCONNECTED: '服务暂时不可用，请稍后重试',
  SERVICE_ERROR: '服务暂时不可用，请稍后重试',
  CONVERSATION_NOT_FOUND: '服务暂时不可用，请稍后重试',
  SEND_FAILED: '服务暂时不可用，请稍后重试',

  // Business layer errors
  MESSAGE_BLOCKED: '对方已拒收消息',
  NOT_FRIEND: '你们还不是好友',

  // Default error
  UNKNOWN_ERROR: '服务暂时不可用，请稍后重试'
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

  // Check for network errors (network layer)
  if (errorCode && (
    errorCode.includes('network') ||
    errorCode.includes('timeout') ||
    errorCode.includes('连接') ||
    errorCode.includes('Network') ||
    errorCode.includes('Timeout')
  )) {
    return ERROR_MESSAGES.NETWORK_ERROR;
  }

  // Check for business errors
  if (errorCode && (
    errorCode.includes('blocked') ||
    errorCode.includes('拒收')
  )) {
    return ERROR_MESSAGES.MESSAGE_BLOCKED;
  }

  if (errorCode && (
    errorCode.includes('not_friend') ||
    errorCode.includes('不是好友')
  )) {
    return ERROR_MESSAGES.NOT_FRIEND;
  }

  // Default to service error
  return ERROR_MESSAGES.UNKNOWN_ERROR;
}

export default {
  getUserFriendlyError,
  ERROR_MESSAGES
};
