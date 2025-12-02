import { get, post } from '../../utils/api';
import authService from '../../utils/auth-service';
import {
  ensureCaptchaConfig,
  getCachedCaptchaConfig,
  initCaptcha,
  showCaptcha,
} from '../../utils/captcha';
import { checkStorage } from '../../utils/debug';
import { getLogger } from '../../utils/logger';
import { saveContacts, type StoredAuthUser } from '../../utils/storage';

const logger = getLogger('Login');

type PhoneNumberEvent = WechatMiniprogram.ButtonGetPhoneNumber;
type InputEvent = WechatMiniprogram.CustomEvent<{ value: string }>;

interface AuthUserResponse extends StoredAuthUser {
  token: string;
}

interface WechatLoginResponse {
  success: boolean;
  needs_phone_binding?: boolean;
  wechat_code?: string;
  message?: string;
  user: AuthUserResponse;
}

interface PhoneVerificationResponse {
  is_new_user: boolean;
  verified_phone_token?: string;
  phone?: string;
  token: string;
  user: StoredAuthUser;
}

interface ApiError extends Error {
  statusCode?: number;
  status?: number;
  errorCode?: string | number;
  data?: {
    detail?: {
      error?: string | number;
      message?: string;
      code?: string | number;
    };
    error?: string | number;
    code?: string | number;
  };
}

interface LoginPageData extends Says.CaptchaPageData {
  showPhoneButton: boolean;
  showPhoneBind: boolean;
  showCaptcha: boolean;
  loadCaptcha: boolean;
  pluginProps: Record<string, unknown>;
  loginCode: string;
  wechatCode: string;
  phone: string;
  smsCode: string;
  countdown: number;
  wechatLoading: boolean;
  phoneLoading: boolean;
  bindLoading: boolean;
  captchaToken: string | null;
  turnstileSiteKey: string;
  captchaSceneId: string;
}

type LoginPageInstance = WechatMiniprogram.Page.Instance<LoginPageData, LoginPageCustom>;

interface LoginPageCustom {
  _captchaActive?: boolean;
  _captchaReady?: boolean;
  _captchaRetryCount?: number;
  onCaptchaSuccess(captchaToken: string): Promise<void>;
  onCaptchaFail(error: unknown): void;
  handleWeChatLogin(): Promise<void>;
  handlePhoneLogin(): void;
  handleGetPhoneNumber(event: PhoneNumberEvent): Promise<void>;
  onPhoneInput(event: InputEvent): void;
  onSmsCodeInput(event: InputEvent): void;
  sendSmsCode(): Promise<void>;
  requestSmsWithCaptcha(captchaToken: string): Promise<void>;
  handleBindPhone(): Promise<void>;
}

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
};

const startCountdown = (page: LoginPageInstance): void => {
  let remaining = 60;
  page.setData({ countdown: remaining });
  const timer = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(timer);
      page.setData({ countdown: 0 });
      return;
    }
    page.setData({ countdown: remaining });
  }, 1000);
};

const hasCaptchaRequirement = (error: ApiError): boolean => {
  const status = Number(error.statusCode ?? error.status ?? 0);
  if (status === 428) {
    return true;
  }
  const code =
    error.errorCode ??
    error.data?.detail?.error ??
    error.data?.detail?.code ??
    error.data?.error ??
    error.data?.code;
  return code === 'CAPTCHA_REQUIRED';
};

const normalizeErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  return fallback;
};

const markWelcomeSeen = (): void => {
  wx.setStorageSync('hasSeenWelcome', true);
};

const loadContacts = async (): Promise<void> => {
  try {
    const response = await get('/contacts');
    const contacts = await saveContacts(response);
    logger.info('Contacts loaded and saved', { count: contacts.length });
  } catch (error) {
    logger.error('Failed to load contacts', { error });
  }
};

const initMessaging = async (): Promise<void> => {
  const app = getApp<SaysAppInstance>();
  await app.initMessageService();
};

