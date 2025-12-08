import authService from '../../utils/auth-service';
import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';

const logger = getLogger('Login');

interface SampleContact {
  qiao_id: string;
  nickname: string;
  avatar: string;
  bio: string;
}

interface LoginFeature {
  id: string;
  title: string;
  description: string;
}

interface LoginPageData {
  pageLayoutData: PageLayoutData;
  sampleContacts: SampleContact[];
  featureList: LoginFeature[];
  wechatLoading: boolean;
}

interface LoginPageCustom {
  handleWeChatLogin(): Promise<void>;
  handlePhoneLogin(): void;
  onRetry(): void;
}

const FEATURE_LIST: LoginFeature[] = [
  {
    id: 'chat',
    title: '智能对话',
    description: '保持真人聊天的语气与节奏，随时陪伴',
  },
  {
    id: 'emotion',
    title: '情感共鸣',
    description: '更懂情绪的 AI 伙伴，持续回应你的感受',
  },
  {
    id: 'roles',
    title: '多元角色',
    description: '学生、同事、恋人…快速切换最契合的角色',
  },
];

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

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
};

Page<LoginPageData, LoginPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      hasFooter: false,
    }),
    sampleContacts: SAMPLE_CONTACTS,
    featureList: FEATURE_LIST,
    wechatLoading: false,
  },

  async onLoad() {
    logger.info('Login page loaded');

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

  onRetry() {
    this.setData({
      'pageLayoutData.hasError': false,
    });
  },

  async handleWeChatLogin() {
    try {
      this.setData({ wechatLoading: true });
      const { code } = await wx.login();
      if (!code) {
        throw new Error('Failed to obtain login code');
      }

      logger.info('WeChat login code obtained', { code });

      // Navigate to phone-bind page with WeChat code
      void wx.navigateTo({
        url: `/pages/phone-bind/phone-bind?wechat_code=${code}`,
      });

      this.setData({ wechatLoading: false });
    } catch (error) {
      logger.error('WeChat login failed', { error });
      this.setData({ wechatLoading: false });
      showToast('微信登录失败');
    }
  },

  handlePhoneLogin() {
    logger.info('User clicked phone login button');
    void wx.navigateTo({
      url: '/pages/phone-login/phone-login',
    });
  },
});
