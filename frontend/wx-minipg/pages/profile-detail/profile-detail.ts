import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { getAvatarUrl } from '../../utils/avatar';
import { completeAvatarUpload } from '../../utils/avatar-uploader';
import { getLogger } from '../../utils/logger';
import {
  fetchAccountInfo,
  fetchCurrentUserProfile,
  updateUserAvatar,
  type UserProfileResponse,
} from '../../utils/profile';

const logger = getLogger('ProfileDetail');

const GENDER_TEXT_MAP = {
  1: '男',
  2: '女',
  3: '其他',
  4: '未知',
} as const;

type GenderCode = keyof typeof GENDER_TEXT_MAP;

type NormalizedProfile =
  | (UserProfileResponse & {
      displayAvatar: string;
      displayUsername: string;
    })
  | null;

interface ProfileDetailPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  profile: NormalizedProfile;
  phoneMasked: string;
  genderText: string;
  avatarUploading: boolean;
}

interface ProfileDetailPageCustom {
  loadProfile(): Promise<void>;
  editPhone(): void;
  editNickname(): void;
  editUsername(): void;
  editGender(): void;
  editRegion(): void;
  editBio(): void;
  handleFooterAction(): void;
  onRetry(): void;
  editAvatar(): Promise<void>;
}

const normalizeGenderText = (gender?: number | null): string => {
  if (typeof gender === 'number' && GENDER_TEXT_MAP[gender as GenderCode]) {
    return GENDER_TEXT_MAP[gender as GenderCode];
  }
  return '未设置';
};

const encodeValue = (value: string | undefined | null): string => encodeURIComponent(value ?? '');

Page<ProfileDetailPageData, ProfileDetailPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      isLoading: true,
      emptyMessage: '暂无详细资料',
      hasFooter: false,
    }),
    profile: null,
    phoneMasked: '',
    genderText: '未设置',
    avatarUploading: false,
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
        'pageLayoutData.isLoading': true,
        'pageLayoutData.hasError': false,
        'pageLayoutData.errorMessage': '',
        'pageLayoutData.hasFooter': false,
      });

      logger.info('Loading user profile');
      const profilePromise = fetchCurrentUserProfile();
      const accountPromise = fetchAccountInfo().catch((error: unknown) => {
        logger.error('Load account info failed', {
          error: error instanceof Error ? error.message : String(error),
        });
        return null;
      });

      const [profile, account] = await Promise.all([profilePromise, accountPromise]);
      const genderText = normalizeGenderText(profile.gender ?? undefined);

      const normalizedProfile = profile
        ? {
            ...profile,
            avatar_url: profile.avatar_url ?? '',
            displayAvatar: getAvatarUrl(profile.avatar_url ?? null),
            displayUsername: profile.username || '--',
          }
        : null;

      this.setData({
        profile: normalizedProfile,
        phoneMasked: account?.phone ?? '未绑定',
        genderText,
        'pageLayoutData.isLoading': false,
        'pageLayoutData.isEmpty': !normalizedProfile,
        'pageLayoutData.hasFooter': Boolean(normalizedProfile),
      });

      logger.info('Profile loaded', { qiao_id: profile.qiao_id });
    } catch (error) {
      logger.error('Load profile failed', {
        error: error instanceof Error ? error.message : String(error),
      });

      this.setData({
        profile: null,
        phoneMasked: '',
        genderText: '未设置',
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': '加载失败，请稍后再试',
        'pageLayoutData.hasFooter': false,
      });

      void wx.showToast({
        title: '加载失败',
        icon: 'none',
      });
    }
  },

  editPhone() {
    void wx.navigateTo({
      url: '/pages/account-security/account-security',
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

  handleFooterAction() {
    this.editPhone();
  },

  onRetry() {
    void this.loadProfile();
  },

  async editAvatar() {
    if (this.data.avatarUploading) {
      return;
    }

    this.setData({ avatarUploading: true });
    void wx.showLoading({ title: '上传中', mask: true });
    try {
      const result = await completeAvatarUpload({ page: 'profile-detail' });
      if (!result) {
        return;
      }
      await updateUserAvatar(result.fileId);
      void wx.showToast({
        title: '头像已更新',
        icon: 'success',
      });
      await this.loadProfile();
    } catch (error) {
      logger.error('Update avatar failed', {
        error: error instanceof Error ? error.message : String(error),
      });
      void wx.showToast({
        title: error instanceof Error && error.message ? error.message : '更新头像失败，请重试',
        icon: 'none',
      });
    } finally {
      void wx.hideLoading();
      this.setData({ avatarUploading: false });
    }
  },
});
