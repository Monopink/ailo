/**
 * Validated API wrapper with Zod runtime validation
 *
 * This module provides type-safe API calls with runtime validation.
 * Use these functions when you need to ensure API responses match expected schemas.
 */

import * as api from './api';
import { getLogger } from './logger';
import type { RuntimeSchema } from './schemas-core';

const logger = getLogger('API-Validated');

type QueryParams = Record<string, string | number | boolean | null | undefined>;
type WxResponseData = string | WechatMiniprogram.IAnyObject | ArrayBuffer;

/**
 * Validated GET request with schema validation
 *
 * @example
 * const user = await getValidated('/users/123', UserInfoSchema);
 * // user is guaranteed to match UserInfo type at runtime
 */
export async function getValidated<T>(
  url: string,
  schema: RuntimeSchema<T>,
  params: QueryParams = {},
  options: Omit<api.RequestOptions, 'url' | 'method' | 'data'> = {}
): Promise<T> {
  const response = await api.get<WxResponseData>(url, params, options);

  try {
    return schema.parse(response);
  } catch (error) {
    logger.error('Response validation failed', { url, error });
    throw new Error('API response validation failed');
  }
}
