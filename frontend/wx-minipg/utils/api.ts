/**
 * API utility
 * Centralized API request handling with error handling and token management
 */
import { API_CONFIG, STORAGE_KEYS } from './config';
import { getLogger } from './logger';
import type { ZodTypeAny } from 'zod';
import { isNonEmptyString } from './guards';
import { normalizeError } from './errors';

const logger = getLogger('API');

let authRefreshHandler: (() => Promise<string>) | null = null;
let authTokenProvider: (() => string | null) | null = null;

export function registerAuthRefreshHandler(handler: () => Promise<string>): void {
  authRefreshHandler = handler;
}

export function registerAuthTokenProvider(provider: () => string | null): void {
  authTokenProvider = provider;
}

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';

type WxResponseData = string | WechatMiniprogram.IAnyObject | ArrayBuffer;
type WxRequestData = string | WechatMiniprogram.IAnyObject | ArrayBuffer;
type WxMethod = NonNullable<WechatMiniprogram.RequestOption['method']>;

export interface RequestOptions<
  TPayload extends WxRequestData | undefined = WechatMiniprogram.IAnyObject,
> {
  url: string;
  method?: HttpMethod;
  data?: TPayload | null;
  header?: Record<string, string>;
  auth?: boolean;
  retryAuth?: boolean;
  /** Internal use only to avoid retry loops */
  _retry?: boolean;
}

export interface ApiError extends Error {
  statusCode?: number;
  status?: number;
  data?: unknown;
  errorCode?: string | number;
  retryAfter?: string | number | null;
}

type QueryParams = Record<string, string | number | boolean | null | undefined>;
type WxCallbackResult = WechatMiniprogram.GeneralCallbackResult & { errMsg?: string };

type ApiResponseDetail = {
  message?: string;
  error?: string | number;
  retry_after?: string | number;
};

type ApiResponseEnvelope<T = unknown> = {
  detail?: ApiResponseDetail;
  message?: string;
  error?: string | number;
  code?: string | number;
} & T;

interface UploadResponse<T = unknown> {
  statusCode: number;
  data: T;
  detail?: ApiResponseDetail;
}

const isWxError = (error: unknown): error is WxCallbackResult =>
  typeof error === 'object' && error !== null && 'errMsg' in (error as Record<string, unknown>);

type WxRequestOptions<TResponse extends WxResponseData> = Omit<
  WechatMiniprogram.RequestOption<TResponse>,
  'success' | 'fail' | 'complete'
>;

type WxUploadOptions = Omit<WechatMiniprogram.UploadFileOption, 'success' | 'fail' | 'complete'>;

type WxDownloadOptions = Omit<
  WechatMiniprogram.DownloadFileOption,
  'success' | 'fail' | 'complete'
>;

const wxRequest = async <TResponse extends WxResponseData>(
  options: WxRequestOptions<TResponse>
): Promise<WechatMiniprogram.RequestSuccessCallbackResult<TResponse>> =>
  await new Promise((resolve, reject) => {
    wx.request<TResponse>({
      ...options,
      success: resolve,
      fail: reject,
    });
  });

const wxUploadFile = async (
  options: WxUploadOptions
): Promise<WechatMiniprogram.UploadFileSuccessCallbackResult> =>
  await new Promise((resolve, reject) => {
    wx.uploadFile({
      ...options,
      success: resolve,
      fail: reject,
    });
  });

const wxDownloadFile = async (
  options: WxDownloadOptions
): Promise<WechatMiniprogram.DownloadFileSuccessCallbackResult> =>
  await new Promise((resolve, reject) => {
    wx.downloadFile({
      ...options,
      success: resolve,
      fail: reject,
    });
  });

const toHeaderRecord = (
  header: Record<string, unknown> | WechatMiniprogram.IAnyObject | null | undefined
): Record<string, string> | null => {
  if (header === null || header === undefined || typeof header !== 'object') {
    return null;
  }
  const normalized: Record<string, string> = {};
  Object.keys(header as Record<string, unknown>).forEach((key) => {
    const value = (header as Record<string, unknown>)[key];
    if (typeof value === 'string') {
      normalized[key] = value;
    }
  });
  return normalized;
};

