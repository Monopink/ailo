/**
 * Simplified API client utilities
 * Provides axios client with authentication and logging
 */

import axios from 'axios';
import { API_CONFIG } from '../config/constants.js';
import { apiLog } from './logger.js';

/**
 * Create configured axios instance with authentication and logging
 */
export function createApiClient(baseURL = API_CONFIG.BASE_URL) {
  const client = axios.create({
    baseURL,
    timeout: API_CONFIG.TIMEOUT,
    headers: API_CONFIG.DEFAULT_HEADERS,
    withCredentials: true,
  });

  // Request interceptor for authentication and logging
  client.interceptors.request.use(
    (config) => {
      // Add authentication token
      const token = localStorage.getItem('token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      // Log request in development
      apiLog.request(config.method, config.url, config.data);

      return config;
    },
    (error) => {
      apiLog.error('REQUEST', 'interceptor', error);
      return Promise.reject(error);
    }
  );

  // Response interceptor for logging
  client.interceptors.response.use(
    (response) => {
      // Log successful response in development
      apiLog.response(response.config.method, response.config.url, response.status, response.data);
      return response;
    },
    (error) => {
      // Log error response in development
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
 * Default API client instance for direct use
 * Use this for all API calls - it includes authentication and logging
 */
export const apiClient = createApiClient();

export default apiClient;
