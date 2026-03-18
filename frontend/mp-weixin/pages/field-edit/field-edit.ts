import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import type { ApiError } from '../../utils/api';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { classifyError } from '../../utils/error-classifier';
import { isDefined, isNonEmptyString } from '../../utils/guards';
import { getLogger } from '../../utils/logger';
import { createFieldEditPageService } from '../../services/pages/field-edit-service';
import type { ContactUpdatePayload } from '../../utils/contact-service';
import { mapTagToneClasses } from '../../utils/tag-tone';
import {
  CONTACT_ALIAS_RULE,
  CONTACT_REMARK_RULE,
  PROFILE_BIO_RULE,
  PROFILE_NICKNAME_RULE,
  getTextMetrics,
  validateTextLimit,
} from '../../utils/text-limit';

const logger = getLogger('FieldEdit');

type Domain = 'profile' | 'contact';
type FieldType = 'text' | 'region' | 'gender';
type ProfileFieldKey = 'nickname' | 'username' | 'bio' | 'region' | 'gender';
type ContactFieldKey = 'alias' | 'remark' | 'tags';
type FieldKey = ProfileFieldKey | ContactFieldKey;

const TAG_MAX_LENGTH = 20;
const TAG_SEPARATOR_REGEX = /[\n,，]/;
const TAG_END_SEPARATOR_REGEX = /[\n,，]$/;
const WHITESPACE_REGEX = /\s/u;

interface FieldConfig {
  title: string;
  placeholder: string;
  maxLength: number;
  hint: string;
  type: FieldType;
  multiline: boolean;
  submitText: string;
}

const PROFILE_FIELD_CONFIG: Record<ProfileFieldKey, FieldConfig> = {
  nickname: {
    title: '编辑昵称',
    placeholder: '昵称',
    maxLength: PROFILE_NICKNAME_RULE.displayWidthLimit,
    hint: '',
    type: 'text',
    multiline: false,
    submitText: '确认',
  },
  username: {
    title: '编辑敲敲号',
    placeholder: '敲敲号',
    maxLength: 20,
    hint: '5-20个字符，字母开头，可包含字母、数字、“_”和“-”',
    type: 'text',
    multiline: false,
    submitText: '确认',
  },
  bio: {
    title: '编辑个性签名',
    placeholder: '个性签名',
    maxLength: PROFILE_BIO_RULE.displayWidthLimit,
    hint: '',
    type: 'text',
    multiline: true,
    submitText: '确认',
  },
  region: {
    title: '编辑地区',
    placeholder: '',
    maxLength: 0,
    hint: '',
    type: 'region',
    multiline: false,
    submitText: '确认',
  },
  gender: {
    title: '编辑性别',
    placeholder: '',
    maxLength: 0,
    hint: '',
    type: 'gender',
    multiline: false,
    submitText: '确认',
  },
};

const CONTACT_FIELD_CONFIG: Record<ContactFieldKey, FieldConfig> = {
  alias: {
    title: '编辑备注',
    placeholder: '备注',
    maxLength: CONTACT_ALIAS_RULE.displayWidthLimit,
    hint: '',
    type: 'text',
    multiline: false,
    submitText: '保存',
  },
  remark: {
    title: '编辑描述',
    placeholder: '描述',
    maxLength: CONTACT_REMARK_RULE.displayWidthLimit,
    hint: '',
    type: 'text',
    multiline: true,
    submitText: '保存',
  },
  tags: {
    title: '编辑标签',
    placeholder: '新增标签',
    maxLength: 200,
    hint: '可添加多个标签，点击标签右侧可删除',
    type: 'text',
    multiline: false,
    submitText: '保存',
  },
};

