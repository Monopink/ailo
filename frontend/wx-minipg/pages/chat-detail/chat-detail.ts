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

const logger = getLogger('ChatDetail');

interface ContactProfile {
  nickname?: string;
  avatar_url?: string;
  gender?: number | null;
  bio?: string | null;
  region?: string | null;
}

interface ConversationResponse {
  contact_profile?: ContactProfile;
}

interface ContactView {
  avatar: string;
  name: string;
  genderLabel: string;
  genderType: 'success' | 'danger' | 'default';
  hasGender: boolean;
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

const createEmptyContactView = (): ContactView => ({
  avatar: '/assets/avatars/default.png',
  name: '',
  genderLabel: '',
  genderType: 'default',
  hasGender: false,
});

const buildContactView = (contact: StoredContact, profile?: ContactProfile): ContactView => {
  const avatarSource =
    profile?.avatar_url ??
    contact.avatar_url ??
    contact.custom_avatar_url ??
    '/assets/avatars/default.png';
  const avatar = getAvatarUrl(avatarSource);
  const alias = contact.alias ?? '';
  const nickname = contact.nickname ?? profile?.nickname ?? '';
  const displayName = alias || nickname || contact.contact_qiao_id || '未命名联系人';
  const genderValue =
    typeof contact.gender === 'number'
      ? contact.gender
      : typeof profile?.gender === 'number'
        ? profile.gender
        : null;
  const genderLabel =
    genderValue === 1 ? '男' : genderValue === 2 ? '女' : genderValue === 3 ? '其他' : '';

  return {
    avatar,
    name: displayName,
    genderLabel,
    genderType: genderValue === 1 ? 'success' : genderValue === 2 ? 'danger' : 'default',
    hasGender: Boolean(genderLabel),
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
    const convId = options?.id;
    if (!convId) {
      void wx.showToast({ title: '参数错误', icon: 'none' });
      void wx.navigateBack();
      return;
    }

    this.setData({ convId });

    const cachedContact = await getContactByConvId(convId);
    if (cachedContact) {
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
      const conversation = await get<ConversationResponse>(
        `/contacts/${this.data.convId}/conversation`
      );
      const profile = conversation?.contact_profile ?? {};
      const contacts = await getContacts();
      const index = contacts.findIndex((contact) => contact.conv_id === this.data.convId);
      if (index === -1) {
        this.setData({
          'pageLayoutData.isLoading': false,
          'pageLayoutData.isEmpty': !this.data.contact,
        });
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
        contact: updatedContacts[index],
        contactView: buildContactView(updatedContacts[index], profile),
        'pageLayoutData.isLoading': false,
        'pageLayoutData.isEmpty': false,
      });
      logger.info('Chat detail refreshed', { conv_id: this.data.convId });
    } catch (error) {
      logger.error('Failed to refresh chat detail', {
        error: error instanceof Error ? error.message : error,
      });
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
    void wx.showToast({ title: '标签管理开发中', icon: 'none' });
  },

  onPinnedChange(event) {
    const isPinned = Boolean(event.detail.value);
    this.setData({ isPinned });
    void wx.showToast({ title: isPinned ? '已置顶' : '已取消置顶', icon: 'success' });
  },

  onMutedChange(event) {
    const isMuted = Boolean(event.detail.value);
    this.setData({ isMuted });
    void wx.showToast({ title: isMuted ? '已开启免打扰' : '已关闭免打扰', icon: 'success' });
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
          void wx.showToast({ title: '已清空', icon: 'success' });
        } catch (error) {
          logger.error('Failed to clear chat history', { error });
          void wx.showToast({ title: '清空失败', icon: 'none' });
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
            (contact) => contact.conv_id !== this.data.convId
          );
          await saveContacts(updatedContacts);
          await clearMessages(this.data.convId);
          void wx.showToast({ title: '已删除', icon: 'success' });
          setTimeout(() => {
            void wx.navigateBack();
          }, 300);
        } catch (error) {
          logger.error('Failed to delete contact', { error });
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
