import { getAvatarUrl } from '../../utils/avatar';
import { fetchAllContactsFromApi, fetchContactLimitFromApi } from '../../utils/contact-sync';
import { classifyError } from '../../utils/error-classifier';
import { formatMessageTime } from '../../utils/format';
import { firstNonEmptyString, isNonEmptyString } from '../../utils/guards';
import {
  getContacts,
  getConversationUnreadCounts,
  getConversationUnreadMarks,
  getLatestTwoRenderableMessages,
  saveContacts,
  type LatestRenderableMessage,
  type StoredContact,
  type StoredContacts,
} from '../../utils/storage';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ContentVariant, type ScreenModel } from './page-state';

export type ContactSwipeActionKey = 'mark-as-unread' | 'mark-as-read' | 'view-contact-info';

export interface ContactSwipeAction {
  key: ContactSwipeActionKey;
  text: string;
  className: string;
}

const SWIPE_CELL_UNREAD_ACTION: ContactSwipeAction = {
  key: 'mark-as-unread',
  text: '标为未读',
  className: 'index-swipe-cell__action index-swipe-cell__action--neutral',
};

const SWIPE_CELL_READ_ACTION: ContactSwipeAction = {
  key: 'mark-as-read',
  text: '标为已读',
  className: 'index-swipe-cell__action index-swipe-cell__action--neutral',
};

const SWIPE_CELL_VIEW_ACTION: ContactSwipeAction = {
  key: 'view-contact-info',
  text: '联系人详情',
  className: 'index-swipe-cell__action index-swipe-cell__action--theme',
};

const buildSwipeActions = (hasUnread: boolean): ReadonlyArray<ContactSwipeAction> => [
  hasUnread ? SWIPE_CELL_READ_ACTION : SWIPE_CELL_UNREAD_ACTION,
  SWIPE_CELL_VIEW_ACTION,
];

type ContactWithPreview = StoredContact & {
  _latestMessage?: LatestRenderableMessage | null;
  _latestRenderableMessages?: LatestRenderableMessage[];
  unreadCount?: number;
  unreadMarked?: boolean;
  last_message_content?: string;
  last_message?: string;
  last_message_time?: number | string | null;
};

interface ResolvedMessagePreview {
  latestMessage: LatestRenderableMessage | null;
  secondLatestMessage: LatestRenderableMessage | null;
}

export interface ContactListItem extends ContactWithPreview {
  avatarUrl: string;
  displayName: string;
  lastMessageTime: string;
  lastMessage: string;
  secondLastMessage: string;
  canShowTwoMessagePreview: boolean;
  hasUnread: boolean;
  unreadBadge: string;
  unreadDot: boolean;
  swipeActions: ReadonlyArray<ContactSwipeAction>;
}

export interface IndexBootstrapResult {
  screenModel: ScreenModel;
  contactList: ContactListItem[];
  unreadTotal: number;
  availableContactSlots: number | null;
}

export interface IndexRefreshResult extends IndexBootstrapResult {
  authInvalid: boolean;
}

export interface IndexRefreshContext {
  contactList: ContactListItem[];
  unreadTotal: number;
  currentContentVariant: ContentVariant;
  availableContactSlots: number | null;
}

const parseComparableTimestamp = (value: number | string | null | undefined): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return null;
  }
  const asNumber = Number(trimmed);
  if (Number.isFinite(asNumber)) {
    return asNumber;
  }
  const asDate = Date.parse(trimmed);
  return Number.isNaN(asDate) ? null : asDate;
};

const resolveSortTimestamp = (contact: ContactWithPreview): number | null => {
  const localTimelineTime = parseComparableTimestamp(contact._latestMessage?.sent_time);
  if (localTimelineTime !== null) {
    return localTimelineTime;
  }
  return parseComparableTimestamp(contact.last_message_time);
};

const sortContactsByLatestMessage = <T extends ContactWithPreview>(contacts: T[]): T[] =>
  [...contacts].sort((left, right) => {
    const leftTimestamp = resolveSortTimestamp(left);
    const rightTimestamp = resolveSortTimestamp(right);

    if (leftTimestamp !== null && rightTimestamp !== null) {
      if (leftTimestamp !== rightTimestamp) {
        return rightTimestamp - leftTimestamp;
      }
    } else if (leftTimestamp !== null) {
      return -1;
    } else if (rightTimestamp !== null) {
      return 1;
    }

    const leftConversationId = isNonEmptyString(left.conversation_id) ? left.conversation_id : '';
    const rightConversationId = isNonEmptyString(right.conversation_id)
      ? right.conversation_id
      : '';
    return leftConversationId.localeCompare(rightConversationId);
  });

