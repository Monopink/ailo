import { get } from '../../utils/api';
import { getLogger } from '../../utils/logger';

const logger = getLogger('AccountSecurity');

Page({
  data: {
    loading: true,
    account: null,
    error: null
  },

  onLoad() {
    logger.info('Account security page loaded');
    this.loadAccount();
  },

  onShow() {
    // Reload account when page shows (in case it was updated)
    this.loadAccount();
  },

  /**
   * Load user account information
   */
  async loadAccount() {
    try {
      this.setData({
        loading: true,
        error: null
      });

      logger.info('Loading user account');
      const account = await get('/user/account');

      this.setData({
        account,
        loading: false
      });

      logger.info('Account loaded', { qiao_id: account.qiao_id });
    } catch (error) {
      logger.error('Load account failed', {
        error: error.message || String(error)
      });

      this.setData({
        error: '加载失败,请稍后再试',
        loading: false
      });

      wx.showToast({
        title: '加载失败',
        icon: 'none'
      });
    }
  },

  /**
   * Manage phone number
   */
  managePhone() {
    // Navigate to verify page first
    wx.navigateTo({
      url: '/pages/verify/verify?callback=/pages/phone-manage/phone-manage'
    });
  },

  /**
   * Manage email
   */
  manageEmail() {
    wx.navigateTo({
      url: '/pages/email-manage/email-manage'
    });
  },

  /**
   * Manage password
   */
  managePassword() {
    wx.navigateTo({
      url: '/pages/password-manage/password-manage'
    });
  }
});