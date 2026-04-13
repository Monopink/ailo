import { getLogger } from '../../utils/logger';
import { normalizeError } from '../../utils/errors';
import { isNonEmptyString } from '../../utils/guards';
import { LOGIN_CONFIG } from '../../utils/config';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import {
  createLoginPageService,
  type AuthSuccessPayload,
  type LoginStatus,
  type WechatPhoneAuthPayload,
} from '../../services/pages/login-service';

const logger = getLogger('Login');
const USER_AGREEMENT_PAGE_KEY = 'user_agreement';
const PRIVACY_POLICY_PAGE_KEY = 'privacy_policy';

interface LoginPageData {
  pageLayoutData: PageLayoutData;
  wechatLoading: boolean;
  loginCode: string;
  loginStatus: LoginStatus;
  remoteBackgroundShouldLoad: boolean;
  remoteBackgroundVisible: boolean;
  remoteBackgroundUrl: string;
  privacyAccepted: boolean;
  privacyDialogVisible: boolean;
  privacyDialogCancelBtn: string | Record<string, unknown>;
  privacyDialogConfirmBtn: string | Record<string, unknown>;
}

interface LoginPageCustom {
  loginPageService: ReturnType<typeof createLoginPageService>;
  backgroundLoadTimeoutHandle: number | null;
  prepareRemoteBackground(): void;
  clearRemoteBackgroundTimeout(): void;
  handleRemoteBackgroundLoad(): void;
  handleRemoteBackgroundError(event: WechatMiniprogram.BaseEvent): void;
  handleWeChatLogin(event: WechatMiniprogram.ButtonGetPhoneNumber): Promise<void>;
  handlePrivacyChange(event: WechatMiniprogram.CustomEvent<{ checked?: boolean }>): void;
  handleLoginTapWithoutPrivacy(): void;
  handlePrivacyDialogOpenTypeEvent(event: WechatMiniprogram.BaseEvent): void;
  handlePrivacyDialogOpenTypeError(event: WechatMiniprogram.BaseEvent): void;
  handlePrivacyDialogClose(): void;
  handleAuthSuccess(authResult: AuthSuccessPayload): Promise<void>;
  navigateToSquareDemo(): void;
  navigateToUserAgreement(): void;
  navigateToPrivacyPolicy(): void;
}

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
};

