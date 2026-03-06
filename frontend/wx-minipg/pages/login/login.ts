import {
  type Feature,
  type SampleContact,
  SAMPLE_CONTACTS,
  FEATURES,
} from '../../constants/login-content';
import { getLogger } from '../../utils/logger';
import { normalizeError } from '../../utils/errors';
import { isNonEmptyString } from '../../utils/guards';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import {
  createLoginPageService,
  type AuthSuccessPayload,
  type LoginStatus,
} from '../../services/pages/login-service';

const logger = getLogger('Login');

interface LoginPageData {
  pageLayoutData: PageLayoutData;
  sampleContacts: SampleContact[];
  featureList: Feature[];
  wechatLoading: boolean;
  loginCode: string;
  loginStatus: LoginStatus;
}

interface LoginPageCustom {
  loginPageService: ReturnType<typeof createLoginPageService>;
  handleWeChatLogin(event: WechatMiniprogram.ButtonGetPhoneNumber): Promise<void>;
  handleAuthSuccess(authResult: AuthSuccessPayload): Promise<void>;
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
    sampleContacts: SAMPLE_CONTACTS,
    featureList: FEATURES,
    wechatLoading: false,
    loginCode: '',
    loginStatus: 'idle',
  },

  loginPageService: null as unknown as ReturnType<typeof createLoginPageService>,

  async onLoad(options?: Record<string, string | undefined>) {
    logger.info('Login page loaded');
    this.loginPageService = createLoginPageService();
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

  async handleWeChatLogin(event) {
    if (event.detail.errMsg !== 'getPhoneNumber:ok') {
      logger.warn('WeChat phone authorization rejected', {
        errMsg: event.detail.errMsg,
      });
      showToast('完成手机号验证后即可开始使用');
      return;
    }

    const phoneCode = event.detail.code;
    logger.info('Got phone code from WeChat', { phoneCode });

    try {
      this.setData({ wechatLoading: true });
      const result = await this.loginPageService.bindPhone(phoneCode, this.data.loginCode);
      this.setData({ loginCode: result.loginCode });
      await this.handleAuthSuccess(result.authSuccess);
    } catch (error) {
      const err = normalizeError(error);
      const errorMessage = isNonEmptyString(err.message) ? err.message : '登录失败，请重试';
      logger.error('WeChat login failed', {
        error: errorMessage,
        rawError: error,
      });
      this.setData({ wechatLoading: false });

      showToast(errorMessage, 'none');
    }
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

  onUnload() {
    this.loginPageService.dispose();
  },
});