const extractErrorMessage = (data: unknown, detail: unknown): string => {
  if (typeof detail === 'string' && detail.trim() !== '') {
    return detail;
  }
  if (detail !== null && detail !== undefined && typeof detail === 'object') {
    const detailMessage = (detail as { message?: unknown }).message;
    if (typeof detailMessage === 'string' && detailMessage.trim() !== '') {
      return detailMessage;
    }
  }
  if (data !== null && data !== undefined && typeof data === 'object') {
    const dataMessage = (data as { message?: unknown }).message;
    if (typeof dataMessage === 'string' && dataMessage.trim() !== '') {
      return dataMessage;
    }
  }
  return '请求失败';
};

const resolveDetail = (detail: unknown, data: unknown): ApiResponseDetail | undefined => {
  if (detail !== null && detail !== undefined && typeof detail === 'object') {
    return detail as ApiResponseDetail;
  }
  if (
    data !== null &&
    data !== undefined &&
    typeof data === 'object' &&
    'detail' in (data as Record<string, unknown>)
  ) {
    return (data as ApiResponseEnvelope).detail;
  }
  return undefined;
};

const toApiError = (
  message: string,
  response: {
    statusCode?: number;
    data?: unknown;
    detail?: unknown;
    header?: Record<string, unknown> | WechatMiniprogram.IAnyObject;
  }
): ApiError => {
  const error = new Error(message) as ApiError;
  if (typeof response.statusCode === 'number') {
    error.statusCode = response.statusCode;
    error.status = response.statusCode;
  }
  error.data = response.data;
  const detail = resolveDetail(response.detail, response.data);
  const dataRecord =
    typeof response.data === 'object' && response.data !== null
      ? (response.data as Record<string, unknown>)
      : undefined;
  if (detail?.error !== undefined) {
    error.errorCode = detail.error;
  } else if (typeof dataRecord?.error === 'string' || typeof dataRecord?.error === 'number') {
    error.errorCode = dataRecord.error;
  } else if (typeof dataRecord?.code === 'string' || typeof dataRecord?.code === 'number') {
    error.errorCode = dataRecord.code;
  }
  if (detail?.retry_after !== undefined) {
    error.retryAfter = detail.retry_after;
  }
  if (error.retryAfter === undefined || error.retryAfter === null) {
    const headers = toHeaderRecord(response.header);
    const retryValue = headers?.['Retry-After'] ?? headers?.['retry-after'];
    if (typeof retryValue === 'string') {
      error.retryAfter = retryValue;
    }
  }
  return error;
};

const safeJsonParse = <T>(raw: string): T => {
  try {
    return JSON.parse(raw) as T;
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('JSON parse failed', { errorMessage: err.message });
    throw new Error('响应解析失败');
  }
};

const extractResponseHeaders = (response: unknown): Record<string, unknown> | undefined => {
  if (response === null || typeof response !== 'object') {
    return undefined;
  }
  const responseObject = response as {
    header?: Record<string, unknown> | null;
  };
  if (!('header' in responseObject)) {
    return undefined;
  }
  const headerValue = responseObject.header;
  if (headerValue !== undefined && headerValue !== null && typeof headerValue === 'object') {
    return headerValue;
  }
  return undefined;
};

const normalizeMethod = (method: HttpMethod): WxMethod => {
  if (method === 'PATCH') {
    return 'PATCH' as unknown as WxMethod;
  }
  return method;
};

function getToken(): string | null {
  if (authTokenProvider !== null) {
    try {
      const providedToken = authTokenProvider();
      if (isNonEmptyString(providedToken)) {
        return providedToken;
      }
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Auth token provider failed', { errorMessage: err.message });
    }
  }
  try {
    return wx.getStorageSync(STORAGE_KEYS.AUTH_TOKEN) ?? null;
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('Get token failed', { errorMessage: err.message });
    return null;
  }
}

const isApiUnauthorizedError = (error: unknown): error is ApiError =>
  error instanceof Error && (error as ApiError).statusCode === 401;

const shouldRetryAuthRequest = (
  auth: boolean,
  retryAuth: boolean,
  _retry: boolean,
  error: unknown
): error is ApiError =>
  auth && retryAuth && !_retry && authRefreshHandler !== null && isApiUnauthorizedError(error);

