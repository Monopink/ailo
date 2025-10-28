import { logout as authLogout } from '../../utils/auth';
import { getLogger } from '../../utils/logger';

const logger = getLogger('Settings');

Page({
  data: {},

  onLoad() {
    logger.info('Settings page loaded');
  },

  /**
   * Navigate to account security
   */
  navigateToAccountSecurity() {
    wx.navigateTo({
      url: '/pages/account-security/account-security'
    });
  },

  /**
   * Navigate to notifications settings
   */
  navigateToNotifications() {
    wx.showToast({
      title: '功能开发中',
      icon: 'none'
    });
  },

  /**
   * Handle logout
   */
  async handleLogout() {
    try {
      const result = await wx.showModal({
        title: '退出登录',
        content: '确定要退出登录吗?',
        confirmText: '退出',
        cancelText: '取消'
      });

      if (!result.confirm) {
        return;
      }

      logger.info('User logout initiated');

      // Show loading
      wx.showLoading({
        title: '退出中...',
        mask: true
      });

      // Call logout from auth utility
      await authLogout();

      wx.hideLoading();
    } catch (error) {
      wx.hideLoading();

      logger.error('Logout failed', {
        error: error.message || String(error)
      });

      wx.showToast({
        title: '退出失败,请稍后再试',
        icon: 'none'
      });
    }
  }
});