Page<LoginPageData, LoginPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      hasFooter: false,
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
    }),
    wechatLoading: false,
    loginCode: '',
    loginStatus: 'idle',
    remoteBackgroundShouldLoad: false,
    remoteBackgroundVisible: false,
    remoteBackgroundUrl: '',
    privacyAccepted: false,
    privacyDialogVisible: false,
    privacyDialogCancelBtn: {
      content: '取消',
      variant: 'base',
      theme: 'default',
    },
    privacyDialogConfirmBtn: {
      content: '同意并继续',
      variant: 'base',
      theme: 'primary',
      openType: 'getPhoneNumber',
    },
  },

  loginPageService: null as unknown as ReturnType<typeof createLoginPageService>,
  backgroundLoadTimeoutHandle: null,

  async onLoad(options?: Record<string, string | undefined>) {
    logger.info('Login page loaded');
    this.loginPageService = createLoginPageService();
    this.prepareRemoteBackground();
    this.setData({ wechatLoading: true });
    try {
      const result = await this.loginPageService.bootstrap(options?.source);
      if (result === null) {
        return;
      }
      if (result.isAuthenticated) {
        logger.info('User already authenticated, redirecting to chat');
        void wx.switchTab({ url: '/pages/index/index' });
        return;
      }

      this.setData({
        loginCode: result.loginCode,
        loginStatus: result.loginStatus,
      });

      if (isNonEmptyString(result.errorMessage)) {
        showToast(result.errorMessage);
        return;
      }
      if (result.authSuccess !== null) {
        await this.handleAuthSuccess(result.authSuccess);
      }
    } catch (error) {
      const err = normalizeError(error);
      logger.error('Auth check or login code fetch failed', { error: err.message });
      showToast('登录失败，请重试');
    } finally {
      this.setData({ wechatLoading: false });
    }
  },

  prepareRemoteBackground() {
    const remoteBackgroundUrl = LOGIN_CONFIG.loginBackgroundUrl;
    if (!isNonEmptyString(remoteBackgroundUrl)) {
      return;
    }

    this.setData({
      remoteBackgroundUrl,
      remoteBackgroundShouldLoad: true,
      remoteBackgroundVisible: false,
    });

    this.clearRemoteBackgroundTimeout();
    this.backgroundLoadTimeoutHandle = setTimeout(() => {
      this.backgroundLoadTimeoutHandle = null;
      if (this.data.remoteBackgroundVisible) {
        return;
      }
      logger.warn('Remote login background load timed out, fallback gradient remains');
      this.setData({
        remoteBackgroundShouldLoad: false,
        remoteBackgroundUrl: '',
      });
    }, LOGIN_CONFIG.loginBackgroundLoadTimeoutMs);
  },

  clearRemoteBackgroundTimeout() {
    if (this.backgroundLoadTimeoutHandle === null) {
      return;
    }
    clearTimeout(this.backgroundLoadTimeoutHandle);
    this.backgroundLoadTimeoutHandle = null;
  },

  handleRemoteBackgroundLoad() {
    this.clearRemoteBackgroundTimeout();
    this.setData({ remoteBackgroundVisible: true });
  },

  handleRemoteBackgroundError(event) {
    this.clearRemoteBackgroundTimeout();
    const detail = (event as unknown as { detail?: { errMsg?: string } }).detail;
    logger.warn('Remote login background load failed, fallback gradient remains', {
      errMsg: detail?.errMsg ?? '',
    });
    this.setData({
      remoteBackgroundShouldLoad: false,
      remoteBackgroundVisible: false,
      remoteBackgroundUrl: '',
    });
  },

  async handleWeChatLogin(event) {
    if (!this.data.privacyAccepted) {
      this.setData({ privacyDialogVisible: true });
      return;
    }

    const detail = (event as unknown as { detail?: Record<string, unknown> }).detail ?? {};
    const eventDetail = detail as {
      errMsg?: string;
      code?: string;
      encryptedData?: string;
      iv?: string;
    };

    if (event.detail.errMsg !== 'getPhoneNumber:ok') {
      logger.warn('Phone authorization rejected', {
        errMsg: event.detail.errMsg,
      });
      showToast('已取消登录');
      return;
    }

    let phoneAuthPayload: WechatPhoneAuthPayload | null = null;
    if (isNonEmptyString(eventDetail.code)) {
      phoneAuthPayload = { phoneCode: eventDetail.code };
    } else if (isNonEmptyString(eventDetail.encryptedData) && isNonEmptyString(eventDetail.iv)) {
      phoneAuthPayload = {
        encryptedData: eventDetail.encryptedData,
        iv: eventDetail.iv,
      };
    }

    if (phoneAuthPayload === null) {
      showToast('登录失败，请重试');
      return;
    }

    try {
      this.setData({ wechatLoading: true });
      const result = await this.loginPageService.bindPhone(phoneAuthPayload, this.data.loginCode);
      this.setData({ loginCode: result.loginCode });
      await this.handleAuthSuccess(result.authSuccess);
    } catch (error) {
      const err = normalizeError(error);
      logger.error('WeChat login failed', {
        error: err.message,
        rawError: error,
      });
      this.setData({ wechatLoading: false });
      showToast(isNonEmptyString(err.message) ? err.message : '登录失败，请重试', 'none');
    }
  },

  handlePrivacyChange(event) {
    const detail = (event as unknown as { detail?: { checked?: unknown } }).detail;
    const checked = detail?.checked === true;
    this.setData({ privacyAccepted: checked });
  },

  handleLoginTapWithoutPrivacy() {
    this.setData({ privacyDialogVisible: true });
  },

  handlePrivacyDialogOpenTypeEvent(event) {
    const detail = (event as unknown as { detail?: { errMsg?: string } }).detail;
    if (detail?.errMsg !== 'getPhoneNumber:ok') {
      this.setData({ privacyDialogVisible: false });
      return;
    }

    this.setData({ privacyAccepted: true, privacyDialogVisible: false }, () => {
      void this.handleWeChatLogin(event as unknown as WechatMiniprogram.ButtonGetPhoneNumber);
    });
  },

  handlePrivacyDialogOpenTypeError() {
    this.setData({ privacyDialogVisible: false });
  },

  handlePrivacyDialogClose() {
    this.setData({ privacyDialogVisible: false });
  },

  navigateToSquareDemo() {
    void wx.navigateTo({ url: '/pages/square-demo/square-demo' });
  },

  async handleAuthSuccess(authResult: AuthSuccessPayload) {
    await this.loginPageService.persistAuth(authResult);

    if (typeof authResult.message === 'string' && authResult.message.trim() !== '') {
      showToast(authResult.message);
    }

    this.setData({ wechatLoading: false, loginStatus: 'idle' });

    if (authResult.needs_profile_setup) {
      void wx.redirectTo({ url: '/pages/setup/setup' });
      return;
    }

    await this.loginPageService.runPostLoginWarmup();
    void wx.switchTab({ url: '/pages/index/index' });
  },

  navigateToUserAgreement() {
    void wx.navigateTo({
      url: `/pages/app-page/app-page?pageKey=${USER_AGREEMENT_PAGE_KEY}`,
    });
  },

  navigateToPrivacyPolicy() {
    void wx.navigateTo({
      url: `/pages/app-page/app-page?pageKey=${PRIVACY_POLICY_PAGE_KEY}`,
    });
  },

  onUnload() {
    this.clearRemoteBackgroundTimeout();
    this.loginPageService.dispose();
  },
});
