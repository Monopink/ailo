import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { del } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';
import {
  clearMessages,
  getContactByConvId,
  getContacts,
  saveContacts,
  type StoredContact,
} from '../../utils/storage';
import { fetchConversationProfile, refreshStoredContact } from '../../utils/contact-service';
import type { ContactProfile } from '../../utils/schemas';
import messageStateStore from '../../utils/message/message-state-store';
import viewStore from '../../utils/message/view-store';
import { isNonEmptyString } from '../../utils/guards';
import { normalizeError } from '../../utils/errors';

const logger = getLogger('ChatDetail');

interface ContactView {
  avatar: string;
  name: string;
  genderLabel: string;
  genderType: 'success' | 'danger' | 'default';
  hasGender: boolean;
  displayQiaoId: string;
}

interface ChatDetailPageData extends Record<string, unknown> {
  convId: string;
  contact: StoredContact | null;
  contactView: ContactView;
  isPinned: boolean;
  isMuted: boolean;
  pageLayoutData: PageLayoutData;
}

interface ChatDetailPageCustom {
  refreshContactInfo(): Promise<void>;
  goToChat(): void;
  viewProfile(): void;
  manageTags(): void;
  onPinnedChange(event: WechatMiniprogram.SwitchChange): void;
  onMutedChange(event: WechatMiniprogram.SwitchChange): void;
  clearChatHistory(): void;
  deleteContact(): void;
  onRetry(): void;
}

const DEFAULT_CONTACT_AVATAR = getAvatarUrl(null);

const createEmptyContactView = (): ContactView => ({
  avatar: DEFAULT_CONTACT_AVATAR,
  name: '',
  genderLabel: '',
  genderType: 'default',
  hasGender: false,
  displayQiaoId: '--',
});

const DEFAULT_CONTACT_NAME = '未命名联系人';

const sanitizeNameCandidate = (value: string | null | undefined): string | undefined =>
  isNonEmptyString(value) ? value : undefined;

const getDisplayName = (contact: StoredContact, profile: ContactProfile): string =>
  sanitizeNameCandidate(contact.alias) ??
  sanitizeNameCandidate(profile.nickname) ??
  sanitizeNameCandidate(contact.contact_qiao_id) ??
  DEFAULT_CONTACT_NAME;

const getResolvedAvatar = (profile: ContactProfile): string => {
  const avatarUrl = isNonEmptyString(profile.avatar_url) ? profile.avatar_url : null;
  const candidate = getAvatarUrl(avatarUrl);
  return isNonEmptyString(candidate) ? candidate : DEFAULT_CONTACT_AVATAR;
};

const getDisplayQiaoId = (contact: StoredContact): string =>
  isNonEmptyString(contact.contact_qiao_id) ? contact.contact_qiao_id : '--';

const getGenderLabel = (genderValue: number | null): string =>
  genderValue === 1 ? '男' : genderValue === 2 ? '女' : genderValue === 3 ? '其他' : '';

const buildContactView = (contact: StoredContact, profile?: ContactProfile): ContactView => {
  const resolvedProfile: ContactProfile = profile ?? contact.profile ?? {};
  const genderValue = typeof resolvedProfile.gender === 'number' ? resolvedProfile.gender : null;
  const genderLabel = getGenderLabel(genderValue);

  return {
    avatar: getResolvedAvatar(resolvedProfile),
    name: getDisplayName(contact, resolvedProfile),
    genderLabel,
    genderType: genderValue === 1 ? 'success' : genderValue === 2 ? 'danger' : 'default',
    hasGender: genderLabel !== '',
    displayQiaoId: getDisplayQiaoId(contact),
  };
};

