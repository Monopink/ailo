import { get, post, put } from '../../utils/api';
import { getLogger } from '../../utils/logger';
import { getCachedCaptchaConfig, ensureCaptchaConfig, initCaptcha, showCaptcha } from '../../utils/captcha';

const logger = getLogger('PhoneManage');

Page({
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
    captchaSceneId: ''
  },

  onLoad() {
    logger.info('Phone manage page loaded');

    // Initialize captcha active flag
    this._captchaActive = false;

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
        currentPhone: account.phone,
        loading: false
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

      this.setData({ loading: false });
    }
  },

  /** Handle new phone input */
  onNewPhoneInput(e) {
    this.setData({
      newPhone: (e.detail.value || '').trim()
    });
  },

  /** Handle SMS code input */
  onSmsCodeInput(e) {
    this.setData({
      smsCode: e.detail.value
    });
  },

  /** Send SMS code */
  async sendSmsCode() {
    const nextPhone = (this.data.newPhone || '').trim();

    // Basic validation
    if (!nextPhone) {
      wx.showToast({ title: '请输入手机号', icon: 'none' });
      return;
    }
    if (!/^1\d{10}$/.test(nextPhone)) {
      wx.showToast({ title: '手机号格式不正确', icon: 'none' });
      return;
    }

    // First try without captcha; backend returns 428 if captcha required
    try {
      this.setData({ sending: true });
      await post('/auth/send-sms', {
        phone: `+86${nextPhone}`
      });
      wx.showToast({ title: '验证码已发送', icon: 'success' });
      this.startCooldown(60);
      this.setData({ sending: false });
      return;
    } catch (error) {
      const status = Number(error?.statusCode || error?.status || 0);
      const code = error?.errorCode || error?.data?.detail?.error || error?.data?.error || error?.data?.code;
      const needCaptcha = (status === 428) || (code === 'CAPTCHA_REQUIRED');
      if (!needCaptcha) {
        if (error.statusCode === 429) {
          wx.showToast({ title: error.message || '发送过于频繁，请稍后再试', icon: 'none' });
        } else {
          wx.showToast({ title: error.message || '发送失败，请稍后再试', icon: 'none' });
        }
        this.setData({ sending: false });
        return;
      }
    }

    // Show Aliyun captcha then retry
    this._captchaActive = true;
    showCaptcha(this);
  },

  async onCaptchaSuccess(captchaVerifyParam) {
    try {
      this._captchaActive = false;
      await this.requestSmsWithCaptcha(captchaVerifyParam);
    } catch (error) {
      logger.error('Send SMS code after captcha failed', { error: error.message || String(error) });
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

  async requestSmsWithCaptcha(captchaToken) {
    try {
      this.setData({ sending: true });
      const nextPhone = (this.data.newPhone || '').trim();
      logger.info('Sending SMS code', { phone: nextPhone });

      await post('/auth/send-sms', {
        phone: `+86${nextPhone}`,
        captcha_token: captchaToken
      });

      wx.showToast({ title: '验证码已发送', icon: 'success' });
      this.startCooldown(60);
      logger.info('SMS code sent');
    } catch (error) {
      logger.error('Send SMS code failed', { error: error.message || String(error) });
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

  /** Handle change phone */
  async handleChangePhone() {
    try {
      const nextPhone = (this.data.newPhone || '').trim();

      // Validate input
      if (!nextPhone) {
        wx.showToast({
          title: '请输入新手机号',
          icon: 'none'
        });
        return;
      }

      if (this.data.smsCode.length !== 6) {
        wx.showToast({
          title: '请输入6位验证码',
          icon: 'none'
        });
        return;
      }

      this.setData({ saving: true });

      logger.info('Changing phone via profile detail');

      await put('/user/phone', {
        new_phone: `+86${nextPhone}`,
        sms_code: this.data.smsCode
      });

      wx.showToast({
        title: '修改成功',
        icon: 'success'
      });

      logger.info('Phone changed successfully');

      // Navigate back to profile detail page
      setTimeout(() => {
        wx.navigateBack();
      }, 1500);
    } catch (error) {
      logger.error('Change phone failed', {
        error: error.message || String(error)
      });

      wx.showToast({
        title: error.message || '修改失败，请稍后再试',
        icon: 'none'
      });
    } finally {
      this.setData({ saving: false });
    }
  }
});
