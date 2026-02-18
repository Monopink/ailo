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
import viewStore from '../../utils/message/view-store';
import { fetchConversationProfile, refreshStoredContact } from '../../utils/contact-service';
import type { ContactProfile } from '../../utils/schemas';
import { isNonEmptyString } from '../../utils/guards';
import { normalizeError } from '../../utils/errors';

const logger = getLogger('ContactInfo');

type PageQuery = Record<string, string | undefined>;

type ContactRecord = StoredContact & {
  is_pinned?: boolean;
  is_muted?: boolean;
  avatar_url?: string | null;
  bio?: string | null;
  region?: string | null;
  displayAvatar: string;
};

interface ContactInfoPageData extends Record<string, unknown> {
  convId: string;
  contact: ContactRecord | null;
  isPinned: boolean;
  isMuted: boolean;
  pageLayoutData: PageLayoutData;
}

interface ContactInfoPageCustom {
  refreshContactInfo(): Promise<void>;
  goToChat(): void;
  editRemarkAndTags(): void;
  onPinnedChange(event: WechatMiniprogram.SwitchChange): void;
  onMutedChange(event: WechatMiniprogram.SwitchChange): void;
  clearChatHistory(): void;
  deleteContact(): void;
}

const normalizeContact = (contact: StoredContact): ContactRecord => {
  const contactRecord = contact as ContactRecord;
  const profile: ContactProfile = contactRecord.profile ?? {};
  const avatarUrl = isNonEmptyString(profile.avatar_url) ? profile.avatar_url : undefined;
  const resolvedBio =
    typeof profile.bio === 'string' && profile.bio.trim().length > 0 ? profile.bio : undefined;
  const resolvedRegion =
    typeof profile.region === 'string' && profile.region.trim().length > 0
      ? profile.region
      : undefined;

  const normalizedAvatar = getAvatarUrl(avatarUrl ?? null);
  return {
    ...contactRecord,
    avatar_url: normalizedAvatar,
    bio: resolvedBio ?? contactRecord.bio ?? null,
    region: resolvedRegion ?? contactRecord.region ?? null,
    displayAvatar: normalizedAvatar,
  };
};
Page<ContactInfoPageData, ContactInfoPageCustom>({
  data: {
    convId: '',
    contact: null,
    isPinned: false,
    isMuted: false,
    pageLayoutData: createPageLayoutData({
      isLoading: true,
      emptyMessage: '暂无联系人资料',
      hasFooter: true,
    }),
  },

  async onLoad(options: PageQuery) {
    const convId = options.id ?? '';

    if (!isNonEmptyString(convId)) {
      void wx.showToast({
        title: '参数错误',
        icon: 'none',
      });
      void wx.navigateBack();
      return;
    }

    this.setData({ convId });

    const cachedContact = await getContactByConvId(convId);
    if (cachedContact !== null) {
      this.setData({
        contact: normalizeContact(cachedContact),
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
      const updated = await refreshStoredContact(this.data.convId, profile);

      if (updated === null) {
        this.setData({
          'pageLayoutData.isLoading': false,
          'pageLayoutData.isEmpty': this.data.contact === null,
        });
        return;
      }

      this.setData({
        contact: normalizeContact(updated),
        'pageLayoutData.isLoading': false,
        'pageLayoutData.isEmpty': false,
      });

      logger.info('Contact info refreshed', { conv_id: this.data.convId });
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to refresh contact info', { error: err.message });
      this.setData({
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': '加载资料失败，请稍后重试',
      });
    }
  },

  goToChat() {
    void wx.navigateTo({
      url: `/pages/chat/chat?id=${this.data.convId}`,
    });
  },

  editRemarkAndTags() {
    void wx.showToast({
      title: '功能即将上线',
      icon: 'none',
    });
  },

  onPinnedChange(event) {
    const isPinned = Boolean(event.detail.value);
    this.setData({ isPinned });
    logger.info('Pinned status changed', { conv_id: this.data.convId, is_pinned: isPinned });
    void wx.showToast({
      title: isPinned ? '置顶成功' : '已取消置顶',
      icon: 'success',
    });
  },

  onMutedChange(event) {
    const isMuted = Boolean(event.detail.value);
    this.setData({ isMuted });
    logger.info('Muted status changed', { conv_id: this.data.convId, is_muted: isMuted });
    void wx.showToast({
      title: isMuted ? '免打扰已开启' : '免打扰已关闭',
      icon: 'success',
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
          await clearMessages(this.data.convId);
          await viewStore.clear(this.data.convId);
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
          await del(`/contacts/${this.data.convId}`);
          const contacts = await getContacts();
          const updatedContacts = contacts.filter(
            (contact) => contact.conversation_id !== this.data.convId
          );
          await saveContacts(updatedContacts);
          await clearMessages(this.data.convId);
          await viewStore.clear(this.data.convId);

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
