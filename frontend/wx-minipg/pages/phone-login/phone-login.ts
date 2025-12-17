import { post } from '../../utils/api';
import authService from '../../utils/auth-service';
import {
  ensureCaptchaConfig,
  getCachedCaptchaConfig,
  initCaptcha,
  showCaptcha,
} from '../../utils/captcha';
import { getLogger } from '../../utils/logger';
import { fetchAllContactsFromApi } from '../../utils/contact-sync';
import { saveContacts, type StoredAuthUser } from '../../utils/storage';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';

const logger = getLogger('PhoneLogin');

type PhoneChangeEvent = WechatMiniprogram.CustomEvent<{
  value: string;
  countryCode: string;
  fullPhone: string;
  valid: boolean;
}>;
type InputEvent = WechatMiniprogram.CustomEvent<{ value: string }>;
type PhoneNumberEvent = WechatMiniprogram.ButtonGetPhoneNumber;

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

interface PhoneLoginResponse {
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

interface PhoneLoginPageData extends Ailo.CaptchaPageData {
  pageLayoutData: PageLayoutData;
  loginCode: string;
  phone: string;
  fullPhone: string;
  smsCode: string;
  smsCountdown: number;
  canSendSms: boolean;
  canLogin: boolean;
  phoneButtonLoading: boolean;
  loginLoading: boolean;
  showCaptcha: boolean;
  captchaScene: string;
}

type PhoneLoginPageInstance = WechatMiniprogram.Page.Instance<
  PhoneLoginPageData,
  PhoneLoginPageCustom
>;

interface PhoneLoginPageCustom {
  _captchaActive?: boolean;
  _captchaReady?: boolean;
  _captchaRetryCount?: number;
  onCaptchaSuccess(captchaToken: string): Promise<void>;
  onCaptchaFail(error: unknown): void;
  handleGetPhoneNumber(event: PhoneNumberEvent): Promise<void>;
  handlePhoneChange(event: PhoneChangeEvent): void;
  handleSmsCodeInput(event: InputEvent): void;
  handleSendSms(): Promise<void>;
  requestSmsWithCaptcha(captchaToken: string): Promise<void>;
  handleLogin(): Promise<void>;
  onRetry(): void;
}

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
};

const startCountdown = (page: PhoneLoginPageInstance): void => {
  let remaining = 60;
  page.setData({ smsCountdown: remaining });
  const timer = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(timer);
      page.setData({ smsCountdown: 0 });
      return;
    }
    page.setData({ smsCountdown: remaining });
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

