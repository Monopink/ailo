import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { completeAvatarUpload } from '../../utils/avatar-uploader';
import { getLogger } from '../../utils/logger';
import profileService, { type ProfileViewModel } from '../../utils/profile-service';
import { updateUserAvatar } from '../../utils/profile';
import { isDefined, isNonEmptyString } from '../../utils/guards';
import { formatRegion } from '../../utils/format';
import { GENDER_OPTIONS, type GenderOption } from '../../utils/constants/user';
import { type ScreenModel } from '../../services/pages/page-state';
import { createProfileDetailPageService } from '../../services/pages/profile-detail-service';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';

const logger = getLogger('ProfileDetail');
const PROVINCE_ADMIN_DIVISIONS = new Set(['省直辖县级行政区划', '自治区直辖县级行政区划']);
const MUNICIPALITY_COUNTY_LABEL = '县';

type RegionValue = [] | [string] | [string, string];

interface ProfileDetailPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  profile: ProfileViewModel | null;
  genderText: string;
  genderOptions: readonly GenderOption[];
  genderIndex: number;
  regionValue: RegionValue;
  avatarUploading: boolean;
  fieldUpdating: boolean;
}

interface ProfileDetailPageCustom {
  profileDetailPageService: ReturnType<typeof createProfileDetailPageService>;
  applyScreenModel(screenModel: ScreenModel): void;
  loadProfile(): Promise<void>;
  saveProfileField(updateData: Record<string, unknown>): Promise<void>;
  editNickname(): void;
  editUsername(): void;
  onGenderChange(event: WechatMiniprogram.PickerChange): void;
  onRegionChange(event: WechatMiniprogram.PickerChange): void;
  editBio(): void;
  editAvatar(): Promise<void>;
  onUnload(): void;
}

const encodeValue = (value: string | undefined | null): string => encodeURIComponent(value ?? '');
const resolveGenderIndex = (gender?: number | null): number =>
  GENDER_OPTIONS.findIndex((option) => option.value === gender);

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
    regionValue: [],
    avatarUploading: false,
    fieldUpdating: false,
  },

  profileDetailPageService: null as unknown as ReturnType<typeof createProfileDetailPageService>,

  applyScreenModel(screenModel: ScreenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  onLoad() {
    logger.info('Profile detail page loaded');
    this.profileDetailPageService = createProfileDetailPageService();
    const bootstrap = this.profileDetailPageService.bootstrap();
    this.setData({
      profile: bootstrap.profile,
      genderText: bootstrap.genderText,
      genderIndex: resolveGenderIndex(bootstrap.profile?.gender),
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
      url: `/pages/field-edit/field-edit?domain=profile&field=nickname&value=${encodeValue(this.data.profile?.nickname)}`,
    });
  },

  editUsername() {
    if (isNonEmptyString(this.data.profile?.displayUsername)) {
      return;
    }
    void wx.navigateTo({
      url: `/pages/field-edit/field-edit?domain=profile&field=username&value=${encodeValue(this.data.profile?.username)}`,
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
    const regionArray = event.detail.value as string[];
    const [province = '', city = '', district = ''] = regionArray;
    let actualCity: string | null = city;
    if (PROVINCE_ADMIN_DIVISIONS.has(city)) {
      actualCity = district;
    } else if (city === MUNICIPALITY_COUNTY_LABEL) {
      actualCity = null;
    }

    const regionDisplay =
      actualCity !== null ? formatRegion(province, actualCity) : formatRegion(province, province);
    if (!isNonEmptyString(regionDisplay)) {
      return;
    }
    this.setData({
      regionValue: actualCity !== null ? [province, actualCity] : [province],
    });
    if (this.data.profile?.region === regionDisplay) {
      return;
    }
    void this.saveProfileField({
      region: regionDisplay,
    });
  },

  editBio() {
    void wx.navigateTo({
      url: `/pages/field-edit/field-edit?domain=profile&field=bio&value=${encodeValue(this.data.profile?.bio)}`,
    });
  },
  async editAvatar() {
    if (this.data.avatarUploading) {
      return;
    }

    this.setData({
      avatarUploading: true,
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
      await profileService.loadProfile(true);
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
      });
    }
  },
});
