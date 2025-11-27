/**
 * MiniProgram App Entry
 */

import authService from './utils/auth-service';
import { fetchCaptchaConfig } from './utils/captcha';
import { checkGlobalData, checkStorage } from './utils/debug';
import { ENABLE_DEBUG_TOOLS } from './utils/env';
import { getLogger } from './utils/logger';
import { initMessageService } from './utils/message/service';
import conversationStore from './utils/message/conversation-store';

const logger = getLogger('App');

App({
  /**
   * Global data
   */
  globalData: {
    messageService: null,
    systemInfo: null,
    captchaConfig: null,
    conversationStore
  },

  /**
   * App launch
   */
  onLaunch(options) {
    logger.info('App launched', { options });

    // Get system info
    this.globalData.systemInfo = wx.getSystemInfoSync();
    logger.info('System info', { systemInfo: this.globalData.systemInfo });

    // Preload and cache captcha config
    this.preloadCaptchaConfig();

    // Check storage status (debug) - only in development
    if (ENABLE_DEBUG_TOOLS) {
      logger.info('=== App Launch Debug ===');
      checkStorage();
      checkGlobalData();
      logger.info('========================');
    }

    // Initialize authentication service
    this.initializeAuth();
  },

  /**
   * App show
   */
  onShow(options) {
    logger.info('App shown', { options });

    // Refresh token if authenticated
    this.refreshTokenIfNeeded();
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
   * Preload captcha config
   */
  async preloadCaptchaConfig() {
    try {
      const cfg = await fetchCaptchaConfig();
      this.globalData.captchaConfig = cfg;
      logger.info('Captcha config preloaded');
    } catch (error) {
      logger.error('Fetch captcha config failed', { error: error.message || String(error) });
    }
  },

  /**
   * Initialize authentication service
   */
  async initializeAuth() {
    try {
      logger.info('=== Initializing Authentication ===');

      const isAuthenticated = await authService.initialize();

      logger.info('Authentication initialized', { isAuthenticated });

      if (isAuthenticated) {
        await conversationStore.init();
        // Initialize message service for authenticated users
        await this.initMessageService();

        // Check if user is on welcome page, redirect to chat
        const pages = getCurrentPages();
        const currentPage = pages[pages.length - 1];

        if (currentPage && currentPage.route === 'pages/welcome/welcome') {
          logger.info('User on welcome page, redirecting to chat');
          wx.switchTab({
            url: '/pages/index/index'
          });
        }
      } else {
        logger.info('User not authenticated');

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
      logger.error('Initialize auth failed', { error: error.message || String(error) });
    }
  },

  /**
   * Refresh token if needed
   */
  async refreshTokenIfNeeded() {
    try {
      if (authService.isAuthenticated()) {
        await authService.refreshToken();
        logger.info('Token refreshed');
      }
    } catch (error) {
      logger.error('Refresh token failed', { error: error.message || String(error) });
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
      logger.error('Initialize message service failed', { error: error.message || String(error) });
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
   * Get conversation store
   */
  getConversationStore() {
    return conversationStore;
  },

  /**
   * Get auth service
   * @returns {AuthService} Auth service instance
   */
  getAuthService() {
    return authService;
  },

  /**
   * Set user info (deprecated - use authService.updateUserInfo)
   * @deprecated Use authService.updateUserInfo() instead
   */
  setUserInfo(userInfo) {
    logger.warn('app.setUserInfo() is deprecated, use authService.updateUserInfo()');
    authService.updateUserInfo(userInfo);
  },

  /**
   * Get user info (deprecated - use authService.getUserInfo)
   * @deprecated Use authService.getUserInfo() instead
   */
  getUserInfo() {
    logger.warn('app.getUserInfo() is deprecated, use authService.getUserInfo()');
    return authService.getUserInfo();
  },

  /**
   * Set token (deprecated - use authService.login)
   * @deprecated Use authService.login() instead
   */
  setToken(token) {
    logger.warn('app.setToken() is deprecated, use authService.login()');
    // Keep for backward compatibility but don't do anything
  },

  /**
   * Get token (deprecated - use authService.getToken)
   * @deprecated Use authService.getToken() instead
   */
  getToken() {
    logger.warn('app.getToken() is deprecated, use authService.getToken()');
    return authService.getToken();
  },

  /**
   * Clear auth data (deprecated - use authService.logout)
   * @deprecated Use authService.logout() instead
   */
  clearAuth() {
    logger.warn('app.clearAuth() is deprecated, use authService.logout()');

    // Disconnect message service
    if (this.globalData.messageService) {
      this.globalData.messageService.disconnect();
      this.globalData.messageService = null;
    }

    // Logout from auth service
    authService.logout();
  },

  /**
   * Message received callback
   */
  onMessageReceived(message) {
    logger.info('Message received in app', {
      msg_id: message.msg_id,
      conv_id: message.conv_id,
      message_type: message.message_type,
      from: message.from
    });
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
    logger.info('Typing received in app', {
      conv_id: typing.conv_id,
      isTyping: typing.isTyping
    });
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
