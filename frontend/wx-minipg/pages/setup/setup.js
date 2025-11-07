import { get, post } from '../../utils/api';
import authService from '../../utils/auth-service';
import { getAvatarUrl } from '../../utils/avatar';
import { APP_CONFIG } from '../../utils/config';
import logger from '../../utils/logger';
import { formatRegion } from '../../utils/format';

Page({
  data: {
    presetAvatars: [],
    selectedAvatar: '',
    nickname: '',
    gender: 0,  // Default to unknown
    genderOptions: [
      { value: 1, label: '男' },
      { value: 2, label: '女' },
      { value: 3, label: '其他' },
      { value: 4, label: '未知' }
    ],
    genderIndex: -1,  // No selection by default
    bio: '',
    phone: '',  // Display phone number
    verifiedPhoneToken: '',  // Temporary token for registration
    regionValue: [],  // Region picker value [province, city, district]
    regionDisplay: '',  // Display text for selected region
    maxNicknameLength: APP_CONFIG.maxNicknameLength || 20,
    maxBioLength: APP_CONFIG.maxBioLength || 200,
    loading: false
  },

  async onLoad() {
    logger.info('Registration profile setup page loaded');

    // Get verified phone token and phone from storage
    const verifiedPhoneToken = wx.getStorageSync('verified_phone_token');
    const phone = wx.getStorageSync('verified_phone');

    if (!verifiedPhoneToken || !phone) {
      logger.error('No verified phone token found, redirect to login');
      wx.showToast({
        title: '请先验证手机号',
        icon: 'none'
      });
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }

    // Mask phone number for display (e.g., 138******00)
    const maskedPhone = phone.replace(/(\+86)?(\d{3})\d{4}(\d{2})/, '$1$2******$3');

    this.setData({
      verifiedPhoneToken,
      phone: maskedPhone
    });

    await this.loadPresetAvatars();
  },

  async loadPresetAvatars() {
    try {
      const result = await get('/preset-assets', { asset_type: 1 });
      const avatars = result.assets.map(asset => ({
        id: asset.id,
        url: getAvatarUrl(asset.url)
      }));
      this.setData({ presetAvatars: avatars });
    } catch (error) {
      // Preset avatars are optional, don't block registration flow
      logger.warn('Failed to load preset avatars, using default avatar', { error });
      this.setData({ presetAvatars: [] });
    }
  },

  selectAvatar(e) {
    const avatarId = e.currentTarget.dataset.id;
    this.setData({ selectedAvatar: avatarId });
  },

  onNicknameInput(e) {
    this.setData({ nickname: e.detail.value });
  },

  onGenderChange(e) {
    const genderIndex = parseInt(e.detail.value);
    const gender = this.data.genderOptions[genderIndex].value;
    this.setData({
      genderIndex,
      gender
    });
  },

  onBioInput(e) {
    this.setData({ bio: e.detail.value });
  },

  onRegionChange(e) {
    const regionArray = e.detail.value;
    const [province, city, district] = regionArray;

    let actualCity = city;

    // Handle special administrative divisions
    if (city === '省直辖县级行政区划' || city === '自治区直辖县级行政区划') {
      // For province/autonomous region-administered county-level divisions, use district as city
      // e.g., "湖北省" "省直辖县级行政区划" "仙桃市" -> use "仙桃市" as city
      actualCity = district;
    } else if (city === '县') {
      // For municipalities' counties, use only province (municipality) name
      // e.g., "重庆市" "县" "丰都县" -> use only "重庆市"
      actualCity = null;
    }

    const regionDisplay = actualCity ? formatRegion(province, actualCity) : formatRegion(province, province);
    this.setData({
      regionValue: actualCity ? [province, actualCity] : [province],
      regionDisplay
    });
  },

  async handleSubmit() {
    // Validate nickname (required, 2-20 characters)
    if (!this.data.nickname || this.data.nickname.trim().length < 2) {
      wx.showToast({
        title: '请输入昵称(至少2个字符)',
        icon: 'none'
      });
      return;
    }

    if (this.data.nickname.length > 20) {
      wx.showToast({
        title: '昵称不能超过20个字符',
        icon: 'none'
      });
      return;
    }

    try {
      this.setData({ loading: true });

      const data = {
        verified_phone_token: this.data.verifiedPhoneToken,
        nickname: this.data.nickname.trim()
      };

      // Optional fields
      if (this.data.gender !== 0) {
        data.gender = this.data.gender;
      }
      if (this.data.bio && this.data.bio.trim()) {
        data.bio = this.data.bio.trim();
      }
      if (this.data.selectedAvatar) {
        data.avatar_url = `assets://${this.data.selectedAvatar}`;
      }
      if (this.data.regionDisplay) {
        data.region = this.data.regionDisplay;
      }

      // Call complete registration API
      const result = await post('/auth/complete-registration', data, { auth: false });

      // Use authService to login
      await authService.login(result.token, result.user);

      // Clear temporary credentials
      wx.removeStorageSync('verified_phone_token');
      wx.removeStorageSync('verified_phone');

      logger.info('Registration complete', { qiao_id: result.user.qiao_id });

      // Redirect to chat list first
      wx.switchTab({ url: '/pages/index/index' });

      // Initialize message service in background (don't block registration)
      const app = getApp();
      app.initMessageService().catch(error => {
        logger.warn('Message service initialization failed, will retry later', { error });
      });
    } catch (error) {
      logger.error('Registration failed', { error });
      this.setData({ loading: false });
      wx.showToast({
        title: error.message || '注册失败',
        icon: 'none'
      });
    }
  },

  handleCancel() {
    wx.showModal({
      title: '取消注册',
      content: '确定要取消注册吗？',
      success: (res) => {
        if (res.confirm) {
          // Clear temporary credentials
          wx.removeStorageSync('verified_phone_token');
          wx.removeStorageSync('verified_phone');

          logger.info('Registration cancelled');

          // Redirect to login page
          wx.redirectTo({ url: '/pages/login/login' });
        }
      }
    });
  }
});
