import { get, post } from '../../utils/api';
import { getCachedCaptchaConfig, ensureCaptchaConfig, initCaptcha, showCaptcha } from '../../utils/captcha';
import { checkStorage } from '../../utils/debug';
import logger from '../../utils/logger';
import { saveContacts, saveUserInfo } from '../../utils/storage';

Page({
  data: {
    showPhoneButton: false,
    showPhoneBind: false,
    showCaptcha: false, // legacy turnstile flag (no longer used)
    loadCaptcha: false, // Aliyun plugin flag
    pluginProps: {},    // Aliyun plugin props
    loginCode: '',
    wechatCode: '',  // For phone binding
    phone: '',
    smsCode: '',
    countdown: 0,
    wechatLoading: false,
    phoneLoading: false,
    bindLoading: false,
    captchaToken: null,
    turnstileSiteKey: '', // legacy
    captchaSceneId: ''
  },

  onLoad(options) {
    logger.info('Login page loaded');
    this._captchaActive = false;
    (async () => {
      try {
        const cached = getCachedCaptchaConfig();
        const cfg = cached || await ensureCaptchaConfig();
        initCaptcha(this, cfg, {
          success: (token) => this.onCaptchaSuccess(token),
          fail: (err) => this.onCaptchaFail(err)
        });
      } catch (_) {
        // ignore
      }
    })();
  },

  onCaptchaSuccess(captchaVerifyParam) {
    // Mark inactive and proceed
    this._captchaActive = false;
    this.setData({ loadCaptcha: true }); // keep mounted for future shows
    return this.requestSmsWithCaptcha(captchaVerifyParam);
  },

  onCaptchaFail(error) {
    logger.error('Aliyun captcha failed', { error });
    // Only toast when user explicitly triggered captcha
    if (this._captchaActive) {
      wx.showToast({ title: '验证服务错误，请稍后再试', icon: 'none' });
    }
    this._captchaActive = false;
  },

  async handleWeChatLogin() {
    try {
      this.setData({ wechatLoading: true });

      const res = await wx.login();
      if (res.code) {
        this.setData({
          loginCode: res.code,
          showPhoneButton: true,
          wechatLoading: false
        });
        logger.info('WeChat login success', { code: res.code });
      } else {
        throw new Error('Failed to get login code');
      }
    } catch (error) {
      logger.error('WeChat login failed', { error });
      this.setData({ wechatLoading: false });
      wx.showToast({
        title: '微信登录失败',
        icon: 'none'
      });
    }
  },

  handlePhoneLogin() {
    logger.info('User clicked phone login button');

    // Show phone input interface for direct phone login
    this.setData({
      showPhoneBind: true,
      wechatCode: ''  // No wechat_code for pure phone login
    });
  },

  async handleGetPhoneNumber(e) {
    if (e.detail.errMsg !== 'getPhoneNumber:ok') {
      logger.warn('User denied phone authorization');
      this.setData({ showPhoneBind: true });
      return;
    }

    const phoneCode = e.detail.code;
    logger.info('Got phone code', { phoneCode });

    try {
      this.setData({ phoneLoading: true });

      const result = await post('/auth/wechat/login', {
        login_code: this.data.loginCode,
        phone_code: phoneCode
      }, { auth: false });

      // Check if phone binding is needed
      if (!result.success && result.needs_phone_binding) {
        // Save wechat_code for phone binding
        this.setData({
          showPhoneBind: true,
          wechatCode: result.wechat_code,
          phoneLoading: false
        });
        wx.showToast({
          title: result.message || '请绑定手机号',
          icon: 'none'
        });
        logger.info('Phone binding required', { wechat_code: result.wechat_code });
        return;
      }

      // Login success
      wx.setStorageSync('auth_token', result.user.token);
      await saveUserInfo(result.user);

      logger.info('Login success', { user: result.user });

      // Update app auth status
      const app = getApp();
      app.globalData.isAuthenticated = true;

      // Mark that user has seen welcome
      wx.setStorageSync('hasSeenWelcome', true);

      this.setData({ phoneLoading: false });

      if (!result.user.nickname) {
        wx.redirectTo({ url: '/pages/setup/setup' });
      } else {
        // Fetch and save contacts list
        try {
          const contacts = await get('/contacts');
          await saveContacts(contacts);
          logger.info('Contacts loaded and saved', { count: contacts.length });
        } catch (error) {
          logger.error('Failed to load contacts', { error });
        }

        // Initialize message service
        await app.initMessageService();

        // Redirect to square page
        wx.switchTab({ url: '/pages/index/index' });
      }
    } catch (error) {
      logger.error('Login failed', { error });
      this.setData({ phoneLoading: false });
      wx.showToast({
        title: error.message || '登录失败',
        icon: 'none'
      });
    }
  },

  onPhoneInput(e) {
    this.setData({ phone: e.detail.value });
  },

  onSmsCodeInput(e) {
    this.setData({ smsCode: e.detail.value });
  },

  async sendSmsCode() {
    if (!this.data.phone || this.data.phone.length !== 11) {
      wx.showToast({
        title: '请输入正确的手机号',
        icon: 'none'
      });
      return;
    }
    // First try sending without captcha_token; backend will return 428 when captcha is required
    try {
      await post('/auth/send-sms', {
        phone: `+86${this.data.phone}`
      }, { auth: false });

      // Start local countdown (60s default)
      this.setData({ countdown: 60 });
      const timer = setInterval(() => {
        const countdown = this.data.countdown - 1;
        if (countdown <= 0) {
          clearInterval(timer);
          this.setData({ countdown: 0 });
        } else {
          this.setData({ countdown });
        }
      }, 1000);

      wx.showToast({ title: '验证码已发送', icon: 'success' });
      return;
    } catch (error) {
      // If backend demands captcha, trigger plugin then retry with token
      const status = Number(error?.statusCode || error?.status || 0);
      const code = error?.errorCode || error?.data?.detail?.error || error?.data?.error || error?.data?.code;
      const needCaptcha = (status === 428) || (code === 'CAPTCHA_REQUIRED');
      if (!needCaptcha) {
        if (error.statusCode === 429) {
          wx.showToast({ title: error.message || '发送过于频繁，请稍后再试', icon: 'none' });
        } else {
          wx.showToast({ title: error.message || '发送失败', icon: 'none' });
        }
        return;
      }
    }

    // Show Aliyun captcha and retry after success
    this._captchaActive = true;
    showCaptcha(this);
  },

  // Legacy Turnstile callbacks removed

  async requestSmsWithCaptcha(captchaToken) {
    try {
      const res = await post('/auth/send-sms', {
        phone: `+86${this.data.phone}`,
        // Reuse field name to keep API shape; backend Aliyun provider will consume it
        captcha_token: captchaToken
      }, { auth: false });

      // Start local countdown (60s default)
      this.setData({ countdown: 60 });
      const timer = setInterval(() => {
        const countdown = this.data.countdown - 1;
        if (countdown <= 0) {
          clearInterval(timer);
          this.setData({ countdown: 0 });
        } else {
          this.setData({ countdown });
        }
      }, 1000);

      wx.showToast({ title: '验证码已发送', icon: 'success' });
    } catch (error) {
      logger.error('Send SMS failed', { error });
      wx.showToast({ title: error.message || '发送失败', icon: 'none' });
    }
  },

  async handleBindPhone() {
    if (!this.data.phone || this.data.phone.length !== 11) {
      wx.showToast({
        title: '请输入正确的手机号',
        icon: 'none'
      });
      return;
    }

    if (!this.data.smsCode || this.data.smsCode.length !== 6) {
      wx.showToast({
        title: '请输入验证码',
        icon: 'none'
      });
      return;
    }

    try {
      this.setData({ bindLoading: true });

      // Use unified phone verification API
      const result = await post('/auth/phone', {
        phone: `+86${this.data.phone}`,
        sms_code: this.data.smsCode,
        wechat_code: this.data.wechatCode || undefined  // Optional WeChat code
      }, { auth: false });

      if (result.is_new_user) {
        // New user - save temporary token and redirect to profile setup
        wx.setStorageSync('verified_phone_token', result.verified_phone_token);
        wx.setStorageSync('verified_phone', result.phone);

        logger.info('New user, redirect to profile setup', { phone: result.phone });

        this.setData({ bindLoading: false });
        wx.redirectTo({ url: '/pages/setup/setup' });
      } else {
        // Existing user - save token and user info, redirect to chat list
        logger.info('Saving token and user info', { qiao_id: result.user.qiao_id });

        wx.setStorageSync('auth_token', result.token);
        await saveUserInfo(result.user);

        // Update global data
        const app = getApp();
        app.setToken(result.token);
        app.setUserInfo(result.user);
        app.globalData.isAuthenticated = true;

        // Mark that user has seen welcome
        wx.setStorageSync('hasSeenWelcome', true);

        logger.info('Existing user login success', { qiao_id: result.user.qiao_id });

        // Debug: check storage after save
        logger.info('=== After Login Debug ===');
        checkStorage();
        logger.info('========================');

        this.setData({ bindLoading: false });

        // Fetch and save contacts list
        try {
          const contacts = await get('/contacts');
          await saveContacts(contacts);
          logger.info('Contacts loaded and saved', { count: contacts.length });
        } catch (error) {
          logger.error('Failed to load contacts', { error });
        }

        // Initialize message service
        await app.initMessageService();

        // Redirect to square page
        wx.switchTab({ url: '/pages/index/index' });
      }
    } catch (error) {
      logger.error('Phone verification failed', { error });
      this.setData({ bindLoading: false });
      wx.showToast({
        title: error.message || '验证失败',
        icon: 'none'
      });
    }
  }
});