interface FieldEditPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  domain: Domain | '';
  convId: string;
  navbarTitle: string;
  field: FieldKey | '';
  fieldType: FieldType | '';
  value: string;
  placeholder: string;
  maxLength: number;
  hint: string;
  isMultiline: boolean;
  isTagEditor: boolean;
  tags: string[];
  tagToneClasses: string[];
  tagDraft: string;
  saving: boolean;
  submitButtonText: string;
  genderOptions: string[];
  genderIndex: number;
  regionValue: string[];
  regionDisplay: string;
  regionCnCityCode: string | null;
  regionProvinceName: string | null;
  regionCityName: string | null;
  regionChanged: boolean;
  valueLength: number;
}

interface FieldEditPageCustom {
  fieldEditPageService: ReturnType<typeof createFieldEditPageService> | null;
  navigateBackWithParamError(delay?: number): void;
  initProfileField(rawField: string, options: Record<string, string | undefined>): boolean;
  initContactField(rawField: string, options: Record<string, string | undefined>): boolean;
  setTagState(tags: string[], tagDraft: string): void;
  appendTagSegments(segments: string[], nextDraft: string): boolean;
  flushTagDraft(): string[] | null;
  onUnload(): void;
  onInput(event: WechatMiniprogram.CustomEvent<{ value: string }>): void;
  onTagInput(event: WechatMiniprogram.CustomEvent<{ value: string }>): void;
  onTagConfirm(): void;
  onTagBlur(): void;
  onRemoveTag(event: WechatMiniprogram.TouchEvent): void;
  onGenderChange(event: WechatMiniprogram.PickerChange): void;
  onRegionChange(event: WechatMiniprogram.PickerChange): void;
  buildProfileUpdateData(): Record<string, unknown> | null;
  buildContactUpdateData(): ContactUpdatePayload | null;
  confirmUsernameSubmission(updateData: Record<string, unknown>): Promise<boolean>;
  saveProfileField(): Promise<boolean>;
  saveContactField(): Promise<boolean>;
  resetSubmitState(): void;
  handleSave(): Promise<void>;
}

const isProfileField = (field: string): field is ProfileFieldKey =>
  Object.prototype.hasOwnProperty.call(PROFILE_FIELD_CONFIG, field);

const isContactField = (field: string): field is ContactFieldKey =>
  Object.prototype.hasOwnProperty.call(CONTACT_FIELD_CONFIG, field);

const isDisplayWidthCounterField = (field: FieldKey | ''): field is 'nickname' | 'alias' =>
  field === 'nickname' || field === 'alias';

const getFieldValueLength = (field: FieldKey | '', value: string): number => {
  const metrics = getTextMetrics(value);
  if (isDisplayWidthCounterField(field)) {
    return metrics.displayWidth;
  }
  return metrics.graphemeCount;
};

const validateTrimmedTextWithRule = (
  value: string,
  fallbackMessage: string,
  rule: Parameters<typeof validateTextLimit>[1]
): boolean => {
  const validation = validateTextLimit(value, rule);
  if (!validation.valid) {
    showErrorToast(validation.message ?? fallbackMessage);
    return false;
  }
  return true;
};

const buildUsernameUpdateData = (value: string): Record<string, unknown> | null => {
  const usernameReason = resolveUsernameInputReason(value);
  if (isNonEmptyString(usernameReason)) {
    showErrorToast(resolveUsernameReasonMessage(usernameReason));
    return null;
  }
  return { username: value };
};

const buildBioUpdateData = (trimmedValue: string): Record<string, unknown> | null => {
  if (
    trimmedValue.length > 0 &&
    !validateTrimmedTextWithRule(trimmedValue, '个性签名格式不正确', PROFILE_BIO_RULE)
  ) {
    return null;
  }

  return {
    bio: trimmedValue.length > 0 ? trimmedValue : null,
  };
};

const buildNicknameUpdateData = (trimmedValue: string): Record<string, unknown> | null => {
  if (trimmedValue.length === 0) {
    showErrorToast('请输入内容');
    return null;
  }

  if (WHITESPACE_REGEX.test(trimmedValue)) {
    showErrorToast('昵称不能包含空格');
    return null;
  }

  if (!validateTrimmedTextWithRule(trimmedValue, '昵称格式不正确', PROFILE_NICKNAME_RULE)) {
    return null;
  }

  return {
    nickname: trimmedValue,
  };
};

