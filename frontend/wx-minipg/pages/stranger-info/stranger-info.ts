import { get, post } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import logger from '../../utils/logger';

Page({
  data: {
    qiaoId: '',
    profile: null,
    loading: true,
    isLoggedIn: false
  },

  async onLoad(options) {
    const qiaoId = options.id;

    if (!qiaoId) {
      wx.showToast({
        title: '参数错误',
        icon: 'none'
      });
      wx.navigateBack();
      return;
    }

    // Check login status
    const token = wx.getStorageSync('auth_token');

    this.setData({
      qiaoId,
      isLoggedIn: !!token
    });

    // Load stranger profile
    await this.loadProfile();
  },

  async loadProfile() {
    try {
      this.setData({ loading: true });

      // Fetch stranger profile (no authentication required)
      const profile = await get(`/discovery/profile/${this.data.qiaoId}`);

      this.setData({
        profile: {
          ...profile,
          avatarUrl: getAvatarUrl(profile.avatar_url),
          genderText: this.getGenderText(profile.gender),
          categoryText: this.getCategoryText(profile.category)
        },
        loading: false
      });

      logger.info('Stranger profile loaded', { qiao_id: this.data.qiaoId });
    } catch (error) {
      logger.error('Failed to load stranger profile', { error });
      this.setData({ loading: false });

      wx.showToast({
        title: error.data?.detail || '加载失败',
        icon: 'none'
      });

      // Navigate back if profile not found
      if (error.statusCode === 404) {
        setTimeout(() => {
          wx.navigateBack();
        }, 1500);
      }
    }
  },

  async handleAddContact() {
    // Check login status
    if (!this.data.isLoggedIn) {
      wx.showModal({
        title: '提示',
        content: '请先登录',
        confirmText: '去登录',
        success: (res) => {
          if (res.confirm) {
            wx.navigateTo({ url: '/pages/login/login' });
          }
        }
      });
      return;
    }

    // Show input dialog for request message
    wx.showModal({
      title: '添加联系人',
      content: '请输入验证消息',
      editable: true,
      placeholderText: '我是...',
      success: async (res) => {
        if (res.confirm) {
          await this.sendContactRequest(res.content || '');
        }
      }
    });
  },

  async sendContactRequest(message) {
    try {
      wx.showLoading({ title: '发送中...' });

      await post('/contact-requests', {
        to_qiao_id: this.data.qiaoId,
        message: message
      });

      wx.hideLoading();
      wx.showToast({
        title: '已发送',
        icon: 'success'
      });

      logger.info('Contact request sent', { qiao_id: this.data.qiaoId });

      // Navigate back after success
      setTimeout(() => {
        wx.navigateBack();
      }, 1500);
    } catch (error) {
      wx.hideLoading();
      logger.error('Failed to send contact request', { error });

      wx.showToast({
        title: error.data?.detail || '发送失败',
        icon: 'none'
      });
    }
  },

  getGenderText(gender) {
    const genderMap = {
      1: '♂',
      2: '♀',
      3: '⚧',
      4: ''
    };
    return genderMap[gender] || '';
  },

  getCategoryText(category) {
    const categoryMap = {
      '1': '交友',
      '2': '恋爱',
      '3': '倾诉',
      '4': '闺蜜',
      '5': '同好'
    };
    return categoryMap[category] || '';
  }
});