const resolveMessagePreview = (contact: ContactWithPreview): ResolvedMessagePreview => {
  const previewMessages = contact._latestRenderableMessages;
  if (Array.isArray(previewMessages) && previewMessages.length > 0) {
    return {
      latestMessage: previewMessages[0],
      secondLatestMessage: previewMessages.length > 1 ? previewMessages[1] : null,
    };
  }
  return {
    latestMessage: contact._latestMessage ?? null,
    secondLatestMessage: null,
  };
};

const canUseTwoMessagePreview = (
  latestMessage: LatestRenderableMessage | null,
  secondLatestMessage: LatestRenderableMessage | null
): boolean => {
  if (latestMessage === null || secondLatestMessage === null) {
    return false;
  }
  if (!isNonEmptyString(latestMessage.from_qiao_id)) {
    return false;
  }
  return latestMessage.from_qiao_id === secondLatestMessage.from_qiao_id;
};

const resolveUnreadDisplayState = (
  unreadCount: number,
  unreadMarked: boolean
): Pick<ContactListItem, 'hasUnread' | 'unreadBadge' | 'unreadDot' | 'swipeActions'> => {
  const hasUnread = unreadCount > 0 || unreadMarked;
  const unreadBadge =
    unreadCount > 0 ? (unreadCount > 99 ? '99+' : String(unreadCount)) : unreadMarked ? '+' : '';
  return {
    hasUnread,
    unreadBadge,
    unreadDot: false,
    swipeActions: buildSwipeActions(hasUnread),
  };
};

const toContactListItem = (contact: ContactWithPreview): ContactListItem => {
  const unreadCount = contact.unreadCount ?? 0;
  const unreadMarked = contact.unreadMarked ?? false;
  const { latestMessage, secondLatestMessage } = resolveMessagePreview(contact);
  const canShowTwoMessagePreview = canUseTwoMessagePreview(latestMessage, secondLatestMessage);
  const lastMessageContent =
    latestMessage !== null
      ? latestMessage.content
      : (contact.last_message_content ?? contact.last_message ?? '');
  const lastMessageTimeRaw =
    latestMessage !== null ? latestMessage.sent_time : (contact.last_message_time ?? null);
  const displayName = firstNonEmptyString(contact.alias, contact.profile?.nickname) ?? '';
  const unreadDisplayState = resolveUnreadDisplayState(unreadCount, unreadMarked);
  return {
    ...contact,
    avatarUrl: getAvatarUrl(
      firstNonEmptyString(contact.avatar_url ?? '', contact.profile?.avatar_url ?? '') ?? ''
    ),
    displayName,
    lastMessageTime: formatMessageTime(lastMessageTimeRaw),
    lastMessage: lastMessageContent,
    secondLastMessage: secondLatestMessage !== null ? secondLatestMessage.content : '',
    canShowTwoMessagePreview,
    ...unreadDisplayState,
  };
};

const resolveUnreadTotal = (contactList: ContactListItem[]): number =>
  contactList.reduce((sum, contact) => sum + (contact.unreadCount ?? 0), 0);

export class IndexPageService extends BasePageService {
  private bootstrapPromise: Promise<IndexBootstrapResult | null> | null = null;

  async bootstrap(): Promise<IndexBootstrapResult | null> {
    if (this.bootstrapPromise !== null) {
      return await this.bootstrapPromise;
    }
    const promise = this.bootstrapInternal();
    this.bootstrapPromise = promise;
    const result = await promise;
    if (this.bootstrapPromise === promise) {
      this.bootstrapPromise = null;
    }
    return result;
  }

  async refresh(context: IndexRefreshContext): Promise<IndexRefreshResult | null> {
    const seq = this.startRequest();
    try {
      const contactLimitPromise = fetchContactLimitFromApi()
        .then((result) => result.available_total)
        .catch(() => null);
      const remoteContacts = await fetchAllContactsFromApi();
      const normalizedContacts = await saveContacts(remoteContacts);
      const contactList = await this.buildContactList(normalizedContacts);
      const availableContactSlots = await contactLimitPromise;
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        screenModel: createReadyScreenModel({
          contentVariant: contactList.length === 0 ? 'empty' : 'data',
          refreshState: 'idle',
        }),
        contactList,
        unreadTotal: resolveUnreadTotal(contactList),
        availableContactSlots,
        authInvalid: false,
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      const hasCurrentModel = context.currentContentVariant !== 'blank';
      const degradedContentVariant: ContentVariant = hasCurrentModel
        ? context.contactList.length === 0
          ? 'empty'
          : 'data'
        : 'blank';
      return {
        screenModel: createReadyScreenModel({
          contentVariant: degradedContentVariant,
          refreshState: 'degraded',
        }),
        contactList: hasCurrentModel ? context.contactList : [],
        unreadTotal: hasCurrentModel ? context.unreadTotal : 0,
        availableContactSlots: hasCurrentModel ? context.availableContactSlots : null,
        authInvalid: semantics.reason === 'auth-invalid',
      };
    }
  }

