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

const logger = getLogger('PhoneBind');

type InputEvent = WechatMiniprogram.CustomEvent<{ value: string }>;
type PhoneChangeEvent = WechatMiniprogram.CustomEvent<{
  value: string;
  countryCode: string;
  fullPhone: string;
  valid: boolean;
}>;
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

interface PhoneBindResponse {
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

interface PhoneBindPageData extends Says.CaptchaPageData {
  pageLayoutData: PageLayoutData;
  wechatCode: string;
  loginCode: string;
  headerSubtitle: string;
  phone: string;
  fullPhone: string;
  smsCode: string;
  smsCountdown: number;
  canSendSms: boolean;
  canBind: boolean;
  phoneButtonLoading: boolean;
  bindLoading: boolean;
  showCaptcha: boolean;
  captchaScene: string;
}

type PhoneBindPageInstance = WechatMiniprogram.Page.Instance<
  PhoneBindPageData,
  PhoneBindPageCustom
>;

interface PhoneBindPageCustom {
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
  handleBind(): Promise<void>;
  onRetry(): void;
}

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
};

const startCountdown = (page: PhoneBindPageInstance): void => {
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

Page<PhoneBindPageData, PhoneBindPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      hasFooter: true,
    }),
    wechatCode: '',
    loginCode: '',
    headerSubtitle: '绑定手机号以完成登录',
    phone: '',
    fullPhone: '',
    smsCode: '',
    smsCountdown: 0,
    canSendSms: false,
    canBind: false,
    phoneButtonLoading: false,
    bindLoading: false,
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

  async onLoad(options) {
    logger.info('Phone bind page loaded', { options });

    const wechatCode = options?.wechat_code ?? '';
    const subtitle = wechatCode ? '绑定手机号以完成微信登录' : '绑定手机号以完成登录';

    this.setData({
      wechatCode,
      headerSubtitle: subtitle,
    });

    // Silently obtain login_code for WeChat retry (valid for 5 minutes)
    try {
      const { code } = await wx.login();
      if (code) {
        this.setData({ loginCode: code });
        logger.info('Login code obtained for phone-bind page', { code });
      } else {
        logger.warn('Failed to obtain login code on phone-bind page load');
      }
    } catch (error) {
      logger.error('Failed to obtain login code', { error });
    }

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
    (this as PhoneBindPageCustom)._captchaActive = false;
    await this.requestSmsWithCaptcha(captchaToken);
  },

  onCaptchaFail(error) {
    logger.error('Aliyun captcha failed', { error });
    if ((this as PhoneBindPageCustom)._captchaActive) {
      showToast('验证服务错误，请稍后再试');
    }
    (this as PhoneBindPageCustom)._captchaActive = false;
  },

  async handleGetPhoneNumber(event) {
    if (event.detail.errMsg !== 'getPhoneNumber:ok') {
      logger.warn('User denied phone authorization');
      showToast('需要手机号授权才能继续');
      return;
    }

    const phoneCode = event.detail.code;
    logger.info('Got phone code for retry', { phoneCode });

    try {
      this.setData({ phoneButtonLoading: true });

      // Use pre-fetched login_code
      const loginCode = this.data.loginCode;
      if (!loginCode) {
        throw new Error('Login code not available, please try again');
      }

      logger.info('Using pre-fetched login code for retry', { loginCode });

      const result = await post<WechatLoginResponse>(
        '/auth/wechat/login',
        {
          login_code: loginCode,
          phone_code: phoneCode,
        },
        { auth: false }
      );

      if (!result.success && result.needs_phone_binding) {
        // Update wechat_code with new one from backend
        this.setData({
          phoneButtonLoading: false,
          wechatCode: result.wechat_code || this.data.wechatCode,
        });
        showToast(result.message || '仍然是国际手机号，请使用短信验证');
        logger.info('Phone binding still required after retry');
        return;
      }

      await authService.login(result.user.token, result.user);
      logger.info('WeChat login success after retry', { user: result.user });

      this.setData({ phoneButtonLoading: false });

      if (!result.user.nickname) {
        void wx.redirectTo({ url: '/pages/setup/setup' });
        return;
      }

      await loadContacts();
      await initMessaging();
      void wx.switchTab({ url: '/pages/index/index' });
    } catch (error) {
      logger.error('Phone authorization failed', { error });
      this.setData({ phoneButtonLoading: false });
      showToast('操作失败，请重试');
    }
  },

  handlePhoneChange(event: PhoneChangeEvent) {
    const { value, fullPhone, valid } = event.detail;
    this.setData({
      phone: value,
      fullPhone,
      canSendSms: valid,
      canBind: valid && this.data.smsCode.length === 6,
    });
  },

  handleSmsCodeInput(event) {
    const smsCode = event.detail.value;
    this.setData({
      smsCode,
      canBind: this.data.canSendSms && smsCode.length === 6,
    });
  },

  async handleSendSms() {
    if (!this.data.canSendSms) {
      showToast('请输入正确的手机号');
      return;
    }

    try {
      await post('/auth/send-sms', { phone: this.data.fullPhone }, { auth: false });
      startCountdown(this as PhoneBindPageInstance);
      showToast('验证码已发送', 'success');
      return;
    } catch (error) {
      const apiError = error as ApiError;
      if (!hasCaptchaRequirement(apiError)) {
        if (apiError.statusCode === 429) {
          showToast('发送过于频繁，请稍后再试');
        } else {
          showToast('发送失败，请重试');
        }
        return;
      }
    }

    (this as PhoneBindPageCustom)._captchaActive = true;
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

      startCountdown(this as PhoneBindPageInstance);
      showToast('验证码已发送', 'success');
    } catch (error) {
      logger.error('Send SMS failed', { error });
      showToast('发送失败，请重试');
    }
  },

  async handleBind() {
    if (!this.data.canSendSms) {
      showToast('请输入正确的手机号');
      return;
    }

    if (!this.data.smsCode || this.data.smsCode.length !== 6) {
      showToast('请输入验证码');
      return;
    }

    try {
      this.setData({ bindLoading: true });

      const result = await post<PhoneBindResponse>(
        '/auth/phone',
        {
          phone: this.data.fullPhone,
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
      logger.info('Existing user login success', { qiao_id: result.user.qiao_id });

      this.setData({ bindLoading: false });

      await loadContacts();
      await initMessaging();
      void wx.switchTab({ url: '/pages/index/index' });
    } catch (error) {
      logger.error('Phone bind failed', { error });
      this.setData({ bindLoading: false });
      showToast('绑定失败，请重试');
    }
  },
});
