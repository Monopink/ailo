/**
 * Authentication Service
 * Single source of truth for authentication state
 * Manages token, user info, and authentication status
 */

import { get, post } from './api';
import { STORAGE_KEYS } from './config';
import { getLogger } from './logger';
import { saveUserInfo, getUserInfo } from './storage';

const logger = getLogger('AuthService');

/**
 * Authentication Service Class
 * Singleton pattern - only one instance should exist
 */
class AuthService {
  constructor() {
    // Authentication state
    this._isAuthenticated = false;
    this._token = null;
    this._userInfo = null;

    // Initialization state
    this._initialized = false;
    this._initPromise = null;
  }

  /**
   * Initialize authentication service
   * Check token validity and load user info
   * @returns {Promise<boolean>} True if authenticated
   */
  async initialize() {
    // Prevent multiple initializations
    if (this._initPromise) {
      logger.info('Initialization already in progress, waiting...');
      return this._initPromise;
    }

    this._initPromise = this._doInitialize();
    return this._initPromise;
  }

  async _doInitialize() {
    try {
      logger.info('=== AuthService Initialization Start ===');

      // Load token from storage
      const token = wx.getStorageSync(STORAGE_KEYS.AUTH_TOKEN);

      if (!token) {
        logger.info('No token found, user not authenticated');
        this._setAuthState(false, null, null);
        this._initialized = true;
        return false;
      }

      logger.info('Token found, verifying with backend', {
        tokenLength: token.length,
        tokenPrefix: token.substring(0, 10) + '...'
      });

      // Verify token with backend
      try {
        const userInfo = await get('/user/profile');

        // Token is valid
        logger.info('Token verified successfully', { qiao_id: userInfo.qiao_id });

        // Save user info to storage
        await saveUserInfo(userInfo);

        // Update auth state
        this._setAuthState(true, token, userInfo);
        this._initialized = true;

        logger.info('=== AuthService Initialization Complete (Authenticated) ===');
        return true;
      } catch (error) {
        // Token is invalid
        logger.warn('Token verification failed, clearing invalid token', {
          error: error.message || error,
          statusCode: error.statusCode
        });

        // Clear invalid token
        wx.removeStorageSync(STORAGE_KEYS.AUTH_TOKEN);

        this._setAuthState(false, null, null);
        this._initialized = true;

        logger.info('=== AuthService Initialization Complete (Not Authenticated) ===');
        return false;
      }
    } catch (error) {
      logger.error('Initialization failed', { error: error.message || error });

      // On error, assume not authenticated
      this._setAuthState(false, null, null);
      this._initialized = true;

      return false;
    }
  }

  /**
   * Wait for initialization to complete
   * @returns {Promise<boolean>} True if authenticated
   */
  async waitForInit() {
    if (this._initialized) {
      return this._isAuthenticated;
    }

    if (this._initPromise) {
      return this._initPromise;
    }

    // Not initialized yet, initialize now
    return this.initialize();
  }

  /**
   * Check if user is authenticated (synchronous)
   * WARNING: Only use this after initialization is complete
   * @returns {boolean} True if authenticated
   */
  isAuthenticated() {
    if (!this._initialized) {
      logger.warn('isAuthenticated() called before initialization complete');
    }
    return this._isAuthenticated;
  }

  /**
   * Get current token
   * @returns {string|null} Token or null
   */
  getToken() {
    return this._token;
  }

  /**
   * Get current user info
   * @returns {Object|null} User info or null
   */
  getUserInfo() {
    return this._userInfo;
  }

  /**
   * Login with token and user info
   * Called after successful login
   * @param {string} token - Auth token
   * @param {Object} userInfo - User info
   */
  async login(token, userInfo) {
    logger.info('Login called', { qiao_id: userInfo.qiao_id });

    // Save token to storage
    wx.setStorageSync(STORAGE_KEYS.AUTH_TOKEN, token);

    // Save user info to storage
    await saveUserInfo(userInfo);

    // Update auth state
    this._setAuthState(true, token, userInfo);

    logger.info('Login successful', { qiao_id: userInfo.qiao_id });
  }

  /**
   * Update user info
   * Called when user info changes
   * @param {Object} userInfo - Updated user info
   */
  async updateUserInfo(userInfo) {
    logger.info('Updating user info', { qiao_id: userInfo.qiao_id });

    // Save to storage
    await saveUserInfo(userInfo);

    // Update state
    this._userInfo = userInfo;

    logger.info('User info updated');
  }

  /**
   * Logout
   * Clear all auth data
   */
  async logout() {
    logger.info('Logout called');

    try {
      // Call logout API
      await post('/auth/logout');
      logger.info('Logout API call successful');
    } catch (error) {
      logger.error('Logout API call failed', { error: error.message || error });
      // Continue with local cleanup even if API fails
    }

    // Clear storage
    wx.removeStorageSync(STORAGE_KEYS.AUTH_TOKEN);
    wx.removeStorageSync(STORAGE_KEYS.USER_INFO);

    // Clear state
    this._setAuthState(false, null, null);

    logger.info('Logout complete');
  }

  /**
   * Refresh token
   * @returns {Promise<string>} New token
   */
  async refreshToken() {
    try {
      logger.info('Refreshing token');

      const data = await post('/auth/refresh-token');

      // Save new token
      wx.setStorageSync(STORAGE_KEYS.AUTH_TOKEN, data.access_token);

      // Update state
      this._token = data.access_token;

      logger.info('Token refreshed successfully');

      return data.access_token;
    } catch (error) {
      logger.error('Refresh token failed', { error: error.message || error });
      throw error;
    }
  }

  /**
   * Set authentication state (internal)
   * @private
   */
  _setAuthState(isAuthenticated, token, userInfo) {
    this._isAuthenticated = isAuthenticated;
    this._token = token;
    this._userInfo = userInfo;

    logger.debug('Auth state updated', {
      isAuthenticated,
      hasToken: !!token,
      hasUserInfo: !!userInfo,
      qiao_id: userInfo?.qiao_id
    });
  }

  /**
   * Reset initialization state (for testing)
   * @private
   */
  _resetForTesting() {
    this._initialized = false;
    this._initPromise = null;
    this._setAuthState(false, null, null);
  }
}

// Create singleton instance
const authService = new AuthService();

// Export singleton instance
export default authService;

// Export class for testing
export { AuthService };