const buildProfileTextUpdateData = (
  field: FieldEditPageData['field'],
  rawValue: string
): Record<string, unknown> | null => {
  if (field === 'username') {
    return buildUsernameUpdateData(rawValue);
  }

  const trimmedValue = rawValue.trim();
  if (field === 'bio') {
    return buildBioUpdateData(trimmedValue);
  }

  if (field === 'nickname') {
    return buildNicknameUpdateData(trimmedValue);
  }

  showErrorToast('参数错误');
  return null;
};

const decodeValue = (value?: string): string => {
  try {
    return decodeURIComponent(value ?? '');
  } catch {
    return value ?? '';
  }
};

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

const parseTagsFromQuery = (rawValue: string): string[] => {
  try {
    const parsed = JSON.parse(rawValue) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    const deduplicated = new Set<string>();
    const tags: string[] = [];
    for (const item of parsed) {
      if (typeof item !== 'string') {
        continue;
      }
      const tag = item.trim();
      if (tag === '' || deduplicated.has(tag)) {
        continue;
      }
      deduplicated.add(tag);
      tags.push(tag);
    }
    return tags;
  } catch {
    return [];
  }
};

const showErrorToast = (title: string): void => {
  void wx.showToast({
    title,
    icon: 'none',
  });
};

const showConfirmModal = async (content: string): Promise<boolean> => {
  try {
    const result = await wx.showModal({
      title: '确认使用敲敲号',
      content,
      confirmText: '确认',
      cancelText: '取消',
    });
    return result.confirm;
  } catch (error) {
    logger.error('Show modal failed', { error });
    return false;
  }
};

const USERNAME_REASON_MESSAGE: Record<string, string> = {
  USERNAME_EMPTY: '敲敲号不能为空',
  USERNAME_LEADING_OR_TRAILING_SPACES: '敲敲号不能以空格开头或结尾',
  USERNAME_TOO_SHORT: '敲敲号长度不能少于5个字符',
  USERNAME_TOO_LONG: '敲敲号长度不能超过20个字符',
  USERNAME_MUST_START_WITH_LETTER: '敲敲号必须以字母开头',
  USERNAME_INVALID_CHARACTERS: '敲敲号仅支持字母、数字、“_”和“-”',
  USERNAME_RESERVED: '该敲敲号不可使用',
  USERNAME_ALREADY_USED: '该用户名已被使用',
  USERNAME_CHECK_RATE_LIMIT_SHORT: '敲敲号检查过于频繁，请稍后再试',
  USERNAME_CHECK_RATE_LIMIT_LONG: '敲敲号检查次数过多，请稍后再试',
  USERNAME_SUBMIT_RATE_LIMIT: '敲敲号提交过于频繁，请稍后再试',
  USERNAME_LOCKED: '敲敲号不可修改',
};

const resolveUsernameInputReason = (value: string): string | null => {
  if (value.length === 0) {
    return 'USERNAME_EMPTY';
  }
  if (value.trim() !== value) {
    return 'USERNAME_LEADING_OR_TRAILING_SPACES';
  }
  if (value.length < 5) {
    return 'USERNAME_TOO_SHORT';
  }
  if (value.length > 20) {
    return 'USERNAME_TOO_LONG';
  }
  if (!/^[A-Za-z]/.test(value)) {
    return 'USERNAME_MUST_START_WITH_LETTER';
  }
  if (!/^[A-Za-z0-9_-]+$/.test(value)) {
    return 'USERNAME_INVALID_CHARACTERS';
  }
  return null;
};

const resolveUsernameReasonMessage = (reason: string): string => {
  const reasonMessage = USERNAME_REASON_MESSAGE[reason];
  if (isNonEmptyString(reasonMessage)) {
    return reasonMessage;
  }
  return '敲敲号格式有误';
};

