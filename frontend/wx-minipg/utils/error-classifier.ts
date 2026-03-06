import { normalizeError } from './errors';
import type { ApiError } from './api';

interface ApiErrorLike {
  statusCode?: number;
  status?: number;
  errorCode?: string | number;
  reason?: string;
  message?: string;
  data?: unknown;
}

export type ErrorSemanticReason =
  | 'auth-invalid'
  | 'invalid-route'
  | 'not-found'
  | 'network-timeout'
  | 'network-offline'
  | 'server-error'
  | 'rate-limit'
  | 'refresh-failed'
  | 'partial-data-unavailable'
  | 'unknown';

export interface ErrorSemantics {
  reason: ErrorSemanticReason;
}

const parseNumericCode = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
};

const toRecord = (value: unknown): Record<string, unknown> | null => {
  if (value === null || typeof value !== 'object') {
    return null;
  }
  return value as Record<string, unknown>;
};

const resolveErrorCode = (error: ApiErrorLike): number | null => {
  const directCode = parseNumericCode(error.errorCode);
  if (directCode !== null) {
    return directCode;
  }

  const dataRecord = toRecord(error.data);
  if (dataRecord === null) {
    return null;
  }

  const directDataCode = parseNumericCode(dataRecord.error_code);
  if (directDataCode !== null) {
    return directDataCode;
  }

  const detailRecord = toRecord(dataRecord.detail);
  if (detailRecord === null) {
    return null;
  }

  return parseNumericCode(detailRecord.error_code);
};

const resolveStatusCode = (error: ApiErrorLike): number | null => {
  if (typeof error.statusCode === 'number') {
    return error.statusCode;
  }
  if (typeof error.status === 'number') {
    return error.status;
  }
  return null;
};

const isTimeoutError = (message: string): boolean => {
  const normalized = message.toLowerCase();
  return (
    normalized.includes('timeout') ||
    normalized.includes('请求超时') ||
    normalized.includes('time out')
  );
};

const isNetworkOfflineError = (message: string): boolean => {
  const normalized = message.toLowerCase();
  return (
    normalized.includes('network') ||
    normalized.includes('网络') ||
    normalized.includes('request:fail')
  );
};

const endsWithCategory = (code: number | null, category: number): boolean => {
  if (code === null) {
    return false;
  }
  return code % 10000 === category;
};

const resolveCriticalReason = (
  statusCode: number | null,
  errorCode: number | null,
  reason: string
): ErrorSemantics | null => {
  const isNotFound =
    errorCode === 21014001 ||
    errorCode === 13014001 ||
    statusCode === 404 ||
    endsWithCategory(errorCode, 4001);
  if (isNotFound) {
    return { reason: 'not-found' };
  }

  const isUnauthorized =
    statusCode === 401 || statusCode === 403 || endsWithCategory(errorCode, 2001);
  if (isUnauthorized) {
    return { reason: 'auth-invalid' };
  }

  const isInvalidRoute =
    statusCode === 400 ||
    endsWithCategory(errorCode, 1001) ||
    reason === 'REQUEST_VALIDATION_ERROR';
  if (isInvalidRoute) {
    return { reason: 'invalid-route' };
  }

  return null;
};

const resolveDegradableReason = (
  statusCode: number | null,
  errorCode: number | null,
  message: string
): ErrorSemantics => {
  if (statusCode === 429 || endsWithCategory(errorCode, 7001)) {
    return { reason: 'rate-limit' };
  }

  if (statusCode !== null && statusCode >= 500) {
    return { reason: 'server-error' };
  }

  if (isTimeoutError(message)) {
    return { reason: 'network-timeout' };
  }

  if (isNetworkOfflineError(message)) {
    return { reason: 'network-offline' };
  }

  return { reason: 'unknown' };
};

export const classifyError = (error: unknown): ErrorSemantics => {
  const normalized = normalizeError(error);
  const apiError = error as ApiErrorLike;
  const statusCode = resolveStatusCode(apiError);
  const errorCode = resolveErrorCode(apiError as ApiError);
  const reason = typeof apiError.reason === 'string' ? apiError.reason : '';

  const criticalReason = resolveCriticalReason(statusCode, errorCode, reason);
  if (criticalReason !== null) {
    return criticalReason;
  }
  return resolveDegradableReason(statusCode, errorCode, normalized.message);
};
