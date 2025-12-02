import { put } from '../../utils/api';
import { getLogger } from '../../utils/logger';

const logger = getLogger('AvatarSelector');

Page({
  data: {
    loading: true,
    presetAvatars: [],
    currentAvatar: '',
    selectedAvatar: '',
    error: null
  },

  onLoad(options) {
    logger.info('Avatar selector page loaded');

    // Get current avatar from options
    const currentAvatar = options.avatar || '';
    this.setData({ currentAvatar });

    this.loadPresetAvatars();
  },

  /**
   * Load preset avatars
   */
  loadPresetAvatars() {
    logger.info('Loading preset avatars');

    // Local preset avatars
    const presetAvatarIds = ['1574', '2454', '3758'];

    const avatars = presetAvatarIds.map(id => ({
      id: `assets://${id}`,
      url: `/assets/avatars/${id}.jpg`,
      name: id
    }));

    this.setData({
      presetAvatars: avatars,
      loading: false
    });

    logger.info('Preset avatars loaded', { count: avatars.length });
  },

  /**
   * Select avatar
   */
  selectAvatar(e) {
    const avatarId = e.currentTarget.dataset.id;
    logger.info('Avatar selected', { avatarId });

    this.setData({ selectedAvatar: avatarId });
  },

  /**
   * Confirm selection
   */
  async confirmSelection() {
    if (!this.data.selectedAvatar) {
      wx.showToast({
        title: '请选择头像',
        icon: 'none'
      });
      return;
    }

    try {
      logger.info('Updating avatar', { avatar: this.data.selectedAvatar });

      await put('/user/profile', {
        avatar_url: this.data.selectedAvatar
      });

      wx.showToast({
        title: '头像已更新',
        icon: 'success'
      });

      // Navigate back after short delay
      setTimeout(() => {
        wx.navigateBack();
      }, 1000);
    } catch (error) {
      logger.error('Update avatar failed', {
        error: error.message || String(error)
      });

      wx.showToast({
        title: '更新失败',
        icon: 'none'
      });
    }
  },

  /**
   * Cancel selection
   */
  cancel() {
    wx.navigateBack();
  }
});

