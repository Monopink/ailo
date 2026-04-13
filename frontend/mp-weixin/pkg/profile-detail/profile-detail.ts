import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { completeAvatarUpload, completeWechatAvatarUpload } from '../../utils/avatar-uploader';
import { getLogger } from '../../utils/logger';
import profileService, { type ProfileViewModel } from '../../utils/profile-service';
import { updateUserAvatar } from '../../utils/profile';
import { isDefined, isNonEmptyString } from '../../utils/guards';
import { GENDER_OPTIONS, type GenderOption } from '../../utils/constants/user';
import { type ScreenModel } from '../services/pages/page-state';
import { createProfileDetailPageService } from '../services/pages/profile-detail-service';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { getWechatProfileCapabilities } from '../../utils/wechat-profile-capability';

const logger = getLogger('ProfileDetail');

interface ProfileDetailPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  profile: ProfileViewModel | null;
  genderText: string;
  genderOptions: readonly GenderOption[];
  genderIndex: number;
  avatarUploading: boolean;
  fieldUpdating: boolean;
  canUseChooseAvatar: boolean;
}

type ChooseAvatarEvent = WechatMiniprogram.CustomEvent<{ avatarUrl?: string }>;
type RegionPickerDetail = {
  value: string[];
  code: string[];
  postcode: string;
};
type RegionPickerChangeEvent = WechatMiniprogram.CustomEvent<RegionPickerDetail>;

interface ProfileDetailPageCustom {
  profileDetailPageService: ReturnType<typeof createProfileDetailPageService>;
  applyScreenModel(screenModel: ScreenModel): void;
  loadProfile(): Promise<void>;
  saveProfileField(updateData: Record<string, unknown>): Promise<void>;
  editNickname(): void;
  editUsername(): void;
  onGenderChange(event: WechatMiniprogram.PickerChange): void;
  onRegionChange(event: RegionPickerChangeEvent): void;
  editBio(): void;
  onChooseWechatAvatar(event: ChooseAvatarEvent): Promise<void>;
  onAvatarRenderSuccess(
    event: WechatMiniprogram.CustomEvent<WechatMiniprogram.GeneralCallbackResult>
  ): void;
  onAvatarRenderError(
    event: WechatMiniprogram.CustomEvent<WechatMiniprogram.GeneralCallbackResult>
  ): void;
  applyAvatarFile(fileId: string): Promise<void>;
  uploadLocalAvatar(): Promise<void>;
  editAvatar(): Promise<void>;
  onUnload(): void;
}

const encodeValue = (value: string | undefined | null): string => encodeURIComponent(value ?? '');
const resolveGenderIndex = (gender?: number | null): number =>
  GENDER_OPTIONS.findIndex((option) => option.value === gender);
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
  regionDisplay: string;
  regionCnCityCode: string | null;
  regionProvinceName: string | null;
  regionCityName: string | null;
} => {
  const [province = '', city = ''] = regionArray;
  const effectiveCity = isNonEmptyString(city) ? city : province;
  const regionDisplay = buildRegionDraftDisplay(province, effectiveCity);

  let candidateCode = '';
  if (codeArray.length >= 2) {
    candidateCode = codeArray[1];
  } else if (codeArray.length === 1) {
    candidateCode = codeArray[0];
  }

  return {
    regionDisplay,
    regionCnCityCode: isNonEmptyString(candidateCode) ? candidateCode : null,
    regionProvinceName: isNonEmptyString(province) ? province : null,
    regionCityName: isNonEmptyString(effectiveCity) ? effectiveCity : null,
  };
};

const buildPageLayoutScreenModelPayload = (screenModel: ScreenModel): Record<string, unknown> => ({
  'pageLayoutData.screenModel': screenModel,
});

