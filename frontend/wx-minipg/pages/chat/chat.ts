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
import { MESSAGE_STATUS, MESSAGE_TYPE, type MessageType } from '../../utils/constants/message';
import {
  addMessage,
  getContactByConvId,
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

const logger = getLogger('Chat');

type MessageStatus = (typeof MESSAGE_STATUS)[keyof typeof MESSAGE_STATUS];

type ChatMessage = MessageViewModel;
type MessageRowRect = { id?: string; bottom?: number };
type MessageListQueryResult = { containerTop: number; rows: MessageRowRect[] };

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
  unsubscribeConversationStore: (() => void) | null;
  messageStoreSubscription: (() => void) | null;
  errorSubscription: (() => void) | null;
  _sendRetried: boolean;
  _retryRefreshed: boolean;
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
  onRetry(): void;
  onInputChange(event: InputEvent): void;
  onInputFocus(): void;
  onInputBlur(): void;
  onCompositionStart(): void;
  onCompositionEnd(event: InputEvent): void;
  onMessageScroll(event: ScrollEvent): void;
  syncNavbarSolidFromScrollOffset(): void;
  onSendMessage(): Promise<void>;
  onNavbarTitleClick(): void;
  onRetryMessage(event: WechatMiniprogram.BaseEvent): Promise<void>;
  updateMessageStatus(messageId: string, status: MessageStatus): void;
  onEmojiButtonTap(): void;
  onEmojiSelect(event: WechatMiniprogram.BaseEvent): void;
  updateMessageListMetrics(): void;
  scrollToBottom(): void;
  restoreViewState(messages: ChatMessage[]): Promise<void>;
  persistViewState(): Promise<void>;
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

Page<ChatPageData, ChatPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      isLoading: true,
      emptyMessage: '开始和对方聊天吧～',
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

  unsubscribeConversationStore: null,
  messageStoreSubscription: null,
  errorSubscription: null,
  _sendRetried: false,
  _retryRefreshed: false,
  _pendingViewRestore: false,
  _initialScrollHandled: false,

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
      'pageLayoutData.isEmpty': messages.length === 0,
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
      this.updateMessagesState(state.messages, { isContactTyping: state.isTyping });
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
      void wx.navigateTo({ url: `/pages/contact-info/contact-info?id=${convId}` });
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

  async restoreViewState(messages: ChatMessage[]) {
    const convId = this.data.convId;
    if (!isNonEmptyString(convId)) {
      return;
    }
    const stored = await viewStore.get(convId);
    const hasMessages = messages.length > 0;
    const shouldDisableAnimation = !this._initialScrollHandled;

    // Case 1: No stored state, or explicitly at bottom, or no messages -> scroll to bottom
    if (stored === null || stored.isAtBottom || !hasMessages) {
      this.scrollToBottom();
      return;
    }

    // Case 2: Has stored anchor, check if it exists in current messages
    const targetId = stored.lastViewedMsgId;
    const hasTarget =
      isNonEmptyString(targetId) &&
      messages.some((message) => message.msg_id === targetId && !message.isInfoMessage);

    if (!hasTarget) {
      // Anchor not found, fallback to bottom
      this.scrollToBottom();
      return;
    }

    // Case 3: Anchor found, scroll to it
    const payload: Record<string, unknown> = {
      isAtBottom: false,
      'pageLayoutData.contentScrollIntoView': `msg-${targetId}`,
    };
    if (shouldDisableAnimation) {
      payload['pageLayoutData.contentScrollWithAnimation'] = false;
    }
    this.setData(payload);
    wx.nextTick(() => {
      this.syncNavbarSolidFromScrollOffset();
    });
    if (shouldDisableAnimation) {
      this._initialScrollHandled = true;
      wx.nextTick(() => {
        this.setData({ 'pageLayoutData.contentScrollWithAnimation': true });
      });
    }
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
        await viewStore.set(convId, { isAtBottom: true });
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
    const convId = options.id ?? '';
    if (!isNonEmptyString(convId)) {
      this.setData({
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': '参数错误',
      });
      showToast('参数错误');
      void wx.navigateBack();
      return;
    }

    this.setData({ convId });
    this._pendingViewRestore = true;
    this._initialScrollHandled = false;
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
      const userInfo = await getUserInfo();
      if (!isNonEmptyString(userInfo?.qiao_id)) {
        throw new Error('User info missing');
      }
      await this.refreshUserAvatar();

      const contact = await getContactByConvId(convId);
      if (contact === null) {
        logger.error('Contact not found', { convId });
        this.setData({
          'pageLayoutData.isLoading': false,
          'pageLayoutData.hasError': true,
          'pageLayoutData.errorMessage': '联系人不存在',
        });
        showToast('联系人不存在');
        return;
      }

      const viewModel = await getChatContactViewModel(convId);
      const contactName = firstNonEmptyString(viewModel.displayName, '') ?? '';
      this.setData({
        contactName,
        navbarTitle: contactName,
        contactAvatar: viewModel.displayAvatar,
        contactQiaoId: viewModel.contactQiaoId,
        imConvId: viewModel.imConvId,
      });

      await this.loadMessages();
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to load chat page', { error: err.message });
      showToast('加载失败');
      this.setData({
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': isNonEmptyString(err.message) ? err.message : '加载失败',
      });
    }
  },

  onShow() {
    const convId = this.data.convId;
    if (!isNonEmptyString(convId)) {
      return;
    }
    void (async () => {
      try {
        await unreadStore.setActiveConversation(convId);
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.warn('Set active conversation failed', { error: err.message });
      }
    })();

    void this.refreshUserAvatar();
  },

  onHide() {
    void this.persistViewState();
    unreadStore.clearActiveConversation(this.data.convId);
  },

  onUnload() {
    void this.persistViewState();
    profileService.cancelRetries();
    unreadStore.clearActiveConversation(this.data.convId);
    typingManager.cleanup(this.data.convId);

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
    messageStateStore.clearConversation();
  },

  async loadMessages() {
    try {
      this.setData({
        'pageLayoutData.isLoading': true,
        'pageLayoutData.hasError': false,
        'pageLayoutData.errorMessage': '',
      });
      await messageStateStore.setConversation(this.data.convId);
      this.setData({
        'pageLayoutData.isLoading': false,
      });
      if (this._pendingViewRestore) {
        this._pendingViewRestore = false;
        wx.nextTick(() => {
          void this.restoreViewState(this.data.messages);
        });
      }
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to load messages', { error: err.message });
      showToast('加载消息失败');
      this.setData({
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': isNonEmptyString(err.message) ? err.message : '加载消息失败',
      });
    }
  },

  onRetry() {
    void this.loadMessages();
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
  },

  updateMessageListMetrics() {
    const query = wx.createSelectorQuery();
    query.select('.chat-page__messages').boundingClientRect((rect) => {
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

  async onSendMessage() {
    const content = this.data.inputText.trim();
    if (content.length === 0) {
      return;
    }

    if (content.length > this.data.maxMessageLength) {
      showToast(`消息长度不能超过${this.data.maxMessageLength}字`);
      return;
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
      const optimisticMsg: StoredMessage = {
        msg_id: clientMsgId,
        from_qiao_id: userInfo.qiao_id,
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

      await messageService.sendMessage({
        client_msg_id: clientMsgId,
        from_qiao_id: userInfo.qiao_id,
        to_qiao_id: this.data.contactQiaoId,
        conv_id: this.data.convId,
        content,
        message_type: MESSAGE_TYPE.TEXT,
        supports_typing: true,
      });
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to send message', { error: err.message });

      if (err.message === 'CONVERSATION_NOT_FOUND' && !this._sendRetried) {
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

          await messageService.sendMessage({
            client_msg_id: clientMsgId,
            from_qiao_id: userInfo.qiao_id,
            to_qiao_id: this.data.contactQiaoId,
            conv_id: this.data.convId,
            content,
            message_type: MESSAGE_TYPE.TEXT,
            supports_typing: true,
          });

          this._sendRetried = false;
          logger.info('Message sent successfully after refresh', { msg_id: clientMsgId });
          return;
        } catch (retryError) {
          const retryErr = normalizeError(retryError);
          logger.error('Retry send failed after refresh', {
            error: retryErr.message,
            errorType: retryError instanceof Error ? retryError.constructor.name : 'Unknown',
          });
          this._sendRetried = false;
        }
      }

      if (isNonEmptyString(clientMsgId)) {
        messageStateStore.updateMessageStatus(clientMsgId, MESSAGE_STATUS.FAILED);
      }
      await this.showErrorMessage(err);
    }
  },
});
