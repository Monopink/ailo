import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { get, post, put } from '../../utils/api';
import {
  ensureCaptchaConfig,
  getCachedCaptchaConfig,
  initCaptcha,
  showCaptcha,
} from '../../utils/captcha';
import { getLogger } from '../../utils/logger';

const logger = getLogger('PhoneManage');

type InputEvent = WechatMiniprogram.CustomEvent<{ value: string }>;
type PhoneChangeEvent = WechatMiniprogram.CustomEvent<{
  value: string;
  countryCode: string;
  fullPhone: string;
  valid: boolean;
}>;

interface ApiError extends Error {
  statusCode?: number;
  status?: number;
  errorCode?: string | number;
  data?: {
    detail?: { error?: string | number; message?: string; code?: string | number };
    error?: string | number;
    code?: string | number;
  };
}

interface AccountInfo {
  phone: string;
}

interface PhoneManagePageData extends Says.CaptchaPageData {
  pageLayoutData: PageLayoutData;
  currentPhone: string;
  newPhone: string;
  fullNewPhone: string;
  isPhoneValid: boolean;
  smsCode: string;
  cooldown: number;
  sending: boolean;
  saving: boolean;
  submitButtonText: string;
  loadCaptcha: boolean;
  pluginProps: Record<string, unknown>;
  captchaSceneId: string;
}

type PhoneManagePageInstance = WechatMiniprogram.Page.Instance<
  PhoneManagePageData,
  PhoneManagePageCustom
>;

interface PhoneManagePageCustom {
  loadAccountInfo(): Promise<void>;
  onNewPhoneChange(event: PhoneChangeEvent): void;
  onSmsCodeInput(event: InputEvent): void;
  sendSmsCode(): Promise<void>;
  onCaptchaSuccess(token: string): Promise<void>;
  onCaptchaFail(error: unknown): void;
  requestSmsWithCaptcha(token: string): Promise<void>;
  startCooldown(seconds: number): void;
  handleChangePhone(): Promise<void>;
  onRetry(): void;
}

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
};

const maskPhone = (phone: string | undefined): string => {
  if (!phone) {
    return '未绑定';
  }
  const digits = phone.replace(/[^0-9]/g, '');
  if (digits.length >= 11) {
    return `${digits.slice(0, 3)}****${digits.slice(-4)}`;
  }
  return phone;
};

const needsCaptcha = (error: ApiError): boolean => {
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

const startCountdown = (page: PhoneManagePageInstance, seconds: number): void => {
  let remaining = seconds;
  page.setData({ cooldown: remaining });
  const timer = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(timer);
      page.setData({ cooldown: 0 });
      return;
    }
    page.setData({ cooldown: remaining });
  }, 1000);
};

const asCaptchaPage = (page: PhoneManagePageInstance): Says.CaptchaPageInstance =>
  page as unknown as Says.CaptchaPageInstance;

