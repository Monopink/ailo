import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';

const logger = getLogger('Welcome');

// Sample contacts for preview
const SAMPLE_CONTACTS = [
  {
    qiao_id: 'sample_1',
    nickname: '小敲',
    avatar: getAvatarUrl('avatar_1.png'),
    bio: '温暖的AI伙伴,喜欢倾听你的故事'
  },
  {
    qiao_id: 'sample_2',
    nickname: '阿暖',
    avatar: getAvatarUrl('avatar_2.png'),
    bio: '想和你一起分享生活的点滴'
  },
  {
    qiao_id: 'sample_3',
    nickname: '倾听者',
    avatar: getAvatarUrl('avatar_3.png'),
    bio: '无论什么烦恼,我都愿意倾听'
  },
  {
    qiao_id: 'sample_4',
    nickname: '小闺蜜',
    avatar: getAvatarUrl('avatar_4.png'),
    bio: '一起逛街、聊八卦、分享秘密'
  },
  {
    qiao_id: 'sample_5',
    nickname: '游戏达人',
    avatar: getAvatarUrl('avatar_5.png'),
    bio: '一起开黑吗?我可是王者段位'
  }
];

Page({
  data: {
    sampleContacts: SAMPLE_CONTACTS
  },

  onLoad() {
    logger.info('Welcome page loaded');

    // Fast-path: if token exists in storage, go to chat tab to避免闪屏
    try {
      const token = wx.getStorageSync('auth_token');
      if (token) {
        logger.info('Token present in storage, redirecting to chat');
        wx.switchTab({ url: '/pages/index/index' });
        return;
      }
    } catch (_) {}

    // Check if user is already logged in (global state)
    const app = getApp();
    if (app.globalData.isAuthenticated) {
      logger.info('User already logged in, redirecting to chat');
      wx.switchTab({ url: '/pages/index/index' });
    }
  },

  /**
   * Handle "Start Use" button click
   * Navigate to login page
   */
  handleStartUse() {
    logger.info('User clicked start use button');
    wx.navigateTo({
      url: '/pages/login/login'
    });
  }
});
