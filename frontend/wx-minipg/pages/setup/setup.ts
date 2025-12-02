import { get, post } from '../../utils/api';
import authService from '../../utils/auth-service';
import { getAvatarUrl } from '../../utils/avatar';
import { APP_CONFIG } from '../../utils/config';
import logger from '../../utils/logger';
import { formatRegion } from '../../utils/format';
import { getStorage, removeStorage, type StoredAuthUser } from '../../utils/storage';

const VERIFIED_PHONE_TOKEN_KEY = 'verified_phone_token';
const VERIFIED_PHONE_KEY = 'verified_phone';
const MIN_NICKNAME_LENGTH = 2;
const PROVINCE_ADMIN_DIVISIONS = new Set(['省直辖县级行政区划', '自治区直辖县级行政区划']);
const MUNICIPALITY_COUNTY_LABEL = '县';

const GENDER_OPTIONS = [
  { value: 1, label: '男' },
  { value: 2, label: '女' },
  { value: 3, label: '其他' },
  { value: 4, label: '未知' },
] as const;

type GenderOption = (typeof GENDER_OPTIONS)[number];
type GenderValue = 0 | GenderOption['value'];
type SelectedGenderValue = Exclude<GenderValue, 0>;
type RegionValue = [] | [string] | [string, string];

type InputEvent = WechatMiniprogram.CustomEvent<{ value: string }>;
type AvatarTapEvent = WechatMiniprogram.TouchEvent<
  WechatMiniprogram.IAnyObject,
  WechatMiniprogram.IAnyObject,
  { id?: string | number }
>;
type RegionPickerDetail = {
  value: [string, string, string];
  code: [string, string, string];
  postcode: string;
};
type RegionPickerChangeEvent = WechatMiniprogram.CustomEvent<RegionPickerDetail>;

interface PresetAssetResponse {
  id: string | number;
  url?: string;
}

interface PresetAssetsResponse {
  assets: PresetAssetResponse[];
}

interface PresetAvatar {
  id: string;
  url: string;
}

interface SetupPageData {
  presetAvatars: PresetAvatar[];
  selectedAvatar: string;
  nickname: string;
  gender: GenderValue;
  genderOptions: readonly GenderOption[];
  genderIndex: number;
  bio: string;
  phone: string;
  verifiedPhoneToken: string;
  regionValue: RegionValue;
  regionDisplay: string;
  maxNicknameLength: number;
  maxBioLength: number;
  loading: boolean;
}

interface CompleteRegistrationPayload {
  verified_phone_token: string;
  nickname: string;
  gender?: SelectedGenderValue;
  bio?: string;
  avatar_url?: string;
  region?: string;
}

interface CompleteRegistrationResponse {
  token: string;
  user: StoredAuthUser;
}

interface SetupPageCustom {
  loadPresetAvatars(): Promise<void>;
  selectAvatar(event: AvatarTapEvent): void;
  onNicknameInput(event: InputEvent): void;
  onGenderChange(event: WechatMiniprogram.PickerChange): void;
  onBioInput(event: InputEvent): void;
  onRegionChange(event: RegionPickerChangeEvent): void;
  handleSubmit(): Promise<void>;
  handleCancel(): void;
}

interface NormalizedRegion {
  regionValue: RegionValue;
  regionDisplay: string;
}

const normalizeRegionSelection = (regionArray: [string, string, string]): NormalizedRegion => {
  const [province, city, district] = regionArray;
  let resolvedCity: string | null = city;

  if (PROVINCE_ADMIN_DIVISIONS.has(city)) {
    resolvedCity = district;
  } else if (city === MUNICIPALITY_COUNTY_LABEL) {
    resolvedCity = null;
  }

  const regionDisplay = resolvedCity
    ? formatRegion(province, resolvedCity)
    : formatRegion(province, province);
  const regionValue: RegionValue = resolvedCity ? [province, resolvedCity] : [province];

  return { regionValue, regionDisplay };
};

const maskPhoneNumber = (phone: string): string =>
  phone.replace(/(\+86)?(\d{3})\d{4}(\d{2})/, '$1$2******$3');

const buildRegistrationPayload = (
  data: SetupPageData,
  nickname: string
): CompleteRegistrationPayload => {
  const payload: CompleteRegistrationPayload = {
    verified_phone_token: data.verifiedPhoneToken,
    nickname,
  };

  if (data.gender !== 0) {
    payload.gender = data.gender as SelectedGenderValue;
  }

  const trimmedBio = data.bio.trim();
  if (trimmedBio) {
    payload.bio = trimmedBio;
  }

  if (data.selectedAvatar) {
    payload.avatar_url = `assets://${data.selectedAvatar}`;
  }

  if (data.regionDisplay) {
    payload.region = data.regionDisplay;
  }

  return payload;
};