Page<PhoneManagePageData, PhoneManagePageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      isLoading: true,
      emptyMessage: '暂无账号信息',
      hasFooter: true,
    }),
    currentPhone: '',
    newPhone: '',
    fullNewPhone: '',
    isPhoneValid: false,
    smsCode: '',
    cooldown: 0,
    sending: false,
    saving: false,
    submitButtonText: '确认修改',
    // CaptchaPageData fields - required for Aliyun captcha plugin
    captchaProvider: undefined,
    captchaSceneId: '',
    loadCaptcha: false,
    pluginProps: {},
  },

  async onLoad() {
    logger.info('Phone manage page loaded');
    await this.loadAccountInfo();

    try {
      const config = getCachedCaptchaConfig() ?? (await ensureCaptchaConfig());
      initCaptcha(asCaptchaPage(this as PhoneManagePageInstance), config, {
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

  /**
   * Load account information
   */
  async loadAccountInfo() {
    try {
      const account = await get<AccountInfo>('/user/account');

      this.setData({
        currentPhone: maskPhone(account.phone),
        'pageLayoutData.isLoading': false,
        'pageLayoutData.isEmpty': false,
        'pageLayoutData.hasError': false,
        'pageLayoutData.errorMessage': '',
      });
    } catch (error) {
      logger.error('Load account info failed', { error });
      showToast('加载失败');
      this.setData({
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': '加载失败，请稍后重试',
      });
    }
  },

  /** Handle new phone input */
  onNewPhoneChange(event: PhoneChangeEvent) {
    const { value, fullPhone, valid } = event.detail;
    this.setData({
      newPhone: value,
      fullNewPhone: fullPhone,
      isPhoneValid: valid,
    });
  },

  /** Handle SMS code input */
  onSmsCodeInput(event: InputEvent) {
    const value = event.detail.value || '';
    this.setData({
      smsCode: value,
    });
  },

  /** Send SMS code */
  async sendSmsCode() {
    if (!this.data.isPhoneValid) {
      showToast('请输入正确的手机号');
      return;
    }

    try {
      this.setData({ sending: true });
      await post('/auth/send-sms', { phone: this.data.fullNewPhone }, { auth: true });
      showToast('验证码已发送', 'success');
      startCountdown(this as PhoneManagePageInstance, 60);
      this.setData({ sending: false });
      return;
    } catch (error) {
      const apiError = error as ApiError;
      if (!needsCaptcha(apiError)) {
        if (apiError.statusCode === 429) {
          showToast(normalizeErrorMessage(apiError, '发送过于频繁，请稍后再试'));
        } else {
          showToast(normalizeErrorMessage(apiError, '发送失败，请稍后再试'));
        }
        this.setData({ sending: false });
        return;
      }
    }

    const captchaPage = asCaptchaPage(this as PhoneManagePageInstance);
    captchaPage._captchaActive = true;
    void showCaptcha(captchaPage);
  },

  async onCaptchaSuccess(token: string) {
    const captchaPage = asCaptchaPage(this as PhoneManagePageInstance);
    captchaPage._captchaActive = false;
    await this.requestSmsWithCaptcha(token);
    this.setData({ sending: false });
  },

  onCaptchaFail(error: unknown) {
    logger.error('Aliyun captcha failed', { error });
    this.setData({ sending: false });
    const captchaPage = asCaptchaPage(this as PhoneManagePageInstance);
    if (captchaPage._captchaActive) {
      showToast('验证服务错误，请稍后再试');
    }
    captchaPage._captchaActive = false;
  },

  async requestSmsWithCaptcha(token: string) {
    try {
      this.setData({ sending: true });
      await post(
        '/auth/send-sms',
        {
          phone: this.data.fullNewPhone,
          captcha_token: token,
        },
        { auth: true }
      );

      showToast('验证码已发送', 'success');
      startCountdown(this as PhoneManagePageInstance, 60);
    } catch (error) {
      logger.error('Send SMS code failed', { error });
      showToast(normalizeErrorMessage(error, '发送失败，请稍后再试'));
    } finally {
      this.setData({ sending: false });
    }
  },

  /** Start cooldown timer */
  startCooldown(seconds: number) {
    startCountdown(this as PhoneManagePageInstance, seconds);
  },

  /** Handle change phone */
  async handleChangePhone() {
    if (!this.data.isPhoneValid) {
      showToast('请输入正确的手机号');
      return;
    }

    if (this.data.smsCode.length !== 6) {
      showToast('请输入6位验证码');
      return;
    }

    try {
      this.setData({ saving: true, submitButtonText: '修改中...' });
      await put(
        '/user/phone',
        {
          new_phone: this.data.fullNewPhone,
          sms_code: this.data.smsCode,
        },
        { auth: true }
      );

      showToast('修改成功', 'success');
      setTimeout(() => {
        void wx.navigateBack();
      }, 1500);
    } catch (error) {
      logger.error('Change phone failed', { error });
      showToast(normalizeErrorMessage(error, '修改失败，请稍后再试'));
    } finally {
      this.setData({ saving: false, submitButtonText: '确认修改' });
    }
  },

  onRetry() {
    void this.loadAccountInfo();
  },
});
