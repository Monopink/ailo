/**
 * Chat Page - Complete Rewrite
 * A stable, modern chat interface following WeChat-like design
 */

import { getChatContactViewModel } from '../../utils/contact-service';
import { MESSAGE_CONFIG } from '../../utils/config';
import { getUserFriendlyError } from '../../utils/error-messages';
import { getLogger } from '../../utils/logger';
import profileService from '../../utils/profile-service';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import {
  createChatPageService,
  type ChatHeaderViewModel,
  type ChatPageService,
} from '../../services/pages/chat-service';
import { MESSAGE_STATUS, MESSAGE_TYPE, type MessageType } from '../../utils/constants/message';
import {
  addMessage,
  getConversationReadState,
  getUserInfo,
  removeMessage,
  removeLatestChatInfoMessage,
  type StoredMessage,
} from '../../utils/storage';
import typingManager from '../../utils/typing-manager';
import conversationStore from '../../utils/message/conversation-store';
import messageStateStore, { MessageStoreState } from '../../utils/message/message-state-store';
import type { MessageViewModel } from '../../utils/message/message-view-model';
import { isNonEmptyString, firstNonEmptyString } from '../../utils/guards';
import { normalizeError } from '../../utils/errors';
import unreadStore from '../../utils/message/unread-store';
import viewStore from '../../utils/message/view-store';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { type ScreenModel } from '../../services/pages/page-state';

const logger = getLogger('Chat');

type MessageStatus = (typeof MESSAGE_STATUS)[keyof typeof MESSAGE_STATUS];

type ChatMessage = MessageViewModel;
type MessageRowRect = { id?: string; bottom?: number };
type MessageListQueryResult = { containerTop: number; rows: MessageRowRect[] };
type ConversationReadMarker = {
  last_read_sent_time: number;
  last_read_msg_id?: string;
};
type InitialScrollPlan = {
  isAtBottom: boolean;
  scrollIntoView: string;
  scrollAnchorKey?: number;
};

interface ChatPageData {
  pageLayoutData: PageLayoutData;
  convId: string;
  contactName: string;
  navbarTitle: string;
  contactAvatar: string;
  contactQiaoId: string;
  imConvId: string;
  userAvatar: string;
  messages: ChatMessage[];
  inputText: string;
  inputPlaceholder: string;
  inputFocused: boolean;
  maxMessageLength: number;
  prevInputValue: string;
  isContactTyping: boolean;
  showEmojiPanel: boolean;
  emojiList: string[];
  sendIconInactive: string;
  sendIconActive: string;
  isAtBottom: boolean;
  navbarSolid: boolean;
  messageListHeight: number;
  scrollAnchorKey: number;
}

type InputEvent = WechatMiniprogram.CustomEvent<{ value: string }>;
type ScrollEvent = WechatMiniprogram.CustomEvent<{ scrollTop: number; scrollHeight: number }>;

interface ChatPageCustom {
  chatService: ChatPageService;
  unsubscribeConversationStore: (() => void) | null;
  messageStoreSubscription: (() => void) | null;
  errorSubscription: (() => void) | null;
  _sendRetried: boolean;
  _retryRefreshed: boolean;
  applyScreenModel(screenModel: ScreenModel): void;
  applyChatHeaderPatch(patch: Partial<ChatHeaderViewModel>): void;
  handleAuthInvalid(): Promise<void>;
  refreshChatHeader(): Promise<void>;
  handleMessageServiceError(error: Error): void;
  updateMessagesState(
    messages: ChatMessage[],
    options?: {
      scrollIntoView?: string;
      isContactTyping?: boolean;
      extraData?: Record<string, unknown>;
    }
  ): void;
  handleMessageStateUpdate(state: MessageStoreState): void;
  showErrorMessage(error: unknown): Promise<void>;
  refreshContactInfo(convId: string): Promise<void>;
  refreshConversationChannel(): Promise<string>;
  handleInfoMessageAction(message: ChatMessage): void;
  loadMessages(): Promise<void>;
  onInputChange(event: InputEvent): void;
  onInputFocus(): void;
  onInputBlur(): void;
  onCompositionStart(): void;
  onCompositionEnd(event: InputEvent): void;
  onMessageScroll(event: ScrollEvent): void;
  syncNavbarSolidFromScrollOffset(): void;
  validateSendPreconditions(content: string): Promise<boolean>;
  appendOptimisticTextMessage(
    clientMsgId: string,
    fromQiaoId: string,
    content: string
  ): Promise<void>;
  sendTextMessage(
    messageService: Ailo.MessageService,
    clientMsgId: string,
    fromQiaoId: string,
    content: string
  ): Promise<void>;
  retrySendAfterConversationRefresh(
    messageService: Ailo.MessageService,
    clientMsgId: string,
    content: string
  ): Promise<boolean>;
  onSendMessage(): Promise<void>;
  onNavbarTitleClick(): void;
  onRetryMessage(event: WechatMiniprogram.BaseEvent): Promise<void>;
  updateMessageStatus(messageId: string, status: MessageStatus): void;
  onEmojiButtonTap(): void;
  onEmojiSelect(event: WechatMiniprogram.BaseEvent): void;
  updateMessageListMetrics(): void;
  scrollToBottom(): void;
  resolveInitialScrollPlan(messages: ChatMessage[]): Promise<InitialScrollPlan>;
  persistViewState(): Promise<void>;
  schedulePersistViewState(): void;
  clearPersistViewStateTimer(): void;
  flushPersistViewState(): void;
  activateConversation(): Promise<void>;
  getFirstVisibleMessageId(): Promise<string | null>;
  retryMessageAfterConversationNotFound(
    msgIdValue: string,
    failedMessage: StoredMessage,
    messageService: Ailo.MessageService,
    newClientMsgId: string
  ): Promise<boolean>;
  refreshUserAvatar(forceRefresh?: boolean): Promise<void>;
  _pendingViewRestore: boolean;
  _initialScrollHandled: boolean;
  _persistViewStateTimer: number | null;
  _pendingMessageState: MessageStoreState | null;
}

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
};

