import { requireAuth } from '../../utils/auth-guard';
import { getAvatarUrl } from '../../utils/avatar';
import { APP_CONFIG } from '../../utils/config';
import { getLogger } from '../../utils/logger';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import {
  getContacts,
  getConversationUnreadCounts,
  getConversationUnreadMarks,
  getLatestRenderableMessage,
  saveContacts,
  type LatestRenderableMessage,
  type StoredContact,
  type StoredContacts,
} from '../../utils/storage';
import { MESSAGE_TYPE } from '../../utils/constants/message';
import { formatMessageTime } from '../../utils/format';
import { firstNonEmptyString, isNonEmptyString } from '../../utils/guards';
import { fetchAllContactsFromApi } from '../../utils/contact-sync';
import { normalizeError } from '../../utils/errors';
import { initTabBar } from '../../utils/tab-bar';
import messageEventBus from '../../utils/message/event-bus';
import unreadStore from '../../utils/message/unread-store';
import type { ConnectionState } from '../../utils/message/adapter-types';

const logger = getLogger('ContactList');
const CONNECTION_ISSUE_DELAY = 8000;

// TDesign SwipeCell action format
interface SwipeCellAction {
  text: string;
  style?: string;
}

const SWIPE_CELL_VIEW_ACTION: SwipeCellAction = {
  text: '查看联系人',
  style: 'background-color: #999999; color: #ffffff; height: 100%;',
};

const SWIPE_CELL_UNREAD_ACTION: SwipeCellAction = {
  text: '标为未读',
  style: 'background-color: #07c160; color: #ffffff; height: 100%;',
};

const SWIPE_CELL_READ_ACTION: SwipeCellAction = {
  text: '标记已读',
  style: 'background-color: #07c160; color: #ffffff; height: 100%;',
};

const buildSwipeActions = (hasUnread: boolean): ReadonlyArray<SwipeCellAction> => [
  SWIPE_CELL_VIEW_ACTION,
  hasUnread ? SWIPE_CELL_READ_ACTION : SWIPE_CELL_UNREAD_ACTION,
];

type SwipeActionEvent = WechatMiniprogram.CustomEvent<SwipeCellAction>;

type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

interface LoadOptions {
  forceReload?: boolean;
}

interface ContactWithPreview extends StoredContact {
  _latestMessage?: LatestRenderableMessage | null;
  unreadCount?: number;
  unreadMarked?: boolean;
  last_message_content?: string;
  last_message?: string;
  last_message_time?: number | string | null;
}

interface ContactListItem extends ContactWithPreview {
  avatarUrl: string;
  displayName: string;
  lastMessageTime: string;
  lastMessage: string;
  hasUnread: boolean;
  unreadBadge: string;
  unreadDot: boolean;
  swipeActions: ReadonlyArray<SwipeCellAction>;
}

interface ContactListPageData {
  pageLayoutData: PageLayoutData;
  contactList: ContactListItem[];
  unreadTotal: number;
  showConnectionIssue: boolean;
  navbarTitle: string;
}

interface ContactListPageCustom {
  _loadPromise: Promise<void> | null;
  _connectionIssueTimer: ReturnType<typeof setTimeout> | null;
  _connectionSubscription: (() => void) | null;
  updateNavigationTitle(): void;
  bindConnectionStatus(): void;
  handleConnectionStateChange(state: ConnectionState): void;
  clearConnectionIssueTimer(): void;
  loadContactList(options?: LoadOptions): Promise<void>;
  loadContactsFromCache(): Promise<boolean>;
  refreshContactListFromAPI(): Promise<void>;
  attachLatestMessages(
    contacts: StoredContacts,
    unreadCounts: Record<string, number>
  ): Promise<ContactWithPreview[]>;
  updateContactList(contacts: ContactWithPreview[]): void;
  updateContactPreview(convId: string): Promise<void>;
  onRetry(): void;
  goToChat(event: WechatMiniprogram.BaseEvent): void;
  goToSquareEntry(): void;
  onSwipeActionClick(event: SwipeActionEvent): void;
  navigateToContactInfo(convId?: string): void;
  markContactAsUnreadByIndex(index: number): void;
  markContactAsReadByIndex(index: number): void;
  onMessageReceived(message: Ailo.MessagePayload): void;
}

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
};

const getDataset = (event: WechatMiniprogram.BaseEvent): Record<string, unknown> => {
  const dataset = event.currentTarget.dataset as Record<string, unknown> | undefined;
  return dataset ?? {};
};

const getDatasetString = (event: WechatMiniprogram.BaseEvent, key: string): string | undefined => {
  const value = getDataset(event)[key];
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number') {
    return String(value);
  }
  return undefined;
};

