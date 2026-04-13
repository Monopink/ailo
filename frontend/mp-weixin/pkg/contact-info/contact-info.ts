import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { completeAvatarUpload } from '../../utils/avatar-uploader';
import { CONTACT_AVATAR_DISPLAY_MODE } from '../utils/constants/contact';
import { classifyError } from '../../utils/error-classifier';
import { getLogger } from '../../utils/logger';
import { isNonEmptyString } from '../../utils/guards';
import { normalizeError } from '../../utils/errors';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { type ScreenModel } from '../services/pages/page-state';
import {
  createContactInfoPageService,
  type ContactRecord,
} from '../services/pages/contact-info-service';
import { mapTagToneClasses } from '../../utils/tag-tone';

const logger = getLogger('ContactInfo');

type PageQuery = Record<string, string | undefined>;

interface ContactInfoPageData extends Record<string, unknown> {
  convId: string;
  contact: ContactRecord | null;
  avatarFrontUrl: string;
  avatarBackUrl: string;
  showAvatarStack: boolean;
  hasRemarkAvatar: boolean;
  isShowingRemarkAvatar: boolean;
  avatarUpdating: boolean;
  displayName: string;
  usernameDisplay: string;
  nicknameDisplay: string;
  aliasDisplay: string;
  remarkDisplay: string;
  hasRemark: boolean;
  tagsList: string[];
  tagsToneClasses: string[];
  hasTags: boolean;
  pageLayoutData: PageLayoutData;
}

interface ContactInfoPageCustom {
  contactInfoPageService: ReturnType<typeof createContactInfoPageService>;
  _lastRemoteRefreshAt: number;
  _needsRemoteRefresh: boolean;
  applyScreenModel(screenModel: ScreenModel): void;
  emitContactAvatarUpdated(): void;
  applyContactDisplay(contact: ContactRecord | null, screenModel?: ScreenModel): void;
  shouldRefreshOnShow(): boolean;
  markRemoteRefreshNeeded(): void;
  handleAuthInvalid(): Promise<void>;
  refreshContactInfo(): Promise<void>;
  onAvatarTap(): void;
  toggleAvatarDisplayMode(): Promise<void>;
  updateRemarkAvatar(): Promise<void>;
  clearRemarkAvatarWithConfirm(): Promise<void>;
  editAlias(): void;
  editRemark(): void;
  editTags(): void;
  editContactField(field: 'alias' | 'remark' | 'tags'): void;
  clearChatHistory(): void;
  deleteContact(): void;
}

interface AvatarDisplayState {
  avatarFrontUrl: string;
  avatarBackUrl: string;
  showAvatarStack: boolean;
  hasRemarkAvatar: boolean;
  isShowingRemarkAvatar: boolean;
}

const buildPageLayoutScreenModelPayload = (screenModel: ScreenModel): Record<string, unknown> => ({
  'pageLayoutData.screenModel': screenModel,
});

const showActionSheetSafe = async (
  itemList: string[],
  options?: { alertText?: string }
): Promise<number | null> => {
  try {
    const result = await new Promise<number>((resolve, reject) => {
      wx.showActionSheet({
        itemList,
        alertText: options?.alertText,
        success: (res) => resolve(res.tapIndex),
        fail: reject,
      });
    });
    return result;
  } catch (error) {
    const errMsg = (error as { errMsg?: string } | null)?.errMsg;
    if (typeof errMsg === 'string' && errMsg.toLowerCase().includes('cancel')) {
      return null;
    }
    throw error;
  }
};

const pickNonEmptyDisplay = (value: string | null | undefined): string =>
  typeof value === 'string' && value.trim().length > 0 ? value.trim() : '';

const resolveAvatarDisplayState = (contact: ContactRecord | null): AvatarDisplayState => {
  const fallbackAvatar = pickNonEmptyDisplay(contact?.displayAvatar);
  const rawOriginalAvatar = pickNonEmptyDisplay(contact?.original_avatar_url);
  const originalAvatar = rawOriginalAvatar !== '' ? rawOriginalAvatar : fallbackAvatar;
  const remarkAvatar = pickNonEmptyDisplay(contact?.remark_avatar_url);
  const hasRemarkAvatar = remarkAvatar !== '';
  const isShowingRemarkAvatar =
    hasRemarkAvatar && contact?.avatar_display_mode === CONTACT_AVATAR_DISPLAY_MODE.CUSTOM;
  const avatarFrontUrl = isShowingRemarkAvatar ? remarkAvatar : originalAvatar;
  const avatarBackUrl = hasRemarkAvatar
    ? isShowingRemarkAvatar
      ? originalAvatar
      : remarkAvatar
    : '';
  return {
    avatarFrontUrl,
    avatarBackUrl,
    showAvatarStack: hasRemarkAvatar,
    hasRemarkAvatar,
    isShowingRemarkAvatar,
  };
};

