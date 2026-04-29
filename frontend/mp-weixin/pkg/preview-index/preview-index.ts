import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { previewMockData, type PreviewConversation } from '../preview-common/data';
import {
  getPreviewTabPath,
  listPreviewTabItems,
  type PreviewTabItem,
  type PreviewTabKey,
} from '../preview-common/navigation';
import { ensurePreviewAccess } from '../../utils/runtime-segment';

interface PreviewContactListItem {
  conversation_id: string;
  displayName: string;
  lastMessageTime: string;
  lastMessage: string;
  secondLastMessage: string;
  hasTags: boolean;
  visibleTags: string[];
  visibleTagToneClasses: string[];
  hiddenTagCount: number;
  hasUnread: boolean;
  unreadBadge: number;
  unreadDot: boolean;
  showTwoMessagePreview: boolean;
  swipeActions: never[];
}

interface PreviewIndexPageData {
  pageLayoutData: PageLayoutData;
  contactList: PreviewContactListItem[];
  tabItems: PreviewTabItem[];
  activeTabKey: PreviewTabKey;
  wordmarkSrc: string;
  showConnectionIssue: boolean;
  showContactLimitHint: boolean;
  showContactLimitReached: boolean;
  canUseInvite: boolean;
  contactLimitHintText: string;
  tagMeasureItems: Array<{ key: string; text: string; kind: 'tag' | 'overflow' }>;
  messageMeasureItems: Array<{ key: string; text: string }>;
}

interface PreviewIndexPageCustom {
  goToChat(event: WechatMiniprogram.BaseEvent): void;
  onSwipeActionClick(): void;
  goToSquareEntry(): void;
  goToInviteShare(): void;
  handleTabTap(event: WechatMiniprogram.BaseEvent): void;
}

const getDatasetValue = (event: WechatMiniprogram.BaseEvent, key: string): unknown => {
  const dataset = event.currentTarget.dataset as Record<string, unknown> | undefined;
  return dataset?.[key];
};

const toConversationId = (value: unknown): string | null =>
  typeof value === 'string' && value.trim() !== '' ? value : null;

const toConversationTitle = (value: unknown): string =>
  typeof value === 'string' && value.trim() !== '' ? value : '会话';

const getCurrentTheme = (): 'light' | 'dark' => {
  const appBaseInfo = wx.getAppBaseInfo() as { theme?: string };
  return appBaseInfo.theme === 'dark' ? 'dark' : 'light';
};

const getWordmarkSrc = (): string =>
  getCurrentTheme() === 'dark' ? '/assets/wordmark-dark.svg' : '/assets/wordmark.svg';

const mapConversationToContactListItem = (
  conversation: PreviewConversation
): PreviewContactListItem => ({
  conversation_id: conversation.id,
  displayName: conversation.title,
  lastMessageTime: conversation.updatedAtLabel,
  lastMessage: conversation.lastMessage,
  secondLastMessage: '',
  hasTags: false,
  visibleTags: [],
  visibleTagToneClasses: [],
  hiddenTagCount: 0,
  hasUnread: conversation.unread > 0,
  unreadBadge: conversation.unread,
  unreadDot: false,
  showTwoMessagePreview: false,
  swipeActions: [],
});

const buildContactList = (): PreviewContactListItem[] =>
  previewMockData.listConversations().map(mapConversationToContactListItem);

const buildScreenModelVariant = (contactList: PreviewContactListItem[]): 'empty' | 'data' =>
  contactList.length === 0 ? 'empty' : 'data';

const initialContactList = buildContactList();

Page<PreviewIndexPageData, PreviewIndexPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: buildScreenModelVariant(initialContactList),
        refreshState: 'idle',
      },
      hasFooter: true,
      emptyMessage: '暂无联系人',
    }),
    contactList: initialContactList,
    tabItems: listPreviewTabItems(),
    activeTabKey: 'index',
    wordmarkSrc: getWordmarkSrc(),
    showConnectionIssue: false,
    showContactLimitHint: false,
    showContactLimitReached: false,
    canUseInvite: false,
    contactLimitHintText: '',
    tagMeasureItems: [],
    messageMeasureItems: [],
  },

  onLoad() {
    if (!ensurePreviewAccess('/pkg/preview-index/preview-index')) {
      return;
    }
  },

  onShow() {
    if (!ensurePreviewAccess('/pkg/preview-index/preview-index')) {
      return;
    }
    const contactList = buildContactList();
    this.setData({
      contactList,
      pageLayoutData: createPageLayoutData({
        screenModel: {
          screenState: 'ready',
          contentVariant: buildScreenModelVariant(contactList),
          refreshState: 'idle',
        },
        hasFooter: true,
        emptyMessage: '暂无联系人',
      }),
      tabItems: listPreviewTabItems(),
      activeTabKey: 'index',
      wordmarkSrc: getWordmarkSrc(),
    });
  },

  goToChat(event: WechatMiniprogram.BaseEvent) {
    const conversationId = toConversationId(getDatasetValue(event, 'id'));
    if (conversationId === null) {
      return;
    }
    const title = encodeURIComponent(toConversationTitle(getDatasetValue(event, 'title')));
    void wx.navigateTo({
      url: `/pkg/preview-chat/preview-chat?conversation_id=${encodeURIComponent(conversationId)}&title=${title}`,
    });
  },

  onSwipeActionClick() {
    // preview mode keeps swipe actions disabled while preserving production layout.
  },

  goToSquareEntry() {
    void wx.redirectTo({ url: '/pkg/preview-square/preview-square' });
  },

  goToInviteShare() {
    void wx.redirectTo({ url: '/pkg/preview-square/preview-square' });
  },

  handleTabTap(event: WechatMiniprogram.BaseEvent) {
    const tabKey = getDatasetValue(event, 'key');
    if (tabKey !== 'index' && tabKey !== 'square' && tabKey !== 'profile') {
      return;
    }
    if (tabKey === this.data.activeTabKey) {
      return;
    }
    void wx.redirectTo({ url: getPreviewTabPath(tabKey) });
  },
});