Page<ChatDetailPageData, ChatDetailPageCustom>({
  data: {
    convId: '',
    contact: null,
    contactView: createEmptyContactView(),
    isPinned: false,
    isMuted: false,
    pageLayoutData: createPageLayoutData({
      isLoading: true,
      emptyMessage: '暂无会话详情',
      hasFooter: true,
    }),
  },

  async onLoad(options) {
    const convId = options.id ?? '';
    if (convId === '') {
      void wx.showToast({ title: '参数错误', icon: 'none' });
      void wx.navigateBack();
      return;
    }

    this.setData({ convId });

    const cachedContact = await getContactByConvId(convId);
    if (cachedContact !== null) {
      this.setData({
        contact: cachedContact,
        contactView: buildContactView(cachedContact),
        isPinned: Boolean(cachedContact.is_pinned),
        isMuted: Boolean(cachedContact.is_muted),
        'pageLayoutData.isLoading': false,
        'pageLayoutData.isEmpty': false,
      });
    }

    await this.refreshContactInfo();
  },

  async refreshContactInfo() {
    try {
      const profile = await fetchConversationProfile(this.data.convId);
      const updatedContact = await refreshStoredContact(this.data.convId, profile);
      if (updatedContact === null) {
        this.setData({
          'pageLayoutData.isLoading': false,
          'pageLayoutData.isEmpty': this.data.contact === null,
        });
        return;
      }

      this.setData({
        contact: updatedContact,
        contactView: buildContactView(updatedContact, profile ?? undefined),
        'pageLayoutData.isLoading': false,
        'pageLayoutData.isEmpty': false,
      });
      logger.info('Chat detail refreshed', { conv_id: this.data.convId });
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to refresh chat detail', { error: err.message });
      this.setData({
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': '加载失败，请稍后重试',
      });
    }
  },

  goToChat() {
    void wx.navigateTo({
      url: `/pages/chat/chat?id=${this.data.convId}`,
    });
  },

  viewProfile() {
    void wx.navigateTo({
      url: `/pages/contact-info/contact-info?id=${this.data.convId}`,
    });
  },

  manageTags() {
    void wx.showToast({ title: '标签管理功能即将上线', icon: 'none' });
  },

  onPinnedChange(event) {
    const isPinned = Boolean(event.detail.value);
    this.setData({ isPinned });
    void wx.showToast({ title: isPinned ? '置顶成功' : '已取消置顶', icon: 'success' });
  },

  onMutedChange(event) {
    const isMuted = Boolean(event.detail.value);
    this.setData({ isMuted });
    void wx.showToast({ title: isMuted ? '免打扰已开启' : '免打扰已关闭', icon: 'success' });
  },

  clearChatHistory() {
    void wx.showModal({
      title: '清空聊天记录',
      content: '确定清空此会话的所有消息吗？',
      success: async (result) => {
        if (!result.confirm) {
          return;
        }
        try {
          await clearMessages(this.data.convId);
          await viewStore.clear(this.data.convId);
          messageStateStore.clearConversation();
          void wx.showToast({ title: '聊天记录已清空', icon: 'success' });
        } catch (error: unknown) {
          const err = normalizeError(error);
          logger.error('Failed to clear chat history', { error: err.message });
          void wx.showToast({ title: '清空失败，请稍后重试', icon: 'none' });
        }
      },
    });
  },

  deleteContact() {
    void wx.showModal({
      title: '删除联系人',
      content: '删除后将移除联系人并清空聊天记录，确定继续？',
      confirmColor: '#ff4d4f',
      success: async (result) => {
        if (!result.confirm) {
          return;
        }
        void wx.showLoading({ title: '正在处理', mask: true });
        try {
          await del(`/contacts/${this.data.convId}`);
          const contacts = await getContacts();
          const updatedContacts = contacts.filter(
            (contact) => contact.conversation_id !== this.data.convId
          );
          await saveContacts(updatedContacts);
          await clearMessages(this.data.convId);
          await viewStore.clear(this.data.convId);
          messageStateStore.clearConversation();
          void wx.showToast({ title: '联系人已删除', icon: 'success' });
          setTimeout(() => {
            void wx.navigateBack();
          }, 300);
        } catch (error: unknown) {
          const err = normalizeError(error);
          logger.error('Failed to delete contact', { error: err.message });
          void wx.showToast({ title: '删除失败，请稍后重试', icon: 'none' });
        } finally {
          void wx.hideLoading();
        }
      },
    });
  },

  onRetry() {
    void this.refreshContactInfo();
  },
});
