/**
 * Chat Page - Complete Rewrite
 * A stable, modern chat interface following WeChat-like design
 */

import { get } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import { MESSAGE_CONFIG } from '../../utils/config';
import { getUserFriendlyError } from '../../utils/error-messages';
import { getLogger } from '../../utils/logger';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { MESSAGE_STATUS, MESSAGE_TYPE, type MessageType } from '../../utils/constants/message';
import {
  addMessage,
  getContactByConvId,
  getContacts,
  getUserInfo,
  saveContacts,
  type StoredContact,
  type StoredMessage,
} from '../../utils/storage';
import typingManager from '../../utils/typing-manager';
import conversationStore from '../../utils/message/conversation-store';
import messageStateStore, { MessageStoreState } from '../../utils/message/message-state-store';
import type { MessageViewModel } from '../../utils/message/message-view-model';
import {
  hasValue,
  isNonEmptyString,
  firstNonEmptyString,
  isPositiveNumber,
} from '../../utils/guards';

const logger = getLogger('Chat');

type MessageStatus = (typeof MESSAGE_STATUS)[keyof typeof MESSAGE_STATUS];

type ChatMessage = MessageViewModel;

interface ContactProfile {
  avatar_url?: string | null;
  nickname?: string | null;
  gender?: number | null;
  bio?: string | null;
  region?: string | null;
}

interface ConversationResponse {
  profile?: ContactProfile;
  contact_qiao_id: string;
  im_conv_id: string;
}

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
  statusBarHeight: number;
  showEmojiPanel: boolean;
  emojiList: string[];
  sendIconInactive: string;
  sendIconActive: string;
}

type InputEvent = WechatMiniprogram.CustomEvent<{ value: string }>;

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
  refreshContactInfo(convId: string): Promise<ConversationResponse>;
  refreshConversationChannel(): Promise<string>;
  handleChatInfoAction(message: ChatMessage): void;
  loadMessages(): Promise<void>;
  onInputChange(event: InputEvent): void;
  onInputFocus(): void;
  onInputBlur(): void;
  onCompositionStart(): void;
  onCompositionEnd(event: InputEvent): void;
  onSendMessage(): Promise<void>;
  onNavbarBack(): void;
  onNavbarTitleClick(): void;
  onRetryMessage(event: WechatMiniprogram.BaseEvent): Promise<void>;
  updateMessageStatus(messageId: string, status: MessageStatus): void;
  onEmojiButtonTap(): void;
  onEmojiSelect(event: WechatMiniprogram.BaseEvent): void;
  retryMessageAfterConversationNotFound(
    msgIdValue: string,
    failedMessage: StoredMessage,
    messageService: Ailo.MessageService,
    newClientMsgId: string
  ): Promise<boolean>;
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

