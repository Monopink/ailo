/**
 * MiniProgram App Entry
 */

import './utils/polyfills';
import authService from './utils/auth-service';
import { checkGlobalData, checkStorage } from './utils/debug';
import { ENABLE_DEBUG_TOOLS } from './utils/env';
import { getLogger } from './utils/logger';
import { initMessageService } from './utils/message/service';
import type { MessageService } from './utils/message/service';
import conversationStore from './utils/message/conversation-store';
import { normalizeError } from './utils/errors';

type MessagePayload = Ailo.MessagePayload;
type LaunchOptions = WechatMiniprogram.App.LaunchShowOption;
type ShowOptions = WechatMiniprogram.App.LaunchShowOption;
type PageNotFoundOption = WechatMiniprogram.App.PageNotFoundOption;
type UnhandledRejectionResult = WechatMiniprogram.OnUnhandledRejectionListenerResult;
type ThemeChangeResult = WechatMiniprogram.OnThemeChangeListenerResult;
type AnyPageInstance = WechatMiniprogram.Page.Instance<
  WechatMiniprogram.IAnyObject,
  WechatMiniprogram.IAnyObject
>;
type MessageHandlerPage = AnyPageInstance & {
  onMessageReceived?(message: MessagePayload): void;
  onMessageError?(error: Error): void;
};

const logger = getLogger('App');

const getActivePage = (): AnyPageInstance | undefined => {
  const pages = getCurrentPages();
  return pages[pages.length - 1] as AnyPageInstance | undefined;
};

const redirectToSetupIfNeeded = (): boolean => {
  if (!authService.needsProfileSetup()) {
    return false;
  }
  const currentPage = getActivePage();
  if (currentPage?.route === 'pages/setup/setup') {
    return true;
  }
  void wx.redirectTo({ url: '/pages/setup/setup' });
  return true;
};

const appOptions: WechatMiniprogram.App.Options<AppInstance> = {
  globalData: {
    messageService: null,
    systemInfo: null,
    conversationStore,
  } satisfies Ailo.GlobalData,

  onLaunch(options: LaunchOptions) {
    logger.info('App launched', { options });

    const systemInfo = wx.getSystemInfoSync();
    this.globalData.systemInfo = systemInfo;
    logger.info('System info', { systemInfo });

    if (ENABLE_DEBUG_TOOLS) {
      logger.info('=== App Launch Debug ===');
      checkStorage();
      checkGlobalData();
      logger.info('========================');
    }

    void this.initializeAuth();
  },

  onShow(options: ShowOptions) {
    logger.info('App shown', { options });
    if (this.globalData.messageService !== null) {
      void this.globalData.messageService.resume().catch((error) => {
        const err = normalizeError(error);
        logger.warn('Resume message service failed', { error: err.message });
      });
    }
  },

  onHide() {
    logger.info('App hidden');
    if (this.globalData.messageService !== null) {
      this.globalData.messageService.suspend();
    }
  },

  onError(error: string) {
    logger.error('App error', { error });
  },

  onPageNotFound(options: PageNotFoundOption) {
    logger.warn('Page not found', { path: options.path, query: options.query });
    void wx.switchTab({ url: '/pages/index/index' });
  },

  onUnhandledRejection(event: UnhandledRejectionResult) {
    logger.error('Unhandled rejection', { reason: event.reason });
  },

  onThemeChange(event: ThemeChangeResult) {
    logger.info('Theme changed', { theme: event.theme });
  },

  async initializeAuth() {
    try {
      logger.info('=== Initializing Authentication ===');

      const isAuthenticated = await authService.initialize();
      logger.info('Authentication initialized', { isAuthenticated });

      if (isAuthenticated) {
        await conversationStore.init();
        await this.initMessageService();

        if (redirectToSetupIfNeeded()) {
          return;
        }

        const currentPage = getActivePage();
        if (currentPage?.route === 'pages/welcome/welcome') {
          logger.info('User on welcome page, redirecting to chat');
          void wx.switchTab({ url: '/pages/index/index' });
        }
        return;
      }

      logger.info('User not authenticated');

      const currentPage = getActivePage();

      if (currentPage?.route !== 'pages/login/login') {
        logger.info('User not on login page, redirecting');
        void wx.reLaunch({ url: '/pages/login/login' });
      }
    } catch (error) {
      const err = normalizeError(error);
      logger.error('Initialize auth failed', { error: err.message });
    } finally {
      if (authService.isAuthenticated()) {
        redirectToSetupIfNeeded();
      }
    }
  },

  async initMessageService() {
    try {
      if (this.globalData.messageService !== null) {
        logger.info('Message service already initialized');
        return;
      }

      const messageService = await initMessageService();
      this.globalData.messageService = messageService;
      logger.info('Message service initialized');
    } catch (error) {
      const err = normalizeError(error);
      logger.error('Initialize message service failed', { error: err.message });
      throw err;
    }
  },

  getMessageService(): MessageService | null {
    return this.globalData.messageService;
  },

  getConversationStore() {
    return conversationStore;
  },

  getAuthService() {
    return authService;
  },

  setUserInfo(userInfo: Parameters<typeof authService.updateUserInfo>[0]) {
    logger.warn('app.setUserInfo() is deprecated, use authService.updateUserInfo()');
    void authService.updateUserInfo(userInfo);
  },

  getUserInfo() {
    logger.warn('app.getUserInfo() is deprecated, use authService.getUserInfo()');
    return authService.getUserInfo();
  },

  setToken(_token: unknown) {
    logger.warn('app.setToken() is deprecated, use authService.login()');
  },

  getToken() {
    logger.warn('app.getToken() is deprecated, use authService.getToken()');
    return authService.getToken();
  },

  clearAuth() {
    logger.warn('app.clearAuth() is deprecated, use authService.logout()');

    if (this.globalData.messageService !== null) {
      void this.globalData.messageService.disconnect();
      this.globalData.messageService = null;
    }

    void authService.logout();
  },

  onMessageReceived(message: MessagePayload) {
    logger.info('Message received in app', {
      msg_id: message.msg_id,
      conv_id: message.conv_id,
      message_type: message.message_type,
      from_qiao_id: message.from_qiao_id,
    });

    const currentPage = getActivePage() as MessageHandlerPage | undefined;
    currentPage?.onMessageReceived?.(message);
  },

  onMessageError(error: unknown) {
    const err = normalizeError(error);
    logger.error('Message error in app', { error: err.message });

    const currentPage = getActivePage() as MessageHandlerPage | undefined;
    currentPage?.onMessageError?.(err);
  },
};

App(appOptions);
