import { requireAuth } from '../../utils/auth-guard';
import { getAvatarUrl } from '../../utils/avatar';
import { APP_CONFIG } from '../../utils/config';
import { getLogger } from '../../utils/logger';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import {
  getContacts,
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

const logger = getLogger('ContactList');

// TDesign SwipeCell action format
interface SwipeCellAction {
  text: string;
  style?: string;
}

const SWIPE_CELL_ACTIONS: ReadonlyArray<SwipeCellAction> = [
  {
    text: '查看联系人',
    style: 'background-color: #999999; color: #ffffff; height: 100%;',
  },
  {
    text: '标为未读',
    style: 'background-color: #07c160; color: #ffffff; height: 100%;',
  },
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
}

interface ContactListPageData {
  pageLayoutData: PageLayoutData;
  contactList: ContactListItem[];
  unreadTotal: number;
  swipeCellActions: ReadonlyArray<SwipeCellAction>;
}

interface ContactListPageCustom {
  _loadPromise: Promise<void> | null;
  updateNavigationTitle(): void;
  loadContactList(options?: LoadOptions): Promise<void>;
  loadContactsFromCache(): Promise<boolean>;
  refreshContactListFromAPI(): Promise<void>;
  attachLatestMessages(contacts: StoredContacts): Promise<ContactWithPreview[]>;
  updateContactList(contacts: ContactWithPreview[]): void;
  goToChat(event: WechatMiniprogram.BaseEvent): void;
  onSwipeActionClick(event: SwipeActionEvent): void;
  navigateToContactInfo(convId?: string): void;
  markContactAsUnreadByIndex(index: number): void;
  onMessageReceived(message: Ailo.MessagePayload): void;
}

const normalizeError = (error: unknown): Error => {
  if (error instanceof Error) {
    return error;
  }
  if (typeof error === 'string') {
    return new Error(error);
  }
  try {
    return new Error(JSON.stringify(error));
  } catch {
    return new Error('Unknown error');
  }
};

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
    swipeCellActions: SWIPE_CELL_ACTIONS,
  },

  _loadPromise: null,

  async onLoad() {
    logger.info('Contact list page loaded');
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }

    this.updateNavigationTitle();
    void this.loadContactList();
  },

  async onShow() {
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }

    // Update custom TabBar active state
    const tabBar = typeof this.getTabBar === 'function' ? this.getTabBar() : null;
    if (tabBar !== null) {
      const initFn = (tabBar as { init?: unknown }).init;
      if (typeof initFn === 'function') {
        void initFn();
      }
    }

    this.updateNavigationTitle();
    void this.loadContactList();
  },

  updateNavigationTitle() {
    const brandName = APP_CONFIG.brandName;
    const unreadTotal = this.data.unreadTotal;
    const badge = unreadTotal > 99 ? '99+' : unreadTotal;
    const title = unreadTotal > 0 ? `${brandName}(${badge})` : brandName;
    if (isNonEmptyString(title)) {
      void wx.setNavigationBarTitle({ title });
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
        const enrichedContacts = await this.attachLatestMessages(normalizedContacts);
        this.updateContactList(enrichedContacts);
      } catch (error) {
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
      const enrichedContacts = await this.attachLatestMessages(cachedContacts);
      this.updateContactList(enrichedContacts);
      return true;
    } catch (error) {
      const err = normalizeError(error);
      logger.error('Failed to load contacts from cache', { error: err.message });
      return false;
    }
  },

  async refreshContactListFromAPI() {
    if (this._loadPromise !== null) {
      try {
        await this._loadPromise;
      } catch (error) {
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
    }
  },

  updateContactList(contacts: ContactWithPreview[]) {
    const contactList = contacts.map((contact) => {
      const unreadCount = contact.unreadCount ?? 0;
      const latestMessage = contact._latestMessage ?? null;
      const lastMessageContent =
        latestMessage?.content ?? contact.last_message_content ?? contact.last_message ?? '';
      const lastMessageTimeRaw = latestMessage?.sent_time ?? contact.last_message_time ?? null;
      const displayName =
        firstNonEmptyString(contact.alias, contact.profile?.nickname, contact.contact_qiao_id) ??
        '';

      return {
        ...contact,
        avatarUrl: getAvatarUrl(contact.profile?.avatar_url ?? ''),
        displayName,
        lastMessageTime: formatMessageTime(lastMessageTimeRaw),
        lastMessage: lastMessageContent,
        hasUnread: unreadCount > 0,
        unreadBadge: unreadCount > 99 ? '99+' : String(unreadCount),
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

  goToChat(event) {
    const convId = getDatasetString(event, 'id');
    if (!isNonEmptyString(convId)) {
      return;
    }
    void wx.navigateTo({ url: `/pages/chat/chat?id=${convId}` });
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

    const count = (target.unreadCount ?? 0) + 1;
    contactList[index] = {
      ...target,
      unreadCount: count,
      hasUnread: true,
      unreadBadge: count > 99 ? '99+' : String(count),
    };

    const unreadTotal = contactList.reduce((sum, contact) => sum + (contact.unreadCount ?? 0), 0);

    this.setData({
      contactList,
      unreadTotal,
    });
    this.updateNavigationTitle();
    showToast('已标为未读', 'success');
  },

  async attachLatestMessages(contacts: StoredContacts): Promise<ContactWithPreview[]> {
    if (contacts.length === 0) {
      return [];
    }

    const enriched = await Promise.all(
      contacts.map(async (contact) => {
        if (!isNonEmptyString(contact.conv_id)) {
          return contact as ContactWithPreview;
        }

        try {
          const latestMessage = await getLatestRenderableMessage(contact.conv_id);
          return {
            ...contact,
            _latestMessage: latestMessage,
          } as ContactWithPreview;
        } catch (error) {
          const err = normalizeError(error);
          logger.warn('Failed to load latest message preview', {
            convId: contact.conv_id,
            error: err.message,
          });
          return {
            ...contact,
            _latestMessage: null,
          } as ContactWithPreview;
        }
      })
    );

    return enriched;
  },
});
