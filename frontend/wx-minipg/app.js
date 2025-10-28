import { fetchCaptchaConfig } from './utils/captcha';
/**
 * MiniProgram App Entry
 */

import { checkAuth, refreshToken } from './utils/auth';
import { checkGlobalData, checkStorage } from './utils/debug';
import { ENABLE_DEBUG_TOOLS } from './utils/env';
import { getLogger } from './utils/logger';
import { initMessageService } from './utils/message/service';

const logger = getLogger('App');

App({
  /**
   * Global data
   */
  globalData: {
    userInfo: null,
    token: null,
    messageService: null,
    systemInfo: null
  },

  /**
   * App launch
   */
  onLaunch(options) {
    logger.info('App launched', { options });

    // Get system info
    this.globalData.systemInfo = wx.getSystemInfoSync();
    logger.info('System info', { systemInfo: this.globalData.systemInfo });

    // Preload and cache captcha config once
    (async () => {
      try {
        const cfg = await fetchCaptchaConfig();
        this.globalData.captchaConfig = cfg;
      } catch (e) {
        logger.error('Fetch captcha config failed', { error: e.message || String(e) });
      }
    })();

    // Check storage status (debug) - only in development
    if (ENABLE_DEBUG_TOOLS) {
      logger.info('=== App Launch Debug ===');
      checkStorage();
      checkGlobalData();
      logger.info('========================');
    }

    // Check auth status
    this.checkAuthStatus();
  },

  /**
   * App show
   */
  onShow(options) {
    logger.info('App shown', { options });

    // Refresh token if needed
    if (this.globalData.token) {
      this.refreshTokenIfNeeded();
    }
  },

  /**
   * App hide
   */
  onHide() {
    logger.info('App hidden');
  },

  /**
   * App error
   */
  onError(error) {
    logger.error('App error', { error });
  },

  /**
   * Check auth status
   */
  async checkAuthStatus() {
    try {
      logger.info('=== Checking Auth Status ===');

      // Debug: check storage before auth check - only in development
      if (ENABLE_DEBUG_TOOLS) {
        checkStorage();
      }

      const isAuthenticated = await checkAuth();
      logger.info('Auth check result', { isAuthenticated });

      // Store auth status in globalData
      this.globalData.isAuthenticated = isAuthenticated;

      if (isAuthenticated) {
        logger.info('User is authenticated');

        // Initialize message service
        await this.initMessageService();

        // Check if user is on welcome page
        const pages = getCurrentPages();
        const currentPage = pages[pages.length - 1];

        if (currentPage && currentPage.route === 'pages/welcome/welcome') {
          // Redirect to chat tab
          logger.info('User on welcome page, redirecting to chat');
          wx.switchTab({
            url: '/pages/index/index'
          });
        }
      } else {
        logger.info('User is not authenticated');

        // Check if user has seen welcome page
        const hasSeenWelcome = wx.getStorageSync('hasSeenWelcome');
        const pages = getCurrentPages();
        const currentPage = pages[pages.length - 1];

        // If not on welcome page and hasn't seen it, redirect to welcome
        if (!hasSeenWelcome && currentPage && currentPage.route !== 'pages/welcome/welcome') {
          logger.info('User has not seen welcome, redirecting');
          wx.reLaunch({
            url: '/pages/welcome/welcome'
          });
        }
      }
    } catch (error) {
      logger.error('Check auth status failed', { error });
      this.globalData.isAuthenticated = false;
    }
  },

  /**
   * Refresh token if needed
   */
  async refreshTokenIfNeeded() {
    try {
      await refreshToken();
      logger.info('Token refreshed');
    } catch (error) {
      logger.error('Refresh token failed', { error });
    }
  },

  /**
   * Initialize message service
   */
  async initMessageService() {
    try {
      if (this.globalData.messageService) {
        logger.info('Message service already initialized');
        return;
      }

      const messageService = await initMessageService();
      this.globalData.messageService = messageService;

      logger.info('Message service initialized');
    } catch (error) {
      logger.error('Initialize message service failed', { error });
      throw error;
    }
  },

  /**
   * Get message service
   */
  getMessageService() {
    return this.globalData.messageService;
  },

  /**
   * Set user info
   */
  setUserInfo(userInfo) {
    this.globalData.userInfo = userInfo;
    logger.info('User info updated', { userInfo });
  },

  /**
   * Get user info
   */
  getUserInfo() {
    return this.globalData.userInfo;
  },

  /**
   * Set token
   */
  setToken(token) {
    this.globalData.token = token;
    wx.setStorageSync('auth_token', token);
    logger.info('Token updated');
  },

  /**
   * Get token
   */
  getToken() {
    if (!this.globalData.token) {
      this.globalData.token = wx.getStorageSync('auth_token');
    }
    return this.globalData.token;
  },

  /**
   * Clear auth data
   */
  clearAuth() {
    this.globalData.userInfo = null;
    this.globalData.token = null;
    wx.removeStorageSync('auth_token');
    wx.removeStorageSync('user_info');

    // Disconnect message service
    if (this.globalData.messageService) {
      this.globalData.messageService.disconnect();
      this.globalData.messageService = null;
    }

    logger.info('Auth data cleared');
  },

  /**
   * Message received callback
   */
  onMessageReceived(message) {
    logger.debug('Message received in app', { message });
    // Notify current page if it has handler
    const pages = getCurrentPages();
    if (pages.length > 0) {
      const currentPage = pages[pages.length - 1];
      if (currentPage.onMessageReceived) {
        currentPage.onMessageReceived(message);
      }
    }
  },

  /**
   * Typing received callback
   */
  onTypingReceived(typing) {
    logger.debug('Typing received in app', { typing });
    // Notify current page if it has handler
    const pages = getCurrentPages();
    if (pages.length > 0) {
      const currentPage = pages[pages.length - 1];
      if (currentPage.onTypingReceived) {
        currentPage.onTypingReceived(typing);
      }
    }
  },

  /**
   * Message error callback
   */
  onMessageError(error) {
    logger.error('Message error in app', { error });
    // Notify current page if it has handler
    const pages = getCurrentPages();
    if (pages.length > 0) {
      const currentPage = pages[pages.length - 1];
      if (currentPage.onMessageError) {
        currentPage.onMessageError(error);
      }
    }
  }
});


