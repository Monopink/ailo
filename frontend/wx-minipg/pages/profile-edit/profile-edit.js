import { put } from '../../utils/api';
import { getLogger } from '../../utils/logger';

const logger = getLogger('ProfileEdit');

// Field configurations
const FIELD_CONFIG = {
  nickname: {
    title: '编辑昵称',
    placeholder: '请输入昵称',
    maxLength: 10,
    hint: '',
    type: 'text'
  },
  username: {
    title: '编辑敲敲ID',
    placeholder: '请输入敲敲ID',
    maxLength: 20,
    hint: '敲敲ID可以包含字母、数字和下划线，3-20个字符',
    type: 'text'
  },
  bio: {
    title: '编辑个性签名',
    placeholder: '请输入个性签名',
    maxLength: 70,
    hint: '',
    type: 'text'
  },
  region: {
    title: '编辑地区',
    placeholder: '',
    maxLength: 0,
    hint: '',
    type: 'region'
  },
  gender: {
    title: '编辑性别',
    placeholder: '',
    maxLength: 0,
    hint: '',
    type: 'gender'
  }
};

Page({
  data: {
    field: '',
    fieldType: '',
    value: '',
    placeholder: '',
    maxLength: 0,
    hint: '',
    saving: false,
    // Gender picker
    genderOptions: ['男', '女', '其他', '未知'],
    genderIndex: 0,
    // Region picker
    regionValue: [],
    regionDisplay: ''
  },

  onLoad(options) {
    const { field, value } = options;
    const config = FIELD_CONFIG[field];

    if (!config) {
      wx.showToast({
        title: '参数错误',
        icon: 'none'
      });
      setTimeout(() => {
        wx.navigateBack();
      }, 1500);
      return;
    }

    // Set navigation bar title
    wx.setNavigationBarTitle({
      title: config.title
    });

    // Initialize data based on field type
    if (config.type === 'gender') {
      const genderValue = parseInt(value) || 0;
      this.setData({
        field,
        fieldType: config.type,
        genderIndex: genderValue > 0 ? genderValue - 1 : 0
      });
    } else if (config.type === 'region') {
      this.setData({
        field,
        fieldType: config.type,
        regionDisplay: decodeURIComponent(value || ''),
        regionValue: []
      });
    } else {
      this.setData({
        field,
        fieldType: config.type,
        value: decodeURIComponent(value || ''),
        placeholder: config.placeholder,
        maxLength: config.maxLength,
        hint: config.hint
      });
    }

    logger.info('Profile edit page loaded', { field });
  },

  /**
   * Handle input change
   */
  onInput(e) {
    this.setData({
      value: e.detail.value
    });
  },

  /**
   * Handle gender change
   */
  onGenderChange(e) {
    this.setData({
      genderIndex: parseInt(e.detail.value)
    });
  },

  /**
   * Handle region change
   */
  onRegionChange(e) {
    const regionArray = e.detail.value;
    const regionDisplay = regionArray.join(' ');
    this.setData({
      regionValue: regionArray,
      regionDisplay
    });
  },

  /**
   * Handle save
   */
  async handleSave() {
    try {
      // Validate input
      if (this.data.fieldType === 'text') {
        const trimmedValue = this.data.value.trim();

        if (!trimmedValue) {
          wx.showToast({
            title: '请输入内容',
            icon: 'none'
          });
          return;
        }

        // Username validation
        if (this.data.field === 'username') {
          if (trimmedValue.length < 3) {
            wx.showToast({
              title: '敲敲ID至少3个字符',
              icon: 'none'
            });
            return;
          }

          // Check username format (letters, numbers, underscore)
          if (!/^[a-zA-Z0-9_]+$/.test(trimmedValue)) {
            wx.showToast({
              title: '敲敲ID只能包含字母、数字和下划线',
              icon: 'none'
            });
            return;
          }
        }
      } else if (this.data.fieldType === 'region') {
        if (!this.data.regionDisplay) {
          wx.showToast({
            title: '请选择地区',
            icon: 'none'
          });
          return;
        }
      }

      this.setData({ saving: true });

      // Prepare update data
      let updateData = {};
      if (this.data.fieldType === 'text') {
        updateData[this.data.field] = this.data.value.trim();
      } else if (this.data.fieldType === 'gender') {
        updateData.gender = this.data.genderIndex + 1;
      } else if (this.data.fieldType === 'region') {
        updateData.region = this.data.regionDisplay;
      }

      logger.info('Updating profile', { field: this.data.field, data: updateData });

      // Call API
      await put('/user/profile', updateData);

      wx.showToast({
        title: '保存成功',
        icon: 'success'
      });

      logger.info('Profile updated successfully', { field: this.data.field });

      // Navigate back after a short delay
      setTimeout(() => {
        wx.navigateBack();
      }, 1500);
    } catch (error) {
      logger.error('Update profile failed', {
        field: this.data.field,
        error: error.message || String(error)
      });

      wx.showToast({
        title: error.message || '保存失败,请稍后再试',
        icon: 'none'
      });

      this.setData({ saving: false });
    }
  }
});