  async enrichContactPreview(
    convId: string,
    currentList: ContactListItem[]
  ): Promise<{ contactList: ContactListItem[]; unreadTotal: number }> {
    if (!isNonEmptyString(convId) || currentList.length === 0) {
      return { contactList: currentList, unreadTotal: resolveUnreadTotal(currentList) };
    }

    const unreadCounts = await getConversationUnreadCounts();
    const unreadMarks = await getConversationUnreadMarks();
    const unreadCount = unreadCounts[convId] ?? 0;
    const unreadMarked = Boolean(unreadMarks[convId]);
    const latestMessages = await getLatestTwoRenderableMessages(convId);
    const latestMessage = latestMessages.length > 0 ? latestMessages[0] : null;

    const contactList = currentList.map((contact) => {
      if (contact.conversation_id !== convId) {
        return contact;
      }
      const lastMessageContent =
        latestMessage !== null
          ? latestMessage.content
          : (contact.last_message_content ?? contact.last_message ?? '');
      const lastMessageTimeRaw =
        latestMessage !== null ? latestMessage.sent_time : (contact.last_message_time ?? null);
      const nextContact: ContactWithPreview = {
        ...contact,
        _latestMessage: latestMessage ?? contact._latestMessage ?? null,
        _latestRenderableMessages: latestMessages,
        last_message_content: lastMessageContent,
        last_message_time: lastMessageTimeRaw,
        unreadCount,
        unreadMarked,
      };
      return toContactListItem(nextContact);
    });

    const sortedContactList = sortContactsByLatestMessage(contactList);
    return { contactList: sortedContactList, unreadTotal: resolveUnreadTotal(sortedContactList) };
  }

  async refreshConversationUnreadState<T extends ContactListItem>(
    currentList: T[],
    convId: string
  ): Promise<{ contactList: T[]; unreadTotal: number }> {
    if (!isNonEmptyString(convId) || currentList.length === 0) {
      return { contactList: currentList, unreadTotal: resolveUnreadTotal(currentList) };
    }

    const unreadCounts = await getConversationUnreadCounts();
    const unreadMarks = await getConversationUnreadMarks();
    const unreadCount = unreadCounts[convId] ?? 0;
    const unreadMarked = Boolean(unreadMarks[convId]);
    const unreadDisplayState = resolveUnreadDisplayState(unreadCount, unreadMarked);

    const contactList = currentList.map((contact) => {
      if (contact.conversation_id !== convId) {
        return contact;
      }
      return {
        ...contact,
        unreadCount,
        unreadMarked,
        ...unreadDisplayState,
      } as T;
    });

    return {
      contactList,
      unreadTotal: resolveUnreadTotal(contactList),
    };
  }

  private async bootstrapInternal(): Promise<IndexBootstrapResult | null> {
    const seq = this.startRequest();
    const contacts = await this.loadContactsFromCache();
    if (!this.isRequestActive(seq)) {
      return null;
    }
    return {
      screenModel: createReadyScreenModel({
        contentVariant: contacts.length === 0 ? 'empty' : 'data',
        refreshState: 'idle',
      }),
      contactList: contacts,
      unreadTotal: resolveUnreadTotal(contacts),
      availableContactSlots: null,
    };
  }

  private async loadContactsFromCache(): Promise<ContactListItem[]> {
    const cachedContacts = await getContacts();
    return await this.buildContactList(cachedContacts);
  }

  private async buildContactList(contacts: StoredContacts): Promise<ContactListItem[]> {
    if (contacts.length === 0) {
      return [];
    }

    const unreadCounts = await getConversationUnreadCounts();
    const unreadMarks = await getConversationUnreadMarks();

    const enriched = await Promise.all(
      contacts.map(async (contact) => {
        if (!isNonEmptyString(contact.conversation_id)) {
          return {
            ...contact,
            unreadCount: 0,
            unreadMarked: false,
          } as ContactWithPreview;
        }

        try {
          const latestMessages = await getLatestTwoRenderableMessages(contact.conversation_id);
          const latestMessage = latestMessages.length > 0 ? latestMessages[0] : null;
          return {
            ...contact,
            _latestMessage: latestMessage,
            _latestRenderableMessages: latestMessages,
            unreadCount: unreadCounts[contact.conversation_id] ?? 0,
            unreadMarked: Boolean(unreadMarks[contact.conversation_id]),
          } as ContactWithPreview;
        } catch {
          return {
            ...contact,
            _latestMessage: null,
            unreadCount: unreadCounts[contact.conversation_id] ?? 0,
            unreadMarked: Boolean(unreadMarks[contact.conversation_id]),
          } as ContactWithPreview;
        }
      })
    );

    const contactList = enriched.map(toContactListItem);
    return sortContactsByLatestMessage(contactList);
  }
}

export const createIndexPageService = (): IndexPageService => new IndexPageService();
