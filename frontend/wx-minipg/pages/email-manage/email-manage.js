import { get, post, put, del } from '../../utils/api';
import { getLogger } from '../../utils/logger';

const logger = getLogger('EmailManage');

Page({
  data: {
    loading: true,
    hasEmail: false,
    currentEmail: '',
    newEmail: '',
    emailCode: '',
    cooldown: 0,
    sending: false,
    saving: false,
    // For change/unbind flow
    operationToken: '',
    action: '' // 'change' or 'unbind'
  },

  onLoad(options) {
    const { operation_token, action } = options;

    if (operation_token) {
      // Change or unbind mode
      this.setData({
        operationToken: operation_token,
        action: action || ''
      });

      if (action === 'change') {
        wx.setNavigationBarTitle({
          title: '修改邮箱'
        });
      } else if (action === 'unbind') {
        wx.setNavigationBarTitle({
          title: '解绑邮箱'
        });
      }
    }

    logger.info('Email manage page loaded', { action });

    this.loadAccountInfo();
  },

  /**
   * Load account information
   */
  async loadAccountInfo() {
    try {
      const account = await get('/user/account');

      this.setData({
        hasEmail: !!account.email,
        currentEmail: account.email || '',
        loading: false
      });

      logger.info('Account info loaded', { hasEmail: !!account.email });

      // If in unbind mode, show confirmation
      if (this.data.action === 'unbind') {
        this.showUnbindConfirmation();
      }
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

  /**
   * Handle new email input
   */
  onNewEmailInput(e) {
    this.setData({
      newEmail: e.detail.value
    });
  },

  /**
   * Handle email code input
   */
  onEmailCodeInput(e) {
    this.setData({
      emailCode: e.detail.value
    });
  },

  /**
   * Send email code
   */
  async sendEmailCode() {
    try {
      // Validate email
      const email = this.data.action === 'change' ? this.data.newEmail : this.data.newEmail;
      if (!email) {
        wx.showToast({
          title: '请输入邮箱地址',
          icon: 'none'
        });
        return;
      }

      // Simple email validation
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        wx.showToast({
          title: '邮箱格式不正确',
          icon: 'none'
        });
        return;
      }

      this.setData({ sending: true });

      logger.info('Sending email code', { email });

      const response = await post('/user/email/send-code', {
        email: email
      });

      wx.showToast({
        title: '验证码已发送',
        icon: 'success'
      });

      // Start cooldown
      this.startCooldown(response.cooldown || 60);

      logger.info('Email code sent');
    } catch (error) {
      logger.error('Send email code failed', {
        error: error.message || String(error)
      });

      wx.showToast({
        title: error.message || '发送失败,请稍后再试',
        icon: 'none'
      });
    } finally {
      this.setData({ sending: false });
    }
  },

  /**
   * Start cooldown timer
   */
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

  /**
   * Handle bind email
   */
  async handleBindEmail() {
    try {
      // Validate input
      if (!this.data.newEmail) {
        wx.showToast({
          title: '请输入邮箱地址',
          icon: 'none'
        });
        return;
      }

      if (this.data.emailCode.length !== 6) {
        wx.showToast({
          title: '请输入6位验证码',
          icon: 'none'
        });
        return;
      }

      this.setData({ saving: true });

      logger.info('Binding email');

      await post('/user/email', {
        email: this.data.newEmail,
        code: this.data.emailCode
      });

      wx.showToast({
        title: '绑定成功',
        icon: 'success'
      });

      logger.info('Email bound successfully');

      // Navigate back after a short delay
      setTimeout(() => {
        wx.navigateBack();
      }, 1500);
    } catch (error) {
      logger.error('Bind email failed', {
        error: error.message || String(error)
      });

      wx.showToast({
        title: error.message || '绑定失败,请稍后再试',
        icon: 'none'
      });

      this.setData({ saving: false });
    }
  },

  /**
   * Handle change email
   */
  handleChangeEmail() {
    // Navigate to verify page
    wx.navigateTo({
      url: '/pages/verify/verify?callback=/pages/email-manage/email-manage&action=change'
    });
  },

  /**
   * Handle change email with operation token
   */
  async handleChangeEmailWithToken() {
    try {
      // Validate input
      if (!this.data.newEmail) {
        wx.showToast({
          title: '请输入新邮箱地址',
          icon: 'none'
        });
        return;
      }

      if (this.data.emailCode.length !== 6) {
        wx.showToast({
          title: '请输入6位验证码',
          icon: 'none'
        });
        return;
      }

      this.setData({ saving: true });

      logger.info('Changing email with operation token');

      await put('/user/email', {
        operation_token: this.data.operationToken,
        new_email: this.data.newEmail,
        email_code: this.data.emailCode
      });

      wx.showToast({
        title: '修改成功',
        icon: 'success'
      });

      logger.info('Email changed successfully');

      // Navigate back to account security page
      setTimeout(() => {
        wx.navigateBack({ delta: 2 }); // Go back 2 pages (verify + email-manage)
      }, 1500);
    } catch (error) {
      logger.error('Change email failed', {
        error: error.message || String(error)
      });

      wx.showToast({
        title: error.message || '修改失败,请稍后再试',
        icon: 'none'
      });

      this.setData({ saving: false });
    }
  },

  /**
   * Handle unbind email
   */
  handleUnbindEmail() {
    // Navigate to verify page
    wx.navigateTo({
      url: '/pages/verify/verify?callback=/pages/email-manage/email-manage&action=unbind'
    });
  },

  /**
   * Show unbind confirmation
   */
  showUnbindConfirmation() {
    wx.showModal({
      title: '确认解绑',
      content: `确定要解绑邮箱 ${this.data.currentEmail} 吗?`,
      confirmText: '确认解绑',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) {
          this.confirmUnbindEmail();
        } else {
          // User cancelled, go back
          wx.navigateBack();
        }
      }
    });
  },

  /**
   * Confirm unbind email with operation token
   */
  async confirmUnbindEmail() {
    try {
      this.setData({ saving: true });

      logger.info('Unbinding email with operation token');

      await del('/user/email', {
        operation_token: this.data.operationToken
      });

      wx.showToast({
        title: '解绑成功',
        icon: 'success'
      });

      logger.info('Email unbound successfully');

      // Navigate back to account security page
      setTimeout(() => {
        wx.navigateBack({ delta: 2 }); // Go back 2 pages (verify + email-manage)
      }, 1500);
    } catch (error) {
      logger.error('Unbind email failed', {
        error: error.message || String(error)
      });

      wx.showToast({
        title: error.message || '解绑失败,请稍后再试',
        icon: 'none'
      });

      this.setData({ saving: false });
    }
  }
});

