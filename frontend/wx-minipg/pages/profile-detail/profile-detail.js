import { get } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';

const logger = getLogger('ProfileDetail');

Page({
  data: {
    loading: true,
    profile: null,
    error: null,
    genderText: '未设置'
  },

  onLoad() {
    logger.info('Profile detail page loaded');
    this.loadProfile();
  },

  onShow() {
    // Reload profile when page shows (in case it was edited)
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

      // Get gender text
      const genderText = this.getGenderText(profile.gender);

      this.setData({
        profile: {
          ...profile,
          avatar_url: getAvatarUrl(profile.avatar_url)
        },
        genderText,
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
   * Edit avatar
   */
  editAvatar() {
    const currentAvatar = this.data.profile.avatar_url || '';
    // Extract original avatar URL (remove local path conversion)
    let avatarParam = '';
    if (currentAvatar.startsWith('/assets/avatars/')) {
      const filename = currentAvatar.replace('/assets/avatars/', '').replace('.jpg', '').replace('.png', '');
      if (filename !== 'default') {
        avatarParam = `assets://${filename}`;
      }
    } else if (currentAvatar.startsWith('http')) {
      avatarParam = currentAvatar;
    }

    wx.navigateTo({
      url: `/pages/avatar-selector/avatar-selector?avatar=${encodeURIComponent(avatarParam)}`
    });
  },

  /**
   * Edit nickname
   */
  editNickname() {
    wx.navigateTo({
      url: `/pages/profile-edit/profile-edit?field=nickname&value=${encodeURIComponent(this.data.profile.nickname || '')}`
    });
  },

  /**
   * Edit username
   */
  editUsername() {
    wx.navigateTo({
      url: `/pages/profile-edit/profile-edit?field=username&value=${encodeURIComponent(this.data.profile.username)}`
    });
  },

  /**
   * Edit gender
   */
  editGender() {
    wx.navigateTo({
      url: `/pages/profile-edit/profile-edit?field=gender&value=${this.data.profile.gender || ''}`
    });
  },

  /**
   * Edit region
   */
  editRegion() {
    wx.navigateTo({
      url: `/pages/profile-edit/profile-edit?field=region&value=${encodeURIComponent(this.data.profile.region || '')}`
    });
  },

  /**
   * Edit bio
   */
  editBio() {
    wx.navigateTo({
      url: `/pages/profile-edit/profile-edit?field=bio&value=${encodeURIComponent(this.data.profile.bio || '')}`
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

