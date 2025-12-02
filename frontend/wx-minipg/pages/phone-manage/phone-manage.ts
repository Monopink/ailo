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
  loading: boolean;
  currentPhone: string;
  newPhone: string;
  smsCode: string;
  cooldown: number;
  sending: boolean;
  saving: boolean;
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
  onNewPhoneInput(event: InputEvent): void;
  onSmsCodeInput(event: InputEvent): void;
  sendSmsCode(): Promise<void>;
  onCaptchaSuccess(token: string): Promise<void>;
  onCaptchaFail(error: unknown): void;
  requestSmsWithCaptcha(token: string): Promise<void>;
  startCooldown(seconds: number): void;
  handleChangePhone(): Promise<void>;
}

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
};

const isValidPhone = (value: string): boolean => /^1\d{10}$/.test(value);

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
    loading: true,
    currentPhone: '',
    newPhone: '',
    smsCode: '',
    cooldown: 0,
    sending: false,
    saving: false,
    // Aliyun captcha
    loadCaptcha: false,
    pluginProps: {},
    captchaSceneId: '',
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
        currentPhone: account.phone,
        loading: false,
      });
    } catch (error) {
      logger.error('Load account info failed', { error });
      showToast('加载失败');
      this.setData({ loading: false });
    }
  },

  /** Handle new phone input */
  onNewPhoneInput(event: InputEvent) {
    this.setData({
      newPhone: (event.detail.value || '').trim(),
    });
  },

  /** Handle SMS code input */
  onSmsCodeInput(event: InputEvent) {
    this.setData({
      smsCode: event.detail.value,
    });
  },

  /** Send SMS code */
  async sendSmsCode() {
    const nextPhone = (this.data.newPhone || '').trim();

    if (!nextPhone) {
      showToast('请输入手机号');
      return;
    }
    if (!isValidPhone(nextPhone)) {
      showToast('手机号格式不正确');
      return;
    }

    try {
      this.setData({ sending: true });
      await post('/auth/send-sms', { phone: `+86${nextPhone}` }, { auth: true });
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
      const nextPhone = (this.data.newPhone || '').trim();
      await post(
        '/auth/send-sms',
        {
          phone: `+86${nextPhone}`,
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
    const nextPhone = (this.data.newPhone || '').trim();

    if (!nextPhone) {
      showToast('请输入新手机号');
      return;
    }
    if (!isValidPhone(nextPhone)) {
      showToast('手机号格式不正确');
      return;
    }
    if (this.data.smsCode.length !== 6) {
      showToast('请输入6位验证码');
      return;
    }

    try {
      this.setData({ saving: true });
      await put(
        '/user/phone',
        {
          new_phone: `+86${nextPhone}`,
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
      this.setData({ saving: false });
    }
  },
});
