import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { completeAvatarUpload } from '../../utils/avatar-uploader';
import { getLogger } from '../../utils/logger';
import profileService, { type ProfileViewModel } from '../../utils/profile-service';
import { fetchAccountInfo, updateUserAvatar } from '../../utils/profile';
import { isDefined, isNonEmptyString } from '../../utils/guards';

const logger = getLogger('ProfileDetail');

interface ProfileDetailPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  profile: ProfileViewModel | null;
  phoneMasked: string;
  genderText: string;
  avatarUploading: boolean;
  avatarHint: string;
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
  switch (gender) {
    case 1:
      return '男';
    case 2:
      return '女';
    case 3:
      return '其他';
    default:
      return '未设置';
  }
};

const encodeValue = (value: string | undefined | null): string => encodeURIComponent(value ?? '');
const getAvatarHint = (isUploading: boolean): string => (isUploading ? '更新中…' : '点击更换');

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
    avatarHint: getAvatarHint(false),
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
      const profilePromise = profileService.loadProfile();
      const accountPromise = fetchAccountInfo().catch((error: unknown) => {
        logger.error('Load account info failed', {
          error: error instanceof Error ? error.message : String(error),
        });
        return null;
      });

      const [profile, account] = await Promise.all([profilePromise, accountPromise]);
      const genderText = normalizeGenderText(profile.gender);

      this.setData({
        profile,
        phoneMasked: account?.phone ?? '未绑定',
        genderText,
        'pageLayoutData.isLoading': false,
        'pageLayoutData.isEmpty': false,
        'pageLayoutData.hasFooter': true,
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

    this.setData({
      avatarUploading: true,
      avatarHint: getAvatarHint(true),
    });
    void wx.showLoading({ title: '上传中', mask: true });
    try {
      const result = await completeAvatarUpload({ page: 'profile-detail' });
      if (!isDefined(result)) {
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
        title:
          error instanceof Error && isNonEmptyString(error.message)
            ? error.message
            : '更新头像失败，请重试',
        icon: 'none',
      });
    } finally {
      void wx.hideLoading();
      this.setData({
        avatarUploading: false,
        avatarHint: getAvatarHint(false),
      });
    }
  },
});
