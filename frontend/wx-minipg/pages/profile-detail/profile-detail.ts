import { get } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';

const logger = getLogger('ProfileDetail');

const GENDER_TEXT_MAP = {
  1: '男',
  2: '女',
  3: '其他',
  4: '未知',
} as const;

type GenderCode = keyof typeof GENDER_TEXT_MAP;

interface UserProfile {
  qiao_id: string;
  nickname?: string;
  avatar_url?: string;
  username?: string;
  gender?: number;
  region?: string;
  bio?: string;
}

interface AccountInfo {
  phone?: string;
}

interface ProfileDetailPageData {
  loading: boolean;
  profile: UserProfile | null;
  phoneMasked: string;
  error: string | null;
  genderText: string;
}

interface ProfileDetailPageCustom {
  loadProfile(): Promise<void>;
  editPhone(): void;
  editAvatar(): void;
  editNickname(): void;
  editUsername(): void;
  editGender(): void;
  editRegion(): void;
  editBio(): void;
}

const normalizeGenderText = (gender?: number): string => {
  if (typeof gender === 'number' && GENDER_TEXT_MAP[gender as GenderCode]) {
    return GENDER_TEXT_MAP[gender as GenderCode];
  }
  return '未设置';
};

const buildAvatarParam = (avatarUrl: string | undefined): string => {
  if (!avatarUrl) {
    return '';
  }
  if (avatarUrl.startsWith('/assets/avatars/')) {
    const filename = avatarUrl
      .replace('/assets/avatars/', '')
      .replace('.jpg', '')
      .replace('.png', '');
    if (filename && filename !== 'default') {
      return `assets://${filename}`;
    }
    return '';
  }
  if (avatarUrl.startsWith('http')) {
    return avatarUrl;
  }
  return '';
};

const encodeValue = (value: string | undefined | null): string => encodeURIComponent(value ?? '');

Page<ProfileDetailPageData, ProfileDetailPageCustom>({
  data: {
    loading: true,
    profile: null,
    phoneMasked: '',
    error: null,
    genderText: '未设置',
  },

  onLoad() {
    logger.info('Profile detail page loaded');
    void this.loadProfile();
  },

  onShow() {
    void this.loadProfile();
  },

  async loadProfile() {
    try {
      this.setData({
        loading: true,
        error: null,
      });

      logger.info('Loading user profile');
      const profilePromise = get<UserProfile>('/user/profile');
      const accountPromise = get<AccountInfo>('/user/account').catch((error: unknown) => {
        logger.error('Load account info failed', {
          error: error instanceof Error ? error.message : String(error),
        });
        return null;
      });

      const [profile, account] = await Promise.all([profilePromise, accountPromise]);
      const genderText = normalizeGenderText(profile.gender);

      this.setData({
        profile: {
          ...profile,
          avatar_url: getAvatarUrl(profile.avatar_url ?? ''),
        },
        phoneMasked: account?.phone ?? '',
        genderText,
        loading: false,
      });

      logger.info('Profile loaded', { qiao_id: profile.qiao_id });
    } catch (error) {
      logger.error('Load profile failed', {
        error: error instanceof Error ? error.message : String(error),
      });

      this.setData({
        error: '加载失败,请稍后再试',
        loading: false,
      });

      void wx.showToast({
        title: '加载失败',
        icon: 'none',
      });
    }
  },

  editPhone() {
    void wx.navigateTo({
      url: '/pages/phone-manage/phone-manage',
    });
  },

  editAvatar() {
    const avatarParam = buildAvatarParam(this.data.profile?.avatar_url);
    void wx.navigateTo({
      url: `/pages/avatar-selector/avatar-selector?avatar=${encodeURIComponent(avatarParam)}`,
    });
  },

  editNickname() {
    void wx.navigateTo({
      url: `/pages/profile-edit/profile-edit?field=nickname&value=${encodeValue(this.data.profile?.nickname)}`,
    });
  },

  editUsername() {
    void wx.navigateTo({
      url: `/pages/profile-edit/profile-edit?field=username&value=${encodeValue(this.data.profile?.username)}`,
    });
  },

  editGender() {
    const value = this.data.profile?.gender ?? '';
    void wx.navigateTo({
      url: `/pages/profile-edit/profile-edit?field=gender&value=${value}`,
    });
  },

  editRegion() {
    void wx.navigateTo({
      url: `/pages/profile-edit/profile-edit?field=region&value=${encodeValue(this.data.profile?.region)}`,
    });
  },

  editBio() {
    void wx.navigateTo({
      url: `/pages/profile-edit/profile-edit?field=bio&value=${encodeValue(this.data.profile?.bio)}`,
    });
  },
});
