import authService from '../../utils/auth-service';
import { APP_CONFIG } from '../../utils/config';
import { getAvatarUrl } from '../../utils/avatar';
import { completeAvatarUpload } from '../../utils/avatar-uploader';
import logger from '../../utils/logger';
import { formatRegion } from '../../utils/format';
import { fetchCurrentUserProfile, updateCurrentUserProfile } from '../../utils/profile';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { GENDER_OPTIONS, type GenderOption, type GenderValue } from '../../utils/constants/user';
import type { StoredAuthUser } from '../../utils/storage';

const MIN_NICKNAME_LENGTH = 2;
const PROVINCE_ADMIN_DIVISIONS = new Set(['省直辖县级行政区划', '自治区直辖县级行政区划']);
const MUNICIPALITY_COUNTY_LABEL = '县';

type RegionValue = [] | [string] | [string, string];

type InputEvent = WechatMiniprogram.CustomEvent<{ value: string }>;
type RegionPickerDetail = {
  value: [string, string, string];
  code: [string, string, string];
  postcode: string;
};
type RegionPickerChangeEvent = WechatMiniprogram.CustomEvent<RegionPickerDetail>;

interface SetupPageData {
  pageLayoutData: PageLayoutData;
  nickname: string;
  avatarUrl: string;
  avatarFileId: string;
  uploadingAvatar: boolean;
  gender: GenderValue | null;
  genderOptions: readonly GenderOption[];
  genderIndex: number;
  bio: string;
  regionValue: RegionValue;
  regionDisplay: string;
  maxNicknameLength: number;
  maxBioLength: number;
  loading: boolean;
}

interface SetupPageCustom {
  loadProfile(): Promise<void>;
  ensureProfileRequired(): boolean;
  onNicknameInput(event: InputEvent): void;
  onGenderChange(event: WechatMiniprogram.PickerChange): void;
  onBioInput(event: InputEvent): void;
  onRegionChange(event: RegionPickerChangeEvent): void;
  handleChooseAvatar(): Promise<void>;
  handleSubmit(): Promise<void>;
  handleCancel(): void;
  onRetry(): void;
}

const normalizeRegionSelection = (
  regionArray: [string, string, string]
): { regionValue: RegionValue; regionDisplay: string } => {
  const [province, city, district] = regionArray;
  let resolvedCity: string | null = city;

  if (PROVINCE_ADMIN_DIVISIONS.has(city)) {
    resolvedCity = district;
  } else if (city === MUNICIPALITY_COUNTY_LABEL) {
    resolvedCity = null;
  }

  const regionDisplay =
    resolvedCity !== null ? formatRegion(province, resolvedCity) : formatRegion(province, province);
  const regionValue: RegionValue = resolvedCity !== null ? [province, resolvedCity] : [province];

  return { regionValue, regionDisplay };
};

const buildProfilePayload = (data: SetupPageData, nickname: string): Record<string, unknown> => {
  const payload: Record<string, unknown> = {
    nickname,
  };

  if (data.gender !== null) {
    payload.gender = data.gender;
  }

  const trimmedBio = data.bio.trim();
  if (trimmedBio !== '') {
    payload.bio = trimmedBio;
  }

  if (data.regionDisplay !== '') {
    payload.region = data.regionDisplay;
  }

  if (data.avatarFileId !== '') {
    payload.avatar_file_id = data.avatarFileId;
  }

  return payload;
};

const mapProfileToStoredUser = (profile: { qiao_id: string }): StoredAuthUser => ({
  qiao_id: profile.qiao_id,
});

const resolveGenderIndex = (value: GenderValue | null): number => {
  if (value === null) {
    return -1;
  }
  return GENDER_OPTIONS.findIndex((option) => option.value === value);
};

