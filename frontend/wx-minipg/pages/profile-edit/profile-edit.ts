import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { formatRegion } from '../../utils/format';
import { getLogger } from '../../utils/logger';
import { updateCurrentUserProfile } from '../../utils/profile';

const logger = getLogger('ProfileEdit');

type FieldType = 'text' | 'region' | 'gender';

interface FieldConfig {
  title: string;
  label: string;
  placeholder: string;
  maxLength: number;
  hint: string;
  type: FieldType;
}

const FIELD_CONFIG = {
  nickname: {
    title: '编辑昵称',
    label: '昵称',
    placeholder: '请输入昵称',
    maxLength: 10,
    hint: '',
    type: 'text',
  },
  username: {
    title: '编辑敲敲号',
    label: '敲敲号',
    placeholder: '请输入敲敲号',
    maxLength: 20,
    hint: '敲敲号可以包含字母、数字和下划线，3-20个字符',
    type: 'text',
  },
  bio: {
    title: '编辑个性签名',
    label: '个性签名',
    placeholder: '请输入个性签名',
    maxLength: 70,
    hint: '',
    type: 'text',
  },
  region: {
    title: '编辑地区',
    label: '地区',
    placeholder: '',
    maxLength: 0,
    hint: '',
    type: 'region',
  },
  gender: {
    title: '编辑性别',
    label: '性别',
    placeholder: '',
    maxLength: 0,
    hint: '',
    type: 'gender',
  },
} as const satisfies Record<string, FieldConfig>;

type FieldKey = keyof typeof FIELD_CONFIG;

interface ProfileEditPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  field: FieldKey | '';
  fieldType: FieldType | '';
  fieldLabel: string;
  value: string;
  placeholder: string;
  maxLength: number;
  hint: string;
  saving: boolean;
  submitButtonText: string;
  genderOptions: string[];
  genderIndex: number;
  regionValue: string[];
  regionDisplay: string;
  valueLength: number;
}

interface ProfileEditPageCustom {
  onInput(event: WechatMiniprogram.CustomEvent<{ value: string }>): void;
  onGenderChange(event: WechatMiniprogram.PickerChange): void;
  onRegionChange(event: WechatMiniprogram.PickerChange): void;
  handleSave(): Promise<void>;
  onRetry(): void;
}

const decodeValue = (value?: string): string => {
  try {
    return decodeURIComponent(value ?? '');
  } catch {
    return value ?? '';
  }
};

const showErrorToast = (title: string): void => {
  void wx.showToast({
    title,
    icon: 'none',
  });
};

Page<ProfileEditPageData, ProfileEditPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      hasFooter: true,
      emptyMessage: '暂无可编辑字段',
    }),
    field: '',
    fieldType: '',
    fieldLabel: '',
    value: '',
    placeholder: '',
    maxLength: 0,
    hint: '',
    saving: false,
    submitButtonText: '保存',
    genderOptions: ['男', '女', '其他', '未知'],
    genderIndex: 0,
    regionValue: [],
    regionDisplay: '请选择地区',
    valueLength: 0,
  },

  onLoad(options) {
    const rawField = (options?.field ?? '') as FieldKey;
    const config = FIELD_CONFIG[rawField];

    if (!config) {
      showErrorToast('参数错误');
      this.setData({
        'pageLayoutData.hasFooter': false,
        'pageLayoutData.isEmpty': true,
        'pageLayoutData.emptyMessage': '参数错误，无法编辑',
      });
      setTimeout(() => {
        void wx.navigateBack();
      }, 1500);
      return;
    }

    void wx.setNavigationBarTitle({
      title: config.title,
    });

    if (config.type === 'gender') {
      const genderValue = Number.parseInt(options?.value ?? '0', 10) || 0;
      this.setData({
        field: rawField,
        fieldType: config.type,
        fieldLabel: config.label,
        genderIndex: genderValue > 0 ? genderValue - 1 : 0,
        placeholder: config.placeholder,
        maxLength: config.maxLength,
        hint: config.hint,
        'pageLayoutData.isEmpty': false,
      });
      return;
    }

    if (config.type === 'region') {
      const decodedValue = decodeValue(options?.value);
      this.setData({
        field: rawField,
        fieldType: config.type,
        fieldLabel: config.label,
        regionDisplay: decodedValue || '请选择地区',
        regionValue: [],
        'pageLayoutData.isEmpty': false,
      });
      return;
    }

    const decodedValue = decodeValue(options?.value);
    this.setData({
      field: rawField,
      fieldType: config.type,
      fieldLabel: config.label,
      value: decodedValue,
      placeholder: config.placeholder,
      maxLength: config.maxLength,
      hint: config.hint,
      valueLength: decodedValue.length,
      'pageLayoutData.isEmpty': false,
    });

    logger.info('Profile edit page loaded', { field: rawField });
  },

  onInput(event) {
    const value = event.detail.value || '';
    this.setData({
      value: value,
      valueLength: value.length,
    });
  },

  onGenderChange(event) {
    this.setData({
      genderIndex: Number.parseInt(String(event.detail.value), 10),
    });
  },

  onRegionChange(event) {
    const regionArray = event.detail.value as string[];
    const [province = '', city = '', district = ''] = regionArray;

    let actualCity: string | null = city;

    if (city === '省直辖县级行政区划' || city === '自治区直辖县级行政区划') {
      actualCity = district;
    } else if (city === '县') {
      actualCity = null;
    }

    const regionDisplay = actualCity
      ? formatRegion(province, actualCity)
      : formatRegion(province, province);
    this.setData({
      regionValue: actualCity ? [province, actualCity] : [province],
      regionDisplay,
    });
  },

  async handleSave() {
    try {
      if (this.data.saving) {
        return;
      }

      if (this.data.fieldType === 'text') {
        const trimmedValue = this.data.value.trim();

        if (!trimmedValue) {
          showErrorToast('请输入内容');
          return;
        }

        if (this.data.field === 'username') {
          if (trimmedValue.length < 3) {
            showErrorToast('敲敲号至少3个字符');
            return;
          }

          if (!/^[a-zA-Z0-9_]+$/.test(trimmedValue)) {
            showErrorToast('敲敲号只能包含字母、数字和下划线');
            return;
          }
        }
      } else if (this.data.fieldType === 'region') {
        if (!this.data.regionDisplay) {
          showErrorToast('请选择地区');
          return;
        }
      }

      this.setData({ saving: true, submitButtonText: '保存中...' });

      const updateData: Record<string, unknown> = {};
      if (this.data.fieldType === 'text' && this.data.field) {
        updateData[this.data.field] = this.data.value.trim();
      } else if (this.data.fieldType === 'gender') {
        updateData.gender = this.data.genderIndex + 1;
      } else if (this.data.fieldType === 'region') {
        updateData.region = this.data.regionDisplay;
      }

      logger.info('Updating profile', { field: this.data.field, data: updateData });

      await updateCurrentUserProfile(updateData);

      void wx.showToast({
        title: '保存成功',
        icon: 'success',
      });

      logger.info('Profile updated successfully', { field: this.data.field });

      setTimeout(() => {
        void wx.navigateBack();
      }, 1500);
    } catch (error) {
      logger.error('Update profile failed', {
        field: this.data.field,
        error,
      });

      const message = error instanceof Error ? error.message : '保存失败,请稍后再试';
      showErrorToast(message);
      this.setData({ saving: false, submitButtonText: '保存' });
    }
  },

  onRetry() {
    // 编辑页无需远程加载，重试逻辑留空即可避免 page-layout 报错
    logger.warn('ProfileEdit retry invoked but no remote data to reload');
  },
});
