import authService from '../../utils/auth-service';
import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';

const logger = getLogger('Welcome');

interface SampleContact {
  qiao_id: string;
  nickname: string;
  avatar: string;
  bio: string;
}

interface WelcomePageData {
  sampleContacts: SampleContact[];
}

interface WelcomePageCustom {
  handleStartUse(): void;
}

const SAMPLE_CONTACTS: SampleContact[] = [
  {
    qiao_id: 'sample_1',
    nickname: '小敲',
    avatar: getAvatarUrl('avatar_1.png'),
    bio: '温暖的AI伙伴,喜欢倾听你的故事',
  },
  {
    qiao_id: 'sample_2',
    nickname: '阿暖',
    avatar: getAvatarUrl('avatar_2.png'),
    bio: '想和你一起分享生活的点滴',
  },
  {
    qiao_id: 'sample_3',
    nickname: '倾听者',
    avatar: getAvatarUrl('avatar_3.png'),
    bio: '无论什么烦恼,我都愿意倾听',
  },
  {
    qiao_id: 'sample_4',
    nickname: '小闺蜜',
    avatar: getAvatarUrl('avatar_4.png'),
    bio: '一起逛街、聊八卦、分享秘密',
  },
  {
    qiao_id: 'sample_5',
    nickname: '游戏达人',
    avatar: getAvatarUrl('avatar_5.png'),
    bio: '一起开黑吗?我可是王者段位',
  },
];

Page<WelcomePageData, WelcomePageCustom>({
  data: {
    sampleContacts: SAMPLE_CONTACTS,
  },

  async onLoad() {
    logger.info('Welcome page loaded');

    try {
      const isAuthenticated = await authService.waitForInit();
      if (isAuthenticated) {
        logger.info('User already authenticated, redirecting to chat');
        void wx.switchTab({ url: '/pages/index/index' });
      }
    } catch (error) {
      logger.error('Auth check failed', { error });
    }
  },

  handleStartUse() {
    logger.info('User clicked start use button');
    void wx.navigateTo({
      url: '/pages/login/login',
    });
  },
});
