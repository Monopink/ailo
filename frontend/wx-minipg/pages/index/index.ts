import { requireAuth } from '../../utils/auth-guard';
import { getAvatarUrl } from '../../utils/avatar';
import { APP_CONFIG } from '../../utils/config';
import { getLogger } from '../../utils/logger';
import {
  clearMessages,
  getContacts,
  getLatestRenderableMessage,
  saveContacts,
  type LatestRenderableMessage,
  type StoredContact,
  type StoredContacts,
} from '../../utils/storage';
import { del } from '../../utils/api';
import { MESSAGE_TYPE } from '../../utils/message/constants';
import { formatMessageTime } from '../../utils/format';
import { fetchAllContactsFromApi } from '../../utils/contact-sync';

const logger = getLogger('ContactList');

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
  contactList: ContactListItem[];
  unreadTotal: number;
  loading: boolean;
  currentMenuIndex: number;
  isEmpty: boolean;
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
  showMenu(event: WechatMiniprogram.BaseEvent): void;
  hideMenu(): void;
  stopPropagation(event: WechatMiniprogram.BaseEvent): void;
  goToContactInfo(event: WechatMiniprogram.BaseEvent): void;
  markAsUnread(event: WechatMiniprogram.BaseEvent): void;
  deleteContact(event: WechatMiniprogram.BaseEvent): void;
  onMessageReceived(message: Says.MessagePayload): void;
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
  const dataset = event?.currentTarget?.dataset as Record<string, unknown> | undefined;
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
    contactList: [],
    unreadTotal: 0,
    loading: false,
    currentMenuIndex: -1,
    isEmpty: false,
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

    this.updateNavigationTitle();
    void this.loadContactList();
  },

  updateNavigationTitle() {
    const brandName = APP_CONFIG.brandName ?? '';
    const unreadTotal = this.data.unreadTotal ?? 0;
    const badge = unreadTotal > 99 ? '99+' : unreadTotal;
    const title = unreadTotal > 0 ? `${brandName}(${badge})` : brandName;
    if (title) {
      void wx.setNavigationBarTitle({ title });
    }
  },

  async loadContactList(options: LoadOptions = {}) {
    const { forceReload = false } = options;
    if (this._loadPromise && !forceReload) {
      return this._loadPromise;
    }

    const loadTask: Promise<void> = (async () => {
      this.setData({ loading: true });
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
        logger.error('Failed to load contact list', { error: err.message });
        this.setData({ loading: false, isEmpty: true });
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
    if (this._loadPromise) {
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
      msg_id: message?.msg_id,
      message_type: message?.message_type,
    });

    if (message?.message_type === MESSAGE_TYPE.CHAT_INFO) {
      void this.refreshContactListFromAPI();
    }
  },

  updateContactList(contacts) {
    const contactList = (contacts ?? []).map((contact) => {
      const unreadCount = contact.unreadCount ?? 0;
      const latestMessage = contact._latestMessage ?? null;
      const lastMessageContent =
        latestMessage?.content ?? contact.last_message_content ?? contact.last_message ?? '';
      const lastMessageTimeRaw = latestMessage?.sent_time ?? contact.last_message_time ?? null;

      return {
        ...contact,
        avatarUrl: getAvatarUrl(contact.custom_avatar_url ?? contact.avatar_url ?? ''),
        displayName: contact.alias || contact.nickname || contact.contact_qiao_id || '',
        lastMessageTime: formatMessageTime(lastMessageTimeRaw),
        lastMessage: lastMessageContent,
        hasUnread: unreadCount > 0,
        unreadBadge: unreadCount > 99 ? '99+' : String(unreadCount),
      };
    });

    const unreadTotal = contactList.reduce((sum, contact) => sum + (contact.unreadCount ?? 0), 0);
    const loading = false;
    const isEmpty = contactList.length === 0 && !loading;

    this.setData({ contactList, unreadTotal, loading, isEmpty });
    this.updateNavigationTitle();
  },

  goToChat(event) {
    const convId = getDatasetString(event, 'id');
    if (!convId) {
      return;
    }
    void wx.navigateTo({ url: `/pages/chat/chat?id=${convId}` });
  },

  showMenu(event) {
    const index = getDatasetNumber(event, 'index');
    if (typeof index === 'number') {
      this.setData({ currentMenuIndex: index });
    }
  },

  hideMenu() {
    this.setData({ currentMenuIndex: -1 });
  },

  stopPropagation(_event) {
    // noop; used to prevent overlay dismissal
  },

  goToContactInfo(event) {
    const convId = getDatasetString(event, 'id');
    this.setData({ currentMenuIndex: -1 });
    if (!convId) {
      return;
    }
    void wx.navigateTo({ url: `/pages/contact-info/contact-info?id=${convId}` });
  },

  markAsUnread(event) {
    const index = getDatasetNumber(event, 'index');
    if (typeof index !== 'number') {
      return;
    }

    const contactList = [...this.data.contactList];
    const target = contactList[index];
    if (!target) {
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
      currentMenuIndex: -1,
      unreadTotal,
    });
    this.updateNavigationTitle();
    showToast('已标为未读', 'success');
  },

  deleteContact(event) {
    const convId = getDatasetString(event, 'id');
    this.setData({ currentMenuIndex: -1 });
    if (!convId) {
      return;
    }

    void wx.showModal({
      title: '删除联系人',
      content: '删除后将解除联系并清空本地聊天记录，确定继续？',
      confirmColor: '#ff4d4f',
      success: async (res) => {
        if (!res.confirm) {
          return;
        }

        void wx.showLoading({ title: '处理中', mask: true });
        try {
          await del(`/contacts/${convId}`);

          const currentContacts = await getContacts();
          const updatedContacts = (currentContacts ?? []).filter(
            (contact) => contact.conv_id !== convId
          );
          await saveContacts(updatedContacts);
          await clearMessages(convId);

          const enrichedContacts = await this.attachLatestMessages(updatedContacts);
          this.updateContactList(enrichedContacts);

          showToast('已删除', 'success');
          logger.info('Contact deleted', { convId });
        } catch (error) {
          const err = normalizeError(error);
          logger.error('Delete contact failed', { convId, error: err.message });
          showToast(err.message || '删除失败，请稍后重试');
        } finally {
          void wx.hideLoading();
        }
      },
    });
  },

  async attachLatestMessages(contacts) {
    if (!Array.isArray(contacts) || contacts.length === 0) {
      return contacts ?? [];
    }

    const enriched = await Promise.all(
      contacts.map(async (contact) => {
        if (!contact?.conv_id) {
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