const clearVerifiedPhone = async (): Promise<void> => {
  await Promise.all([
    removeStorage(VERIFIED_PHONE_TOKEN_KEY).catch((error: unknown) => {
      logger.warn('Failed to remove verified phone token', { error });
    }),
    removeStorage(VERIFIED_PHONE_KEY).catch((error: unknown) => {
      logger.warn('Failed to remove verified phone number', { error });
    }),
  ]);
};

Page<SetupPageData, SetupPageCustom>({
  data: {
    presetAvatars: [],
    selectedAvatar: '',
    nickname: '',
    gender: 0,
    genderOptions: GENDER_OPTIONS,
    genderIndex: -1,
    bio: '',
    phone: '',
    verifiedPhoneToken: '',
    regionValue: [],
    regionDisplay: '',
    maxNicknameLength: APP_CONFIG.maxNicknameLength || 20,
    maxBioLength: APP_CONFIG.maxBioLength || 200,
    loading: false,
  },

  async onLoad() {
    logger.info('Registration profile setup page loaded');

    let verifiedPhoneToken: string | null = null;
    let phone: string | null = null;

    try {
      [verifiedPhoneToken, phone] = await Promise.all([
        getStorage<string | null>(VERIFIED_PHONE_TOKEN_KEY, null),
        getStorage<string | null>(VERIFIED_PHONE_KEY, null),
      ]);
    } catch (error) {
      logger.error('Failed to load verified phone info from storage', { error });
    }

    if (!verifiedPhoneToken || !phone) {
      logger.error('No verified phone token found, redirect to login');
      void wx.showToast({
        title: '请先验证手机号',
        icon: 'none',
      });
      void wx.redirectTo({ url: '/pages/login/login' });
      return;
    }

    this.setData({
      verifiedPhoneToken,
      phone: maskPhoneNumber(phone),
    });

    await this.loadPresetAvatars();
  },

  async loadPresetAvatars() {
    try {
      const result = await get<PresetAssetsResponse>('/preset-assets', { asset_type: 1 });
      const avatars: PresetAvatar[] = (result.assets || []).map((asset) => ({
        id: String(asset.id),
        url: getAvatarUrl(asset.url),
      }));
      this.setData({ presetAvatars: avatars });
    } catch (error) {
      logger.warn('Failed to load preset avatars, using default avatar', { error });
      this.setData({ presetAvatars: [] });
    }
  },

  selectAvatar(event) {
    const avatarId = event.currentTarget.dataset.id;
    if (!avatarId) {
      return;
    }
    this.setData({ selectedAvatar: String(avatarId) });
  },

  onNicknameInput(event) {
    this.setData({ nickname: event.detail.value });
  },

  onGenderChange(event) {
    const genderIndex = Number(event.detail.value);
    const genderOption = Number.isNaN(genderIndex) ? undefined : GENDER_OPTIONS[genderIndex];
    if (!genderOption) {
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
    if (!Array.isArray(regionArray) || regionArray.length < 3) {
      this.setData({ regionValue: [], regionDisplay: '' });
      return;
    }

    const normalized = normalizeRegionSelection(regionArray);
    this.setData({
      regionValue: normalized.regionValue,
      regionDisplay: normalized.regionDisplay,
    });
  },

  async handleSubmit() {
    const trimmedNickname = this.data.nickname.trim();

    if (!trimmedNickname || trimmedNickname.length < MIN_NICKNAME_LENGTH) {
      void wx.showToast({
        title: '请输入昵称(至少2个字符)',
        icon: 'none',
      });
      return;
    }

    if (trimmedNickname.length > this.data.maxNicknameLength) {
      void wx.showToast({
        title: `昵称不能超过${this.data.maxNicknameLength}个字符`,
        icon: 'none',
      });
      return;
    }

    try {
      this.setData({ loading: true });
      const payload = buildRegistrationPayload(this.data, trimmedNickname);
      const result = await post<CompleteRegistrationResponse>(
        '/auth/complete-registration',
        payload,
        { auth: false }
      );
      await authService.login(result.token, result.user);
      await clearVerifiedPhone();

      logger.info('Registration complete', { qiao_id: result.user.qiao_id });

      void wx.switchTab({ url: '/pages/index/index' });

      const app = getApp<SaysAppInstance>();
      app.initMessageService().catch((error: unknown) => {
        logger.warn('Message service initialization failed, will retry later', { error });
      });
    } catch (error) {
      logger.error('Registration failed', { error });
      this.setData({ loading: false });
      void wx.showToast({
        title: (error as Error).message || '注册失败',
        icon: 'none',
      });
    }
  },

  handleCancel() {
    wx.showModal({
      title: '取消注册',
      content: '确定要取消注册吗？',
      success: (res) => {
        if (res.confirm) {
          void clearVerifiedPhone();
          logger.info('Registration cancelled');
          void wx.redirectTo({ url: '/pages/login/login' });
        }
      },
    });
  },
});