const getDatasetNumber = (event: WechatMiniprogram.BaseEvent, key: string): number | undefined => {
  const value = getDataset(event)[key];
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? undefined : parsed;
  }
  return undefined;
};

Page<ContactListPageData, ContactListPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      isLoading: true,
      emptyMessage: '暂无联系人',
      hasFooter: false,
    }),
    contactList: [],
    unreadTotal: 0,
    showConnectionIssue: false,
    navbarTitle: APP_CONFIG.brandName,
  },

  _loadPromise: null,
  _connectionIssueTimer: null,
  _connectionSubscription: null,

  async onLoad() {
    logger.info('Contact list page loaded');
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }

    this.updateNavigationTitle();
    this.bindConnectionStatus();
    void this.loadContactList();
  },

  async onShow() {
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }

    initTabBar(this);

    this.updateNavigationTitle();
    void this.loadContactList();
  },

  onUnload() {
    this.clearConnectionIssueTimer();
    if (this._connectionSubscription !== null) {
      this._connectionSubscription();
      this._connectionSubscription = null;
    }
  },

  bindConnectionStatus() {
    if (this._connectionSubscription !== null) {
      return;
    }
    const app = getApp<AppInstance>();
    const messageService = app.getMessageService();
    if (messageService !== null) {
      this.handleConnectionStateChange(messageService.getConnectionState());
    }
    this._connectionSubscription = messageEventBus.onConnection((state) => {
      this.handleConnectionStateChange(state);
    });
  },

  handleConnectionStateChange(state: ConnectionState) {
    if (state === 'connected') {
      this.clearConnectionIssueTimer();
      if (this.data.showConnectionIssue) {
        this.setData({ showConnectionIssue: false });
      }
      return;
    }

    if (state === 'suspending') {
      this.clearConnectionIssueTimer();
      if (this.data.showConnectionIssue) {
        this.setData({ showConnectionIssue: false });
      }
      return;
    }

    if (state === 'disconnected') {
      if (this._connectionIssueTimer !== null) {
        return;
      }
      this._connectionIssueTimer = setTimeout(() => {
        this._connectionIssueTimer = null;
        if (!this.data.showConnectionIssue) {
          this.setData({ showConnectionIssue: true });
        }
      }, CONNECTION_ISSUE_DELAY);
    }
  },

  clearConnectionIssueTimer() {
    if (this._connectionIssueTimer !== null) {
      clearTimeout(this._connectionIssueTimer);
      this._connectionIssueTimer = null;
    }
  },

  updateNavigationTitle() {
    const brandName = APP_CONFIG.brandName;
    if (isNonEmptyString(brandName)) {
      this.setData({ navbarTitle: brandName });
    }
  },

  async loadContactList(options: LoadOptions = {}) {
    const { forceReload = false } = options;
    if (this._loadPromise !== null && !forceReload) {
      return this._loadPromise;
    }

    const loadTask: Promise<void> = (async () => {
      this.setData({
        'pageLayoutData.isLoading': true,
        'pageLayoutData.hasError': false,
        'pageLayoutData.errorMessage': '',
      });
      try {
        const remoteContacts = await fetchAllContactsFromApi();
        const normalizedContacts = await saveContacts(remoteContacts);
        const unreadCounts = await getConversationUnreadCounts();
        const unreadMarks = await getConversationUnreadMarks();
        const enrichedContacts = await this.attachLatestMessages(normalizedContacts, unreadCounts);
        const merged = enrichedContacts.map((contact) => ({
          ...contact,
          unreadMarked: isNonEmptyString(contact.conversation_id)
            ? Boolean(unreadMarks[contact.conversation_id])
            : false,
        }));
        this.updateContactList(merged);
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.warn('Contact list API failed, falling back to cache', { error: err.message });
        const cacheLoaded = await this.loadContactsFromCache();
        if (!cacheLoaded) {
          throw err;
        }
      }
    })();

    this._loadPromise = loadTask
      .catch((error) => {
        const err = normalizeError(error);
        const errorMessage = isNonEmptyString(err.message) ? err.message : '加载失败，请稍后重试';
        logger.error('Failed to load contact list', { error: err.message });
        this.setData({
          'pageLayoutData.isLoading': false,
          'pageLayoutData.hasError': true,
          'pageLayoutData.errorMessage': errorMessage,
          'pageLayoutData.isEmpty': false,
        });
        showToast('加载失败');
      })
      .finally(() => {
        this._loadPromise = null;
      });

    return this._loadPromise;
  },

  async loadContactsFromCache() {
    try {
      const cachedContacts = await getContacts();
      const unreadCounts = await getConversationUnreadCounts();
      const unreadMarks = await getConversationUnreadMarks();
      const enrichedContacts = await this.attachLatestMessages(cachedContacts, unreadCounts);
      const merged = enrichedContacts.map((contact) => ({
        ...contact,
        unreadMarked: isNonEmptyString(contact.conversation_id)
          ? Boolean(unreadMarks[contact.conversation_id])
          : false,
      }));
      this.updateContactList(merged);
      return true;
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to load contacts from cache', { error: err.message });
      return false;
    }
  },

  async refreshContactListFromAPI() {
    if (this._loadPromise !== null) {
      try {
        await this._loadPromise;
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.warn('Previous contact refresh failed', { error: err.message });
      }
    }
    return this.loadContactList({ forceReload: true });
  },

  onMessageReceived(message) {
    logger.info('Message received in contact list', {
      msg_id: message.msg_id,
      message_type: message.message_type,
    });

    if (message.message_type === MESSAGE_TYPE.CHAT_INFO) {
      void this.refreshContactListFromAPI();
      return;
    }

    if (isNonEmptyString(message.conv_id)) {
      void this.updateContactPreview(message.conv_id);
    }
  },

  async updateContactPreview(convId: string): Promise<void> {
    if (!isNonEmptyString(convId)) {
      return;
    }
    const unreadCounts = await getConversationUnreadCounts();
    const unreadMarks = await getConversationUnreadMarks();
    const unreadCount = unreadCounts[convId] ?? 0;
    const unreadMarked = Boolean(unreadMarks[convId]);
    const latestMessage = await getLatestRenderableMessage(convId);

    const contactList = this.data.contactList.map((contact) => {
      if (contact.conversation_id !== convId) {
        return contact;
      }
      const lastMessageContent =
        latestMessage?.content ?? contact.last_message_content ?? contact.last_message ?? '';
      const lastMessageTimeRaw = latestMessage?.sent_time ?? contact.last_message_time ?? null;
      return {
        ...contact,
        _latestMessage: latestMessage ?? contact._latestMessage ?? null,
        lastMessage: lastMessageContent,
        lastMessageTime: formatMessageTime(lastMessageTimeRaw),
        unreadCount,
        unreadMarked,
        hasUnread: unreadCount > 0 || unreadMarked,
        unreadBadge: unreadCount > 0 ? (unreadCount > 99 ? '99+' : String(unreadCount)) : '',
        unreadDot: unreadCount === 0 && unreadMarked,
        swipeActions: buildSwipeActions(unreadCount > 0 || unreadMarked),
      };
    });

    const unreadTotal = contactList.reduce((sum, contact) => sum + (contact.unreadCount ?? 0), 0);
    this.setData({ contactList, unreadTotal });
    this.updateNavigationTitle();
  },

  updateContactList(contacts: ContactWithPreview[]) {
    const contactList = contacts.map((contact) => {
      const unreadCount = contact.unreadCount ?? 0;
      const unreadMarked = contact.unreadMarked ?? false;
      const latestMessage = contact._latestMessage ?? null;
      const lastMessageContent =
        latestMessage?.content ?? contact.last_message_content ?? contact.last_message ?? '';
      const lastMessageTimeRaw = latestMessage?.sent_time ?? contact.last_message_time ?? null;
      const displayName = firstNonEmptyString(contact.alias, contact.profile?.nickname) ?? '';

      const hasUnread = unreadCount > 0 || unreadMarked;
      return {
        ...contact,
        avatarUrl: getAvatarUrl(contact.profile?.avatar_url ?? ''),
        displayName,
        lastMessageTime: formatMessageTime(lastMessageTimeRaw),
        lastMessage: lastMessageContent,
        hasUnread,
        unreadBadge: unreadCount > 0 ? (unreadCount > 99 ? '99+' : String(unreadCount)) : '',
        unreadDot: unreadCount === 0 && unreadMarked,
        swipeActions: buildSwipeActions(hasUnread),
      };
    });

    const unreadTotal = contactList.reduce((sum, contact) => sum + (contact.unreadCount ?? 0), 0);

    this.setData({
      contactList,
      unreadTotal,
      'pageLayoutData.isLoading': false,
      'pageLayoutData.isEmpty': contactList.length === 0,
      'pageLayoutData.hasError': false,
      'pageLayoutData.errorMessage': '',
    });
    this.updateNavigationTitle();
  },

  onRetry() {
    void this.refreshContactListFromAPI();
  },

  goToChat(event) {
    const convId = getDatasetString(event, 'id');
    if (!isNonEmptyString(convId)) {
      return;
    }
    void wx.navigateTo({ url: `/pages/chat/chat?id=${convId}` });
  },

  goToSquareEntry() {
    void wx.switchTab({ url: '/pages/square-entry/square-entry' });
  },

  onSwipeActionClick(event: SwipeActionEvent) {
    const action = event.detail;
    const convId = getDatasetString(event, 'id');
    if (!isNonEmptyString(convId)) {
      return;
    }
    const contactIndex = getDatasetNumber(event, 'index');
    if (typeof contactIndex !== 'number') {
      return;
    }

    // Determine action by text
    if (action.text === '查看联系人') {
      this.navigateToContactInfo(convId);
    } else if (action.text === '标为未读') {
      this.markContactAsUnreadByIndex(contactIndex);
    } else if (action.text === '标记已读') {
      this.markContactAsReadByIndex(contactIndex);
    }
  },

  navigateToContactInfo(convId?: string) {
    if (!isNonEmptyString(convId)) {
      return;
    }
    void wx.navigateTo({ url: `/pages/contact-info/contact-info?id=${convId}` });
  },

  markContactAsUnreadByIndex(index: number) {
    if (!Number.isInteger(index) || index < 0) {
      return;
    }

    const contactList = [...this.data.contactList];
    const target = contactList[index];
    if (typeof target === 'undefined') {
      return;
    }

    const convId = target.conversation_id;
    if (!isNonEmptyString(convId)) {
      return;
    }

    void (async () => {
      try {
        await unreadStore.markConversationAsUnread(convId);
        const unreadCounts = await getConversationUnreadCounts();
        const count = unreadCounts[convId] ?? 0;

        const unreadMarks = await getConversationUnreadMarks();
        const unreadMarked = Boolean(unreadMarks[convId]);

        const hasUnread = count > 0 || unreadMarked;
        contactList[index] = {
          ...target,
          unreadCount: count,
          unreadMarked,
          hasUnread,
          unreadBadge: count > 0 ? (count > 99 ? '99+' : String(count)) : '',
          unreadDot: count === 0 && unreadMarked,
          swipeActions: buildSwipeActions(hasUnread),
        };

        const unreadTotal = contactList.reduce(
          (sum, contact) => sum + (contact.unreadCount ?? 0),
          0
        );

        this.setData({
          contactList,
          unreadTotal,
        });
        this.updateNavigationTitle();
        showToast('已标为未读', 'success');
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.warn('Mark contact as unread failed', { error: err.message });
        showToast('标记失败');
      }
    })();
  },

  markContactAsReadByIndex(index: number) {
    if (!Number.isInteger(index) || index < 0) {
      return;
    }

    const contactList = [...this.data.contactList];
    const target = contactList[index];
    if (typeof target === 'undefined') {
      return;
    }

    const convId = target.conversation_id;
    if (!isNonEmptyString(convId)) {
      return;
    }

    void (async () => {
      try {
        await unreadStore.markConversationAsRead(convId);
        const unreadCounts = await getConversationUnreadCounts();
        const unreadMarks = await getConversationUnreadMarks();
        const count = unreadCounts[convId] ?? 0;
        const unreadMarked = Boolean(unreadMarks[convId]);
        const hasUnread = count > 0 || unreadMarked;

        contactList[index] = {
          ...target,
          unreadCount: count,
          unreadMarked,
          hasUnread,
          unreadBadge: count > 0 ? (count > 99 ? '99+' : String(count)) : '',
          unreadDot: count === 0 && unreadMarked,
          swipeActions: buildSwipeActions(hasUnread),
        };

        const unreadTotal = contactList.reduce(
          (sum, contact) => sum + (contact.unreadCount ?? 0),
          0
        );

        this.setData({
          contactList,
          unreadTotal,
        });
        this.updateNavigationTitle();
        showToast('已标记为已读', 'success');
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.warn('Mark contact as read failed', { error: err.message });
        showToast('标记失败');
      }
    })();
  },

  async attachLatestMessages(
    contacts: StoredContacts,
    unreadCounts: Record<string, number>
  ): Promise<ContactWithPreview[]> {
    if (contacts.length === 0) {
      return [];
    }

    const enriched = await Promise.all(
      contacts.map(async (contact) => {
        if (!isNonEmptyString(contact.conversation_id)) {
          return {
            ...contact,
            unreadCount: 0,
          } as ContactWithPreview;
        }

        try {
          const latestMessage = await getLatestRenderableMessage(contact.conversation_id);
          return {
            ...contact,
            _latestMessage: latestMessage,
            unreadCount: unreadCounts[contact.conversation_id] ?? 0,
          } as ContactWithPreview;
        } catch (error: unknown) {
          const err = normalizeError(error);
          logger.warn('Failed to load latest message preview', {
            convId: contact.conversation_id,
            error: err.message,
          });
          return {
            ...contact,
            _latestMessage: null,
            unreadCount: unreadCounts[contact.conversation_id] ?? 0,
          } as ContactWithPreview;
        }
      })
    );

    return enriched;
  },
});
