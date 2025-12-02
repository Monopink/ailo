import { get } from '../../utils/api';
import { requireAuth } from '../../utils/auth-guard';
import authService from '../../utils/auth-service';
import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';

const logger = getLogger('Profile');

Page({
  data: {
    loading: true,
    profile: null,
    error: null
  },

  async onLoad() {
    logger.info('Profile page loaded');

    // Require authentication
    const isAuth = await requireAuth(this);
    if (!isAuth) return;

    this.loadProfile();
  },

  async onShow() {
    // Check auth status
    const isAuth = await requireAuth(this);
    if (!isAuth) return;

    // Reload profile when page shows
    this.loadProfile();
  },

  /**
   * Load user profile
   */
  async loadProfile() {
    try {
      this.setData({
        loading: true,
        error: null
      });

      logger.info('Loading user profile');
      const profile = await get('/user/profile');

      this.setData({
        profile: {
          ...profile,
          avatar_url: getAvatarUrl(profile.avatar_url)
        },
        loading: false
      });

      logger.info('Profile loaded', { qiao_id: profile.qiao_id });
    } catch (error) {
      logger.error('Load profile failed', {
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
   * Navigate to profile detail
   */
  navigateToProfileDetail() {
    wx.navigateTo({
      url: '/pages/profile-detail/profile-detail'
    });
  },

  /**
   * Handle logout action
   */
  async handleLogout() {
    try {
      const result = await wx.showModal({
        title: '退出登录',
        content: '确定要退出当前账号吗？',
        confirmText: '退出',
        cancelText: '取消'
      });

      if (!result.confirm) {
        return;
      }

      wx.showLoading({
        title: '正在退出',
        mask: true
      });

      // Logout using authService
      await authService.logout();

      // Disconnect message service
      const app = getApp();
      if (app.globalData.messageService) {
        app.globalData.messageService.disconnect();
        app.globalData.messageService = null;
      }

      wx.hideLoading();

      // Redirect to login page
      wx.reLaunch({
        url: '/pages/login/login'
      });
    } catch (error) {
      logger.error('Logout failed', {
        error: error.message || String(error)
      });

      wx.hideLoading();

      wx.showToast({
        title: '退出失败，请稍后重试',
        icon: 'none'
      });
    }
  },

  /**
   * Get gender text
   */
  getGenderText(gender) {
    const genderMap = {
      1: '男',
      2: '女',
      3: '其他',
      4: '未知'
    };
    return genderMap[gender] || '未设置';
  }
});
