/**
 * Chat Page - Complete Rewrite
 * A stable, modern chat interface following WeChat-like design
 */

import { get } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import { MESSAGE_CONFIG } from '../../utils/config';
import { getUserFriendlyError } from '../../utils/error-messages';
import { getLogger } from '../../utils/logger';
import { MESSAGE_STATUS, MESSAGE_TYPE, type MessageType } from '../../utils/message/constants';
import {
  addMessage,
  getContactByConvId,
  getContacts,
  getMessages,
  getUserInfo,
  saveContacts,
  type StoredContact,
  type StoredMessage,
  type StoredMessages,
} from '../../utils/storage';
import typingManager from '../../utils/typing-manager';
import conversationStore from '../../utils/message/conversation-store';

const logger = getLogger('Chat');

// Standard emoji list
const EMOJI_LIST = [
  '😀',
  '😃',
  '😄',
  '😁',
  '😆',
  '😅',
  '🤣',
  '😂',
  '🙂',
  '🙃',
  '😉',
  '😊',
  '😇',
  '🥰',
  '😍',
  '🤩',
  '😘',
  '😗',
  '😚',
  '😙',
  '😋',
  '😛',
  '😜',
  '🤪',
  '😝',
  '🤑',
  '🤗',
  '🤭',
  '🤫',
  '🤔',
  '🤐',
  '🤨',
  '😐',
  '😑',
  '😶',
  '😏',
  '😒',
  '🙄',
  '😬',
  '🤥',
  '😌',
  '😔',
  '😪',
  '🤤',
  '😴',
  '😷',
  '🤒',
  '🤕',
  '🤢',
  '🤮',
  '🤧',
  '🥵',
  '🥶',
  '🥴',
  '😵',
  '🤯',
  '🤠',
  '🥳',
  '😎',
  '🤓',
  '🧐',
  '😕',
  '😟',
  '🙁',
  '☹️',
  '😮',
  '😯',
  '😲',
  '😳',
  '🥺',
  '😦',
  '😧',
  '😨',
  '😰',
  '😥',
  '😢',
  '😭',
  '😱',
  '😖',
  '😣',
  '😞',
  '😓',
  '😩',
  '😫',
  '🥱',
  '😤',
  '😡',
  '😠',
  '🤬',
  '😈',
  '👿',
  '💀',
  '☠️',
  '💩',
  '🤡',
  '👹',
  '👺',
  '👻',
  '👽',
  '👾',
  '🤖',
  '😺',
  '😸',
  '😹',
  '😻',
  '😼',
  '😽',
  '🙀',
  '😿',
  '😾',
  '👋',
  '🤚',
  '🖐️',
  '✋',
  '🖖',
  '👌',
  '🤏',
  '✌️',
  '🤞',
  '🤟',
  '🤘',
  '🤙',
  '👈',
  '👉',
  '👆',
  '🖕',
  '👇',
  '☝️',
  '👍',
  '👎',
  '✊',
  '👊',
  '🤛',
  '🤜',
  '👏',
  '🙌',
  '👐',
  '🤲',
  '🤝',
  '🙏',
  '✍️',
  '💅',
  '🤳',
  '💪',
  '🦾',
  '🦿',
  '🦵',
  '🦶',
  '👂',
  '🦻',
  '👃',
  '🧠',
  '🦷',
  '🦴',
  '👀',
  '👁️',
  '👅',
  '👄',
  '💋',
  '🩸',
  '❤️',
  '🧡',
  '💛',
  '💚',
  '💙',
  '💜',
  '🖤',
  '🤍',
  '🤎',
  '💔',
  '❣️',
  '💕',
  '💞',
  '💓',
  '💗',
  '💖',
  '💘',
  '💝',
  '💟',
  '☮️',
  '✝️',
  '☪️',
  '🕉️',
  '☸️',
  '✡️',
  '🔯',
  '🕎',
  '☯️',
  '☦️',
  '🛐',
  '⛎',
  '♈',
  '♉',
  '♊',
  '♋',
  '♌',
  '♍',
  '♎',
  '♏',
  '♐',
  '♑',
  '♒',
  '♓',
  '🆔',
  '⚛️',
  '🉑',
  '☢️',
  '☣️',
  '📴',
  '📳',
  '🈶',
  '🈚',
  '🈸',
  '🈺',
  '🈷️',
  '✴️',
  '🆚',
  '💮',
  '🉐',
  '㊙️',
  '㊗️',
  '🈴',
  '🈵',
  '🈹',
  '🈲',
  '🅰️',
  '🅱️',
  '🆎',
  '🆑',
  '🅾️',
  '🆘',
  '❌',
  '⭕',
  '🛑',
  '⛔',
  '📛',
  '🚫',
  '💯',
  '💢',
  '♨️',
  '🚷',
  '🚯',
  '🚳',
  '🚱',
  '🔞',
  '📵',
  '🚭',
  '❗',
  '❕',
  '❓',
  '❔',
  '‼️',
  '⁉️',
  '🔅',
  '🔆',
  '〽️',
  '⚠️',
  '🚸',
  '🔱',
  '⚜️',
  '🔰',
  '♻️',
  '✅',
  '🈯',
  '💹',
  '❇️',
  '✳️',
  '❎',
  '🌐',
  '💠',
];

