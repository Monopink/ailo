import { get, put, post } from '../../utils/api';
import { getLogger } from '../../utils/logger';

const logger = getLogger('PasswordManage');

Page({
  data: {
    loading: true,
    hasPassword: false,
    oldPassword: '',
    newPassword: '',
    confirmPassword: '',
    saving: false,
    // For reset password flow
    operationToken: '',
    isResetMode: false
  },

  onLoad(options) {
    const { operation_token, action } = options;

    if (operation_token && action === 'reset') {
      // Reset password mode
      this.setData({
        isResetMode: true,
        operationToken: operation_token,
        loading: false
      });

      wx.setNavigationBarTitle({
        title: '重置密码'
      });

      logger.info('Password manage page loaded (reset mode)');
    } else {
      // Change password mode
      logger.info('Password manage page loaded (change mode)');
      this.loadAccountInfo();
    }
  },

  /**
   * Load account information
   */
  async loadAccountInfo() {
    try {
      const account = await get('/user/account');

      this.setData({
        hasPassword: account.has_password,
        loading: false
      });

      logger.info('Account info loaded', { hasPassword: account.has_password });
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
   * Handle old password input
   */
  onOldPasswordInput(e) {
    this.setData({
      oldPassword: e.detail.value
    });
  },

  /**
   * Handle new password input
   */
  onNewPasswordInput(e) {
    this.setData({
      newPassword: e.detail.value
    });
  },

  /**
   * Handle confirm password input
   */
  onConfirmPasswordInput(e) {
    this.setData({
      confirmPassword: e.detail.value
    });
  },

  /**
   * Handle change password
   */
  async handleChangePassword() {
    try {
      // Validate input
      if (this.data.hasPassword && !this.data.oldPassword) {
        wx.showToast({
          title: '请输入当前密码',
          icon: 'none'
        });
        return;
      }

      if (!this.data.newPassword) {
        wx.showToast({
          title: '请输入新密码',
          icon: 'none'
        });
        return;
      }

      if (this.data.newPassword.length < 8) {
        wx.showToast({
          title: '密码至少8位',
          icon: 'none'
        });
        return;
      }

      if (this.data.newPassword !== this.data.confirmPassword) {
        wx.showToast({
          title: '两次密码不一致',
          icon: 'none'
        });
        return;
      }

      this.setData({ saving: true });

      logger.info('Changing password');

      // Call API
      await put('/user/password', {
        old_password: this.data.hasPassword ? this.data.oldPassword : null,
        new_password: this.data.newPassword
      });

      wx.showToast({
        title: this.data.hasPassword ? '密码修改成功' : '密码设置成功',
        icon: 'success'
      });

      logger.info('Password changed successfully');

      // Navigate back after a short delay
      setTimeout(() => {
        wx.navigateBack();
      }, 1500);
    } catch (error) {
      logger.error('Change password failed', {
        error: error.message || String(error)
      });

      wx.showToast({
        title: error.message || '操作失败,请稍后再试',
        icon: 'none'
      });

      this.setData({ saving: false });
    }
  },

  /**
   * Handle reset password
   */
  handleResetPassword() {
    // Navigate to verify page
    wx.navigateTo({
      url: '/pages/verify/verify?callback=/pages/password-manage/password-manage&action=reset'
    });
  },

  /**
   * Handle reset password with operation token
   */
  async handleResetPasswordWithToken() {
    try {
      // Validate input
      if (!this.data.newPassword) {
        wx.showToast({
          title: '请输入新密码',
          icon: 'none'
        });
        return;
      }

      if (this.data.newPassword.length < 8) {
        wx.showToast({
          title: '密码至少8位',
          icon: 'none'
        });
        return;
      }

      if (this.data.newPassword !== this.data.confirmPassword) {
        wx.showToast({
          title: '两次密码不一致',
          icon: 'none'
        });
        return;
      }

      this.setData({ saving: true });

      logger.info('Resetting password with operation token');

      // Call API
      await post('/user/password/reset', {
        operation_token: this.data.operationToken,
        new_password: this.data.newPassword
      });

      wx.showToast({
        title: '密码重置成功',
        icon: 'success'
      });

      logger.info('Password reset successfully');

      // Navigate back to account security page
      setTimeout(() => {
        wx.navigateBack({ delta: 2 }); // Go back 2 pages (verify + password-manage)
      }, 1500);
    } catch (error) {
      logger.error('Reset password failed', {
        error: error.message || String(error)
      });

      wx.showToast({
        title: error.message || '重置失败,请稍后再试',
        icon: 'none'
      });

      this.setData({ saving: false });
    }
  }
});