const handleWxCallbackError = (error: unknown): void => {
  if (!isWxError(error)) {
    return;
  }
  const errMsg = isNonEmptyString(error.errMsg) ? error.errMsg : '';
  if (errMsg.includes('timeout')) {
    throw new Error('请求超时，请检查网络连接');
  }
  if (errMsg.includes('fail')) {
    throw new Error('网络连接失败，请检查网络设置');
  }
};

export async function request<
  TResponse extends WxResponseData = WechatMiniprogram.IAnyObject,
  TPayload extends WxRequestData | undefined = WechatMiniprogram.IAnyObject,
>(options: RequestOptions<TPayload>): Promise<TResponse> {
  const {
    url,
    method = 'GET',
    data = null,
    header = {},
    auth = true,
    retryAuth = true,
    _retry = false,
  } = options;
  const headers: Record<string, string> = { ...header };
  const fullUrl = `${API_CONFIG.baseUrl}/api/${API_CONFIG.version}${url}`;

  if (auth) {
    const token = getToken();
    if (isNonEmptyString(token)) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  if (method === 'POST' || method === 'PUT' || method === 'PATCH') {
    headers['Content-Type'] = 'application/json';
  }

  headers['X-Client'] = 'wxminipg';
  logger.debug('API request', { method, url, data });

  try {
    const response = await wxRequest<TResponse>({
      url: fullUrl,
      method: normalizeMethod(method),
      data: data ?? undefined,
      header: headers,
      timeout: API_CONFIG.timeout,
    });

    logger.debug('API response', { method, url, statusCode: response.statusCode });

    if (response.statusCode >= 400) {
      const detail = (response.data as ApiResponseEnvelope).detail;
      const message = extractErrorMessage(response.data, detail);
      throw toApiError(message, {
        statusCode: response.statusCode,
        data: response.data,
        detail,
        header: response.header,
      });
    }

    return response.data;
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('API request failed', {
      method,
      url,
      errorMessage: err.message,
    });
    handleWxCallbackError(error);
    if (shouldRetryAuthRequest(auth, retryAuth, _retry, error)) {
      try {
        await authRefreshHandler!();
        return await request<TResponse, TPayload>({
          ...options,
          _retry: true,
        });
      } catch (refreshError: unknown) {
        const refreshErr = normalizeError(refreshError);
        logger.error('Auth refresh handler failed', {
          errorMessage: refreshErr.message,
        });
      }
    }
    throw error;
  }
}

export async function requestValidated<
  TSchema extends ZodTypeAny,
  TPayload extends WxRequestData | undefined = WechatMiniprogram.IAnyObject,
>(schema: TSchema, options: RequestOptions<TPayload>): Promise<TSchema['_output']> {
  const raw = await request<WxResponseData, TPayload>(options);
  logger.debug('requestValidated: received raw data', { raw, url: options.url });

  try {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
    const validated = schema.parse(raw);
    logger.debug('requestValidated: validation successful', { url: options.url });
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return
    return validated;
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('requestValidated: Zod validation failed', {
      url: options.url,
      rawData: raw,
      errorName: err.name,
      errorMessage: err.message,
    });
    throw err;
  }
}

export async function get<T extends WxResponseData = WechatMiniprogram.IAnyObject>(
  url: string,
  params: QueryParams = {},
  options: Omit<RequestOptions, 'url' | 'method' | 'data'> = {}
): Promise<T> {
  const queryString = Object.entries(params)
    .filter(([, value]) => value !== null && value !== undefined)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&');
  const hasQueryString = queryString !== '';
  const fullUrl = hasQueryString ? `${url}?${queryString}` : url;
  return await request<T>({
    url: fullUrl,
    method: 'GET',
    ...options,
  });
}

export async function post<
  T extends WxResponseData = WechatMiniprogram.IAnyObject,
  D extends WxRequestData | undefined = WechatMiniprogram.IAnyObject,
>(
  url: string,
  data: D = {} as D,
  options: Omit<RequestOptions, 'url' | 'method' | 'data'> = {}
): Promise<T> {
  return await request<T, D>({
    url,
    method: 'POST',
    data,
    ...options,
  });
}

export async function patch<
  T extends WxResponseData = WechatMiniprogram.IAnyObject,
  D extends WxRequestData | undefined = WechatMiniprogram.IAnyObject,
>(
  url: string,
  data: D = {} as D,
  options: Omit<RequestOptions, 'url' | 'method' | 'data'> = {}
): Promise<T> {
  return await request<T, D>({
    url,
    method: 'PATCH',
    data,
    ...options,
  });
}

export async function put<
  T extends WxResponseData = WechatMiniprogram.IAnyObject,
  D extends WxRequestData | undefined = WechatMiniprogram.IAnyObject,
>(
  url: string,
  data: D = {} as D,
  options: Omit<RequestOptions, 'url' | 'method' | 'data'> = {}
): Promise<T> {
  return await request<T, D>({
    url,
    method: 'PUT',
    data,
    ...options,
  });
}

export async function del<T extends WxResponseData = WechatMiniprogram.IAnyObject>(
  url: string,
  options: Omit<RequestOptions, 'url' | 'method' | 'data'> = {}
): Promise<T> {
  return await request<T>({
    url,
    method: 'DELETE',
    ...options,
  });
}

interface UploadOptions {
  auth?: boolean;
  retryAuth?: boolean;
}

export async function uploadFile<T extends WxResponseData = WechatMiniprogram.IAnyObject>(
  url: string,
  filePath: string,
  name = 'file',
  formData: Record<string, string> = {},
  options: UploadOptions = {}
): Promise<T> {
  const { auth = true, retryAuth = true } = options;
  const fullUrl = `${API_CONFIG.baseUrl}/api/${API_CONFIG.version}${url}`;
  const hasUploadData = (value: unknown): value is UploadResponse<T> =>
    typeof value === 'object' && value !== null && 'data' in value;

  const performUpload = async (_retry = false): Promise<T> => {
    const header: Record<string, string> = { 'X-Client': 'wxminipg' };
    if (auth) {
      const token = getToken();
      if (isNonEmptyString(token)) {
        header.Authorization = `Bearer ${token}`;
      }
    }

    logger.debug('Upload file', { url, filePath, name, retry: _retry });

    const response = await wxUploadFile({
      url: fullUrl,
      filePath,
      name,
      formData,
      header,
      timeout: API_CONFIG.timeout,
    });

    logger.debug('Upload response', { url, statusCode: response.statusCode });

    const parsed = safeJsonParse<UploadResponse<T> | ApiResponseEnvelope<T> | T>(response.data);
    const detail = (parsed as UploadResponse<T>).detail ?? (parsed as ApiResponseEnvelope).detail;
    const responseHeaders = extractResponseHeaders(response);

    if (
      response.statusCode === 401 &&
      auth &&
      retryAuth &&
      !_retry &&
      authRefreshHandler !== null
    ) {
      try {
        await authRefreshHandler();
        return await performUpload(true);
      } catch (refreshError: unknown) {
        const err = normalizeError(refreshError);
        logger.error('Upload auth refresh failed', {
          url,
          errorMessage: err.message,
        });
      }
    }

    if (response.statusCode >= 400) {
      const message = extractErrorMessage(parsed, detail);
      throw toApiError(message, {
        statusCode: response.statusCode,
        data: parsed,
        detail,
        header: responseHeaders,
      });
    }

    if (hasUploadData(parsed)) {
      return parsed.data;
    }
    return parsed as T;
  };

  return await performUpload();
}

export async function downloadFile(url: string, filePath?: string): Promise<string> {
  const fullUrl = url.startsWith('http') ? url : `${API_CONFIG.baseUrl}${url}`;
  logger.debug('Download file', { url, filePath });

  const response = await wxDownloadFile({
    url: fullUrl,
    filePath,
    timeout: API_CONFIG.timeout,
  });

  logger.debug('Download response', { url, statusCode: response.statusCode });

  if (response.statusCode >= 400) {
    throw toApiError('下载失败', {
      statusCode: response.statusCode,
      data: null,
      detail: null,
      header: extractResponseHeaders(response),
    });
  }

  if (isNonEmptyString(response.tempFilePath)) {
    return response.tempFilePath;
  }
  if (isNonEmptyString(response.filePath)) {
    return response.filePath;
  }
  return '';
}

export default {
  request,
  get,
  post,
  patch,
  put,
  del,
  uploadFile,
  downloadFile,
  registerAuthRefreshHandler,
};
