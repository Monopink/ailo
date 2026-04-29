import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { previewMockData, type PreviewMessage } from '../preview-common/data';
import { ensurePreviewAccess } from '../../utils/runtime-segment';

interface PreviewChatPageData {
  pageLayoutData: PageLayoutData;
  title: string;
  conversationId: string;
  messages: PreviewMessage[];
  draftText: string;
}

interface PreviewChatPageCustom {
  handleInput(event: WechatMiniprogram.CustomEvent<{ value?: string }>): void;
  handleSend(): void;
  handleBack(): void;
}

const resolveString = (value: string | undefined): string => {
  if (typeof value !== 'string') {
    return '';
  }
  return value.trim();
};

const showToast = (title: string): void => {
  void wx.showToast({ title, icon: 'none' });
};

Page<PreviewChatPageData, PreviewChatPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      emptyMessage: '暂无消息',
      hasFooter: false,
    }),
    title: '会话',
    conversationId: '',
    messages: [],
    draftText: '',
  },

  onLoad(options?: Record<string, string | undefined>) {
    if (!ensurePreviewAccess('/pkg/preview-chat/preview-chat')) {
      return;
    }
    const conversations = previewMockData.listConversations();
    const fallbackConversationId = conversations[0]?.id ?? '';
    const requestedConversationId = resolveString(options?.conversation_id);
    const conversationId =
      requestedConversationId !== '' ? requestedConversationId : fallbackConversationId;
    const titleFromQuery = decodeURIComponent(resolveString(options?.title));
    const title =
      titleFromQuery !== ''
        ? titleFromQuery
        : (conversations.find((item) => item.id === conversationId)?.title ?? '会话');

    this.setData({
      title,
      conversationId,
      messages: previewMockData.listConversationMessages(conversationId),
    });
  },

  onShow() {
    if (!ensurePreviewAccess('/pkg/preview-chat/preview-chat')) {
      return;
    }
    if (this.data.conversationId === '') {
      return;
    }
    this.setData({
      messages: previewMockData.listConversationMessages(this.data.conversationId),
    });
  },

  handleInput(event: WechatMiniprogram.CustomEvent<{ value?: string }>) {
    const value = typeof event.detail.value === 'string' ? event.detail.value : '';
    this.setData({ draftText: value });
  },

  handleSend() {
    if (this.data.conversationId === '') {
      return;
    }
    const text = this.data.draftText.trim();
    if (text === '') {
      showToast('请输入内容');
      return;
    }
    previewMockData.appendGuestMessage(this.data.conversationId, text);
    this.setData({
      draftText: '',
      messages: previewMockData.listConversationMessages(this.data.conversationId),
    });
  },

  handleBack() {
    void wx.navigateBack();
  },
});
