import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { get } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';
import { promptContactRequestMessage, sendContactRequest } from '../../utils/contact-request';
import { isNonEmptyString } from '../../utils/guards';

const logger = getLogger('StrangerInfo');

const GENDER_SYMBOL_MAP: Record<number, string> = {
  1: '♂',
  2: '♀',
  3: '⚧',
};

const CATEGORY_TEXT_MAP: Record<string, string> = {
  '1': '交友',
  '2': '恋爱',
  '3': '倾诉',
  '4': '闺蜜',
  '5': '同好',
};

type GenderKey = keyof typeof GENDER_SYMBOL_MAP;
type CategoryKey = keyof typeof CATEGORY_TEXT_MAP;

const isGenderKey = (value: unknown): value is GenderKey =>
  typeof value === 'number' && value in GENDER_SYMBOL_MAP;

const isCategoryKey = (value: unknown): value is CategoryKey =>
  typeof value === 'string' && value in CATEGORY_TEXT_MAP;

interface StrangerProfileResponse {
  qiao_id: string;
  nickname?: string;
  avatar_url?: string;
  gender?: number;
  category?: string;
  bio?: string;
  region?: string;
}

interface StrangerProfileView {
  qiaoId: string;
  avatarUrl: string;
  displayName: string;
  gender: number;
  genderText: string;
  genderType: 'success' | 'danger' | 'default';
  categoryText: string;
  regionText: string;
  bioText: string;
}

interface StrangerInfoPageData {
  qiaoId: string;
  profile: StrangerProfileView | null;
  pageLayoutData: PageLayoutData;
  isLoggedIn: boolean;
}

interface StrangerInfoPageCustom {
  loadProfile(): Promise<void>;
  handleAddContact(): Promise<void>;
  sendContactRequest(message: string): Promise<void>;
  onRetry(): void;
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
  typeof error === 'object' && error !== null;

const getGenderText = (gender?: number): string => {
  if (!isGenderKey(gender)) {
    return '';
  }
  return GENDER_SYMBOL_MAP[gender];
};

const getCategoryText = (category?: string): string => {
  if (!isCategoryKey(category)) {
    return '';
  }
  return CATEGORY_TEXT_MAP[category];
};

const normalizeProfile = (profile: StrangerProfileResponse): StrangerProfileView => {
  const displayName = profile.nickname ?? '';
  const genderText = getGenderText(profile.gender);
  const resolvedGender = isGenderKey(profile.gender) ? profile.gender : 0;
  let genderType: 'success' | 'danger' | 'default' = 'default';
  if (resolvedGender === 1) {
    genderType = 'success';
  } else if (resolvedGender === 2) {
    genderType = 'danger';
  }
  return {
    qiaoId: profile.qiao_id,
    avatarUrl: getAvatarUrl(profile.avatar_url),
    displayName,
    gender: resolvedGender,
    genderText,
    genderType,
    categoryText: getCategoryText(profile.category),
    regionText: isNonEmptyString(profile.region) ? profile.region : '',
    bioText: isNonEmptyString(profile.bio) ? profile.bio : '',
  };
};

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (isApiError(error) && typeof error.data?.detail === 'string') {
    return error.data.detail;
  }
  if (error instanceof Error && isNonEmptyString(error.message)) {
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
    pageLayoutData: createPageLayoutData({
      isLoading: true,
      emptyMessage: '暂无用户信息',
      hasFooter: true,
    }),
    isLoggedIn: false,
  },

  async onLoad(options: StrangerInfoLoadOptions) {
    const qiaoId = options.id;

    if (!isNonEmptyString(qiaoId)) {
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
      this.setData({
        'pageLayoutData.isLoading': true,
        'pageLayoutData.hasError': false,
        'pageLayoutData.errorMessage': '',
      });
      const profile = await get<StrangerProfileResponse>(`/discovery/profile/${this.data.qiaoId}`);

      this.setData({
        profile: normalizeProfile(profile),
        'pageLayoutData.isLoading': false,
        'pageLayoutData.isEmpty': false,
      });

      logger.info('Stranger profile loaded', { qiao_id: this.data.qiaoId });
    } catch (error) {
      logger.error('Failed to load stranger profile', { error });
      this.setData({
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': getErrorMessage(error, '加载失败'),
      });

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
        content: '登录后才能发送联系人申请，是否前往登录？',
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

  onRetry() {
    void this.loadProfile();
  },
});
