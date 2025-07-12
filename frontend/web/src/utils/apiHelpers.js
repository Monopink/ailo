/**
 * Unified API response handling utilities
 * Provides consistent error handling and response processing across all API calls
 */

import axios from 'axios';
import { API_CONFIG } from '../config/constants.js';
import { apiLog, apiLogger } from './logger.js';
import { handleApiError } from './errorHandler.js';

/**
 * Standard API response format expected from backend
 */
export const API_RESPONSE_FORMAT = {
  SUCCESS: 'success',
  ERROR: 'error',
};

/**
 * Create configured axios instance
 */
export function createApiClient(baseURL = API_CONFIG.BASE_URL) {
  const client = axios.create({
    baseURL,
    timeout: API_CONFIG.TIMEOUT,
    headers: API_CONFIG.DEFAULT_HEADERS,
    withCredentials: true,
  });

  // Request interceptor
  client.interceptors.request.use(
    (config) => {
      // Add authentication token
      const token = localStorage.getItem('token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      // Log request
      apiLog.request(config.method, config.url, config.data);

      return config;
    },
    (error) => {
      apiLog.error('REQUEST', 'interceptor', error);
      return Promise.reject(error);
    }
  );

  // Response interceptor
  client.interceptors.response.use(
    (response) => {
      // Log successful response
      apiLog.response(response.config.method, response.config.url, response.status, response.data);
      return response;
    },
    (error) => {
      // Log error response
      const method = error.config?.method || 'UNKNOWN';
      const url = error.config?.url || 'UNKNOWN';
      const status = error.response?.status || 'NO_RESPONSE';
      
      apiLog.response(method, url, status, error.response?.data);
      
      return Promise.reject(error);
    }
  );

  return client;
}

/**
 * Process standard API response format
 */
export function processApiResponse(response, operation = null) {
  try {
    const { data } = response;

    // Check for standard success response format
    if (data && data.status === API_RESPONSE_FORMAT.SUCCESS) {
      apiLogger.debug(`API operation successful: ${operation}`, { data: data.data });
      return { data: data.data, success: true };
    }

    // Handle error response format
    if (data && data.status === API_RESPONSE_FORMAT.ERROR) {
      const errorMessage = data.message || 'API operation failed';
      apiLogger.warn(`API operation failed: ${operation}`, { message: errorMessage });
      throw new Error(errorMessage);
    }

    // Handle unexpected response format
    apiLogger.warn(`Unexpected API response format for: ${operation}`, { response: data });
    throw new Error('Unexpected response format from server');

  } catch (error) {
    apiLogger.error(`Error processing API response for: ${operation}`, error);
    throw error;
  }
}

/**
 * Make API request with unified error handling
 */
export async function makeApiRequest(requestFn, operation = null, options = {}) {
  const {
    retryAttempts = API_CONFIG.RETRY_ATTEMPTS,
    retryDelay = API_CONFIG.RETRY_DELAY,
    showErrorToast = true,
  } = options;

  let lastError = null;

  for (let attempt = 1; attempt <= retryAttempts; attempt++) {
    try {
      apiLogger.debug(`API request attempt ${attempt}/${retryAttempts}: ${operation}`);
      
      const response = await requestFn();
      return processApiResponse(response, operation);

    } catch (error) {
      lastError = error;
      
      // Don't retry on authentication errors or client errors
      if (error.response?.status === 401 || error.response?.status === 403) {
        break;
      }
      
      // Don't retry on validation errors (4xx except 401/403)
      if (error.response?.status >= 400 && error.response?.status < 500) {
        break;
      }

      // Wait before retry (except on last attempt)
      if (attempt < retryAttempts) {
        apiLogger.debug(`Retrying API request in ${retryDelay}ms: ${operation}`);
        await new Promise(resolve => setTimeout(resolve, retryDelay));
      }
    }
  }

  // Handle final error
  if (showErrorToast) {
    handleApiError(lastError, operation);
  }
  
  throw lastError;
}

/**
 * Wrapper for GET requests
 */
export async function apiGet(url, options = {}) {
  const { client = createApiClient(), operation = 'GET', ...requestOptions } = options;
  
  return makeApiRequest(
    () => client.get(url),
    operation,
    requestOptions
  );
}

/**
 * Wrapper for POST requests
 */
export async function apiPost(url, data = null, options = {}) {
  const { client = createApiClient(), operation = 'POST', ...requestOptions } = options;
  
  return makeApiRequest(
    () => client.post(url, data),
    operation,
    requestOptions
  );
}

/**
 * Wrapper for PUT requests
 */
export async function apiPut(url, data = null, options = {}) {
  const { client = createApiClient(), operation = 'PUT', ...requestOptions } = options;
  
  return makeApiRequest(
    () => client.put(url, data),
    operation,
    requestOptions
  );
}

/**
 * Wrapper for DELETE requests
 */
export async function apiDelete(url, options = {}) {
  const { client = createApiClient(), operation = 'DELETE', ...requestOptions } = options;
  
  return makeApiRequest(
    () => client.delete(url),
    operation,
    requestOptions
  );
}

/**
 * Create specialized API client for specific service
 */
export function createServiceClient(serviceName, baseURL = null) {
  const client = createApiClient(baseURL);
  
  return {
    get: (url, options = {}) => apiGet(url, { 
      client, 
      operation: `${serviceName}_GET`,
      ...options 
    }),
    post: (url, data, options = {}) => apiPost(url, data, { 
      client, 
      operation: `${serviceName}_POST`,
      ...options 
    }),
    put: (url, data, options = {}) => apiPut(url, data, { 
      client, 
      operation: `${serviceName}_PUT`,
      ...options 
    }),
    delete: (url, options = {}) => apiDelete(url, { 
      client, 
      operation: `${serviceName}_DELETE`,
      ...options 
    }),
  };
}

/**
 * Handle file upload with progress tracking
 */
export async function uploadFile(url, file, options = {}) {
  const {
    onProgress = null,
    operation = 'file_upload',
    ...requestOptions
  } = options;

  const formData = new FormData();
  formData.append('file', file);

  const client = createApiClient();
  
  return makeApiRequest(
    () => client.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    }),
    operation,
    requestOptions
  );
}

// Export default API client
export const defaultApiClient = createApiClient();
