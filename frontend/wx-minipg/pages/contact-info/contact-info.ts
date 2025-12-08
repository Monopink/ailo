import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { del, get } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';
import {
  clearMessages,
  getContactByConvId,
  getContacts,
  saveContacts,
  type StoredContact,
  type StoredContacts,
} from '../../utils/storage';

const logger = getLogger('ContactInfo');

type PageQuery = Record<string, string | undefined>;

interface ContactProfile {
  nickname?: string;
  avatar_url?: string;
  gender?: number | null;
  bio?: string;
  region?: string;
  [key: string]: unknown;
}

interface ConversationResponse {
  contact_profile?: ContactProfile;
}

type ContactRecord = StoredContact & {
  is_pinned?: boolean;
  is_muted?: boolean;
  custom_avatar_url?: string | null;
  avatar_url?: string | null;
  bio?: string | null;
  region?: string | null;
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
  const profile =
    (contact.profile as ContactProfile | undefined) ??
    (contact.contact_profile as ContactProfile | undefined) ??
    {};

  const avatarFallback = profile.avatar_url ?? '';
  const avatarUrl = contact.avatar_url ?? avatarFallback;

  const resolvedGender =
    typeof contact.gender === 'number'
      ? contact.gender
      : typeof profile.gender === 'number'
        ? profile.gender
        : null;

  const resolvedBio =
    typeof profile.bio === 'string' && profile.bio.trim().length > 0 ? profile.bio : undefined;
  const resolvedRegion =
    typeof profile.region === 'string' && profile.region.trim().length > 0
      ? profile.region
      : undefined;

  return {
    ...contact,
    avatar_url: getAvatarUrl(avatarUrl ?? ''),
    custom_avatar_url: contact.custom_avatar_url
      ? getAvatarUrl(contact.custom_avatar_url)
      : undefined,
    gender: resolvedGender,
    bio: resolvedBio ?? (typeof contact.bio === 'string' ? contact.bio : undefined) ?? null,
    region:
      resolvedRegion ?? (typeof contact.region === 'string' ? contact.region : undefined) ?? null,
  };
};

const toErrorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  try {
    return JSON.stringify(error);
  } catch {
    return '未知错误';
  }
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
    const convId = options?.id;

    if (!convId) {
      void wx.showToast({
        title: '参数错误',
        icon: 'none',
      });
      void wx.navigateBack();
      return;
    }

    this.setData({ convId });

    const cachedContact = await getContactByConvId(convId);
    if (cachedContact) {
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
      const conversation = await get<ConversationResponse>(
        `/contacts/${this.data.convId}/conversation`
      );
      const profile = conversation?.contact_profile ?? {};

      const contacts = await getContacts();
      const index = contacts.findIndex((contact) => contact.conv_id === this.data.convId);

      if (index === -1) {
        return;
      }

      const updatedContacts: StoredContacts = [...contacts];
      const existing = updatedContacts[index];

      updatedContacts[index] = {
        ...existing,
        nickname: profile.nickname ?? existing.nickname,
        avatar_url: profile.avatar_url ?? existing.avatar_url,
        gender: profile.gender ?? existing.gender,
        profile: {
          ...(existing.profile ?? {}),
          ...profile,
        },
      };

      await saveContacts(updatedContacts);

      this.setData({
        contact: normalizeContact(updatedContacts[index]),
        'pageLayoutData.isLoading': false,
        'pageLayoutData.isEmpty': false,
      });

      logger.info('Contact info refreshed', { conv_id: this.data.convId });
    } catch (error) {
      logger.error('Failed to refresh contact info', { error: toErrorMessage(error) });
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
      title: '功能开发中',
      icon: 'none',
    });
  },

  onPinnedChange(event) {
    const isPinned = Boolean(event.detail.value);
    this.setData({ isPinned });
    logger.info('Pinned status changed', { conv_id: this.data.convId, is_pinned: isPinned });
    void wx.showToast({
      title: isPinned ? '已置顶' : '已取消置顶',
      icon: 'success',
    });
  },

  onMutedChange(event) {
    const isMuted = Boolean(event.detail.value);
    this.setData({ isMuted });
    logger.info('Muted status changed', { conv_id: this.data.convId, is_muted: isMuted });
    void wx.showToast({
      title: isMuted ? '已开启免打扰' : '已关闭免打扰',
      icon: 'success',
    });
  },

  clearChatHistory() {
    void wx.showModal({
      title: '提示',
      content: '确定清空聊天记录吗？',
      success: async (res) => {
        if (!res.confirm) {
          return;
        }

        try {
          await clearMessages(this.data.convId);
          void wx.showToast({
            title: '已清空',
            icon: 'success',
          });
          logger.info('Chat history cleared', { conv_id: this.data.convId });
        } catch (error) {
          logger.error('Failed to clear chat history', { error: toErrorMessage(error) });
          void wx.showToast({
            title: '清空失败',
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
            (contact) => contact.conv_id !== this.data.convId
          );
          await saveContacts(updatedContacts);
          await clearMessages(this.data.convId);

          void wx.showToast({
            title: '已删除',
            icon: 'success',
          });

          logger.info('Contact deleted', { conv_id: this.data.convId });

          setTimeout(() => {
            void wx.navigateBack();
          }, 300);
        } catch (error) {
          const message = toErrorMessage(error) || '删除失败，请稍后重试';
          logger.error('Failed to delete contact', { error: message });
          void wx.showToast({
            title: message,
            icon: 'none',
          });
        } finally {
          void wx.hideLoading();
        }
      },
    });
  },
});