Page<ProfileDetailPageData, ProfileDetailPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      emptyMessage: '暂无详细资料',
      hasFooter: false,
    }),
    profile: null,
    genderText: '',
    genderOptions: GENDER_OPTIONS,
    genderIndex: -1,
    avatarUploading: false,
    fieldUpdating: false,
    canUseChooseAvatar: false,
  },

  profileDetailPageService: null as unknown as ReturnType<typeof createProfileDetailPageService>,

  applyScreenModel(screenModel: ScreenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  onLoad() {
    logger.info('Profile detail page loaded');
    this.profileDetailPageService = createProfileDetailPageService();
    const capabilities = getWechatProfileCapabilities();
    const bootstrap = this.profileDetailPageService.bootstrap();
    this.setData({
      profile: bootstrap.profile,
      genderText: bootstrap.genderText,
      genderIndex: resolveGenderIndex(bootstrap.profile?.gender),
      canUseChooseAvatar: capabilities.canUseChooseAvatar,
      ...buildPageLayoutScreenModelPayload(bootstrap.screenModel),
    });
    void this.loadProfile();
  },

  onShow() {
    const bootstrap = this.profileDetailPageService.bootstrap();
    if (bootstrap.profile === null) {
      return;
    }
    this.setData({
      profile: bootstrap.profile,
      genderText: bootstrap.genderText,
      genderIndex: resolveGenderIndex(bootstrap.profile.gender),
      ...buildPageLayoutScreenModelPayload(bootstrap.screenModel),
    });
  },

  onUnload() {
    this.profileDetailPageService.dispose();
  },

  async loadProfile() {
    this.applyScreenModel({
      ...this.data.pageLayoutData.screenModel,
      screenState: 'ready',
      contentVariant: this.data.profile === null ? 'blank' : 'data',
      refreshState: 'refreshing',
    });

    logger.info('Loading user profile');
    const result = await this.profileDetailPageService.load(this.data.profile);
    if (result === null) {
      return;
    }
    if (result.authInvalid) {
      await showAuthExpiredModalAndRelogin();
      return;
    }

    this.setData({
      profile: result.profile,
      genderText: result.genderText,
      genderIndex: resolveGenderIndex(result.profile?.gender),
      ...buildPageLayoutScreenModelPayload(result.screenModel),
      'pageLayoutData.hasFooter': false,
    });
  },

  async saveProfileField(updateData) {
    if (this.data.fieldUpdating || this.data.avatarUploading) {
      return;
    }
    this.setData({
      fieldUpdating: true,
    });
    try {
      const result = await this.profileDetailPageService.updateProfile(
        updateData,
        this.data.profile
      );
      if (result === null) {
        return;
      }
      if (result.authInvalid) {
        await showAuthExpiredModalAndRelogin();
        return;
      }
      this.setData({
        profile: result.profile,
        genderText: result.genderText,
        genderIndex: resolveGenderIndex(result.profile?.gender),
      });
      void wx.showToast({
        title: '修改成功',
        icon: 'success',
      });
    } catch (error) {
      logger.error('Update profile field failed', {
        error: error instanceof Error ? error.message : String(error),
      });
      void wx.showToast({
        title:
          error instanceof Error && isNonEmptyString(error.message)
            ? error.message
            : '修改失败，请重试',
        icon: 'none',
      });
    } finally {
      this.setData({
        fieldUpdating: false,
      });
    }
  },

  editNickname() {
    void wx.navigateTo({
      url: `/pkg/field-edit/field-edit?domain=profile&field=nickname&value=${encodeValue(this.data.profile?.nickname)}`,
    });
  },

  editUsername() {
    if (isNonEmptyString(this.data.profile?.displayUsername)) {
      return;
    }
    void wx.navigateTo({
      url: `/pkg/field-edit/field-edit?domain=profile&field=username&value=${encodeValue(this.data.profile?.username)}`,
    });
  },

  onGenderChange(event) {
    const nextIndex = Number.parseInt(String(event.detail.value), 10);
    const option = this.data.genderOptions[nextIndex];
    if (!isDefined(option)) {
      return;
    }
    if (this.data.profile?.gender === option.value) {
      return;
    }
    void this.saveProfileField({
      gender: option.value,
    });
  },

  onRegionChange(event) {
    if (this.data.fieldUpdating || this.data.avatarUploading) {
      return;
    }

    try {
      const normalized = normalizeRegionSelection(event.detail.value, event.detail.code);
      if (
        !isNonEmptyString(normalized.regionCnCityCode) ||
        !isNonEmptyString(normalized.regionProvinceName) ||
        !isNonEmptyString(normalized.regionCityName)
      ) {
        void wx.showToast({
          title: '请选择地区',
          icon: 'none',
        });
        return;
      }

      if (normalized.regionDisplay === (this.data.profile?.region ?? '')) {
        return;
      }

      void this.saveProfileField({
        region_country_code: 'CN',
        region_cn_city_code: normalized.regionCnCityCode,
        region_province_name: normalized.regionProvinceName,
        region_city_name: normalized.regionCityName,
      });
    } catch (error) {
      logger.error('Region picker change handler crashed', { error });
      void wx.showToast({
        title: '地区选择异常，请重试',
        icon: 'none',
      });
    }
  },

  editBio() {
    void wx.navigateTo({
      url: `/pkg/field-edit/field-edit?domain=profile&field=bio&value=${encodeValue(this.data.profile?.bio)}`,
    });
  },

  async applyAvatarFile(fileId) {
    await updateUserAvatar(fileId);
    void wx.showToast({
      title: '头像已更新',
      icon: 'success',
    });
    await profileService.loadProfile(true);
    await this.loadProfile();
  },

  async onChooseWechatAvatar(event) {
    if (this.data.avatarUploading) {
      return;
    }

    const avatarUrl = event.detail.avatarUrl ?? '';
    if (!isNonEmptyString(avatarUrl)) {
      return;
    }

    this.setData({
      avatarUploading: true,
    });
    try {
      const result = await completeWechatAvatarUpload(avatarUrl, {
        page: 'profile-detail',
        sourceType: 'wechat-avatar',
      });
      if (result === null) {
        return;
      }
      await this.applyAvatarFile(result.fileId);
    } catch (error) {
      logger.error('Update WeChat avatar failed', {
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
      this.setData({
        avatarUploading: false,
      });
    }
  },

  onAvatarRenderSuccess(event) {
    logger.info('Avatar render success in profile-detail native image', {
      detail: event.detail,
      avatarUrl: this.data.profile?.displayAvatar ?? '',
    });
  },

  onAvatarRenderError(event) {
    logger.error('Avatar render failed in profile-detail native image', {
      detail: event.detail,
      avatarUrl: this.data.profile?.displayAvatar ?? '',
    });
  },

  async uploadLocalAvatar() {
    if (this.data.avatarUploading) {
      return;
    }

    this.setData({
      avatarUploading: true,
    });
    try {
      const result = await completeAvatarUpload({ page: 'profile-detail' });
      if (!isDefined(result)) {
        return;
      }
      await this.applyAvatarFile(result.fileId);
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
      this.setData({
        avatarUploading: false,
      });
    }
  },

  async editAvatar() {
    if (this.data.avatarUploading) {
      return;
    }

    await this.uploadLocalAvatar();
  },
});
