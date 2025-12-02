import { get } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';
import { promptContactRequestMessage, sendContactRequest } from '../../utils/contact-request';

const logger = getLogger('StrangerInfo');

const GENDER_SYMBOL_MAP = {
  1: '♂',
  2: '♀',
  3: '⚧',
  4: '',
} as const;

const CATEGORY_TEXT_MAP = {
  '1': '交友',
  '2': '恋爱',
  '3': '倾诉',
  '4': '闺蜜',
  '5': '同好',
} as const;

type GenderKey = keyof typeof GENDER_SYMBOL_MAP;
type CategoryKey = keyof typeof CATEGORY_TEXT_MAP;

interface StrangerProfileResponse {
  qiao_id: string;
  nickname?: string;
  avatar_url?: string;
  gender?: number;
  category?: string;
  bio?: string;
  [key: string]: unknown;
}

interface StrangerProfileView extends StrangerProfileResponse {
  avatarUrl: string;
  genderText: string;
  categoryText: string;
}

interface StrangerInfoPageData {
  qiaoId: string;
  profile: StrangerProfileView | null;
  loading: boolean;
  isLoggedIn: boolean;
}

interface StrangerInfoPageCustom {
  loadProfile(): Promise<void>;
  handleAddContact(): Promise<void>;
  sendContactRequest(message: string): Promise<void>;
}

interface ApiError {
  statusCode?: number;
  data?: {
    detail?: string;
    [key: string]: unknown;
  };
  message?: string;
}

const isApiError = (error: unknown): error is ApiError =>
  Boolean(error) && typeof error === 'object';

const getGenderText = (gender?: number): string => {
  if (typeof gender === 'number' && GENDER_SYMBOL_MAP[gender as GenderKey] !== undefined) {
    return GENDER_SYMBOL_MAP[gender as GenderKey];
  }
  return '';
};

const getCategoryText = (category?: string): string => {
  if (category && CATEGORY_TEXT_MAP[category as CategoryKey]) {
    return CATEGORY_TEXT_MAP[category as CategoryKey];
  }
  return '';
};

const normalizeProfile = (profile: StrangerProfileResponse): StrangerProfileView => ({
  ...profile,
  avatarUrl: getAvatarUrl(profile.avatar_url ?? ''),
  genderText: getGenderText(profile.gender),
  categoryText: getCategoryText(profile.category),
});

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (isApiError(error) && typeof error.data?.detail === 'string') {
    return error.data.detail;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
};

interface StrangerInfoLoadOptions extends Record<string, string | undefined> {
  id?: string;
}

Page<StrangerInfoPageData, StrangerInfoPageCustom>({
  data: {
    qiaoId: '',
    profile: null,
    loading: true,
    isLoggedIn: false,
  },

  async onLoad(options: StrangerInfoLoadOptions) {
    const qiaoId = options?.id;

    if (!qiaoId) {
      void wx.showToast({
        title: '参数错误',
        icon: 'none',
      });
      void wx.navigateBack();
      return;
    }

    const token = wx.getStorageSync<string | null>('auth_token');

    this.setData({
      qiaoId,
      isLoggedIn: Boolean(token),
    });

    await this.loadProfile();
  },

  async loadProfile() {
    try {
      this.setData({ loading: true });
      const profile = await get<StrangerProfileResponse>(`/discovery/profile/${this.data.qiaoId}`);

      this.setData({
        profile: normalizeProfile(profile),
        loading: false,
      });

      logger.info('Stranger profile loaded', { qiao_id: this.data.qiaoId });
    } catch (error) {
      logger.error('Failed to load stranger profile', { error });
      this.setData({ loading: false });

      void wx.showToast({
        title: getErrorMessage(error, '加载失败'),
        icon: 'none',
      });

      if (isApiError(error) && error.statusCode === 404) {
        setTimeout(() => {
          void wx.navigateBack();
        }, 1500);
      }
    }
  },

  async handleAddContact() {
    if (!this.data.isLoggedIn) {
      void wx.showModal({
        title: '提示',
        content: '请先登录',
        confirmText: '去登录',
        success: (res) => {
          if (res.confirm) {
            void wx.navigateTo({ url: '/pages/login/login' });
          }
        },
      });
      return;
    }

    const message = await promptContactRequestMessage();
    if (message === null) {
      return;
    }

    await this.sendContactRequest(message);
  },

  async sendContactRequest(message: string) {
    try {
      void wx.showLoading({ title: '发送中...' });

      await sendContactRequest({
        qiaoId: this.data.qiaoId,
        message,
      });

      void wx.hideLoading();
      void wx.showToast({
        title: '已发送',
        icon: 'success',
      });

      logger.info('Contact request sent', { qiao_id: this.data.qiaoId });

      setTimeout(() => {
        void wx.navigateBack();
      }, 1500);
    } catch (error) {
      void wx.hideLoading();
      logger.error('Failed to send contact request', { error });

      void wx.showToast({
        title: getErrorMessage(error, '发送失败'),
        icon: 'none',
      });
    }
  },
});
