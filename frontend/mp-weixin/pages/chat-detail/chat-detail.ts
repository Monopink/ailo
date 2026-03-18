import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { getLogger } from '../../utils/logger';
import { type StoredContact } from '../../utils/storage';
import messageStateStore from '../../utils/message/message-state-store';
import { normalizeError } from '../../utils/errors';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { type ScreenModel } from '../../services/pages/page-state';
import {
  createChatDetailPageService,
  type ContactView,
} from '../../services/pages/chat-detail-service';

const logger = getLogger('ChatDetail');

interface ChatDetailPageData extends Record<string, unknown> {
  convId: string;
  contact: StoredContact | null;
  contactView: ContactView;
  pageLayoutData: PageLayoutData;
}

interface ChatDetailPageCustom {
  chatDetailPageService: ReturnType<typeof createChatDetailPageService>;
  applyScreenModel(screenModel: ScreenModel): void;
  handleAuthInvalid(): Promise<void>;
  refreshContactInfo(): Promise<void>;
  goToChat(): void;
  viewProfile(): void;
  manageTags(): void;
  clearChatHistory(): void;
  deleteContact(): void;
}

const buildPageLayoutScreenModelPayload = (screenModel: ScreenModel): Record<string, unknown> => ({
  'pageLayoutData.screenModel': screenModel,
});

Page<ChatDetailPageData, ChatDetailPageCustom>({
  data: {
    convId: '',
    contact: null,
    contactView: {
      avatar: '',
      name: '',
      genderLabel: '',
      genderType: 'default',
      hasGender: false,
      displayQiaoId: '',
    },
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      emptyMessage: '暂无会话详情',
      hasFooter: true,
    }),
  },

  applyScreenModel(screenModel: ScreenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  async handleAuthInvalid() {
    await showAuthExpiredModalAndRelogin();
  },

  chatDetailPageService: null as unknown as ReturnType<typeof createChatDetailPageService>,

  async onLoad(options) {
    this.chatDetailPageService = createChatDetailPageService();
    const convId = options.id ?? '';
    if (convId === '') {
      this.applyScreenModel({
        screenState: 'ready',
        contentVariant: 'blank',
        refreshState: 'idle',
      });
      return;
    }

    this.setData({ convId });
    const bootstrap = await this.chatDetailPageService.bootstrap(convId);
    if (bootstrap !== null) {
      this.setData({
        contact: bootstrap.contact,
        contactView: bootstrap.contactView,
        ...buildPageLayoutScreenModelPayload(bootstrap.screenModel),
      });
    }

    await this.refreshContactInfo();
  },

  async refreshContactInfo() {
    this.applyScreenModel({
      ...this.data.pageLayoutData.screenModel,
      screenState: 'ready',
      contentVariant: 'data',
      refreshState: 'refreshing',
    });

    const result = await this.chatDetailPageService.refresh(this.data.convId, this.data.contact);
    if (result === null) {
      return;
    }
    if (result.authInvalid) {
      await this.handleAuthInvalid();
      return;
    }

    this.setData({
      contact: result.contact,
      contactView: result.contactView,
      ...buildPageLayoutScreenModelPayload(result.screenModel),
    });
  },

  goToChat() {
    void wx.navigateTo({
      url: `/pages/chat/chat?id=${this.data.convId}`,
    });
  },

  viewProfile() {
    void wx.navigateTo({
      url: `/pages/contact-info/contact-info?id=${this.data.convId}`,
      events: {
        contactAvatarUpdated: () => {
          void this.refreshContactInfo();
        },
      },
    });
  },

  manageTags() {
    void wx.showToast({ title: '标签管理功能即将上线', icon: 'none' });
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
          await this.chatDetailPageService.clearChatHistory(this.data.convId);
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
          await this.chatDetailPageService.deleteContact(this.data.convId);
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

  onUnload() {
    this.chatDetailPageService.dispose();
  },
});