const buildClientMessageId = (): string =>
  `client_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;

const getDatasetValue = (event: WechatMiniprogram.BaseEvent, key: string): unknown => {
  const dataset = event.currentTarget.dataset as Record<string, unknown> | undefined;
  return dataset?.[key];
};

const ensureMessageService = (): Ailo.MessageService => {
  const app = getApp<AppInstance>();
  const messageService = app.getMessageService();
  if (!hasValue(messageService)) {
    throw new Error('MESSAGE_SERVICE_DISCONNECTED');
  }
  return messageService;
};

Page<ChatPageData, ChatPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      isLoading: true,
      emptyMessage: '暂未开始聊天',
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
    statusBarHeight: 0,
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
  },

  unsubscribeConversationStore: null,
  messageStoreSubscription: null,
  errorSubscription: null,
  _sendRetried: false,
  _retryRefreshed: false,

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
    const hasMessages = state.messages.length > 0;
    const scrollIntoView = hasMessages
      ? `msg-${state.messages[state.messages.length - 1].msg_id}`
      : '';
    this.updateMessagesState(state.messages, {
      scrollIntoView,
      isContactTyping: state.isTyping,
    });
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
   * Handle navbar back button click
   */
  onNavbarBack() {
    void wx.navigateBack();
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

  /**
   * Refresh contact info from backend
   */
  async refreshContactInfo(convId: string) {
    const conversation = await get<ConversationResponse>(`/contacts/${convId}/conversation`);

    if (!hasValue(conversation)) {
      throw new Error('CONVERSATION_NOT_FOUND');
    }

    const profile: ContactProfile = conversation.profile ?? {};
    const contactName =
      firstNonEmptyString(profile.nickname, this.data.contactName, conversation.contact_qiao_id) ??
      '';

    this.setData({
      contactName,
      navbarTitle: contactName,
      contactAvatar: getAvatarUrl(profile.avatar_url ?? this.data.contactAvatar),
      contactQiaoId: conversation.contact_qiao_id,
      imConvId: conversation.im_conv_id,
    });

    const contacts = await getContacts();
    const contactIndex = contacts.findIndex((contact) => contact.conv_id === convId);

    if (contactIndex !== -1) {
      const current = contacts[contactIndex];
      const updatedContact: StoredContact & { im_conv_id?: string } = {
        ...current,
        im_conv_id: conversation.im_conv_id,
        contact_qiao_id: conversation.contact_qiao_id,
        profile: {
          ...(current.profile ?? {}),
          ...profile,
        },
      };
      contacts[contactIndex] = updatedContact;
      await saveContacts(contacts);
      logger.info('Contact info refreshed and cached', { convId });
    }

    return conversation;
  },

  async refreshConversationChannel() {
    const messageService = ensureMessageService();
    const previousImConvId = this.data.imConvId;

    if (typeof messageService.invalidateConversation === 'function') {
      await messageService.invalidateConversation(previousImConvId);
    }

    const refreshedConversation = await this.refreshContactInfo(this.data.convId);
    let nextImConvId = refreshedConversation.im_conv_id;

    try {
      const refreshedState = await conversationStore.refresh();
      if (isNonEmptyString(refreshedState.im_conv_id)) {
        nextImConvId = refreshedState.im_conv_id;
      }
    } catch (error) {
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

  handleChatInfoAction(message: ChatMessage) {
    const action = message.action as { type?: string; target_msg_id?: string } | null;
    if (!hasValue(action)) {
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

    // Get status bar height for custom navbar
    const systemInfo = wx.getSystemInfoSync();
    const statusBarHeight = isPositiveNumber(systemInfo.statusBarHeight)
      ? systemInfo.statusBarHeight
      : 20;
    this.setData({
      statusBarHeight,
    });

    this.setData({ convId });
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
      this.setData({ userAvatar: getAvatarUrl(userInfo.avatar ?? '') });

      const contact = await getContactByConvId(convId);
      if (!hasValue(contact)) {
        logger.error('Contact not found', { convId });
        this.setData({
          'pageLayoutData.isLoading': false,
          'pageLayoutData.hasError': true,
          'pageLayoutData.errorMessage': '联系人不存在',
        });
        showToast('联系人不存在');
        return;
      }

      const profile: ContactProfile = contact.profile ?? {};
      const contactName =
        firstNonEmptyString(contact.alias, profile.nickname, contact.contact_qiao_id) ?? '';

      const contactWithIm = contact as StoredContact & { im_conv_id?: string };
      const conversationState = await conversationStore.getState();
      const currentImConvId =
        firstNonEmptyString(conversationState?.im_conv_id, contactWithIm.im_conv_id) ?? '';

      this.setData({
        contactName,
        navbarTitle: contactName,
        contactAvatar: getAvatarUrl(profile.avatar_url ?? ''),
        contactQiaoId: contact.contact_qiao_id ?? '',
        imConvId: currentImConvId,
      });

      await this.loadMessages();
    } catch (error) {
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

  onUnload() {
    typingManager.cleanup(this.data.convId);

    if (hasValue(this.unsubscribeConversationStore)) {
      this.unsubscribeConversationStore();
      this.unsubscribeConversationStore = null;
    }
    if (hasValue(this.messageStoreSubscription)) {
      this.messageStoreSubscription();
      this.messageStoreSubscription = null;
    }
    if (hasValue(this.errorSubscription)) {
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
    } catch (error) {
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
  },

  /**
   * Handle input blur
   */
  onInputBlur() {
    this.setData({ inputFocused: false });

    // Notify typing manager
    typingManager.onInputBlur(this.data.convId);
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

  /**
   * Handle emoji selection
   */
  onEmojiSelect(event: WechatMiniprogram.BaseEvent) {
    const emoji = getDatasetValue(event, 'emoji') as string | undefined;
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
    const msgIdValue = getDatasetValue(event, 'msgid');
    if (!isNonEmptyString(msgIdValue)) {
      return;
    }
    const failedMessage = this.data.messages.find((msg) => msg.msg_id === msgIdValue);
    if (!hasValue(failedMessage) || failedMessage.status !== MESSAGE_STATUS.FAILED) {
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
        from: userInfo.qiao_id,
        to: this.data.contactQiaoId,
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
        from: userInfo.qiao_id,
        to: this.data.contactQiaoId,
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
        from: userInfo.qiao_id,
        to: this.data.contactQiaoId,
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
        from: userInfo.qiao_id,
        to: this.data.contactQiaoId,
        conv_id: this.data.convId,
        content,
        message_type: MESSAGE_TYPE.TEXT,
        supports_typing: true,
      });
    } catch (error) {
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
            from: userInfo.qiao_id,
            to: this.data.contactQiaoId,
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
