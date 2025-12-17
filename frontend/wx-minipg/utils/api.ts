/**
 * API utility
 * Centralized API request handling with error handling and token management
 */
import { API_CONFIG, STORAGE_KEYS } from './config';
import { getLogger } from './logger';

const logger = getLogger('API');

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
}

export interface ApiError extends Error {
  statusCode?: number;
  status?: number;
  data?: unknown;
  errorCode?: string | number;
  retryAfter?: string | number;
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
  Boolean(error) && typeof error === 'object' && 'errMsg' in (error as Record<string, unknown>);

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
  header: Record<string, unknown> | WechatMiniprogram.IAnyObject | undefined
): Record<string, string> | null => {
  if (!header || typeof header !== 'object') {
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
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (
    detail &&
    typeof detail === 'object' &&
    typeof (detail as { message?: string }).message === 'string'
  ) {
    return (detail as { message?: string }).message as string;
  }
  if (data && typeof (data as { message?: string }).message === 'string') {
    return (data as { message?: string }).message as string;
  }
  return '请求失败';
};

const resolveDetail = (detail: unknown, data: unknown): ApiResponseDetail | undefined => {
  if (detail && typeof detail === 'object') {
    return detail as ApiResponseDetail;
  }
  if (
    data &&
    typeof data === 'object' &&
    data !== null &&
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
  if (!error.retryAfter) {
    const headers = toHeaderRecord(response.header);
    const retryValue = headers?.['Retry-After'] ?? headers?.['retry-after'];
    if (retryValue) {
      error.retryAfter = retryValue;
    }
  }
  return error;
};

const safeJsonParse = <T>(raw: string): T => {
  try {
    return JSON.parse(raw) as T;
  } catch (error) {
    logger.error('JSON parse failed', { error });
    throw new Error('响应解析失败');
  }
};

const extractResponseHeaders = (response: unknown): Record<string, unknown> | undefined => {
  if (response && typeof response === 'object' && 'header' in response) {
    const headerValue = (response as { header?: Record<string, unknown> }).header;
    if (headerValue && typeof headerValue === 'object') {
      return headerValue;
    }
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
  try {
    return wx.getStorageSync(STORAGE_KEYS.AUTH_TOKEN) ?? null;
  } catch (error) {
    logger.error('Get token failed', { error });
    return null;
  }
}

export async function request<
  TResponse extends WxResponseData = WechatMiniprogram.IAnyObject,
  TPayload extends WxRequestData | undefined = WechatMiniprogram.IAnyObject,
>(options: RequestOptions<TPayload>): Promise<TResponse> {
  const { url, method = 'GET', data = null, header = {}, auth = true } = options;
  const headers: Record<string, string> = { ...header };
  const fullUrl = `${API_CONFIG.baseUrl}/api/${API_CONFIG.version}${url}`;

  if (auth) {
    const token = getToken();
    if (token) {
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
      const detail = (response.data as ApiResponseEnvelope)?.detail;
      const message = extractErrorMessage(response.data, detail);
      throw toApiError(message, {
        statusCode: response.statusCode,
        data: response.data,
        detail,
        header: response.header,
      });
    }

    return response.data;
  } catch (error) {
    logger.error('API request failed', { method, url, error });
    if (isWxError(error) && error.errMsg) {
      if (error.errMsg.includes('timeout')) {
        throw new Error('请求超时，请检查网络连接');
      }
      if (error.errMsg.includes('fail')) {
        throw new Error('网络连接失败，请检查网络设置');
      }
    }
    throw error;
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
  const fullUrl = queryString ? `${url}?${queryString}` : url;
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

export async function uploadFile<T extends WxResponseData = WechatMiniprogram.IAnyObject>(
  url: string,
  filePath: string,
  name = 'file',
  formData: Record<string, string> = {}
): Promise<T> {
  const fullUrl = `${API_CONFIG.baseUrl}/api/${API_CONFIG.version}${url}`;
  const token = getToken();
  const header: Record<string, string> = {};
  if (token) {
    header.Authorization = `Bearer ${token}`;
  }
  logger.debug('Upload file', { url, filePath, name });

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

  if (response.statusCode >= 400) {
    const message = extractErrorMessage(parsed, detail);
    throw toApiError(message, {
      statusCode: response.statusCode,
      data: parsed,
      detail,
      header: responseHeaders,
    });
  }

  if (parsed && typeof parsed === 'object' && 'data' in (parsed as UploadResponse<T>)) {
    return (parsed as UploadResponse<T>).data;
  }
  return parsed as T;
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

  return response.tempFilePath || response.filePath || '';
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
};