const resolveSubmitErrorMessage = (error: unknown): string => {
  const apiReason = (error as Partial<ApiError>).reason;
  if (isNonEmptyString(apiReason)) {
    return resolveUsernameReasonMessage(apiReason);
  }
  if (error instanceof Error) {
    return error.message;
  }
  return '确认失败,请稍后再试';
};

const buildTagValueLength = (tags: string[], tagDraft: string): number => {
  const normalizedDraft = tagDraft.trim();
  const tagsLength = tags.join(', ').length;
  if (normalizedDraft.length === 0) {
    return tagsLength;
  }
  if (tagsLength === 0) {
    return normalizedDraft.length;
  }
  return tagsLength + 2 + normalizedDraft.length;
};

Page<FieldEditPageData, FieldEditPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      hasFooter: false,
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      emptyMessage: '',
    }),
    domain: '',
    convId: '',
    navbarTitle: '',
    field: '',
    fieldType: '',
    value: '',
    placeholder: '',
    maxLength: 0,
    hint: '',
    isMultiline: false,
    isTagEditor: false,
    tags: [],
    tagToneClasses: [],
    tagDraft: '',
    saving: false,
    submitButtonText: '确认',
    genderOptions: ['男', '女', '其他', '未知'],
    genderIndex: 0,
    regionValue: [],
    regionDisplay: '请选择地区',
    regionCnCityCode: null,
    regionProvinceName: null,
    regionCityName: null,
    regionChanged: false,
    valueLength: 0,
  },

  fieldEditPageService: null,

  navigateBackWithParamError(delay = 300) {
    showErrorToast('参数错误');
    setTimeout(() => {
      void wx.navigateBack();
    }, delay);
  },

  setTagState(tags, tagDraft) {
    this.setData({
      tags,
      tagToneClasses: mapTagToneClasses(tags),
      tagDraft,
      valueLength: buildTagValueLength(tags, tagDraft),
    });
  },

  appendTagSegments(segments, nextDraft) {
    const deduplicated = new Set(this.data.tags);
    const nextTags = [...this.data.tags];
    for (const segment of segments) {
      const tag = segment.trim();
      if (tag === '' || deduplicated.has(tag)) {
        continue;
      }
      if (tag.length > TAG_MAX_LENGTH) {
        showErrorToast(`单个标签最多${TAG_MAX_LENGTH}字符`);
        return false;
      }
      deduplicated.add(tag);
      nextTags.push(tag);
    }

    const nextLength = buildTagValueLength(nextTags, nextDraft);
    if (nextLength > this.data.maxLength) {
      showErrorToast(`最多${this.data.maxLength}字符`);
      return false;
    }

    this.setTagState(nextTags, nextDraft);
    return true;
  },

  flushTagDraft() {
    const draft = this.data.tagDraft.trim();
    if (draft === '') {
      return [...this.data.tags];
    }
    const deduplicated = new Set(this.data.tags);
    if (deduplicated.has(draft)) {
      this.setTagState(this.data.tags, '');
      return [...this.data.tags];
    }
    if (draft.length > TAG_MAX_LENGTH) {
      showErrorToast(`单个标签最多${TAG_MAX_LENGTH}字符`);
      return null;
    }
    const nextTags = [...this.data.tags, draft];
    const nextLength = buildTagValueLength(nextTags, '');
    if (nextLength > this.data.maxLength) {
      showErrorToast(`最多${this.data.maxLength}字符`);
      return null;
    }
    this.setTagState(nextTags, '');
    return nextTags;
  },

  initProfileField(rawField, options) {
    if (!isProfileField(rawField)) {
      return false;
    }

    const config = PROFILE_FIELD_CONFIG[rawField];
    this.setData({
      domain: 'profile',
      field: rawField,
      fieldType: config.type,
      navbarTitle: config.title,
      placeholder: config.placeholder,
      maxLength: config.maxLength,
      hint: config.hint,
      isMultiline: config.multiline,
      isTagEditor: false,
      submitButtonText: config.submitText,
    });

    if (config.type === 'gender') {
      const parsedValue = Number.parseInt(options.value ?? '0', 10);
      const genderValue = Number.isNaN(parsedValue) ? 0 : parsedValue;
      this.setData({
        genderIndex: genderValue > 0 ? genderValue - 1 : 0,
      });
      return true;
    }

    if (config.type === 'region') {
      const decodedValue = decodeValue(options.value);
      this.setData({
        regionDisplay: isNonEmptyString(decodedValue) ? decodedValue : '请选择地区',
        regionValue: [],
        regionCnCityCode: null,
        regionProvinceName: null,
        regionCityName: null,
        regionChanged: false,
      });
      return true;
    }

    const decodedValue = decodeValue(options.value);
    if (rawField === 'username' && isNonEmptyString(decodedValue)) {
      showErrorToast('敲敲号不可修改');
      setTimeout(() => {
        void wx.navigateBack();
      }, 300);
      return true;
    }

    this.setData({
      value: decodedValue,
      valueLength: getFieldValueLength(rawField, decodedValue),
    });
    return true;
  },

  initContactField(rawField, options) {
    if (!isContactField(rawField)) {
      return false;
    }

    const convId = options.id ?? '';
    if (!isNonEmptyString(convId)) {
      this.navigateBackWithParamError();
      return true;
    }

    const config = CONTACT_FIELD_CONFIG[rawField];
    this.setData({
      domain: 'contact',
      convId,
      field: rawField,
      fieldType: config.type,
      navbarTitle: config.title,
      placeholder: config.placeholder,
      maxLength: config.maxLength,
      hint: config.hint,
      isMultiline: config.multiline,
      isTagEditor: rawField === 'tags',
      submitButtonText: config.submitText,
    });

    if (rawField === 'tags') {
      const tags = parseTagsFromQuery(decodeValue(options.value));
      this.setTagState(tags, '');
      return true;
    }

    const value = decodeValue(options.value).trim();
    this.setData({
      value,
      valueLength: getFieldValueLength(rawField, value),
      tags: [],
      tagToneClasses: [],
      tagDraft: '',
    });
    return true;
  },

  onLoad(options: Record<string, string | undefined>) {
    this.fieldEditPageService = createFieldEditPageService();
    const domain = options.domain ?? '';
    const rawField = options.field ?? '';

    if (domain === 'profile' && this.initProfileField(rawField, options)) {
      return;
    }
    if (domain === 'contact' && this.initContactField(rawField, options)) {
      return;
    }

    this.navigateBackWithParamError();
  },

  onUnload() {
    this.fieldEditPageService?.dispose();
    this.fieldEditPageService = null;
  },

  onInput(event) {
    const value = event.detail.value;
    this.setData({
      value,
      valueLength: getFieldValueLength(this.data.field, value),
    });
  },

  onTagInput(event) {
    if (!this.data.isTagEditor) {
      return;
    }

    const rawValue = event.detail.value;
    if (!TAG_SEPARATOR_REGEX.test(rawValue)) {
      this.setTagState(this.data.tags, rawValue);
      return;
    }

    const parts = rawValue.split(TAG_SEPARATOR_REGEX);
    const hasTrailingSeparator = TAG_END_SEPARATOR_REGEX.test(rawValue);
    const segments = hasTrailingSeparator ? parts : parts.slice(0, -1);
    const nextDraft = hasTrailingSeparator ? '' : (parts[parts.length - 1] ?? '');
    void this.appendTagSegments(segments, nextDraft);
  },

  onTagConfirm() {
    if (!this.data.isTagEditor) {
      return;
    }
    void this.flushTagDraft();
  },

  onTagBlur() {
    if (!this.data.isTagEditor) {
      return;
    }
    void this.flushTagDraft();
  },

  onRemoveTag(event) {
    if (!this.data.isTagEditor) {
      return;
    }
    const index = Number.parseInt(String(event.currentTarget.dataset.index ?? '-1'), 10);
    if (Number.isNaN(index) || index < 0 || index >= this.data.tags.length) {
      return;
    }
    const nextTags = this.data.tags.filter((_, tagIndex) => tagIndex !== index);
    this.setTagState(nextTags, this.data.tagDraft);
  },

  onGenderChange(event) {
    this.setData({
      genderIndex: Number.parseInt(String(event.detail.value), 10),
    });
  },

  onRegionChange(event) {
    try {
      const detailRecord = (event as { detail?: unknown }).detail as
        | Record<string, unknown>
        | undefined;
      const regionArrayRaw = detailRecord?.value;
      const codeArrayRaw = detailRecord?.code;

      if (!Array.isArray(regionArrayRaw)) {
        logger.warn('Region picker detail.value is not an array', { detail: detailRecord });
        void wx.showToast({ title: '地区选择异常，请重试', icon: 'none' });
        return;
      }

      const regionArray = regionArrayRaw.map((item) => String(item));
      const codeArray = Array.isArray(codeArrayRaw) ? codeArrayRaw.map((item) => String(item)) : [];

      const [province = '', city = ''] = regionArray;
      const effectiveCity = isNonEmptyString(city) ? city : province;
      const regionDisplay = buildRegionDraftDisplay(province, effectiveCity);

      let candidateCode = '';
      if (codeArray.length >= 2) {
        candidateCode = codeArray[1];
      } else if (codeArray.length === 1) {
        candidateCode = codeArray[0];
      }
      const candidateCityCode = isNonEmptyString(candidateCode) ? candidateCode : null;

      this.setData({
        regionValue:
          isNonEmptyString(province) && isNonEmptyString(city)
            ? [province, city]
            : isNonEmptyString(province)
              ? [province]
              : [],
        regionDisplay,
        regionCnCityCode: candidateCityCode,
        regionProvinceName: isNonEmptyString(province) ? province : null,
        regionCityName: isNonEmptyString(effectiveCity) ? effectiveCity : null,
        regionChanged: true,
      });
    } catch (error) {
      logger.error('Region picker change handler crashed', { error });
      void wx.showToast({ title: '地区选择异常，请重试', icon: 'none' });
    }
  },

  buildProfileUpdateData() {
    if (this.data.fieldType === 'text') {
      return buildProfileTextUpdateData(this.data.field, this.data.value);
    }

    if (this.data.fieldType === 'gender') {
      return {
        gender: this.data.genderIndex + 1,
      };
    }

    if (this.data.fieldType === 'region') {
      if (!this.data.regionChanged) {
        showErrorToast('请选择地区');
        return null;
      }
      if (
        !isNonEmptyString(this.data.regionCnCityCode) ||
        !isNonEmptyString(this.data.regionProvinceName) ||
        !isNonEmptyString(this.data.regionCityName)
      ) {
        showErrorToast('请选择地区');
        return null;
      }
      return {
        region_country_code: 'CN',
        region_cn_city_code: this.data.regionCnCityCode,
        region_province_name: this.data.regionProvinceName,
        region_city_name: this.data.regionCityName,
      };
    }

    showErrorToast('参数错误');
    return null;
  },

  buildContactUpdateData() {
    if (!isNonEmptyString(this.data.convId)) {
      showErrorToast('参数错误');
      return null;
    }

    const payload: ContactUpdatePayload = {};
    if (this.data.field === 'tags') {
      const tags = this.flushTagDraft();
      if (!isDefined(tags)) {
        return null;
      }
      payload.tags = tags;
      return payload;
    }

    if (this.data.field === 'alias' || this.data.field === 'remark') {
      const normalizedValue = this.data.value.trim();
      if (normalizedValue.length > 0) {
        const rule = this.data.field === 'alias' ? CONTACT_ALIAS_RULE : CONTACT_REMARK_RULE;
        const validation = validateTextLimit(normalizedValue, rule);
        if (!validation.valid) {
          showErrorToast(validation.message ?? '内容格式不正确');
          return null;
        }
      }
      payload[this.data.field] = normalizedValue.length > 0 ? normalizedValue : null;
      return payload;
    }

    showErrorToast('参数错误');
    return null;
  },

  async confirmUsernameSubmission(updateData) {
    if (this.data.domain !== 'profile' || this.data.field !== 'username') {
      return true;
    }

    const usernameValue = updateData.username;
    if (typeof usernameValue !== 'string' || !isNonEmptyString(usernameValue)) {
      return true;
    }

    this.setData({ submitButtonText: '校验中...' });
    if (this.fieldEditPageService === null) {
      showErrorToast('页面初始化失败');
      return false;
    }
    const stillActive = await this.fieldEditPageService.checkUsernameAvailability(usernameValue);
    if (!stillActive) {
      return false;
    }
    return await showConfirmModal(`敲敲号「${usernameValue}」设置后不可修改，是否确认使用？`);
  },

  resetSubmitState() {
    this.setData({
      saving: false,
      submitButtonText: this.data.domain === 'contact' ? '保存' : '确认',
    });
  },

  async saveProfileField() {
    if (this.fieldEditPageService === null) {
      showErrorToast('页面初始化失败');
      this.resetSubmitState();
      return false;
    }

    const updateData = this.buildProfileUpdateData();
    if (!isDefined(updateData)) {
      this.resetSubmitState();
      return false;
    }

    const confirmed = await this.confirmUsernameSubmission(updateData);
    if (!confirmed) {
      this.resetSubmitState();
      return false;
    }

    this.setData({ submitButtonText: '提交中...' });
    const stillActive = await this.fieldEditPageService.updateProfile(updateData);
    if (!stillActive) {
      return false;
    }

    void wx.showToast({
      title: '修改成功',
      icon: 'success',
    });
    setTimeout(() => {
      void wx.navigateBack();
    }, 1500);
    return true;
  },

  async saveContactField() {
    if (this.fieldEditPageService === null) {
      showErrorToast('页面初始化失败');
      this.resetSubmitState();
      return false;
    }

    const payload = this.buildContactUpdateData();
    if (!isDefined(payload)) {
      this.resetSubmitState();
      return false;
    }

    const stillActive = await this.fieldEditPageService.updateContactField(
      this.data.convId,
      payload
    );
    if (!stillActive) {
      return false;
    }

    void wx.showToast({
      title: '更新成功',
      icon: 'success',
    });

    try {
      const eventChannel = this.getOpenerEventChannel();
      eventChannel.emit('contactFieldUpdated');
    } catch (error: unknown) {
      logger.warn('Failed to emit contactFieldUpdated event', {
        error: error instanceof Error ? error.message : String(error),
      });
    }

    setTimeout(() => {
      void wx.navigateBack();
    }, 300);
    return true;
  },

  async handleSave() {
    if (this.data.saving) {
      return;
    }

    try {
      this.setData({
        saving: true,
        submitButtonText: this.data.domain === 'contact' ? '保存中...' : '确认中...',
      });

      if (this.data.domain === 'profile') {
        await this.saveProfileField();
        return;
      }

      if (this.data.domain === 'contact') {
        await this.saveContactField();
        return;
      }

      showErrorToast('参数错误');
      this.resetSubmitState();
    } catch (error) {
      const semantics = classifyError(error);
      if (semantics.reason === 'auth-invalid') {
        await showAuthExpiredModalAndRelogin();
        return;
      }

      logger.error('Field update failed', {
        domain: this.data.domain,
        field: this.data.field,
        error,
      });

      if (this.data.domain === 'profile') {
        showErrorToast(resolveSubmitErrorMessage(error));
      } else {
        showErrorToast('保存失败，请稍后重试');
      }
    } finally {
      this.resetSubmitState();
    }
  },
});
