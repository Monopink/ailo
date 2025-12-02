/**
 * API utility
 * Centralized API request handling with error handling and token management
 */
import { API_CONFIG, STORAGE_KEYS } from './config';
import { getLogger } from './logger';
const logger = getLogger('API');
/**
 * Get auth token
 * @returns {string|null} Auth token
 */
function getToken() {
  try {
    return wx.getStorageSync(STORAGE_KEYS.AUTH_TOKEN);
  } catch (error) {
    logger.error('Get token failed', { error });
    return null;
  }
}
/**
 * Make HTTP request
 * @param {Object} options - Request options
 * @param {string} options.url - Request URL (relative to base URL)
 * @param {string} options.method - HTTP method
 * @param {Object} options.data - Request data
 * @param {Object} options.header - Request headers
 * @param {boolean} options.auth - Whether to include auth token
 * @returns {Promise<any>} Response data
 */
export async function request({
  url,
  method = 'GET',
  data = null,
  header = {},
  auth = true
}) {
  const fullUrl = `${API_CONFIG.baseUrl}/api/${API_CONFIG.version}${url}`;
  // Add auth token if required
  if (auth) {
    const token = getToken();
    if (token) {
      header['Authorization'] = `Bearer ${token}`;
    }
  }
  // Add content type for POST/PUT requests
  if (method === 'POST' || method === 'PUT') {
    header['Content-Type'] = 'application/json';
  }
  // Identify client for server-side per-client configuration
  header['X-Client'] = 'wxminipg';
  logger.debug('API request', { method, url, data });
  return new Promise((resolve, reject) => {
    wx.request({
      url: fullUrl,
      method,
      data,
      header,
      timeout: API_CONFIG.timeout,
      success: (res) => {
        logger.debug('API response', { method, url, statusCode: res.statusCode });

        // Handle HTTP errors
        if (res.statusCode >= 400) {
          const detail = res.data?.detail;
          let message = '请求失败';
          if (typeof detail === 'string') message = detail;
          else if (detail && typeof detail.message === 'string') message = detail.message;
          else if (typeof res.data?.message === 'string') message = res.data.message;

          const error = new Error(message);
          // Normalize common error fields for robust client-side handling
          error.statusCode = res.statusCode;
          error.status = Number(res.statusCode) || res.statusCode;
          error.data = res.data;
          try { error.errorCode = (detail?.error) || res.data?.error || res.data?.code; } catch (_) { }
          try { error.retryAfter = detail?.retry_after || res.header?.['Retry-After'] } catch (_) { }
          reject(error);
          return;
        }

        resolve(res.data);
      },
      fail: (error) => {
        logger.error('API request failed', { method, url, error });
        // Handle network errors
        if (error.errMsg) {
          if (error.errMsg.includes('timeout')) {
            reject(new Error('请求超时，请检查网络连接'));
            return;
          } else if (error.errMsg.includes('fail')) {
            reject(new Error('网络连接失败，请检查网络设置'));
            return;
          }
        }
        reject(error);
      }
    });
  });
}
/**
 * GET request
 * @param {string} url - Request URL
 * @param {Object} params - Query parameters
 * @param {Object} options - Additional options
 * @returns {Promise<any>} Response data
 */
export async function get(url, params = {}, options = {}) {
  // Convert params to query string
  const queryString = Object.keys(params)
    .filter(key => params[key] !== null && params[key] !== undefined)
    .map(key => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
    .join('&');
  const fullUrl = queryString ? `${url}?${queryString}` : url;
  return await request({
    url: fullUrl,
    method: 'GET',
    ...options
  });
}
/**
 * POST request
 * @param {string} url - Request URL
 * @param {Object} data - Request data
 * @param {Object} options - Additional options
 * @returns {Promise<any>} Response data
 */
export async function post(url, data = {}, options = {}) {
  return await request({
    url,
    method: 'POST',
    data,
    ...options
  });
}
/**
 * PUT request
 * @param {string} url - Request URL
 * @param {Object} data - Request data
 * @param {Object} options - Additional options
 * @returns {Promise<any>} Response data
 */
export async function put(url, data = {}, options = {}) {
  return await request({
    url,
    method: 'PUT',
    data,
    ...options
  });
}
/**
 * DELETE request
 * @param {string} url - Request URL
 * @param {Object} options - Additional options
 * @returns {Promise<any>} Response data
 */
export async function del(url, options = {}) {
  return await request({
    url,
    method: 'DELETE',
    ...options
  });
}
/**
 * Upload file
 * @param {string} url - Upload URL
 * @param {string} filePath - Local file path
 * @param {string} name - File field name
 * @param {Object} formData - Additional form data
 * @returns {Promise<any>} Response data
 */
export async function uploadFile(url, filePath, name = 'file', formData = {}) {
  const fullUrl = `${API_CONFIG.baseUrl}/api/${API_CONFIG.version}${url}`;
  const token = getToken();
  const header = {};
  if (token) {
    header['Authorization'] = `Bearer ${token}`;
  }
  logger.debug('Upload file', { url, filePath, name });
  try {
    const res = await wx.uploadFile({
      url: fullUrl,
      filePath,
      name,
      formData,
      header,
      timeout: API_CONFIG.timeout
    });
    logger.debug('Upload response', { url, statusCode: res.statusCode });
    // Parse response data
    const data = JSON.parse(res.data);
    // Handle HTTP errors
    if (res.statusCode >= 400) {
      const error = new Error(data?.detail || '涓婁紶澶辫触');
      error.statusCode = res.statusCode;
      error.data = data;
      throw error;
    }
    return data;
  } catch (error) {
    logger.error('Upload file failed', { url, error });
    throw error;
  }
}
/**
 * Download file
 * @param {string} url - Download URL
 * @param {string} filePath - Save file path
 * @returns {Promise<string>} Saved file path
 */
export async function downloadFile(url, filePath) {
  const fullUrl = url.startsWith('http') ? url : `${API_CONFIG.baseUrl}${url}`;
  logger.debug('Download file', { url, filePath });
  try {
    const res = await wx.downloadFile({
      url: fullUrl,
      filePath,
      timeout: API_CONFIG.timeout
    });
    logger.debug('Download response', { url, statusCode: res.statusCode });
    if (res.statusCode >= 400) {
      throw new Error('涓嬭浇澶辫触');
    }
    return res.tempFilePath || res.filePath;
  } catch (error) {
    logger.error('Download file failed', { url, error });
    throw error;
  }
}
export default {
  request,
  get,
  post,
  put,
  del,
  uploadFile,
  downloadFile
};