type MessageStatus = (typeof MESSAGE_STATUS)[keyof typeof MESSAGE_STATUS];

interface ChatMessage extends StoredMessage {
  from_me?: boolean;
  showTimestamp?: boolean;
  timestampText?: string;
  isSystemMessage?: boolean;
  systemContent?: string;
  status?: MessageStatus;
}

interface ContactProfile {
  avatar_url?: string;
  nickname?: string;
  gender?: number | null;
}

interface ConversationResponse {
  contact_profile?: ContactProfile;
  contact_qiao_id: string;
  im_conv_id: string;
}

interface ChatPageData {
  convId: string;
  contactName: string;
  contactAvatar: string;
  contactQiaoId: string;
  imConvId: string;
  userAvatar: string;
  messages: ChatMessage[];
  scrollToView: string;
  inputText: string;
  inputPlaceholder: string;
  inputFocused: boolean;
  maxMessageLength: number;
  prevInputValue: string;
  showEmojiPicker: boolean;
  emojiList: readonly string[];
  isContactTyping: boolean;
}

type InputEvent = WechatMiniprogram.CustomEvent<{ value: string }>;

interface ChatPageCustom {
  typingTimer: ReturnType<typeof setTimeout> | null;
  unsubscribeConversationStore: (() => void) | null;
  _sendRetried: boolean;
  _retryRefreshed: boolean;
  showErrorMessage(error: unknown): Promise<void>;
  refreshContactInfo(convId: string): Promise<ConversationResponse>;
  refreshConversationChannel(): Promise<string>;
  handleChatInfoAction(message: ChatMessage): void;
  loadMessages(): Promise<void>;
  processMessages(messages: StoredMessages): ChatMessage[];
  isSystemMessage(message: StoredMessage): boolean;
  getSystemMessageContent(message: StoredMessage): string;
  formatTimestamp(timestamp: number): string;
  onInputChange(event: InputEvent): void;
  onInputFocus(): void;
  onInputBlur(): void;
  onCompositionStart(): void;
  onCompositionEnd(event: InputEvent): void;
  onToggleEmoji(): void;
  onSelectEmoji(event: WechatMiniprogram.TouchEvent): void;
  onSendMessage(): Promise<void>;
  onRetryMessage(event: WechatMiniprogram.BaseEvent): Promise<void>;
  onMessageReceived(message: Says.MessagePayload): Promise<void>;
  onTypingReceived(payload: Says.TypingEvent): void;
  showTypingIndicator(): void;
  hideTypingIndicator(): void;
  updateMessageStatus(messageId: string, status: MessageStatus): void;
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
  const dataset = event?.currentTarget?.dataset as Record<string, unknown> | undefined;
  return dataset?.[key];
};