Page<LoginPageData, LoginPageCustom>({
  data: {
    showPhoneButton: false,
    showPhoneBind: false,
    showCaptcha: false,
    loadCaptcha: false,
    pluginProps: {},
    loginCode: '',
    wechatCode: '',
    phone: '',
    smsCode: '',
    countdown: 0,
    wechatLoading: false,
    phoneLoading: false,
    bindLoading: false,
    captchaToken: null,
    turnstileSiteKey: '',
    captchaSceneId: '',
  },

  async onLoad() {
    logger.info('Login page loaded');
    try {
      const cached = getCachedCaptchaConfig();
      const config = cached ?? (await ensureCaptchaConfig());
      initCaptcha(this as unknown as Says.CaptchaPageInstance, config, {
        success: (token: string) => {
          void this.onCaptchaSuccess(token);
        },
        fail: (error: unknown) => {
          this.onCaptchaFail(error);
        },
      });
    } catch (error) {
      logger.error('Initialize captcha failed', { error });
    }
  },

  async onCaptchaSuccess(captchaToken) {
    (this as LoginPageCustom)._captchaActive = false;
    this.setData({ loadCaptcha: true });
    await this.requestSmsWithCaptcha(captchaToken);
  },

  onCaptchaFail(error) {
    logger.error('Aliyun captcha failed', { error });
    if ((this as LoginPageCustom)._captchaActive) {
      showToast('验证服务错误，请稍后再试');
    }
    (this as LoginPageCustom)._captchaActive = false;
  },

  async handleWeChatLogin() {
    try {
      this.setData({ wechatLoading: true });
      const { code } = await wx.login();
      if (!code) {
        throw new Error('Failed to obtain login code');
      }

      this.setData({
        loginCode: code,
        showPhoneButton: true,
        wechatLoading: false,
      });
      logger.info('WeChat login success', { code });
    } catch (error) {
      logger.error('WeChat login failed', { error });
      this.setData({ wechatLoading: false });
      showToast('微信登录失败');
    }
  },

  handlePhoneLogin() {
    logger.info('User clicked phone login button');
    this.setData({
      showPhoneBind: true,
      wechatCode: '',
    });
  },

  async handleGetPhoneNumber(event) {
    if (event.detail.errMsg !== 'getPhoneNumber:ok') {
      logger.warn('User denied phone authorization');
      this.setData({ showPhoneBind: true });
      return;
    }

    const phoneCode = event.detail.code;
    logger.info('Got phone code', { phoneCode });

    try {
      this.setData({ phoneLoading: true });

      const result = await post<WechatLoginResponse>(
        '/auth/wechat/login',
        {
          login_code: this.data.loginCode,
          phone_code: phoneCode,
        },
        { auth: false }
      );

      if (!result.success && result.needs_phone_binding) {
        this.setData({
          showPhoneBind: true,
          wechatCode: result.wechat_code ?? '',
          phoneLoading: false,
        });
        showToast(result.message || '请绑定手机号');
        logger.info('Phone binding required', { wechat_code: result.wechat_code });
        return;
      }

      await authService.login(result.user.token, result.user);
      logger.info('Login success', { user: result.user });
      markWelcomeSeen();

      this.setData({ phoneLoading: false });

      if (!result.user.nickname) {
        void wx.redirectTo({ url: '/pages/setup/setup' });
        return;
      }

      await loadContacts();
      await initMessaging();
      void wx.switchTab({ url: '/pages/index/index' });
    } catch (error) {
      logger.error('Login failed', { error });
      this.setData({ phoneLoading: false });
      showToast(normalizeErrorMessage(error, '登录失败'));
    }
  },

  onPhoneInput(event) {
    this.setData({ phone: event.detail.value });
  },

  onSmsCodeInput(event) {
    this.setData({ smsCode: event.detail.value });
  },

  async sendSmsCode() {
    if (!this.data.phone || this.data.phone.length !== 11) {
      showToast('请输入正确的手机号');
      return;
    }

    try {
      await post('/auth/send-sms', { phone: `+86${this.data.phone}` }, { auth: false });
      startCountdown(this as LoginPageInstance);
      showToast('验证码已发送', 'success');
      return;
    } catch (error) {
      const apiError = error as ApiError;
      if (!hasCaptchaRequirement(apiError)) {
        if (apiError.statusCode === 429) {
          showToast(normalizeErrorMessage(apiError, '发送过于频繁，请稍后再试'));
        } else {
          showToast(normalizeErrorMessage(apiError, '发送失败'));
        }
        return;
      }
    }

    (this as LoginPageCustom)._captchaActive = true;
    void showCaptcha(this as unknown as Says.CaptchaPageInstance);
  },

  async requestSmsWithCaptcha(captchaToken) {
    try {
      await post(
        '/auth/send-sms',
        {
          phone: `+86${this.data.phone}`,
          captcha_token: captchaToken,
        },
        { auth: false }
      );

      startCountdown(this as LoginPageInstance);
      showToast('验证码已发送', 'success');
    } catch (error) {
      logger.error('Send SMS failed', { error });
      showToast(normalizeErrorMessage(error, '发送失败'));
    }
  },

  async handleBindPhone() {
    if (!this.data.phone || this.data.phone.length !== 11) {
      showToast('请输入正确的手机号');
      return;
    }

    if (!this.data.smsCode || this.data.smsCode.length !== 6) {
      showToast('请输入验证码');
      return;
    }

    try {
      this.setData({ bindLoading: true });

      const result = await post<PhoneVerificationResponse>(
        '/auth/phone',
        {
          phone: `+86${this.data.phone}`,
          sms_code: this.data.smsCode,
          wechat_code: this.data.wechatCode || undefined,
        },
        { auth: false }
      );

      if (result.is_new_user) {
        wx.setStorageSync('verified_phone_token', result.verified_phone_token);
        wx.setStorageSync('verified_phone', result.phone);
        logger.info('New user, redirect to profile setup', { phone: result.phone });

        this.setData({ bindLoading: false });
        void wx.redirectTo({ url: '/pages/setup/setup' });
        return;
      }

      logger.info('Existing user login', { qiao_id: result.user.qiao_id });
      await authService.login(result.token, result.user);
      markWelcomeSeen();
      logger.info('Existing user login success', { qiao_id: result.user.qiao_id });

      logger.info('=== After Login Debug ===');
      checkStorage();
      logger.info('========================');

      this.setData({ bindLoading: false });

      await loadContacts();
      await initMessaging();
      void wx.switchTab({ url: '/pages/index/index' });
    } catch (error) {
      logger.error('Phone verification failed', { error });
      this.setData({ bindLoading: false });
      showToast(normalizeErrorMessage(error, '验证失败'));
    }
  },
});