Page<PhoneLoginPageData, PhoneLoginPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      hasFooter: true,
    }),
    loginCode: '',
    phone: '',
    fullPhone: '',
    smsCode: '',
    smsCountdown: 0,
    canSendSms: false,
    canLogin: false,
    phoneButtonLoading: false,
    loginLoading: false,
    showCaptcha: false,
    captchaScene: '',
    // CaptchaPageData fields - required for Aliyun captcha plugin
    captchaProvider: undefined,
    captchaSceneId: undefined,
    loadCaptcha: false,
    pluginProps: undefined,
  },

  onRetry() {
    this.setData({
      'pageLayoutData.hasError': false,
    });
  },

  async onLoad() {
    logger.info('Phone login page loaded');

    // Silently obtain login_code for WeChat one-click login (valid for 5 minutes)
    try {
      const { code } = await wx.login();
      if (code) {
        this.setData({ loginCode: code });
        logger.info('Login code obtained for phone-login page', { code });
      } else {
        logger.warn('Failed to obtain login code on phone-login page load');
      }
    } catch (error) {
      logger.error('Failed to obtain login code', { error });
    }

    try {
      const cached = getCachedCaptchaConfig();
      const config = cached ?? (await ensureCaptchaConfig());
      initCaptcha(this as unknown as Ailo.CaptchaPageInstance, config, {
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
    (this as PhoneLoginPageCustom)._captchaActive = false;
    await this.requestSmsWithCaptcha(captchaToken);
  },

  onCaptchaFail(error) {
    logger.error('Aliyun captcha failed', { error });
    if ((this as PhoneLoginPageCustom)._captchaActive) {
      showToast('验证服务错误，请稍后再试');
    }
    (this as PhoneLoginPageCustom)._captchaActive = false;
  },

  async handleGetPhoneNumber(event) {
    if (event.detail.errMsg !== 'getPhoneNumber:ok') {
      logger.warn('User denied phone authorization');
      showToast('需要手机号授权才能继续');
      return;
    }

    const phoneCode = event.detail.code;
    logger.info('Got phone code for one-click login', { phoneCode });

    try {
      this.setData({ phoneButtonLoading: true });

      // Use pre-fetched login_code
      const loginCode = this.data.loginCode;
      if (!loginCode) {
        throw new Error('Login code not available, please try again');
      }

      logger.info('Using pre-fetched login code for one-click login', { loginCode });

      const result = await post<WechatLoginResponse>(
        '/auth/wechat/login',
        {
          login_code: loginCode,
          phone_code: phoneCode,
        },
        { auth: false }
      );

      // Check if phone binding is needed (international phone)
      if (!result.success && result.needs_phone_binding) {
        logger.info('International phone detected, switch to manual input');
        this.setData({ phoneButtonLoading: false });
        showToast(result.message || '请使用手机号和验证码登录');
        return;
      }

      // Login successful
      await authService.login(result.user.token, result.user);
      logger.info('WeChat one-click login success', { user: result.user });

      this.setData({ phoneButtonLoading: false });

      // Check if user needs to complete profile setup
      if (!result.user.nickname) {
        void wx.redirectTo({ url: '/pages/setup/setup' });
        return;
      }

      // Load contacts and init messaging
      await loadContacts();
      await initMessaging();
      void wx.switchTab({ url: '/pages/index/index' });
    } catch (error) {
      logger.error('Phone authorization failed', { error });
      this.setData({ phoneButtonLoading: false });
      showToast('操作失败，请重试');
    }
  },

  handlePhoneChange(event) {
    const { value, fullPhone, valid } = event.detail;
    this.setData({
      phone: value,
      fullPhone,
      canSendSms: valid,
      canLogin: valid && this.data.smsCode.length === 6,
    });
  },

  handleSmsCodeInput(event) {
    const smsCode = event.detail.value;
    this.setData({
      smsCode,
      canLogin: this.data.canSendSms && smsCode.length === 6,
    });
  },

  async handleSendSms() {
    if (!this.data.canSendSms) {
      showToast('请输入正确的手机号');
      return;
    }

    try {
      await post('/auth/send-sms', { phone: this.data.fullPhone }, { auth: false });
      startCountdown(this as PhoneLoginPageInstance);
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

    (this as PhoneLoginPageCustom)._captchaActive = true;
    void showCaptcha(this as unknown as Ailo.CaptchaPageInstance);
  },

  async requestSmsWithCaptcha(captchaToken) {
    try {
      await post(
        '/auth/send-sms',
        {
          phone: this.data.fullPhone,
          captcha_token: captchaToken,
        },
        { auth: false }
      );

      startCountdown(this as PhoneLoginPageInstance);
      showToast('验证码已发送', 'success');
    } catch (error) {
      logger.error('Send SMS failed', { error });
      showToast(normalizeErrorMessage(error, '发送失败'));
    }
  },

  async handleLogin() {
    if (!this.data.canSendSms) {
      showToast('请输入正确的手机号');
      return;
    }

    if (!this.data.smsCode || this.data.smsCode.length !== 6) {
      showToast('请输入验证码');
      return;
    }

    try {
      this.setData({ loginLoading: true });

      const result = await post<PhoneLoginResponse>(
        '/auth/phone',
        {
          phone: this.data.fullPhone,
          sms_code: this.data.smsCode,
        },
        { auth: false }
      );

      if (result.is_new_user) {
        wx.setStorageSync('verified_phone_token', result.verified_phone_token);
        wx.setStorageSync('verified_phone', result.phone);
        logger.info('New user, redirect to profile setup', { phone: result.phone });

        this.setData({ loginLoading: false });
        void wx.redirectTo({ url: '/pages/setup/setup' });
        return;
      }

      logger.info('Existing user login', { qiao_id: result.user.qiao_id });
      await authService.login(result.token, result.user);
      logger.info('Existing user login success', { qiao_id: result.user.qiao_id });

      this.setData({ loginLoading: false });

      await loadContacts();
      await initMessaging();
      void wx.switchTab({ url: '/pages/index/index' });
    } catch (error) {
      logger.error('Phone login failed', { error });
      this.setData({ loginLoading: false });
      showToast(normalizeErrorMessage(error, '登录失败'));
    }
  },
});
