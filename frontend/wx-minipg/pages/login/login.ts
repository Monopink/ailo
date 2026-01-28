import { post } from '../../utils/api';
import authService from '../../utils/auth-service';
import {
  type Feature,
  type SampleContact,
  SAMPLE_CONTACTS,
  FEATURES,
} from '../../constants/login-content';
import { fetchAllContactsFromApi } from '../../utils/contact-sync';
import { getLogger } from '../../utils/logger';
import { saveContacts, type StoredAuthUser } from '../../utils/storage';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import {
  parse,
  type AuthUserPayload,
  type WechatBindPhoneResponse,
  type WechatLoginCheckResponse,
  WechatBindPhoneResponseSchema,
  WechatLoginCheckSchema,
} from '../../utils/schemas';

const logger = getLogger('Login');

type LoginStatus = 'idle' | 'need_phone';

interface AuthSuccessPayload {
  access_token: string;
  refresh_token: string;
  needs_profile_setup?: boolean | null;
  user: AuthUserPayload;
  message?: string | null;
}

interface LoginPageData {
  pageLayoutData: PageLayoutData;
  sampleContacts: SampleContact[];
  featureList: Feature[];
  wechatLoading: boolean;
  loginCode: string;
  loginStatus: LoginStatus;
}

interface LoginPageCustom {
  handleWeChatLogin(event: WechatMiniprogram.ButtonGetPhoneNumber): Promise<void>;
  checkBindingStatus(loginCode: string): Promise<void>;
  handleAuthSuccess(authResult: AuthSuccessPayload): Promise<void>;
}

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
};

const loadContacts = async (): Promise<void> => {
  try {
    const remoteContacts = await fetchAllContactsFromApi();
    const contacts = await saveContacts(remoteContacts);
    logger.info('Contacts loaded and saved', { count: contacts.length });
  } catch (error) {
    logger.error('Failed to load contacts', { error });
  }
};

const initMessaging = async (): Promise<void> => {
  const app = getApp<AppInstance>();
  await app.initMessageService();
};

const normalizeAuthUser = (payload: AuthUserPayload): StoredAuthUser => ({
  qiao_id: payload.qiao_id,
});

Page<LoginPageData, LoginPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      hasFooter: false,
      isLoading: false,
    }),
    sampleContacts: SAMPLE_CONTACTS,
    featureList: FEATURES,
    wechatLoading: false,
    loginCode: '',
    loginStatus: 'idle',
  },

  async onLoad(options?: Record<string, string | undefined>) {
    logger.info('Login page loaded');

    try {
      const isAuthenticated = await authService.waitForInit();
      if (isAuthenticated) {
        logger.info('User already authenticated, redirecting to chat');
        void wx.switchTab({ url: '/pages/index/index' });
        return;
      }

      const fromLogout = options?.source === 'logout';
      const { code } = await wx.login();
      if (typeof code === 'string' && code !== '') {
        this.setData({ loginCode: code });
        logger.info('Login code obtained silently', { code });

        if (!fromLogout) {
          await this.checkBindingStatus(code);
        } else {
          logger.info('Skipped auto login check due to explicit logout source');
        }
      } else {
        logger.warn('Failed to obtain login code on page load');
      }
    } catch (error) {
      logger.error('Auth check or login code fetch failed', { error });
    }
  },

  async checkBindingStatus(loginCode: string) {
    try {
      this.setData({ wechatLoading: true });
      const response = await post<WechatLoginCheckResponse>(
        '/auth/wechat/login',
        { login_code: loginCode },
        { auth: false }
      );
      const parsed = parse(WechatLoginCheckSchema, response);

      if (parsed.status === 'bound') {
        const accessToken = parsed.access_token ?? '';
        const refreshToken = parsed.refresh_token ?? '';
        const user = parsed.user ?? null;

        if (accessToken === '' || refreshToken === '' || user === null) {
          throw new Error('登录失败，请重试');
        }

        await this.handleAuthSuccess({
          access_token: accessToken,
          refresh_token: refreshToken,
          needs_profile_setup: parsed.needs_profile_setup ?? false,
          user,
          message: parsed.message ?? undefined,
        });
      } else {
        this.setData({ loginStatus: 'need_phone' });
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error && error.message !== '' ? error.message : '登录失败，请重试';
      logger.error('WeChat login status check failed', {
        error: errorMessage,
        rawError: error,
      });
      showToast(errorMessage, 'none');
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

      let loginCode = this.data.loginCode;
      try {
        const { code: refreshedCode } = await wx.login();
        if (typeof refreshedCode === 'string' && refreshedCode !== '') {
          loginCode = refreshedCode;
          this.setData({ loginCode: refreshedCode });
          logger.info('Login code refreshed on demand', { refreshedCode });
        }
      } catch (refreshError) {
        logger.warn('Failed to refresh login code', { error: refreshError });
      }

      if (loginCode === '') {
        throw new Error('Login code not available, please try again');
      }

      logger.info('Using pre-fetched login code', { loginCode });

      const bindResponseRaw = await post<WechatBindPhoneResponse>(
        '/auth/wechat/bind-phone',
        {
          login_code: loginCode,
          phone_code: phoneCode,
        },
        { auth: false }
      );
      const bindResponse = parse(WechatBindPhoneResponseSchema, bindResponseRaw);

      await this.handleAuthSuccess({
        access_token: bindResponse.access_token,
        refresh_token: bindResponse.refresh_token,
        needs_profile_setup: bindResponse.needs_profile_setup,
        user: bindResponse.user,
        message: bindResponse.message ?? undefined,
      });
    } catch (error) {
      const errorMessage =
        error instanceof Error && error.message !== '' ? error.message : '登录失败，请重试';
      logger.error('WeChat login failed', {
        error: errorMessage,
        rawError: error,
      });
      this.setData({ wechatLoading: false });

      // Show user-friendly error message (no technical details)
      showToast(errorMessage, 'none');
    }
  },

  async handleAuthSuccess(authResult: AuthSuccessPayload) {
    const normalizedUser = normalizeAuthUser(authResult.user);
    await authService.login(authResult.access_token, authResult.refresh_token, normalizedUser, {
      needsProfileSetup: Boolean(authResult.needs_profile_setup),
    });
    logger.info('WeChat login success', { qiao_id: normalizedUser.qiao_id });

    if (typeof authResult.message === 'string' && authResult.message.trim() !== '') {
      showToast(authResult.message);
    }

    this.setData({ wechatLoading: false, loginStatus: 'idle' });

    if (authResult.needs_profile_setup) {
      void wx.redirectTo({ url: '/pages/setup/setup' });
      return;
    }

    await loadContacts();
    await initMessaging();
    void wx.switchTab({ url: '/pages/index/index' });
  },
});