const buildContactDisplayPayload = (contact: ContactRecord | null): Record<string, unknown> => {
  const nicknameDisplay =
    typeof contact?.profile?.nickname === 'string' ? contact.profile.nickname.trim() : '';
  const aliasDisplay = typeof contact?.alias === 'string' ? contact.alias.trim() : '';
  const usernameDisplay = typeof contact?.username === 'string' ? contact.username.trim() : '';
  const remarkDisplay = typeof contact?.remark === 'string' ? contact.remark.trim() : '';
  const tagsList = Array.isArray(contact?.tags)
    ? contact.tags.reduce<string[]>((accumulator, tag) => {
        if (typeof tag !== 'string') {
          return accumulator;
        }
        const normalizedTag = tag.trim();
        if (normalizedTag !== '') {
          accumulator.push(normalizedTag);
        }
        return accumulator;
      }, [])
    : [];

  const avatarDisplayState = resolveAvatarDisplayState(contact);
  return {
    ...avatarDisplayState,
    displayName: aliasDisplay !== '' ? aliasDisplay : nicknameDisplay,
    usernameDisplay,
    nicknameDisplay,
    aliasDisplay,
    remarkDisplay,
    hasRemark: remarkDisplay !== '',
    tagsList,
    tagsToneClasses: mapTagToneClasses(tagsList),
    hasTags: tagsList.length > 0,
  };
};

const CONTACT_INFO_REFRESH_TTL_MS = 60_000;

