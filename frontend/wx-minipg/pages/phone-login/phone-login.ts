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

interface PhoneLoginPageData extends Says.CaptchaPageData {
  pageLayoutData: PageLayoutData;
  phone: string;
  fullPhone: string;
  smsCode: string;
  smsCountdown: number;
  canSendSms: boolean;
  canLogin: boolean;
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
  onCaptchaSuccess(captchaToken: string): Promise<void>;
  onCaptchaFail(error: unknown): void;
  handlePhoneChange(event: PhoneChangeEvent): void;
  handleSmsCodeInput(event: InputEvent): void;
  handleSendSms(): Promise<void>;
  requestSmsWithCaptcha(captchaToken: string): Promise<void>;
  handleLogin(): Promise<void>;
  handleCaptchaVerify(event: WechatMiniprogram.CustomEvent): void;
  handleCaptchaClose(): void;
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
  const app = getApp<SaysAppInstance>();
  await app.initMessageService();
};

Page<PhoneLoginPageData, PhoneLoginPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      hasFooter: true,
    }),
    phone: '',
    fullPhone: '',
    smsCode: '',
    smsCountdown: 0,
    canSendSms: false,
    canLogin: false,
    loginLoading: false,
    showCaptcha: false,
    captchaScene: '',
  },

  onRetry() {
    this.setData({
      'pageLayoutData.hasError': false,
    });
  },

  async onLoad() {
    logger.info('Phone login page loaded');
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
    void showCaptcha(this as unknown as Says.CaptchaPageInstance);
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

  handleCaptchaVerify(event) {
    const token = event.detail?.token as string | undefined;
    if (token) {
      void this.onCaptchaSuccess(token);
    }
  },

  handleCaptchaClose() {
    (this as PhoneLoginPageCustom)._captchaActive = false;
    this.setData({ showCaptcha: false });
  },
});
