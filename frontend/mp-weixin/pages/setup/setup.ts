import authService from '../../utils/auth-service';
import { getAvatarUrl } from '../../utils/avatar';
import { completeAvatarUpload } from '../../utils/avatar-uploader';
import logger from '../../utils/logger';
import { classifyError } from '../../utils/error-classifier';
import { isNonEmptyString } from '../../utils/guards';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { GENDER_OPTIONS, type GenderOption, type GenderValue } from '../../utils/constants/user';
import type { StoredAuthUser } from '../../utils/storage';
import { createSetupPageService } from '../../services/pages/setup-service';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { PROFILE_BIO_RULE, PROFILE_NICKNAME_RULE, validateTextLimit } from '../../utils/text-limit';

const MIN_NICKNAME_LENGTH = 2;
const WHITESPACE_REGEX = /\s/u;

type RegionValue = [] | [string] | [string, string];

type InputEvent = WechatMiniprogram.CustomEvent<{ value: string }>;
type RegionPickerDetail = {
  value: string[];
  code: string[];
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
  regionCnCityCode: string | null;
  regionProvinceName: string | null;
  regionCityName: string | null;
  regionChanged: boolean;
  maxNicknameLength: number;
  maxBioLength: number;
  loading: boolean;
}

interface SetupPageCustom {
  setupPageService: ReturnType<typeof createSetupPageService>;
  loadProfile(): Promise<void>;
  ensureProfileRequired(): boolean;
  onUnload(): void;
  onNicknameInput(event: InputEvent): void;
  onGenderChange(event: WechatMiniprogram.PickerChange): void;
  onBioInput(event: InputEvent): void;
  onRegionChange(event: RegionPickerChangeEvent): void;
  handleChooseAvatar(): Promise<void>;
  handleSubmit(): Promise<void>;
  handleCancel(): void;
}

const buildScreenModelPayload = (
  screenState: 'booting' | 'ready',
  contentVariant: 'data' | 'empty' | 'blank',
  refreshState: 'idle' | 'refreshing' | 'degraded'
): Record<string, unknown> => ({
  'pageLayoutData.screenModel': {
    screenState,
    contentVariant,
    refreshState,
  },
});

const buildRegionDraftDisplay = (province: string, city: string): string => {
  if (!isNonEmptyString(province)) {
    return '';
  }
  const effectiveCity = isNonEmptyString(city) ? city : province;
  if (!isNonEmptyString(effectiveCity)) {
    return '';
  }
  return province === effectiveCity ? province : `${province} ${effectiveCity}`;
};

const normalizeRegionSelection = (
  regionArray: string[],
  codeArray: string[]
): {
  regionValue: RegionValue;
  regionDisplay: string;
  regionCnCityCode: string | null;
  regionProvinceName: string | null;
  regionCityName: string | null;
} => {
  const [province = '', city = ''] = regionArray;
  const effectiveCity = isNonEmptyString(city) ? city : province;
  const regionDisplay = buildRegionDraftDisplay(province, effectiveCity);
  const regionValue: RegionValue =
    isNonEmptyString(province) && isNonEmptyString(city)
      ? [province, city]
      : isNonEmptyString(province)
        ? [province]
        : [];
  let candidateCode = '';
  if (codeArray.length >= 2) {
    candidateCode = codeArray[1];
  } else if (codeArray.length === 1) {
    candidateCode = codeArray[0];
  }
  const regionCnCityCode = isNonEmptyString(String(candidateCode)) ? String(candidateCode) : null;
  const regionProvinceName = isNonEmptyString(province) ? province : null;
  const regionCityName = isNonEmptyString(effectiveCity) ? effectiveCity : null;

  return { regionValue, regionDisplay, regionCnCityCode, regionProvinceName, regionCityName };
};

const validateSetupSubmissionOrToast = (
  payload: Pick<
    SetupPageData,
    | 'nickname'
    | 'bio'
    | 'regionChanged'
    | 'regionCnCityCode'
    | 'regionProvinceName'
    | 'regionCityName'
  >
): { trimmedNickname: string } | null => {
  const trimmedNickname = payload.nickname.trim();

  if (trimmedNickname === '' || trimmedNickname.length < MIN_NICKNAME_LENGTH) {
    void wx.showToast({
      title: '请输入昵称',
      icon: 'none',
    });
    return null;
  }

  if (WHITESPACE_REGEX.test(trimmedNickname)) {
    void wx.showToast({
      title: '昵称不能包含空格',
      icon: 'none',
    });
    return null;
  }

  const nicknameValidation = validateTextLimit(trimmedNickname, PROFILE_NICKNAME_RULE);
  if (!nicknameValidation.valid) {
    void wx.showToast({
      title: nicknameValidation.message ?? '昵称格式不正确',
      icon: 'none',
    });
    return null;
  }

  const trimmedBio = payload.bio.trim();
  if (trimmedBio !== '') {
    const bioValidation = validateTextLimit(trimmedBio, PROFILE_BIO_RULE);
    if (!bioValidation.valid) {
      void wx.showToast({
        title: bioValidation.message ?? '个性签名格式不正确',
        icon: 'none',
      });
      return null;
    }
  }

  if (payload.regionChanged) {
    if (
      !isNonEmptyString(payload.regionCnCityCode) ||
      !isNonEmptyString(payload.regionProvinceName) ||
      !isNonEmptyString(payload.regionCityName)
    ) {
      void wx.showToast({
        title: '请选择地区',
        icon: 'none',
      });
      return null;
    }
  }

  return { trimmedNickname };
};