Page<SetupPageData, SetupPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      hasFooter: true,
    }),
    nickname: '',
    avatarUrl: '',
    avatarFileId: '',
    uploadingAvatar: false,
    gender: null,
    genderOptions: GENDER_OPTIONS,
    genderIndex: -1,
    bio: '',
    regionValue: [],
    regionDisplay: '',
    maxNicknameLength: APP_CONFIG.maxNicknameLength,
    maxBioLength: APP_CONFIG.maxBioLength,
    loading: false,
  },

  async onLoad() {
    logger.info('Profile setup page loaded');
    if (!this.ensureProfileRequired()) {
      return;
    }
    await this.loadProfile();
  },

  onShow() {
    void this.ensureProfileRequired();
  },

  ensureProfileRequired() {
    if (!authService.needsProfileSetup()) {
      logger.info('Profile setup already completed, redirecting to home');
      void wx.switchTab({ url: '/pages/index/index' });
      return false;
    }
    return true;
  },

  async loadProfile() {
    if (!authService.isAuthenticated()) {
      void wx.reLaunch({ url: '/pages/login/login' });
      return;
    }

    if (!this.ensureProfileRequired()) {
      return;
    }

    this.setData({ 'pageLayoutData.isLoading': true, 'pageLayoutData.hasError': false });

    try {
      logger.debug('Fetching user profile for setup');
      const profile = await fetchCurrentUserProfile();
      logger.debug('Profile fetched successfully', { profile });

      const gender = typeof profile.gender === 'number' ? (profile.gender as GenderValue) : null;
      const avatarUrl = getAvatarUrl(profile.avatar_url ?? '');
      const genderIndex = resolveGenderIndex(gender);

      this.setData({
        nickname: profile.nickname ?? '',
        avatarUrl,
        gender,
        genderIndex,
        bio: profile.bio ?? '',
        regionDisplay: profile.region ?? '',
        regionValue: [],
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': false,
        'pageLayoutData.isEmpty': false,
      });
    } catch (error) {
      // Enhanced error logging
      const errorMessage = error instanceof Error ? error.message : String(error);
      const errorName = error instanceof Error ? error.name : 'Unknown';
      const errorStack = error instanceof Error ? error.stack : undefined;

      logger.error('Load profile for setup failed', {
        errorMessage,
        errorName,
        errorStack,
        errorType: typeof error,
      });

      this.setData({
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': '加载失败，请稍后重试',
      });
    }
  },

  onRetry() {
    void this.loadProfile();
  },

  onNicknameInput(event) {
    this.setData({ nickname: event.detail.value });
  },

  onGenderChange(event) {
    const genderIndex = Number(event.detail.value);
    const genderOption = Number.isNaN(genderIndex) ? undefined : GENDER_OPTIONS[genderIndex];
    if (genderOption === undefined) {
      return;
    }
    this.setData({
      genderIndex,
      gender: genderOption.value,
    });
  },

  onBioInput(event) {
    this.setData({ bio: event.detail.value });
  },

  onRegionChange(event) {
    const regionArray = event.detail.value;
    const normalized = normalizeRegionSelection(regionArray);
    this.setData({
      regionValue: normalized.regionValue,
      regionDisplay: normalized.regionDisplay,
    });
  },

  async handleChooseAvatar() {
    if (this.data.uploadingAvatar) {
      return;
    }

    this.setData({ uploadingAvatar: true });
    try {
      const result = await completeAvatarUpload({ page: 'setup' });
      if (result === null) {
        return;
      }

      const resolvedUrl = getAvatarUrl(result.url);
      this.setData({
        avatarFileId: result.fileId,
        avatarUrl: resolvedUrl !== '' ? resolvedUrl : result.url,
      });
      void wx.showToast({
        title: '头像已更新',
        icon: 'success',
      });
    } catch (error) {
      logger.error('Avatar upload failed during setup', { error });
      void wx.showToast({
        title: '头像更新失败，请重试',
        icon: 'none',
      });
    } finally {
      this.setData({ uploadingAvatar: false });
    }
  },

  async handleSubmit() {
    const trimmedNickname = this.data.nickname.trim();

    if (trimmedNickname === '' || trimmedNickname.length < MIN_NICKNAME_LENGTH) {
      this.setData({
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': '请输入昵称(至少2个字符)',
      });
      return;
    }

    if (trimmedNickname.length > this.data.maxNicknameLength) {
      this.setData({
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': `昵称不能超过${this.data.maxNicknameLength}个字符`,
      });
      return;
    }

    try {
      this.setData({ loading: true, 'pageLayoutData.hasError': false });
      const payload = buildProfilePayload(this.data, trimmedNickname);
      const updatedProfile = await updateCurrentUserProfile(payload);
      const storedUser = mapProfileToStoredUser(updatedProfile);
      await authService.updateUserInfo(storedUser);
      authService.setNeedsProfileSetup(false);

      void wx.showToast({
        title: '资料已更新',
        icon: 'success',
      });

      const app = getApp<AppInstance>();
      app
        .initMessageService()
        .catch((error: unknown) =>
          logger.warn('Init message service after setup failed', { error })
        );

      void wx.switchTab({ url: '/pages/index/index' });
    } catch (error) {
      logger.error('Update profile failed', { error });
      this.setData({
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage':
          (error as Error).message !== '' ? (error as Error).message : '提交失败，请稍后重试',
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  handleCancel() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出并返回登录页吗？',
      success: async (res) => {
        if (!res.confirm) {
          return;
        }
        await authService.logout();
        logger.info('User exited setup and logged out');
        void wx.reLaunch({ url: '/pages/login/login?source=logout' });
      },
    });
  },
});
