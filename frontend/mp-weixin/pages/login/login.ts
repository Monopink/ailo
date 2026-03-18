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
  type WechatPhoneAuthPayload,
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
    const detail = (event as unknown as { detail?: Record<string, unknown> }).detail ?? {};
    const eventDetail = detail as {
      errMsg?: string;
      code?: string;
      encryptedData?: string;
      iv?: string;
    };

    if (event.detail.errMsg !== 'getPhoneNumber:ok') {
      logger.warn('WeChat phone authorization rejected', {
        errMsg: event.detail.errMsg,
      });
      showToast('请先登录后即可开始使用');
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
      showToast('登录失败，请尝试更新微信');
      return;
    }

    try {
      this.setData({ wechatLoading: true });
      const result = await this.loginPageService.bindPhone(phoneAuthPayload, this.data.loginCode);
      this.setData({ loginCode: result.loginCode });
      await this.handleAuthSuccess(result.authSuccess);
    } catch (error) {
      logger.error('WeChat login failed', {
        error: normalizeError(error).message,
        rawError: error,
      });
      this.setData({ wechatLoading: false });
      showToast('登录失败，请尝试更新微信', 'none');
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