const mapProfileToStoredUser = (profile: { qiao_id: string }): StoredAuthUser => ({
  qiao_id: profile.qiao_id,
});

Page<SetupPageData, SetupPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
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
    regionCnCityCode: null,
    regionProvinceName: null,
    regionCityName: null,
    regionChanged: false,
    maxNicknameLength: PROFILE_NICKNAME_RULE.displayWidthLimit,
    maxBioLength: PROFILE_BIO_RULE.graphemeLimit,
    loading: false,
  },

  setupPageService: null as unknown as ReturnType<typeof createSetupPageService>,

  async onLoad() {
    logger.info('Profile setup page loaded');
    this.setupPageService = createSetupPageService();
    if (!this.ensureProfileRequired()) {
      return;
    }
    await this.loadProfile();
  },

  onShow() {
    void this.ensureProfileRequired();
  },

  onUnload() {
    this.setupPageService.dispose();
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

    this.setData(buildScreenModelPayload('ready', 'data', 'refreshing'));

    try {
      logger.debug('Fetching user profile for setup');
      const snapshot = await this.setupPageService.loadProfile();
      if (snapshot === null) {
        return;
      }
      logger.debug('Profile fetched successfully');

      this.setData({
        nickname: snapshot.nickname,
        avatarUrl: snapshot.avatarUrl,
        gender: snapshot.gender,
        genderIndex: snapshot.genderIndex,
        bio: snapshot.bio,
        regionDisplay: snapshot.regionDisplay,
        regionValue: [],
        regionCnCityCode: null,
        regionProvinceName: null,
        regionCityName: null,
        regionChanged: false,
        ...buildScreenModelPayload('ready', 'data', 'idle'),
      });
    } catch (error) {
      const semantics = classifyError(error);
      if (semantics.reason === 'auth-invalid') {
        await showAuthExpiredModalAndRelogin();
        return;
      }

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
        ...buildScreenModelPayload('ready', 'data', 'degraded'),
      });
    }
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

  onRegionChange(event: RegionPickerChangeEvent) {
    const regionArray = event.detail.value;
    const codeArray = event.detail.code;
    const normalized = normalizeRegionSelection(regionArray, codeArray);
    this.setData({
      regionValue: normalized.regionValue,
      regionDisplay: normalized.regionDisplay,
      regionCnCityCode: normalized.regionCnCityCode,
      regionProvinceName: normalized.regionProvinceName,
      regionCityName: normalized.regionCityName,
      regionChanged: true,
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
    const validated = validateSetupSubmissionOrToast(this.data);
    if (validated === null) {
      return;
    }

    try {
      this.setData({ loading: true, ...buildScreenModelPayload('ready', 'data', 'refreshing') });
      const updatedProfile = await this.setupPageService.submitProfile({
        nickname: validated.trimmedNickname,
        gender: this.data.gender,
        bio: this.data.bio,
        regionCnCityCode: this.data.regionCnCityCode,
        regionProvinceName: this.data.regionProvinceName,
        regionCityName: this.data.regionCityName,
        regionChanged: this.data.regionChanged,
        avatarFileId: this.data.avatarFileId,
      });
      if (updatedProfile === null) {
        return;
      }
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

      this.setData(buildScreenModelPayload('ready', 'data', 'idle'));
      void wx.switchTab({ url: '/pages/index/index' });
    } catch (error) {
      const semantics = classifyError(error);
      if (semantics.reason === 'auth-invalid') {
        await showAuthExpiredModalAndRelogin();
        return;
      }

      logger.error('Update profile failed', { error });
      this.setData(buildScreenModelPayload('ready', 'data', 'degraded'));
      void wx.showToast({
        title: (error as Error).message !== '' ? (error as Error).message : '提交失败，请稍后重试',
        icon: 'none',
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  handleCancel() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出吗？',
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