Page<ContactInfoPageData, ContactInfoPageCustom>({
  data: {
    convId: '',
    contact: null,
    avatarFrontUrl: '',
    avatarBackUrl: '',
    showAvatarStack: false,
    hasRemarkAvatar: false,
    isShowingRemarkAvatar: false,
    avatarUpdating: false,
    displayName: '',
    usernameDisplay: '',
    nicknameDisplay: '',
    aliasDisplay: '',
    remarkDisplay: '',
    hasRemark: false,
    tagsList: [],
    tagsToneClasses: [],
    hasTags: false,
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      emptyMessage: '暂无内容',
      hasFooter: false,
    }),
  },

  applyScreenModel(screenModel: ScreenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  emitContactAvatarUpdated() {
    try {
      this.getOpenerEventChannel().emit('contactAvatarUpdated', { convId: this.data.convId });
    } catch (error) {
      logger.debug('No opener event channel for contact avatar update', {
        error: normalizeError(error).message,
      });
    }
  },

  applyContactDisplay(contact: ContactRecord | null, screenModel?: ScreenModel) {
    const payload: Record<string, unknown> = {
      contact,
      ...buildContactDisplayPayload(contact),
    };
    if (screenModel !== undefined) {
      Object.assign(payload, buildPageLayoutScreenModelPayload(screenModel));
    }
    this.setData(payload);
  },

  _lastRemoteRefreshAt: 0,
  _needsRemoteRefresh: false,

  shouldRefreshOnShow() {
    if (this._needsRemoteRefresh) {
      return true;
    }
    if (this._lastRemoteRefreshAt <= 0) {
      return true;
    }
    return Date.now() - this._lastRemoteRefreshAt >= CONTACT_INFO_REFRESH_TTL_MS;
  },

  markRemoteRefreshNeeded() {
    this._needsRemoteRefresh = true;
  },

  async handleAuthInvalid() {
    await showAuthExpiredModalAndRelogin();
  },

  contactInfoPageService: null as unknown as ReturnType<typeof createContactInfoPageService>,

  async onLoad(options: PageQuery) {
    this.contactInfoPageService = createContactInfoPageService();
    const convId = options.id ?? '';

    if (!isNonEmptyString(convId)) {
      this.applyScreenModel({
        screenState: 'ready',
        contentVariant: 'blank',
        refreshState: 'idle',
      });
      return;
    }

    this.setData({ convId });
    this.markRemoteRefreshNeeded();
    const bootstrap = await this.contactInfoPageService.bootstrap(convId);
    if (bootstrap !== null) {
      this.applyContactDisplay(bootstrap.contact, bootstrap.screenModel);
    }

    await this.refreshContactInfo();
  },

  onShow() {
    if (!isNonEmptyString(this.data.convId)) {
      return;
    }
    if (!this.shouldRefreshOnShow()) {
      return;
    }
    void this.refreshContactInfo();
  },

  onUnload() {
    this.contactInfoPageService.dispose();
  },

  async refreshContactInfo() {
    this.applyScreenModel({
      ...this.data.pageLayoutData.screenModel,
      screenState: 'ready',
      contentVariant: 'data',
      refreshState: 'refreshing',
    });

    const result = await this.contactInfoPageService.refresh(this.data.convId, this.data.contact);
    if (result === null) {
      return;
    }
    if (result.authInvalid) {
      await this.handleAuthInvalid();
      return;
    }
    this.applyContactDisplay(result.contact, result.screenModel);
    this._lastRemoteRefreshAt = Date.now();
    this._needsRemoteRefresh = false;
  },

  onAvatarTap() {
    if (this.data.avatarUpdating || !isNonEmptyString(this.data.convId)) {
      return;
    }

    if (!this.data.hasRemarkAvatar) {
      void (async () => {
        try {
          const selectedIndex = await showActionSheetSafe(['设置备注头像']);
          if (selectedIndex === 0) {
            await this.updateRemarkAvatar();
          }
        } catch (error) {
          logger.error('Avatar setup action sheet failed', {
            error: normalizeError(error).message,
          });
          void wx.showToast({ title: '操作失败，请重试', icon: 'none' });
        }
      })();
      return;
    }

    const toggleLabel = this.data.isShowingRemarkAvatar ? '展示原始头像' : '展示备注头像';
    void (async () => {
      try {
        const selectedIndex = await showActionSheetSafe(
          [toggleLabel, '更新备注头像', '清除备注头像'],
          { alertText: '警告：清除备注头像后将展示原始头像' }
        );
        if (selectedIndex === null) {
          return;
        }
        if (selectedIndex === 0) {
          await this.toggleAvatarDisplayMode();
          return;
        }
        if (selectedIndex === 1) {
          await this.updateRemarkAvatar();
          return;
        }
        if (selectedIndex === 2) {
          await this.clearRemarkAvatarWithConfirm();
        }
      } catch (error) {
        logger.error('Avatar action sheet failed', { error: normalizeError(error).message });
        void wx.showToast({ title: '操作失败，请重试', icon: 'none' });
      }
    })();
  },

  async toggleAvatarDisplayMode() {
    const contact = this.data.contact;
    if (contact === null || !this.data.hasRemarkAvatar) {
      return;
    }
    const nextMode =
      contact.avatar_display_mode === CONTACT_AVATAR_DISPLAY_MODE.CUSTOM
        ? CONTACT_AVATAR_DISPLAY_MODE.ORIGINAL
        : CONTACT_AVATAR_DISPLAY_MODE.CUSTOM;
    this.setData({ avatarUpdating: true });
    void wx.showLoading({ title: '更新中', mask: true });
    try {
      const updated = await this.contactInfoPageService.setAvatarDisplayMode(
        this.data.convId,
        nextMode
      );
      this.applyContactDisplay(updated);
      this._lastRemoteRefreshAt = Date.now();
      this._needsRemoteRefresh = false;
      this.emitContactAvatarUpdated();
    } catch (error) {
      const semantics = classifyError(error);
      if (semantics.reason === 'auth-invalid') {
        await this.handleAuthInvalid();
        return;
      }
      logger.error('Failed to toggle avatar display mode', {
        convId: this.data.convId,
        reason: semantics.reason,
        error: normalizeError(error).message,
      });
      void wx.showToast({ title: '更新失败，请重试', icon: 'none' });
    } finally {
      void wx.hideLoading();
      this.setData({ avatarUpdating: false });
    }
  },

  async updateRemarkAvatar() {
    if (!isNonEmptyString(this.data.convId) || this.data.avatarUpdating) {
      return;
    }
    const hadRemarkAvatar = this.data.hasRemarkAvatar;
    const uploadResult = await completeAvatarUpload({ page: 'contact-info' });
    if (uploadResult === null) {
      return;
    }

    this.setData({ avatarUpdating: true });
    void wx.showLoading({ title: '保存中', mask: true });
    try {
      const updated = await this.contactInfoPageService.setRemarkAvatar(
        this.data.convId,
        uploadResult.fileId
      );
      this.applyContactDisplay(updated);
      this._lastRemoteRefreshAt = Date.now();
      this._needsRemoteRefresh = false;
      this.emitContactAvatarUpdated();
      void wx.showToast({
        title: hadRemarkAvatar ? '备注头像已更新' : '备注头像已设置',
        icon: 'success',
      });
    } catch (error) {
      const semantics = classifyError(error);
      if (semantics.reason === 'auth-invalid') {
        await this.handleAuthInvalid();
        return;
      }
      logger.error('Failed to update remark avatar', {
        convId: this.data.convId,
        reason: semantics.reason,
        error: normalizeError(error).message,
      });
      void wx.showToast({ title: '保存失败，请重试', icon: 'none' });
    } finally {
      void wx.hideLoading();
      this.setData({ avatarUpdating: false });
    }
  },

  async clearRemarkAvatarWithConfirm() {
    if (
      !this.data.hasRemarkAvatar ||
      !isNonEmptyString(this.data.convId) ||
      this.data.avatarUpdating
    ) {
      return;
    }
    const confirm = await new Promise<boolean>((resolve) => {
      wx.showModal({
        title: '清除备注头像',
        content: '清除后将展示原始头像，确定继续吗？',
        confirmColor: '#ff4d4f',
        success: (result) => resolve(result.confirm === true),
        fail: () => resolve(false),
      });
    });
    if (!confirm) {
      return;
    }

    this.setData({ avatarUpdating: true });
    void wx.showLoading({ title: '更新中', mask: true });
    try {
      const updated = await this.contactInfoPageService.clearRemarkAvatar(this.data.convId);
      this.applyContactDisplay(updated);
      this._lastRemoteRefreshAt = Date.now();
      this._needsRemoteRefresh = false;
      this.emitContactAvatarUpdated();
      void wx.showToast({ title: '备注头像已清除', icon: 'success' });
    } catch (error) {
      const semantics = classifyError(error);
      if (semantics.reason === 'auth-invalid') {
        await this.handleAuthInvalid();
        return;
      }
      logger.error('Failed to clear remark avatar', {
        convId: this.data.convId,
        reason: semantics.reason,
        error: normalizeError(error).message,
      });
      void wx.showToast({ title: '清除失败，请重试', icon: 'none' });
    } finally {
      void wx.hideLoading();
      this.setData({ avatarUpdating: false });
    }
  },

  editAlias() {
    this.editContactField('alias');
  },

  editRemark() {
    this.editContactField('remark');
  },

  editTags() {
    this.editContactField('tags');
  },

  editContactField(field) {
    const contact = this.data.contact;
    if (contact === null) {
      return;
    }

    let rawValue = '';
    if (field === 'alias') {
      rawValue = contact.alias ?? '';
    } else if (field === 'remark') {
      rawValue = contact.remark ?? '';
    } else {
      rawValue = JSON.stringify(Array.isArray(contact.tags) ? contact.tags : []);
    }
    const encodedValue = encodeURIComponent(rawValue);
    const targetUrl = `/pkg/field-edit/field-edit?domain=contact&id=${this.data.convId}&field=${field}&value=${encodedValue}`;
    void wx.navigateTo({
      url: targetUrl,
      events: {
        contactFieldUpdated: () => {
          this.markRemoteRefreshNeeded();
          void this.refreshContactInfo();
        },
      },
    });
  },

  clearChatHistory() {
    void wx.showModal({
      title: '提示',
      content: '确定清空聊天记录吗？',
      success: async (res) => {
        if (res.confirm !== true) {
          return;
        }

        try {
          await this.contactInfoPageService.clearChatHistory(this.data.convId);
          this.markRemoteRefreshNeeded();
          await this.refreshContactInfo();
          void wx.showToast({
            title: '聊天记录已清空',
            icon: 'success',
          });
          logger.info('Chat history cleared', { conv_id: this.data.convId });
        } catch (error: unknown) {
          const err = normalizeError(error);
          logger.error('Failed to clear chat history', { error: err.message });
          void wx.showToast({
            title: '清空失败，请稍后重试',
            icon: 'none',
          });
        }
      },
    });
  },

  deleteContact() {
    void wx.showModal({
      title: '提示',
      content: '确定删除该联系人吗？删除后将从联系人列表移除。',
      confirmColor: '#ff4d4f',
      success: async (res) => {
        if (!res.confirm) {
          return;
        }

        void wx.showLoading({ title: '正在删除', mask: true });
        try {
          await this.contactInfoPageService.deleteContact(this.data.convId);

          void wx.showToast({
            title: '联系人已删除',
            icon: 'success',
          });

          logger.info('Contact deleted', { conv_id: this.data.convId });

          setTimeout(() => {
            void wx.navigateBack();
          }, 300);
        } catch (error: unknown) {
          const err = normalizeError(error);
          const safeMessage = isNonEmptyString(err.message) ? err.message : '删除失败，请稍后重试';
          logger.error('Failed to delete contact', { error: safeMessage });
          void wx.showToast({
            title: safeMessage,
            icon: 'none',
          });
        } finally {
          void wx.hideLoading();
        }
      },
    });
  },
});
