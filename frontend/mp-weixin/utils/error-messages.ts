/**
 * Error Message Mapping
 * Maps technical error codes to user-friendly messages
 *
 * Error categories:
 * - Network errors: Connection issues, timeouts
 * - Service errors: Backend service unavailable
 * - Business errors: Message blocked, not friends
 */

import { isNonEmptyString } from './guards';

export const ERROR_MESSAGES = {
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
  UNKNOWN_ERROR: '服务暂时不可用，请稍后重试',
} as const;

export type ErrorMessageKey = keyof typeof ERROR_MESSAGES;

const isKnownErrorCode = (code: string): code is ErrorMessageKey => {
  if (!isNonEmptyString(code)) {
    return false;
  }
  return Object.prototype.hasOwnProperty.call(ERROR_MESSAGES, code);
};

const matchesKeyword = (value: string, keywords: string[]): boolean =>
  keywords.some((keyword) => value.includes(keyword));

const ERROR_KEYWORD_CHECKS: { keywords: string[]; message: string }[] = [
  {
    keywords: ['network', 'timeout', '连接', 'Network', 'Timeout'],
    message: ERROR_MESSAGES.NETWORK_ERROR,
  },
  {
    keywords: ['blocked', '拒收'],
    message: ERROR_MESSAGES.MESSAGE_BLOCKED,
  },
  {
    keywords: ['not_friend', '不是好友'],
    message: ERROR_MESSAGES.NOT_FRIEND,
  },
];

/**
 * Get user-friendly error message
 * @param {Error|string} error - Error object or error code
 * @returns {string} User-friendly error message
 */
type ErrorLike = Error | { message?: string } | string | null | undefined;

export function getUserFriendlyError(error: ErrorLike): string {
  if (error === null || error === undefined) {
    return ERROR_MESSAGES.UNKNOWN_ERROR;
  }

  const rawCode =
    typeof error === 'string'
      ? error
      : typeof error.message === 'string'
      ? error.message
      : '';
  const errorCode = isNonEmptyString(rawCode) ? rawCode : '';

  // Check if it's a known error code
  if (isKnownErrorCode(errorCode)) {
    return ERROR_MESSAGES[errorCode];
  }

  for (const check of ERROR_KEYWORD_CHECKS) {
    if (matchesKeyword(errorCode, check.keywords)) {
      return check.message;
    }
  }

  // Default to service error
  return ERROR_MESSAGES.UNKNOWN_ERROR;
}

export default {
  getUserFriendlyError,
  ERROR_MESSAGES,
};