const ensureMessageService = (): Says.MessageService => {
  const app = getApp<SaysAppInstance>();
  const messageService = app.getMessageService();
  if (!messageService) {
    throw new Error('MESSAGE_SERVICE_DISCONNECTED');
  }
  return messageService;
};

Page<ChatPageData, ChatPageCustom>({
  data: {
    convId: '',
    contactName: '',
    contactAvatar: '',
    contactQiaoId: '',
    imConvId: '',
    userAvatar: '',
    messages: [] as ChatMessage[],
    scrollToView: '',
    inputText: '',
    inputPlaceholder: '请输入消息',
    inputFocused: false,
    maxMessageLength: MESSAGE_CONFIG.maxLength ?? 1000,
    prevInputValue: '',
    showEmojiPicker: false,
    emojiList: EMOJI_LIST,
    isContactTyping: false,
  },

  typingTimer: null,
  unsubscribeConversationStore: null,
  _sendRetried: false,
  _retryRefreshed: false,

  async showErrorMessage(error: unknown) {
    const messageContent = getUserFriendlyError(error as Error | string | null | undefined);
    const errorMsg: ChatMessage = {
      msg_id: `error_${Date.now()}`,
      conv_id: this.data.convId,
      content: messageContent,
      message_type: MESSAGE_TYPE.CHAT_INFO,
      sent_time: Date.now(),
      from_me: false,
    };

    await addMessage(this.data.convId, errorMsg);

    const updatedMessages: StoredMessages = [...this.data.messages, errorMsg];
    const processedMessages = this.processMessages(updatedMessages);
    this.setData({
      messages: processedMessages,
      scrollToView: `msg-${errorMsg.msg_id}`,
    });
  },

  /**
   * Refresh contact info from backend
   */
  async refreshContactInfo(convId: string) {
    const conversation = await get<ConversationResponse>(`/contacts/${convId}/conversation`);

    if (!conversation) {
      throw new Error('CONVERSATION_NOT_FOUND');
    }

    const profile = conversation.contact_profile ?? {};
    const contactName = profile.nickname || this.data.contactName || '';
    if (contactName) {
      void wx.setNavigationBarTitle({ title: contactName });
    }

    this.setData({
      contactName,
      contactAvatar: getAvatarUrl(profile.avatar_url || this.data.contactAvatar),
      contactQiaoId: conversation.contact_qiao_id,
      imConvId: conversation.im_conv_id,
    });

    const contacts = await getContacts();
    const contactIndex = contacts.findIndex((contact) => contact.conv_id === convId);

    if (contactIndex !== -1) {
      const current = contacts[contactIndex];
      contacts[contactIndex] = {
        ...current,
        im_conv_id: conversation.im_conv_id,
        contact_qiao_id: conversation.contact_qiao_id,
        avatar_url: profile.avatar_url || current.avatar_url,
        nickname: profile.nickname || current.nickname,
        gender: profile.gender ?? current.gender,
        profile: {
          ...(current.profile || {}),
          ...profile,
        },
      };
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
    let nextImConvId = refreshedConversation?.im_conv_id || '';

    try {
      const refreshedState = await conversationStore.refresh();
      nextImConvId = refreshedState?.im_conv_id || nextImConvId;
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
    if (!action) {
      return;
    }

    if (action.type === 'mark_message_failed' && action.target_msg_id) {
      this.updateMessageStatus(action.target_msg_id, MESSAGE_STATUS.FAILED);
    }
  },

  async onLoad(options: Record<string, string | undefined>) {
    const convId = options?.id;
    if (!convId) {
      showToast('参数错误');
      void wx.navigateBack();
      return;
    }

    this.setData({ convId });
    this.unsubscribeConversationStore = conversationStore.subscribe((state) => {
      if (state?.im_conv_id) {
        this.setData({ imConvId: state.im_conv_id });
      }
    });

    try {
      const userInfo = await getUserInfo();
      if (!userInfo?.qiao_id) {
        throw new Error('User info missing');
      }
      this.setData({ userAvatar: getAvatarUrl(userInfo?.avatar ?? '') });

      const contact = await getContactByConvId(convId);
      if (!contact) {
        logger.error('Contact not found', { convId });
        showToast('联系人不存在');
        return;
      }

      const contactName = contact.alias || contact.nickname || '';
      if (contactName) {
        void wx.setNavigationBarTitle({ title: contactName });
      }

      const contactWithIm = contact as StoredContact & { im_conv_id?: string };
      const conversationState = await conversationStore.getState();
      const currentImConvId = conversationState?.im_conv_id || contactWithIm.im_conv_id || '';

      this.setData({
        contactName,
        contactAvatar: getAvatarUrl(contact.avatar_url ?? ''),
        contactQiaoId: contact.contact_qiao_id ?? '',
        imConvId: currentImConvId,
      });

      await this.loadMessages();
    } catch (error) {
      const err = normalizeError(error);
      logger.error('Failed to load chat page', { error: err.message });
      showToast('加载失败');
    }
  },

  onUnload() {
    typingManager.cleanup(this.data.convId);

    if (this.typingTimer) {
      clearTimeout(this.typingTimer);
      this.typingTimer = null;
    }

    if (this.unsubscribeConversationStore) {
      this.unsubscribeConversationStore();
      this.unsubscribeConversationStore = null;
    }
  },

  async loadMessages() {
    try {
      const messages = await getMessages(this.data.convId);
      const userInfo = await getUserInfo();
      if (!userInfo?.qiao_id) {
        throw new Error('User info missing');
      }

      const markedMessages: StoredMessages = messages.map((msg) => ({
        ...msg,
        from_me: msg.from === userInfo.qiao_id,
      }));

      const processedMessages = this.processMessages(markedMessages);

      if (processedMessages.length > 0) {
        const lastMsg = processedMessages[processedMessages.length - 1];
        this.setData({
          messages: processedMessages,
          scrollToView: `msg-${lastMsg.msg_id}`,
        });
      } else {
        this.setData({ messages: processedMessages });
      }
    } catch (error) {
      const err = normalizeError(error);
      logger.error('Failed to load messages', { error: err.message });
      showToast('加载消息失败');
    }
  },

  processMessages(messages: StoredMessages) {
    const processed: ChatMessage[] = [];
    let prevMsg: ChatMessage | null = null;

    for (const msg of messages) {
      if (
        msg.message_type === MESSAGE_TYPE.TYPING_START ||
        msg.message_type === MESSAGE_TYPE.TYPING_END ||
        msg.message_type === MESSAGE_TYPE.NOTIFICATION
      ) {
        continue;
      }

      const processedMsg: ChatMessage = {
        ...msg,
        status: msg.status as MessageStatus | undefined,
      };
      processedMsg.sent_time = processedMsg.sent_time || Date.now();

      if (!prevMsg || processedMsg.sent_time - (prevMsg.sent_time || 0) > 5 * 60 * 1000) {
        processedMsg.showTimestamp = true;
        processedMsg.timestampText = this.formatTimestamp(processedMsg.sent_time);
      } else {
        processedMsg.showTimestamp = false;
      }

      processedMsg.isSystemMessage = this.isSystemMessage(processedMsg);
      processedMsg.systemContent = processedMsg.isSystemMessage
        ? this.getSystemMessageContent(processedMsg)
        : '';

      processed.push(processedMsg);
      prevMsg = processedMsg;
    }

    return processed;
  },

  isSystemMessage(message: StoredMessage) {
    // Only CHAT_INFO messages are displayed as system messages in chat window
    return message.message_type === MESSAGE_TYPE.CHAT_INFO;
  },

  getSystemMessageContent(message: StoredMessage) {
    return message.content || '';
  },

  formatTimestamp(timestamp: number) {
    const now = Date.now();
    const diff = now - timestamp;
    const date = new Date(timestamp);

    // Within 1 minute
    if (diff < 60000) {
      return '刚刚';
    }

    // Within 1 hour
    if (diff < 3600000) {
      const minutes = Math.floor(diff / 60000);
      return `${minutes}分钟前`;
    }

    // Today
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
      const hours = date.getHours();
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `${hours}:${minutes}`;
    }

    // Yesterday
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) {
      const hours = date.getHours();
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `昨天 ${hours}:${minutes}`;
    }

    // This week
    const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    if (diff < 7 * 24 * 3600000) {
      const hours = date.getHours();
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `${weekDays[date.getDay()]} ${hours}:${minutes}`;
    }

    // This year
    if (date.getFullYear() === today.getFullYear()) {
      const month = date.getMonth() + 1;
      const day = date.getDate();
      return `${month}-${day}`;
    }

    // Previous years
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${year}-${month}-${day}`;
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
      showEmojiPicker: false,
    });

    // Notify typing manager
    typingManager.onInputFocus(this.data.convId, this.data.inputText);
  },

  /**
   * Handle input blur
   */
  onInputBlur() {
    // Delay to allow emoji selection
    setTimeout(() => {
      this.setData({ inputFocused: false });
    }, 200);

    // Notify typing manager
    typingManager.onInputBlur(this.data.convId);
  },

  onCompositionStart() {
    typingManager.onCompositionStart(this.data.convId, this.data.inputText);
  },

  onCompositionEnd(event: InputEvent) {
    const value = event?.detail?.value ?? this.data.inputText;
    typingManager.onCompositionEnd(this.data.convId, value);
  },

  /**
   * Toggle emoji picker
   */
  onToggleEmoji() {
    const show = !this.data.showEmojiPicker;
    this.setData({
      showEmojiPicker: show,
      inputFocused: !show,
    });
  },

  /**
   * Select emoji
   */
  onSelectEmoji(event: WechatMiniprogram.TouchEvent) {
    const emojiValue = getDatasetValue(event, 'emoji');
    if (typeof emojiValue !== 'string') {
      return;
    }
    const emoji = emojiValue;
    const newText = this.data.inputText + emoji;

    // Check length
    if (newText.length > this.data.maxMessageLength) {
      showToast(`消息长度不能超过${this.data.maxMessageLength}字`);
      return;
    }

    const oldValue = this.data.inputText;
    this.setData({
      inputText: newText,
      prevInputValue: newText,
    });

    // Notify typing manager
    typingManager.onInputChange(this.data.convId, newText, oldValue);
  },

  async onRetryMessage(event: WechatMiniprogram.BaseEvent) {
    const msgIdValue = getDatasetValue(event, 'msgid');
    if (typeof msgIdValue !== 'string') {
      return;
    }
    const msgId = msgIdValue;
    const message = this.data.messages.find((msg) => msg.msg_id === msgId);

    if (!message || message.status !== MESSAGE_STATUS.FAILED) {
      return;
    }

    typingManager.forceStopTyping(this.data.convId);
    this.hideTypingIndicator();

    const messageService = ensureMessageService();

    let newClientMsgId = '';

    try {
      const userInfo = await getUserInfo();
      if (!userInfo?.qiao_id) {
        throw new Error('User info missing');
      }

      newClientMsgId = buildClientMessageId();
      const messagesWithoutOld = this.data.messages.filter((msg) => msg.msg_id !== msgId);
      const newMessage: ChatMessage = {
        ...message,
        msg_id: newClientMsgId,
        sent_time: Date.now(),
        status: MESSAGE_STATUS.SENDING as MessageStatus,
      };

      const updatedMessages: StoredMessages = [...messagesWithoutOld, newMessage];
      const processedMessages = this.processMessages(updatedMessages);
      this.setData({
        messages: processedMessages,
        scrollToView: `msg-${newClientMsgId}`,
      });

      await addMessage(this.data.convId, newMessage);

      await messageService.sendMessage({
        client_msg_id: newClientMsgId,
        from: userInfo.qiao_id,
        to: this.data.contactQiaoId,
        conv_id: this.data.convId,
        content: message.content || '',
        message_type: (message.message_type ?? MESSAGE_TYPE.TEXT) as MessageType,
        supports_typing: message.supports_typing !== false,
      });

      const sentMessages = this.data.messages.map((msg) =>
        msg.msg_id === newClientMsgId
          ? { ...msg, status: MESSAGE_STATUS.SENT as MessageStatus }
          : msg
      );
      this.setData({ messages: sentMessages });

      logger.info('Message retry successful', { old_msg_id: msgId, new_msg_id: newClientMsgId });
    } catch (error) {
      const err = normalizeError(error);
      logger.error('Failed to retry message', { msg_id: msgId, error: err.message });

      if (err.message === 'CONVERSATION_NOT_FOUND' && !this._retryRefreshed) {
        this._retryRefreshed = true;
        logger.info('Retry failed due to conversation not found, refreshing contact info', {
          convId: this.data.convId,
          oldImConvId: this.data.imConvId,
        });

        try {
          const refreshedImConvId = await this.refreshConversationChannel();
          const nextImConvId = refreshedImConvId || this.data.imConvId;
          logger.info('Contact info refreshed for retry, retrying send', {
            newImConvId: nextImConvId,
          });

          const userInfo = await getUserInfo();
          if (!userInfo?.qiao_id) {
            throw new Error('User info missing');
          }

          await messageService.sendMessage({
            client_msg_id: newClientMsgId,
            from: userInfo.qiao_id,
            to: this.data.contactQiaoId,
            conv_id: this.data.convId,
            content: message.content || '',
            message_type: (message.message_type ?? MESSAGE_TYPE.TEXT) as MessageType,
            supports_typing: message.supports_typing !== false,
          });

          const sentMessages = this.data.messages
            .filter((msg) => {
              if (msg.message_type === MESSAGE_TYPE.CHAT_INFO && msg.msg_id.startsWith('error_')) {
                return false;
              }
              return true;
            })
            .map((msg) =>
              msg.msg_id === newClientMsgId
                ? { ...msg, status: MESSAGE_STATUS.SENT as MessageStatus }
                : msg
            );

          this.setData({ messages: this.processMessages(sentMessages as StoredMessages) });
          this._retryRefreshed = false;
          logger.info('Message retry successful after refresh', { old_msg_id: msgId });
          return;
        } catch (retryError) {
          const retryErr = normalizeError(retryError);
          logger.error('Retry send failed after refresh', {
            error: retryErr.message,
            errorType: retryError instanceof Error ? retryError.constructor.name : 'Unknown',
          });
          this._retryRefreshed = false;
        }
      }

      const failedMessages = this.data.messages.map((msg) => {
        if (msg.status === MESSAGE_STATUS.SENDING && msg.content === message.content) {
          return { ...msg, status: MESSAGE_STATUS.FAILED as MessageStatus };
        }
        return msg;
      });

      this.setData({ messages: this.processMessages(failedMessages as StoredMessages) });
      await this.showErrorMessage(err);
    }
  },

  async onMessageReceived(message: Says.MessagePayload) {
    try {
      if (message.conv_id !== this.data.convId) {
        return;
      }

      const userInfo = await getUserInfo();
      if (!userInfo?.qiao_id) {
        return;
      }
      this.hideTypingIndicator();

      const newMessage: ChatMessage = {
        ...message,
        from_me: message.from === userInfo.qiao_id,
        status: message.status as MessageStatus | undefined,
      };

      if (newMessage.message_type === MESSAGE_TYPE.CHAT_INFO) {
        this.handleChatInfoAction(newMessage);
      }

      const updatedMessages: StoredMessages = [...this.data.messages, newMessage];
      const processedMessages = this.processMessages(updatedMessages);
      this.setData({
        messages: processedMessages,
        scrollToView: `msg-${message.msg_id}`,
      });
    } catch (error) {
      const err = normalizeError(error);
      logger.error('Failed to handle received message', { error: err.message });
    }
  },

  onTypingReceived(typing: Says.TypingEvent) {
    try {
      if (typing.conv_id !== this.data.convId) {
        return;
      }

      if (typing.typing) {
        this.showTypingIndicator();
      } else {
        this.hideTypingIndicator();
      }
    } catch (error) {
      const err = normalizeError(error);
      logger.error('Failed to handle typing indicator', { error: err.message });
    }
  },

  /**
   * Show typing indicator
   */
  showTypingIndicator() {
    if (this.typingTimer) {
      clearTimeout(this.typingTimer);
    }

    this.setData({ isContactTyping: true });
    void wx.setNavigationBarTitle({ title: '对方正在输入...' });

    this.typingTimer = setTimeout(() => {
      this.hideTypingIndicator();
    }, 30000);
  },

  hideTypingIndicator() {
    if (this.typingTimer) {
      clearTimeout(this.typingTimer);
      this.typingTimer = null;
    }

    this.setData({ isContactTyping: false });

    if (this.data.contactName) {
      void wx.setNavigationBarTitle({ title: this.data.contactName });
    }
  },

  updateMessageStatus(messageId: string, status: MessageStatus) {
    const messages = this.data.messages.map((msg) =>
      msg.msg_id === messageId ? { ...msg, status } : msg
    );
    this.setData({ messages });
  },

  async onSendMessage() {
    const content = this.data.inputText.trim();
    if (!content) {
      return;
    }

    if (content.length > this.data.maxMessageLength) {
      showToast(`消息长度不能超过${this.data.maxMessageLength}字`);
      return;
    }

    const currentImConvId = await conversationStore.getImConvId();
    if (!this.data.contactQiaoId || !currentImConvId) {
      logger.error('Missing contact info', {
        contactQiaoId: this.data.contactQiaoId,
        imConvId: this.data.imConvId,
      });
      await this.showErrorMessage('CONVERSATION_NOT_FOUND');
      return;
    }

    typingManager.forceStopTyping(this.data.convId);
    this.hideTypingIndicator();

    const messageService = ensureMessageService();
    let clientMsgId = '';

    try {
      const userInfo = await getUserInfo();
      if (!userInfo?.qiao_id) {
        throw new Error('User info missing');
      }

      clientMsgId = buildClientMessageId();
      const optimisticMsg: ChatMessage = {
        msg_id: clientMsgId,
        from: userInfo.qiao_id,
        to: this.data.contactQiaoId,
        conv_id: this.data.convId,
        content,
        message_type: MESSAGE_TYPE.TEXT,
        supports_typing: true,
        sent_time: Date.now(),
        status: MESSAGE_STATUS.SENDING as MessageStatus,
        from_me: true,
      };

      const updatedMessages: StoredMessages = [...this.data.messages, optimisticMsg];
      const processedMessages = this.processMessages(updatedMessages);
      this.setData({
        messages: processedMessages,
        inputText: '',
        prevInputValue: '',
        scrollToView: `msg-${clientMsgId}`,
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

      const sentMessages = this.data.messages.map((msg) =>
        msg.msg_id === clientMsgId ? { ...msg, status: MESSAGE_STATUS.SENT as MessageStatus } : msg
      );
      this.setData({ messages: sentMessages });
      logger.info('Message sent', { msg_id: clientMsgId });
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
          const nextImConvId = refreshedImConvId || this.data.imConvId;
          logger.info('Contact info refreshed, retrying send', { newImConvId: nextImConvId });

          const userInfo = await getUserInfo();
          if (!userInfo?.qiao_id) {
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

          const sentMessages = this.data.messages
            .filter((msg) => {
              if (msg.message_type === MESSAGE_TYPE.CHAT_INFO && msg.msg_id.startsWith('error_')) {
                return false;
              }
              return true;
            })
            .map((msg) =>
              msg.msg_id === clientMsgId ? { ...msg, status: MESSAGE_STATUS.SENT } : msg
            );

          this.setData({ messages: this.processMessages(sentMessages as StoredMessages) });
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

      const failedMessages = this.data.messages.map((msg) =>
        msg.msg_id === clientMsgId
          ? { ...msg, status: MESSAGE_STATUS.FAILED as MessageStatus }
          : msg
      );
      this.setData({ messages: this.processMessages(failedMessages as StoredMessages) });
      await this.showErrorMessage(err);
    }
  },
});
