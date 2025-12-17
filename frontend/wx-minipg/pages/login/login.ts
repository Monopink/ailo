import { post } from '../../utils/api';
import authService from '../../utils/auth-service';
import { getAvatarUrl } from '../../utils/avatar';
import { fetchAllContactsFromApi } from '../../utils/contact-sync';
import { getLogger } from '../../utils/logger';
import { saveContacts, type StoredAuthUser } from '../../utils/storage';
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

interface AuthUserResponse extends StoredAuthUser {
  token: string;
}

interface WechatLoginResponse {
  success: boolean;
  needs_phone_binding?: boolean;
  wechat_code?: string;
  message?: string;
  user: AuthUserResponse;
}

interface LoginPageData {
  pageLayoutData: PageLayoutData;
  sampleContacts: SampleContact[];
  featureList: LoginFeature[];
  wechatLoading: boolean;
  loginCode: string;
}

interface LoginPageCustom {
  handleWeChatLogin(event: WechatMiniprogram.ButtonGetPhoneNumber): Promise<void>;
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

const loadContacts = async (): Promise<void> => {
  try {
    const remoteContacts = await fetchAllContactsFromApi();
    const contacts = await saveContacts(remoteContacts);
    logger.info('Contacts loaded and saved', { count: contacts.length });
  } catch (error) {
    logger.error('Failed to load contacts', { error });
  }
};

const initMessaging = async (): Promise<void> => {
  const app = getApp<AppInstance>();
  await app.initMessageService();
};

Page<LoginPageData, LoginPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      hasFooter: false,
    }),
    sampleContacts: SAMPLE_CONTACTS,
    featureList: FEATURE_LIST,
    wechatLoading: false,
    loginCode: '',
  },

  async onLoad() {
    logger.info('Login page loaded');

    try {
      const isAuthenticated = await authService.waitForInit();
      if (isAuthenticated) {
        logger.info('User already authenticated, redirecting to chat');
        void wx.switchTab({ url: '/pages/index/index' });
        return;
      }

      // Silently obtain login_code when page loads (valid for 5 minutes)
      const { code } = await wx.login();
      if (code) {
        this.setData({ loginCode: code });
        logger.info('Login code obtained silently', { code });
      } else {
        logger.warn('Failed to obtain login code on page load');
      }
    } catch (error) {
      logger.error('Auth check or login code fetch failed', { error });
    }
  },

  onRetry() {
    this.setData({
      'pageLayoutData.hasError': false,
    });
  },

  async handleWeChatLogin(event) {
    // Check if user authorized phone number
    if (event.detail.errMsg !== 'getPhoneNumber:ok') {
      logger.warn('WeChat phone authorization failed, fallback to phone binding', {
        errMsg: event.detail.errMsg,
      });

      // Fallback to phone binding without wechat_code
      // User will need to use SMS verification to complete login
      void wx.navigateTo({
        url: '/pages/phone-bind/phone-bind',
      });

      // Show toast after navigation starts (brief, user-friendly message)
      setTimeout(() => {
        showToast('请使用手机号完成登录', 'none');
      }, 100);
      return;
    }

    const phoneCode = event.detail.code;
    logger.info('Got phone code from WeChat', { phoneCode });

    try {
      this.setData({ wechatLoading: true });

      // Use pre-fetched login_code
      const loginCode = this.data.loginCode;
      if (!loginCode) {
        throw new Error('Login code not available, please try again');
      }

      logger.info('Using pre-fetched login code', { loginCode });

      // Call backend WeChat login API
      const result = await post<WechatLoginResponse>(
        '/auth/wechat/login',
        {
          login_code: loginCode,
          phone_code: phoneCode,
        },
        { auth: false }
      );

      // Check if phone binding is needed (international phone)
      if (!result.success && result.needs_phone_binding) {
        logger.info('International phone detected, navigate to phone-bind', {
          wechat_code: result.wechat_code,
        });
        this.setData({ wechatLoading: false });
        void wx.navigateTo({
          url: `/pages/phone-bind/phone-bind?wechat_code=${result.wechat_code}`,
        });
        return;
      }

      // Login successful
      await authService.login(result.user.token, result.user);
      logger.info('WeChat login success', { user: result.user });

      this.setData({ wechatLoading: false });

      // Check if user needs to complete profile setup
      if (!result.user.nickname) {
        void wx.redirectTo({ url: '/pages/setup/setup' });
        return;
      }

      // Load contacts and init messaging
      await loadContacts();
      await initMessaging();
      void wx.switchTab({ url: '/pages/index/index' });
    } catch (error) {
      logger.error('WeChat login failed', { error });
      this.setData({ wechatLoading: false });

      // Show user-friendly error message (no technical details)
      showToast('登录失败，请重试', 'none');
    }
  },

  handlePhoneLogin() {
    logger.info('User clicked phone login button');
    void wx.navigateTo({
      url: '/pages/phone-login/phone-login',
    });
  },
});