const buildClientMessageId = (): string =>
  `client_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;

const calcBottomThreshold = (viewHeight: number): number =>
  Math.max(80, Math.min(160, Math.round(viewHeight * 0.2)));

const NAVBAR_SOLID_THRESHOLD = 12;
const VIEW_STATE_PERSIST_THROTTLE_MS = 400;

const isUnknownArray = (value: unknown): value is unknown[] => Array.isArray(value);

const getDatasetValue = (event: WechatMiniprogram.BaseEvent, key: string): unknown => {
  const dataset = event.currentTarget.dataset as Record<string, unknown> | undefined;
  return dataset?.[key];
};

const toStringValue = (value: unknown): string | null => (typeof value === 'string' ? value : null);

const ensureMessageService = (): Ailo.MessageService => {
  const app = getApp<AppInstance>();
  const messageService = app.getMessageService();
  if (messageService === null) {
    throw new Error('MESSAGE_SERVICE_DISCONNECTED');
  }
  return messageService;
};

const parseMessageListQueryResults = (results: unknown): MessageListQueryResult | null => {
  if (!isUnknownArray(results) || results.length < 2) {
    return null;
  }
  const [container, rows] = results;
  if (container === null || typeof container !== 'object') {
    return null;
  }
  const containerTop = (container as { top?: unknown }).top;
  if (typeof containerTop !== 'number' || !Number.isFinite(containerTop)) {
    return null;
  }
  if (!Array.isArray(rows)) {
    return null;
  }
  const normalizedRows: MessageRowRect[] = [];
  for (const row of rows) {
    if (row === null || typeof row !== 'object') {
      return null;
    }
    normalizedRows.push(row as MessageRowRect);
  }
  return { containerTop, rows: normalizedRows };
};

const resolveFirstUnreadMessageId = (
  messages: ChatMessage[],
  marker: ConversationReadMarker | null
): string | null => {
  if (marker === null) {
    return null;
  }

  const timelineMessages = messages.filter(
    (message) => !message.isInfoMessage && !message.from_me && isNonEmptyString(message.msg_id)
  );
  if (timelineMessages.length === 0) {
    return null;
  }

  const lastReadMsgId = marker.last_read_msg_id;
  if (isNonEmptyString(lastReadMsgId)) {
    const lastReadIndex = timelineMessages.findIndex((message) => message.msg_id === lastReadMsgId);
    if (lastReadIndex >= 0 && lastReadIndex + 1 < timelineMessages.length) {
      return timelineMessages[lastReadIndex + 1].msg_id;
    }
  }

  const lastReadSentTime = marker.last_read_sent_time;
  if (!Number.isFinite(lastReadSentTime)) {
    return null;
  }
  const firstUnread = timelineMessages.find((message) => {
    if (typeof message.sent_time !== 'number' || !Number.isFinite(message.sent_time)) {
      return false;
    }
    return message.sent_time > lastReadSentTime;
  });
  return firstUnread?.msg_id ?? null;
};

const buildPageLayoutScreenModelPayload = (screenModel: ScreenModel): Record<string, unknown> => ({
  'pageLayoutData.screenModel': screenModel,
});

Page<ChatPageData, ChatPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'booting',
        contentVariant: 'blank',
        refreshState: 'idle',
      },
      hasFooter: true,
    }),
    convId: '',
    contactName: '',
    navbarTitle: '',
    contactAvatar: '',
    contactQiaoId: '',
    imConvId: '',
    userAvatar: '',
    messages: [] as ChatMessage[],
    inputText: '',
    inputPlaceholder: '请输入消息',
    inputFocused: false,
    maxMessageLength: MESSAGE_CONFIG.maxLength,
    prevInputValue: '',
    isContactTyping: false,
    showEmojiPanel: false,
    emojiList: [
      '😀',
      '😃',
      '😄',
      '😁',
      '😆',
      '😅',
      '🤣',
      '😂',
      '🙂',
      '😊',
      '😇',
      '😍',
      '🥰',
      '😘',
      '😗',
      '😋',
      '😛',
      '😜',
      '🤪',
      '😝',
      '🤗',
      '🤔',
      '🤐',
      '😏',
      '😒',
    ],
    // Send icon paths
    sendIconInactive: '/assets/icons/send-inactive.svg',
    sendIconActive: '/assets/icons/send-active.svg',
    isAtBottom: true,
    navbarSolid: false,
    messageListHeight: 0,
    scrollAnchorKey: 0,
  },

  chatService: null as unknown as ChatPageService,
  unsubscribeConversationStore: null,
  messageStoreSubscription: null,
  errorSubscription: null,
  _sendRetried: false,
  _retryRefreshed: false,
  _pendingViewRestore: false,
  _initialScrollHandled: false,
  _persistViewStateTimer: null,
  _pendingMessageState: null,

  applyScreenModel(screenModel: ScreenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  applyChatHeaderPatch(patch: Partial<ChatHeaderViewModel>) {
    const payload: Record<string, unknown> = {};
    if (patch.contactName !== undefined) {
      payload.contactName = patch.contactName;
      payload.navbarTitle = patch.contactName;
    }
    if (patch.navbarTitle !== undefined) {
      payload.navbarTitle = patch.navbarTitle;
    }
    if (patch.contactAvatar !== undefined) {
      payload.contactAvatar = patch.contactAvatar;
    }
    if (patch.contactQiaoId !== undefined) {
      payload.contactQiaoId = patch.contactQiaoId;
    }
    if (patch.imConvId !== undefined) {
      payload.imConvId = patch.imConvId;
    }
    if (Object.keys(payload).length > 0) {
      this.setData(payload);
    }
  },

  async handleAuthInvalid() {
    await showAuthExpiredModalAndRelogin();
  },

  async activateConversation() {
    const convId = this.data.convId;
    if (!isNonEmptyString(convId)) {
      return;
    }
    try {
      await unreadStore.setActiveConversation(convId);
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.warn('Set active conversation failed', { convId, error: err.message });
    }
  },

  async refreshChatHeader() {
    const convId = this.data.convId;
    if (!isNonEmptyString(convId)) {
      return;
    }
    const result = await this.chatService.refresh(convId);
    if (result === null) {
      return;
    }
    this.applyScreenModel(result.screenModel);
    this.applyChatHeaderPatch(result.headerPatch);
    if (result.authInvalid) {
      await this.handleAuthInvalid();
    }
  },

  updateMessagesState(
    messages,
    options: {
      scrollIntoView?: string;
      isContactTyping?: boolean;
      extraData?: Record<string, unknown>;
    } = {}
  ) {
    const payload: Record<string, unknown> = {
      messages,
    };
    if (options.scrollIntoView !== undefined) {
      payload['pageLayoutData.contentScrollIntoView'] = options.scrollIntoView;
    }
    if (options.isContactTyping !== undefined) {
      payload.isContactTyping = options.isContactTyping;
    }
    if (options.extraData !== undefined) {
      Object.assign(payload, options.extraData);
    }
    this.setData(payload);
  },

  handleMessageStateUpdate(state: MessageStoreState) {
    const convId = this.data.convId;
    if (!isNonEmptyString(convId) || state.convId !== convId) {
      return;
    }
    if (this._pendingViewRestore) {
      this._pendingMessageState = state;
      return;
    }
    const hasMessages = state.messages.length > 0;
    const shouldScroll = this.data.isAtBottom && hasMessages;
    if (shouldScroll) {
      const nextAnchorKey = this.data.scrollAnchorKey + 1;
      const shouldDisableAnimation = !this._initialScrollHandled;
      const extraData: Record<string, unknown> = { scrollAnchorKey: nextAnchorKey };
      if (shouldDisableAnimation) {
        extraData['pageLayoutData.contentScrollWithAnimation'] = false;
      }
      this.updateMessagesState(state.messages, {
        scrollIntoView: `scroll-anchor-${nextAnchorKey}`,
        isContactTyping: state.isTyping,
        extraData,
      });
      if (shouldDisableAnimation) {
        this._initialScrollHandled = true;
        wx.nextTick(() => {
          this.setData({ 'pageLayoutData.contentScrollWithAnimation': true });
        });
      }
      return;
    }
    this.updateMessagesState(state.messages, { isContactTyping: state.isTyping });
  },

  async showErrorMessage(error: unknown) {
    const messageContent = getUserFriendlyError(error as Error | string | null | undefined);
    const errorMsg: StoredMessage = {
      msg_id: `error_${Date.now()}`,
      conv_id: this.data.convId,
      content: messageContent,
      message_type: MESSAGE_TYPE.CHAT_INFO,
      sent_time: Date.now(),
    };

    await addMessage(this.data.convId, errorMsg);
    await messageStateStore.addOptimisticMessage(errorMsg);
  },

  /**
   * Handle navbar title click - navigate to contact info page
   */
  onNavbarTitleClick() {
    const convId = this.data.convId;
    if (isNonEmptyString(convId)) {
      void wx.navigateTo({
        url: `/pages/contact-info/contact-info?id=${convId}`,
        events: {
          contactAvatarUpdated: () => {
            void this.refreshChatHeader();
          },
        },
      });
    }
  },

  onReady() {
    this.updateMessageListMetrics();
  },

  scrollToBottom() {
    const nextAnchorKey = this.data.scrollAnchorKey + 1;
    const shouldDisableAnimation = !this._initialScrollHandled;
    const payload: Record<string, unknown> = {
      isAtBottom: true,
      scrollAnchorKey: nextAnchorKey,
    };
    if (shouldDisableAnimation) {
      payload['pageLayoutData.contentScrollWithAnimation'] = false;
    }
    this.setData(payload);
    wx.nextTick(() => {
      this.setData({
        'pageLayoutData.contentScrollIntoView': `scroll-anchor-${nextAnchorKey}`,
      });
      // Programmatic scroll (scroll-into-view) may not reliably trigger scroll events on first render.
      // Sync navbarSolid from the actual scrollTop so the header matches the current position.
      wx.nextTick(() => {
        this.syncNavbarSolidFromScrollOffset();
      });
      if (shouldDisableAnimation) {
        this._initialScrollHandled = true;
        wx.nextTick(() => {
          this.setData({ 'pageLayoutData.contentScrollWithAnimation': true });
        });
      }
    });
  },

  clearPersistViewStateTimer() {
    if (this._persistViewStateTimer === null) {
      return;
    }
    clearTimeout(this._persistViewStateTimer);
    this._persistViewStateTimer = null;
  },

  schedulePersistViewState() {
    if (this._pendingViewRestore) {
      return;
    }
    if (this._persistViewStateTimer !== null) {
      return;
    }
    this._persistViewStateTimer = setTimeout(() => {
      this._persistViewStateTimer = null;
      void this.persistViewState();
    }, VIEW_STATE_PERSIST_THROTTLE_MS);
  },

  flushPersistViewState() {
    this.clearPersistViewStateTimer();
    void this.persistViewState();
  },

  syncNavbarSolidFromScrollOffset() {
    const query = wx.createSelectorQuery();
    query.select('.chat-page__messages').scrollOffset((result) => {
      const scrollTopRaw = (result as { scrollTop?: unknown } | null)?.scrollTop;
      if (typeof scrollTopRaw !== 'number' || !Number.isFinite(scrollTopRaw)) {
        return;
      }
      const clampedScrollTop = Math.max(0, Math.round(scrollTopRaw));
      const shouldSolidNavbar = clampedScrollTop > NAVBAR_SOLID_THRESHOLD;
      if (shouldSolidNavbar !== this.data.navbarSolid) {
        this.setData({ navbarSolid: shouldSolidNavbar });
      }
    });
    query.exec();
  },

  async resolveInitialScrollPlan(messages: ChatMessage[]): Promise<InitialScrollPlan> {
    const convId = this.data.convId;
    const nextAnchorKey = this.data.scrollAnchorKey + 1;
    const bottomPlan: InitialScrollPlan = {
      isAtBottom: true,
      scrollIntoView: `scroll-anchor-${nextAnchorKey}`,
      scrollAnchorKey: nextAnchorKey,
    };
    if (!isNonEmptyString(convId) || messages.length === 0) {
      return bottomPlan;
    }

    try {
      const readState = await getConversationReadState();
      const marker = (readState[convId] as ConversationReadMarker | undefined) ?? null;
      const unreadTargetId = resolveFirstUnreadMessageId(messages, marker);
      const hasUnreadTarget =
        isNonEmptyString(unreadTargetId) &&
        messages.some((message) => message.msg_id === unreadTargetId && !message.isInfoMessage);
      if (hasUnreadTarget) {
        return {
          isAtBottom: false,
          scrollIntoView: `msg-${unreadTargetId}`,
        };
      }
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.warn('Read unread marker failed, fallback to stored anchor', {
        convId,
        error: err.message,
      });
    }

    const stored = await viewStore.get(convId);
    if (stored !== null && !stored.isAtBottom && isNonEmptyString(stored.lastViewedMsgId)) {
      const hasStoredAnchor = messages.some(
        (message) => message.msg_id === stored.lastViewedMsgId && !message.isInfoMessage
      );
      if (hasStoredAnchor) {
        return {
          isAtBottom: false,
          scrollIntoView: `msg-${stored.lastViewedMsgId}`,
        };
      }
    }

    return bottomPlan;
  },

  async getFirstVisibleMessageId(): Promise<string | null> {
    return new Promise((resolve) => {
      const query = wx.createSelectorQuery();
      query.select('.chat-page__messages').boundingClientRect();
      query.selectAll('.msg-row').fields({ id: true, rect: true });
      query.exec((results) => {
        const parsed = parseMessageListQueryResults(results as unknown);
        if (parsed === null) {
          resolve(null);
          return;
        }
        const { containerTop, rows } = parsed;
        const firstVisible = rows.find(
          (row) => typeof row.bottom === 'number' && row.bottom > containerTop + 1
        );
        const rawId = typeof firstVisible?.id === 'string' ? firstVisible.id : null;
        if (rawId?.startsWith('msg-')) {
          resolve(rawId.slice(4));
          return;
        }
        resolve(null);
      });
    });
  },

  async persistViewState() {
    const convId = this.data.convId;
    if (!isNonEmptyString(convId)) {
      return;
    }
    try {
      const messages = this.data.messages;
      if (messages.length === 0) {
        await viewStore.set(convId, { isAtBottom: true });
        return;
      }
      if (this.data.isAtBottom) {
        await viewStore.set(convId, { isAtBottom: true });
        return;
      }
      await new Promise<void>((resolve) => {
        wx.nextTick(resolve);
      });
      const anchorId = await this.getFirstVisibleMessageId();
      if (!isNonEmptyString(anchorId)) {
        // Keep previous anchor when current viewport cannot be resolved.
        return;
      }
      await viewStore.set(convId, {
        isAtBottom: false,
        lastViewedMsgId: anchorId,
      });
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.warn('Persist view state failed', { convId, error: err.message });
    }
  },

  /**
   * Refresh contact info from backend
   */
  async refreshContactInfo(convId: string) {
    const viewModel = await getChatContactViewModel(convId);
    const contactName = firstNonEmptyString(viewModel.displayName, this.data.contactName) ?? '';

    this.setData({
      contactName,
      navbarTitle: contactName,
      contactAvatar: viewModel.displayAvatar,
      contactQiaoId: viewModel.contactQiaoId,
      imConvId: viewModel.imConvId,
    });
  },

  async refreshConversationChannel() {
    const messageService = ensureMessageService();
    const previousImConvId = this.data.imConvId;

    if (typeof messageService.invalidateConversation === 'function') {
      await messageService.invalidateConversation(previousImConvId);
    }

    await this.refreshContactInfo(this.data.convId);
    let nextImConvId = this.data.imConvId;

    try {
      const refreshedState = await conversationStore.refresh();
      if (isNonEmptyString(refreshedState.im_conv_id)) {
        nextImConvId = refreshedState.im_conv_id;
      }
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to refresh conversation store', { error: err.message });
    }

    this.setData({ imConvId: nextImConvId });

    logger.info('Conversation channel refreshed', {
      convId: this.data.convId,
      oldImConvId: previousImConvId,
      imConvId: nextImConvId,
    });

    return nextImConvId;
  },

  async refreshUserAvatar(forceRefresh = false) {
    const cached = profileService.getProfile();
    if (!forceRefresh && cached !== null) {
      this.setData({ userAvatar: cached.displayAvatar });
      return;
    }

    try {
      const profile = await profileService.loadProfile(forceRefresh);
      this.setData({ userAvatar: profile.displayAvatar });
    } catch (error) {
      logger.warn('Load profile for avatar failed', {
        error: error instanceof Error ? error.message : String(error),
      });
    }
  },

  handleInfoMessageAction(message: ChatMessage) {
    const action = message.action as { type?: string; target_msg_id?: string } | null;
    if (action === null) {
      return;
    }

    if (action.type === 'mark_message_failed' && isNonEmptyString(action.target_msg_id)) {
      this.updateMessageStatus(action.target_msg_id, MESSAGE_STATUS.FAILED);
    }
  },

  async onLoad(options: Record<string, string | undefined>) {
    // Recreate service per page lifecycle to avoid reusing a disposed instance.
    this.chatService = createChatPageService();
    const convId = options.id ?? '';
    if (!isNonEmptyString(convId)) {
      this.setData({
        'pageLayoutData.hasFooter': false,
      });
      this.applyScreenModel({
        screenState: 'ready',
        contentVariant: 'blank',
        refreshState: 'idle',
      });
      return;
    }

    this.setData({ convId });
    this._pendingViewRestore = true;
    this._initialScrollHandled = false;
    this._pendingMessageState = null;
    this.messageStoreSubscription = messageStateStore.subscribe((state) => {
      this.handleMessageStateUpdate(state);
    });
    this.errorSubscription = messageStateStore.onError((error) => {
      this.handleMessageServiceError(error);
    });
    this.unsubscribeConversationStore = conversationStore.subscribe((state) => {
      if (state === null || !isNonEmptyString(state.im_conv_id)) {
        return;
      }
      this.setData({ imConvId: state.im_conv_id });
    });

    try {
      const bootstrap = await this.chatService.bootstrap(convId);
      if (bootstrap === null) {
        logger.warn('Chat bootstrap returned null, fallback to ready state', { convId });
        this.applyScreenModel({
          screenState: 'ready',
          contentVariant: 'data',
          refreshState: 'degraded',
        });
        return;
      }
      this.applyChatHeaderPatch(bootstrap.header);

      void this.refreshUserAvatar();
      await this.loadMessages();
      void this.refreshChatHeader();
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to load chat page', { error: err.message });
      this.applyScreenModel({
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'degraded',
      });
    }
  },

  onShow() {
    const convId = this.data.convId;
    if (!isNonEmptyString(convId)) {
      return;
    }

    if (this._pendingViewRestore) {
      return;
    }

    void this.activateConversation();
    void this.refreshChatHeader();
    void this.loadMessages();
    void this.refreshUserAvatar();
  },

  onHide() {
    this.flushPersistViewState();
    unreadStore.clearActiveConversation(this.data.convId);
  },

  onUnload() {
    this.flushPersistViewState();
    unreadStore.clearActiveConversation(this.data.convId);
    typingManager.cleanup(this.data.convId);
    this.chatService.dispose();
    this.clearPersistViewStateTimer();

    if (this.unsubscribeConversationStore !== null) {
      this.unsubscribeConversationStore();
      this.unsubscribeConversationStore = null;
    }
    if (this.messageStoreSubscription !== null) {
      this.messageStoreSubscription();
      this.messageStoreSubscription = null;
    }
    if (this.errorSubscription !== null) {
      this.errorSubscription();
      this.errorSubscription = null;
    }
    this._pendingMessageState = null;
    messageStateStore.clearConversation();
  },

  async loadMessages() {
    const currentScreenModel = this.data.pageLayoutData.screenModel;
    const shouldRestoreInitialView = this._pendingViewRestore;
    try {
      if (!shouldRestoreInitialView) {
        this.applyScreenModel({
          ...currentScreenModel,
          screenState: 'ready',
          contentVariant: 'data',
          refreshState: 'refreshing',
        });
      }
      await messageStateStore.setConversation(this.data.convId);
      if (shouldRestoreInitialView) {
        const currentState = messageStateStore.getStateSnapshot();
        const initialState =
          currentState.convId === this.data.convId
            ? currentState
            : { convId: this.data.convId, messages: [] as ChatMessage[], isTyping: false };
        const scrollPlan = await this.resolveInitialScrollPlan(initialState.messages);
        const initialPayload: Record<string, unknown> = {
          messages: initialState.messages,
          isContactTyping: initialState.isTyping,
          isAtBottom: scrollPlan.isAtBottom,
          'pageLayoutData.screenModel': {
            screenState: 'ready',
            contentVariant: 'data',
            refreshState: 'idle',
          },
          'pageLayoutData.contentScrollIntoView': scrollPlan.scrollIntoView,
          'pageLayoutData.contentScrollWithAnimation': false,
        };
        if (scrollPlan.scrollAnchorKey !== undefined) {
          initialPayload.scrollAnchorKey = scrollPlan.scrollAnchorKey;
        }
        await new Promise<void>((resolve) => {
          this.setData(initialPayload, resolve);
        });
        this._pendingViewRestore = false;
        this._initialScrollHandled = true;
        this.setData({ 'pageLayoutData.contentScrollWithAnimation': true });

        const bufferedState = this._pendingMessageState;
        this._pendingMessageState = null;
        const isBufferedStateUnchanged =
          bufferedState !== null &&
          bufferedState.messages.length === initialState.messages.length &&
          bufferedState.isTyping === initialState.isTyping &&
          bufferedState.messages[bufferedState.messages.length - 1]?.msg_id ===
            initialState.messages[initialState.messages.length - 1]?.msg_id;
        if (
          bufferedState !== null &&
          bufferedState.convId === this.data.convId &&
          !isBufferedStateUnchanged
        ) {
          this.handleMessageStateUpdate(bufferedState);
        }

        void this.activateConversation();
        return;
      }
      this.applyScreenModel({
        ...this.data.pageLayoutData.screenModel,
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      });
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to load messages', { error: err.message });
      if (this._pendingViewRestore) {
        this._pendingViewRestore = false;
      }
      this._pendingMessageState = null;
      this.applyScreenModel({
        ...this.data.pageLayoutData.screenModel,
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'degraded',
      });
    }
  },

  /**
   * Handle input change
   */
  onInputChange(event: InputEvent) {
    const newValue = event.detail.value;
    const oldValue = this.data.prevInputValue;

    this.setData({
      inputText: newValue,
      prevInputValue: newValue,
    });

    // Notify typing manager
    typingManager.onInputChange(this.data.convId, newValue, oldValue);
  },

  /**
   * Handle input focus
   */
  onInputFocus() {
    this.setData({
      inputFocused: true,
      showEmojiPanel: false, // Hide emoji panel when keyboard shows
    });

    // Notify typing manager
    typingManager.onInputFocus(this.data.convId, this.data.inputText);
    wx.nextTick(() => {
      this.updateMessageListMetrics();
    });
  },

  /**
   * Handle input blur
   */
  onInputBlur() {
    this.setData({ inputFocused: false });

    // Notify typing manager
    typingManager.onInputBlur(this.data.convId);
    wx.nextTick(() => {
      this.updateMessageListMetrics();
    });
  },

  onCompositionStart() {
    typingManager.onCompositionStart(this.data.convId, this.data.inputText);
  },

  onCompositionEnd(event: InputEvent) {
    const value = event.detail.value;
    typingManager.onCompositionEnd(this.data.convId, value);
  },

  /**
   * Toggle emoji panel visibility
   */
  onEmojiButtonTap() {
    this.setData({
      showEmojiPanel: !this.data.showEmojiPanel,
      inputFocused: false, // Hide keyboard when emoji panel shows
    });
  },

  onMessageScroll(event: ScrollEvent) {
    const { scrollTop, scrollHeight } = event.detail;
    const clampedScrollTop = Math.max(0, Math.round(scrollTop));
    const viewHeight = this.data.messageListHeight;
    if (viewHeight <= 0) {
      this.updateMessageListMetrics();
      return;
    }
    const threshold = calcBottomThreshold(viewHeight);
    const isAtBottom = clampedScrollTop + viewHeight >= scrollHeight - threshold;
    const shouldSolidNavbar = clampedScrollTop > NAVBAR_SOLID_THRESHOLD;
    const payload: Partial<ChatPageData> = {};
    if (isAtBottom !== this.data.isAtBottom) {
      payload.isAtBottom = isAtBottom;
    }
    if (shouldSolidNavbar !== this.data.navbarSolid) {
      payload.navbarSolid = shouldSolidNavbar;
    }
    if (Object.keys(payload).length > 0) {
      this.setData(payload);
    }
    this.schedulePersistViewState();
  },

  updateMessageListMetrics() {
    const query = wx.createSelectorQuery();
    query.select('.chat-page__messages').boundingClientRect((rect) => {
      if (typeof rect.height !== 'number' || !Number.isFinite(rect.height)) {
        return;
      }
      const height = Math.max(0, Math.round(rect.height));
      if (height > 0 && height !== this.data.messageListHeight) {
        this.setData({ messageListHeight: height });
      }
    });
    query.exec();
  },

  /**
   * Handle emoji selection
   */
  onEmojiSelect(event: WechatMiniprogram.BaseEvent) {
    const emoji = toStringValue(getDatasetValue(event, 'emoji'));
    if (!isNonEmptyString(emoji)) {
      return;
    }

    const newValue = this.data.inputText + emoji;
    this.setData({
      inputText: newValue,
    });

    // Notify typing manager
    typingManager.onInputChange(this.data.convId, newValue, this.data.inputText);
  },

  async onRetryMessage(event: WechatMiniprogram.BaseEvent) {
    const msgIdValue = toStringValue(getDatasetValue(event, 'msgid'));
    if (!isNonEmptyString(msgIdValue)) {
      return;
    }
    const failedMessage = this.data.messages.find((msg) => msg.msg_id === msgIdValue);
    if (failedMessage?.status !== MESSAGE_STATUS.FAILED) {
      return;
    }

    typingManager.forceStopTyping(this.data.convId);
    const messageService = ensureMessageService();
    let newClientMsgId = '';

    try {
      const userInfo = await getUserInfo();
      if (!isNonEmptyString(userInfo?.qiao_id)) {
        throw new Error('User info missing');
      }

      messageStateStore.removeMessage(msgIdValue);
      await removeMessage(this.data.convId, msgIdValue);
      const removedInfoMsgId = await removeLatestChatInfoMessage(this.data.convId);
      if (isNonEmptyString(removedInfoMsgId)) {
        messageStateStore.removeMessage(removedInfoMsgId);
      }

      newClientMsgId = buildClientMessageId();
      const newMessage: StoredMessage = {
        ...failedMessage,
        msg_id: newClientMsgId,
        msg_id_server: null,
        msg_id_client: newClientMsgId,
        sent_time: Date.now(),
        status: MESSAGE_STATUS.SENDING,
      };

      await messageStateStore.addOptimisticMessage(newMessage);
      await addMessage(this.data.convId, newMessage);

      await messageService.sendMessage({
        client_msg_id: newClientMsgId,
        from_qiao_id: userInfo.qiao_id,
        to_qiao_id: this.data.contactQiaoId,
        conv_id: this.data.convId,
        content: newMessage.content ?? '',
        message_type: (newMessage.message_type ?? MESSAGE_TYPE.TEXT) as MessageType,
        supports_typing: newMessage.supports_typing !== false,
      });

      logger.info('Message retry successful', {
        old_msg_id: msgIdValue,
        new_msg_id: newClientMsgId,
      });
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to retry message', { msg_id: msgIdValue, error: err.message });

      if (err.message === 'CONVERSATION_NOT_FOUND') {
        const retried = await this.retryMessageAfterConversationNotFound(
          msgIdValue,
          failedMessage,
          messageService,
          newClientMsgId
        );
        if (retried === true) {
          return;
        }
      }

      if (isNonEmptyString(newClientMsgId)) {
        messageStateStore.updateMessageStatus(newClientMsgId, MESSAGE_STATUS.FAILED);
      }
      await this.showErrorMessage(err);
    }
  },

  async retryMessageAfterConversationNotFound(
    msgIdValue: string,
    failedMessage: StoredMessage,
    messageService: Ailo.MessageService,
    newClientMsgId: string
  ): Promise<boolean> {
    if (this._retryRefreshed) {
      return false;
    }

    this._retryRefreshed = true;
    logger.info('Retry failed due to conversation not found, refreshing contact info', {
      convId: this.data.convId,
      oldImConvId: this.data.imConvId,
    });

    try {
      const refreshedImConvId = await this.refreshConversationChannel();
      const nextImConvId = firstNonEmptyString(refreshedImConvId, this.data.imConvId) ?? '';
      logger.info('Contact info refreshed for retry, retrying send', { newImConvId: nextImConvId });

      const userInfo = await getUserInfo();
      if (!isNonEmptyString(userInfo?.qiao_id)) {
        throw new Error('User info missing');
      }

      await messageService.sendMessage({
        client_msg_id: firstNonEmptyString(newClientMsgId, msgIdValue) ?? msgIdValue,
        from_qiao_id: userInfo.qiao_id,
        to_qiao_id: this.data.contactQiaoId,
        conv_id: this.data.convId,
        content: failedMessage.content ?? '',
        message_type: (failedMessage.message_type ?? MESSAGE_TYPE.TEXT) as MessageType,
        supports_typing: failedMessage.supports_typing !== false,
      });

      this._retryRefreshed = false;
      logger.info('Message retry successful after refresh', {
        old_msg_id: msgIdValue,
        new_msg_id: firstNonEmptyString(newClientMsgId, msgIdValue) ?? msgIdValue,
      });
      return true;
    } catch (retryError: unknown) {
      const retryErr = normalizeError(retryError);
      logger.error('Retry failed after refresh', { error: retryErr.message });
      this._retryRefreshed = false;
      return false;
    }
  },

  handleMessageServiceError(error: Error) {
    logger.error('Message service emitted an error', { error: error.message });
    const friendly = getUserFriendlyError(error);
    showToast(friendly);
  },

  updateMessageStatus(messageId: string, status: MessageStatus) {
    messageStateStore.updateMessageStatus(messageId, status);
  },

  async validateSendPreconditions(content: string): Promise<boolean> {
    if (content.length === 0) {
      return false;
    }
    if (content.length > this.data.maxMessageLength) {
      showToast(`消息长度不能超过${this.data.maxMessageLength}字`);
      return false;
    }

    const currentImConvId = await conversationStore.getImConvId();
    const hasContactQiaoId = isNonEmptyString(this.data.contactQiaoId);
    const hasCurrentImConvId = isNonEmptyString(currentImConvId);
    if (!hasContactQiaoId || !hasCurrentImConvId) {
      logger.error('Missing contact info', {
        contactQiaoId: this.data.contactQiaoId,
        imConvId: this.data.imConvId,
      });
      await this.showErrorMessage('CONVERSATION_NOT_FOUND');
      return false;
    }

    return true;
  },

  async appendOptimisticTextMessage(
    clientMsgId: string,
    fromQiaoId: string,
    content: string
  ): Promise<void> {
    const optimisticMsg: StoredMessage = {
      msg_id: clientMsgId,
      msg_id_server: null,
      msg_id_client: clientMsgId,
      from_qiao_id: fromQiaoId,
      to_qiao_id: this.data.contactQiaoId,
      conv_id: this.data.convId,
      content,
      message_type: MESSAGE_TYPE.TEXT,
      supports_typing: true,
      sent_time: Date.now(),
      status: MESSAGE_STATUS.SENDING,
    };

    await messageStateStore.addOptimisticMessage(optimisticMsg);
    this.setData({
      inputText: '',
      prevInputValue: '',
    });
    await addMessage(this.data.convId, optimisticMsg);
  },

  async sendTextMessage(
    messageService: Ailo.MessageService,
    clientMsgId: string,
    fromQiaoId: string,
    content: string
  ): Promise<void> {
    await messageService.sendMessage({
      client_msg_id: clientMsgId,
      from_qiao_id: fromQiaoId,
      to_qiao_id: this.data.contactQiaoId,
      conv_id: this.data.convId,
      content,
      message_type: MESSAGE_TYPE.TEXT,
      supports_typing: true,
    });
  },

  async retrySendAfterConversationRefresh(
    messageService: Ailo.MessageService,
    clientMsgId: string,
    content: string
  ): Promise<boolean> {
    if (this._sendRetried) {
      return false;
    }

    this._sendRetried = true;
    logger.info('Conversation not found, refreshing contact info and retrying', {
      convId: this.data.convId,
      oldImConvId: this.data.imConvId,
    });

    try {
      const refreshedImConvId = await this.refreshConversationChannel();
      const nextImConvId = firstNonEmptyString(refreshedImConvId, this.data.imConvId) ?? '';
      logger.info('Contact info refreshed, retrying send', { newImConvId: nextImConvId });

      const userInfo = await getUserInfo();
      if (!isNonEmptyString(userInfo?.qiao_id)) {
        throw new Error('User info missing');
      }

      await this.sendTextMessage(messageService, clientMsgId, userInfo.qiao_id, content);
      logger.info('Message sent successfully after refresh', { msg_id: clientMsgId });
      return true;
    } catch (retryError: unknown) {
      const retryErr = normalizeError(retryError);
      logger.error('Retry send failed after refresh', {
        error: retryErr.message,
        errorType: retryError instanceof Error ? retryError.constructor.name : 'Unknown',
      });
      return false;
    } finally {
      this._sendRetried = false;
    }
  },

  async onSendMessage() {
    const content = this.data.inputText.trim();
    if (!(await this.validateSendPreconditions(content))) {
      return;
    }

    typingManager.forceStopTyping(this.data.convId);

    const messageService = ensureMessageService();
    let clientMsgId = '';

    try {
      const userInfo = await getUserInfo();
      if (!isNonEmptyString(userInfo?.qiao_id)) {
        throw new Error('User info missing');
      }

      clientMsgId = buildClientMessageId();
      await this.appendOptimisticTextMessage(clientMsgId, userInfo.qiao_id, content);
      await this.sendTextMessage(messageService, clientMsgId, userInfo.qiao_id, content);
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to send message', { error: err.message });

      if (err.message === 'CONVERSATION_NOT_FOUND') {
        const retried = await this.retrySendAfterConversationRefresh(
          messageService,
          clientMsgId,
          content
        );
        if (retried) {
          return;
        }
      }

      if (isNonEmptyString(clientMsgId)) {
        messageStateStore.updateMessageStatus(clientMsgId, MESSAGE_STATUS.FAILED);
      }
      await this.showErrorMessage(err);
    }
  },
});
