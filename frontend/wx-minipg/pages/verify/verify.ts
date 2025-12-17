import { post } from '../../utils/api';
import {
  ensureCaptchaConfig,
  getCachedCaptchaConfig,
  initCaptcha,
  showCaptcha,
} from '../../utils/captcha';
import { getLogger } from '../../utils/logger';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { fetchAccountInfo } from '../../utils/profile';

const logger = getLogger('Verify');

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

interface SendCodeResponse {
  cooldown?: number;
}

interface VerifyConfirmResponse {
  operation_token: string;
}

interface VerifyPageData extends Ailo.CaptchaPageData {
  pageLayoutData: PageLayoutData;
  verifyType: 'phone' | 'email';
  maskedPhone: string;
  maskedEmail: string;
  hasEmail: boolean;
  code: string;
  cooldown: number;
  sending: boolean;
  verifying: boolean;
  loadCaptcha: boolean;
  pluginProps: Record<string, unknown>;
  captchaSceneId: string;
  callbackPage: string;
  callbackParams: Record<string, string | undefined>;
}

interface VerifyPageCustom {
  _captchaActive?: boolean;
  _captchaReady?: boolean;
  _captchaRetryCount?: number;
  loadAccountInfo(): Promise<void>;
  onRetry(): void;
  selectPhone(): void;
  selectEmail(): void;
  onCodeInput(event: InputEvent): void;
  sendCode(): Promise<void>;
  onCaptchaSuccess(captchaToken: string): Promise<void>;
  onCaptchaFail(error: unknown): void;
  requestSendWithCaptcha(captchaToken: string): Promise<void>;
  startCooldown(seconds: number): void;
  handleVerify(): Promise<void>;
}

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
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

Page<VerifyPageData, VerifyPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      isLoading: true,
      hasFooter: true,
      emptyMessage: '',
    }),
    verifyType: 'phone',
    maskedPhone: '',
    maskedEmail: '',
    hasEmail: false,
    code: '',
    cooldown: 0,
    sending: false,
    verifying: false,
    callbackPage: '',
    callbackParams: {},
    // CaptchaPageData fields - required for Aliyun captcha plugin
    captchaProvider: undefined,
    captchaSceneId: '',
    loadCaptcha: false,
    pluginProps: {},
  },

  async onLoad(options: Record<string, string | undefined>) {
    const { callback, ...params } = options ?? {};
    this.setData({
      callbackPage: callback ?? '',
      callbackParams: params ?? {},
    });

    logger.info('Verify page loaded', { callback });

    await this.loadAccountInfo();

    try {
      const config = getCachedCaptchaConfig() ?? (await ensureCaptchaConfig());
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

  async loadAccountInfo() {
    this.setData({
      'pageLayoutData.isLoading': true,
      'pageLayoutData.hasError': false,
      'pageLayoutData.errorMessage': '',
    });
    try {
      const account = await fetchAccountInfo();
      this.setData({
        maskedPhone: account.phone || '未绑定',
        maskedEmail: account.email || '未绑定',
        hasEmail: Boolean(account.email),
        'pageLayoutData.isLoading': false,
      });
    } catch (error) {
      logger.error('Load account info failed', { error });
      showToast('加载失败');
      this.setData({
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': '加载失败，请稍后再试',
      });
    }
  },

  onRetry() {
    this.setData({
      'pageLayoutData.hasError': false,
      'pageLayoutData.errorMessage': '',
    });
    void this.loadAccountInfo();
  },

  selectPhone() {
    this.setData({
      verifyType: 'phone',
      code: '',
    });
  },

  selectEmail() {
    if (!this.data.hasEmail) {
      showToast('未绑定邮箱');
      return;
    }
    this.setData({
      verifyType: 'email',
      code: '',
    });
  },

  onCodeInput(event) {
    this.setData({ code: event.detail.value });
  },

  async sendCode() {
    try {
      this.setData({ sending: true });
      const response = await post<SendCodeResponse>(
        '/auth/user/verify/send-code',
        {
          verify_type: this.data.verifyType,
          target: null,
        },
        { auth: true }
      );

      showToast('验证码已发送', 'success');
      this.startCooldown(response.cooldown ?? 60);
      logger.info('Verification code sent');
      this.setData({ sending: false });
      return;
    } catch (error) {
      const apiError = error as ApiError;
      if (!needsCaptcha(apiError)) {
        this.setData({ sending: false });
        if (apiError.statusCode === 429) {
          showToast(normalizeErrorMessage(apiError, '发送过于频繁，请稍后再试'));
        } else {
          showToast(normalizeErrorMessage(apiError, '发送失败，请稍后再试'));
        }
        return;
      }
    }

    const captchaPage = this as unknown as Ailo.CaptchaPageInstance;
    captchaPage._captchaActive = true;
    void showCaptcha(captchaPage);
  },

  async onCaptchaSuccess(captchaToken) {
    (this as unknown as Ailo.CaptchaPageInstance)._captchaActive = false;
    await this.requestSendWithCaptcha(captchaToken);
    this.setData({ sending: false });
  },

  onCaptchaFail(error) {
    logger.error('Aliyun captcha failed', { error });
    this.setData({ sending: false });
    if ((this as unknown as Ailo.CaptchaPageInstance)._captchaActive) {
      showToast('验证服务错误，请稍后再试');
    }
    (this as unknown as Ailo.CaptchaPageInstance)._captchaActive = false;
  },

  async requestSendWithCaptcha(captchaToken) {
    try {
      this.setData({ sending: true });
      const response = await post<SendCodeResponse>(
        '/auth/user/verify/send-code',
        {
          verify_type: this.data.verifyType,
          target: null,
          captcha_token: captchaToken,
        },
        { auth: true }
      );

      showToast('验证码已发送', 'success');
      this.startCooldown(response.cooldown ?? 60);
      logger.info('Verification code sent');
    } catch (error) {
      logger.error('Send verification code failed', { error });
      showToast(normalizeErrorMessage(error, '发送失败，请稍后再试'));
    } finally {
      this.setData({ sending: false });
    }
  },

  startCooldown(seconds) {
    this.setData({ cooldown: seconds });
    const timer = setInterval(() => {
      const newCooldown = this.data.cooldown - 1;
      if (newCooldown <= 0) {
        clearInterval(timer);
        this.setData({ cooldown: 0 });
        return;
      }
      this.setData({ cooldown: newCooldown });
    }, 1000);
  },

  async handleVerify() {
    if (this.data.code.length !== 6) {
      showToast('请输入6位验证码');
      return;
    }

    try {
      this.setData({ verifying: true });
      const response = await post<VerifyConfirmResponse>(
        '/auth/user/verify/confirm',
        {
          verify_type: this.data.verifyType,
          code: this.data.code,
        },
        { auth: true }
      );

      showToast('验证成功', 'success');
      logger.info('Verification successful', { operation_token: response.operation_token });

      if (this.data.callbackPage) {
        const paramsObj = {
          ...this.data.callbackParams,
          operation_token: response.operation_token,
        };
        const params = Object.entries(paramsObj)
          .filter(([, value]) => value !== undefined && value !== null && value !== '')
          .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
          .join('&');

        setTimeout(() => {
          void wx.redirectTo({
            url: params ? `${this.data.callbackPage}?${params}` : this.data.callbackPage,
          });
        }, 500);
      } else {
        setTimeout(() => {
          void wx.navigateBack();
        }, 500);
      }
    } catch (error) {
      logger.error('Verification failed', { error });
      showToast(normalizeErrorMessage(error, '验证失败，请稍后再试'));
      this.setData({ verifying: false });
    }
  },
});
