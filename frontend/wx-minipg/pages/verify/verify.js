import { post, get } from '../../utils/api';
import { getLogger } from '../../utils/logger';
import { getCachedCaptchaConfig, ensureCaptchaConfig, initCaptcha, showCaptcha } from '../../utils/captcha';

const logger = getLogger('Verify');

Page({
  data: {
    verifyType: 'phone',
    maskedPhone: '',
    maskedEmail: '',
    hasEmail: false,
    code: '',
    cooldown: 0,
    sending: false,
    verifying: false,
    loadCaptcha: false,
    pluginProps: {},
    captchaSceneId: '',
    // Callback page and params
    callbackPage: '',
    callbackParams: {}
  },

  onLoad(options) {
    const { callback, ...params } = options || {};

    this.setData({
      callbackPage: callback || '',
      callbackParams: params
    });

    logger.info('Verify page loaded', { callback });

    // Initialize captcha active flag
    this._captchaActive = false;

    // Load account info to get masked phone/email
    this.loadAccountInfo();

    // Preload/init captcha plugin once
    (async () => {
      try {
        const cfg = getCachedCaptchaConfig() || await ensureCaptchaConfig();
        initCaptcha(this, cfg, {
          success: (token) => this.onCaptchaSuccess(token),
          fail: (err) => this.onCaptchaFail(err)
        });
      } catch (_) {}
    })();
  },

  /**
   * Load account information
   */
  async loadAccountInfo() {
    try {
      const account = await get('/user/account');

      this.setData({
        maskedPhone: account.phone,
        maskedEmail: account.email || '',
        hasEmail: !!account.email
      });

      logger.info('Account info loaded');
    } catch (error) {
      logger.error('Load account info failed', {
        error: error.message || String(error)
      });

      wx.showToast({
        title: '加载失败',
        icon: 'none'
      });
    }
  },

  /** Select phone verification */
  selectPhone() {
    this.setData({
      verifyType: 'phone',
      code: ''
    });
  },

  /** Select email verification */
  selectEmail() {
    if (!this.data.hasEmail) {
      wx.showToast({
        title: '未绑定邮箱',
        icon: 'none'
      });
      return;
    }

    this.setData({
      verifyType: 'email',
      code: ''
    });
  },

  /** Handle code input */
  onCodeInput(e) {
    this.setData({
      code: e.detail.value
    });
  },

  /** Send verification code */
  async sendCode() {
    // First try without captcha; backend will reply 428 if captcha required
    try {
      this.setData({ sending: true });
      const payload = {
        verify_type: this.data.verifyType,
        target: null
      };
      const response = await post('/auth/user/verify/send-code', payload);
      wx.showToast({ title: '验证码已发送', icon: 'success' });
      this.startCooldown(response.cooldown || 60);
      logger.info('Verification code sent');
      this.setData({ sending: false });
      return;
    } catch (error) {
      const status = Number(error?.statusCode || error?.status || 0);
      const code = error?.errorCode || error?.data?.detail?.error || error?.data?.error || error?.data?.code;
      const needCaptcha = (status === 428) || (code === 'CAPTCHA_REQUIRED');
      if (!needCaptcha) {
        this.setData({ sending: false });
        if (error.statusCode === 429) {
          wx.showToast({ title: error.message || '发送过于频繁，请稍后再试', icon: 'none' });
        } else {
          wx.showToast({ title: error.message || '发送失败，请稍后再试', icon: 'none' });
        }
        return;
      }
    }

    // Trigger Aliyun captcha then retry
    this._captchaActive = true;
    showCaptcha(this);
  },

  async onCaptchaSuccess(captchaVerifyParam) {
    try {
      this._captchaActive = false;
      await this.requestSendWithCaptcha(captchaVerifyParam);
    } catch (error) {
      logger.error('Send verification code failed', { error: error.message || String(error) });
      wx.showToast({ title: error.message || '发送失败，请稍后再试', icon: 'none' });
    } finally {
      this.setData({ sending: false });
    }
  },

  onCaptchaFail(error) {
    logger.error('Aliyun captcha failed', { error });
    this.setData({ sending: false });
    if (this._captchaActive) {
      wx.showToast({ title: '验证服务错误，请稍后再试', icon: 'none' });
    }
    this._captchaActive = false;
  },

  async requestSendWithCaptcha(captchaToken) {
    try {
      this.setData({ sending: true });
      logger.info('Sending verification code', { verifyType: this.data.verifyType });

      const payload = {
        verify_type: this.data.verifyType,
        target: null,
        captcha_token: captchaToken
      };

      const response = await post('/auth/user/verify/send-code', payload);

      wx.showToast({ title: '验证码已发送', icon: 'success' });
      this.startCooldown(response.cooldown || 60);
      logger.info('Verification code sent');
    } catch (error) {
      logger.error('Send verification code failed', { error: error.message || String(error) });
      wx.showToast({ title: error.message || '发送失败，请稍后再试', icon: 'none' });
    } finally {
      this.setData({ sending: false });
    }
  },

  /** Start cooldown timer */
  startCooldown(seconds) {
    this.setData({ cooldown: seconds });

    const timer = setInterval(() => {
      const newCooldown = this.data.cooldown - 1;

      if (newCooldown <= 0) {
        clearInterval(timer);
        this.setData({ cooldown: 0 });
      } else {
        this.setData({ cooldown: newCooldown });
      }
    }, 1000);
  },

  /** Handle verify */
  async handleVerify() {
    try {
      if (this.data.code.length !== 6) {
        wx.showToast({
          title: '请输入6位验证码',
          icon: 'none'
        });
        return;
      }

      this.setData({ verifying: true });

      logger.info('Verifying code', { verifyType: this.data.verifyType });

      const response = await post('/auth/user/verify/confirm', {
        verify_type: this.data.verifyType,
        code: this.data.code
      });

      wx.showToast({
        title: '验证成功',
        icon: 'success'
      });

      logger.info('Verification successful', { operation_token: response.operation_token });

      // Navigate to callback page with operation_token
      if (this.data.callbackPage) {
        const paramsObj = Object.assign({}, this.data.callbackParams || {}, {
          operation_token: response.operation_token
        });
        const params = Object.keys(paramsObj)
          .filter(k => paramsObj[k] !== undefined && paramsObj[k] !== null)
          .map(k => `${encodeURIComponent(k)}=${encodeURIComponent(paramsObj[k])}`)
          .join('&');

        setTimeout(() => {
          wx.redirectTo({
            url: params ? `${this.data.callbackPage}?${params}` : `${this.data.callbackPage}`
          });
        }, 500);
      } else {
        // No callback, just go back
        setTimeout(() => {
          wx.navigateBack();
        }, 500);
      }
    } catch (error) {
      logger.error('Verification failed', {
        error: error.message || String(error)
      });

      wx.showToast({
        title: error.message || '验证失败，请稍后再试',
        icon: 'none'
      });

      this.setData({ verifying: false });
    }
  }
});
