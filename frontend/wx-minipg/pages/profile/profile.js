import { get } from '../../utils/api';
import { requireAuthForPage } from '../../utils/auth-guard';
import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';

const logger = getLogger('Profile');

Page({
  data: {
    loading: true,
    profile: null,
    error: null
  },

  onLoad() {
    logger.info('Profile page loaded');

    // Require authentication
    if (!requireAuthForPage(this)) {
      return;
    }

    this.loadProfile();
  },

  onShow() {
    // Check auth status
    if (!requireAuthForPage(this)) {
      return;
    }

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
   * Navigate to contacts
   */
  navigateToContacts() {
    wx.navigateTo({
      url: '/pages/contacts-list/contacts-list'
    });
  },

  /**
   * Navigate to settings
   */
  navigateToSettings() {
    wx.navigateTo({
      url: '/pages/settings/settings'
    });
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

