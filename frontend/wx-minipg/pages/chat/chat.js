/**
 * Chat Page - Complete Rewrite
 * A stable, modern chat interface following WeChat-like design
 */

import { get } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import { MESSAGE_CONFIG } from '../../utils/config';
import { getUserFriendlyError } from '../../utils/error-messages';
import logger from '../../utils/logger';
import { MESSAGE_STATUS, MESSAGE_TYPE } from '../../utils/message/constants';
import { addMessage, getContactByConvId, getContacts, getMessages, getUserInfo, saveContacts } from '../../utils/storage';
import typingManager from '../../utils/typing-manager';

// Standard emoji list
const EMOJI_LIST = [
  '😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃',
  '😉', '😊', '😇', '🥰', '😍', '🤩', '😘', '😗', '😚', '😙',
  '😋', '😛', '😜', '🤪', '😝', '🤑', '🤗', '🤭', '🤫', '🤔',
  '🤐', '🤨', '😐', '😑', '😶', '😏', '😒', '🙄', '😬', '🤥',
  '😌', '😔', '😪', '🤤', '😴', '😷', '🤒', '🤕', '🤢', '🤮',
  '🤧', '🥵', '🥶', '🥴', '😵', '🤯', '🤠', '🥳', '😎', '🤓',
  '🧐', '😕', '😟', '🙁', '☹️', '😮', '😯', '😲', '😳', '🥺',
  '😦', '😧', '😨', '😰', '😥', '😢', '😭', '😱', '😖', '😣',
  '😞', '😓', '😩', '😫', '🥱', '😤', '😡', '😠', '🤬', '😈',
  '👿', '💀', '☠️', '💩', '🤡', '👹', '👺', '👻', '👽', '👾',
  '🤖', '😺', '😸', '😹', '😻', '😼', '😽', '🙀', '😿', '😾',
  '👋', '🤚', '🖐️', '✋', '🖖', '👌', '🤏', '✌️', '🤞', '🤟',
  '🤘', '🤙', '👈', '👉', '👆', '🖕', '👇', '☝️', '👍', '👎',
  '✊', '👊', '🤛', '🤜', '👏', '🙌', '👐', '🤲', '🤝', '🙏',
  '✍️', '💅', '🤳', '💪', '🦾', '🦿', '🦵', '🦶', '👂', '🦻',
  '👃', '🧠', '🦷', '🦴', '👀', '👁️', '👅', '👄', '💋', '🩸',
  '❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍', '🤎', '💔',
  '❣️', '💕', '💞', '💓', '💗', '💖', '💘', '💝', '💟', '☮️',
  '✝️', '☪️', '🕉️', '☸️', '✡️', '🔯', '🕎', '☯️', '☦️', '🛐',
  '⛎', '♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐',
  '♑', '♒', '♓', '🆔', '⚛️', '🉑', '☢️', '☣️', '📴', '📳',
  '🈶', '🈚', '🈸', '🈺', '🈷️', '✴️', '🆚', '💮', '🉐', '㊙️',
  '㊗️', '🈴', '🈵', '🈹', '🈲', '🅰️', '🅱️', '🆎', '🆑', '🅾️',
  '🆘', '❌', '⭕', '🛑', '⛔', '📛', '🚫', '💯', '💢', '♨️',
  '🚷', '🚯', '🚳', '🚱', '🔞', '📵', '🚭', '❗', '❕', '❓',
  '❔', '‼️', '⁉️', '🔅', '🔆', '〽️', '⚠️', '🚸', '🔱', '⚜️',
  '🔰', '♻️', '✅', '🈯', '💹', '❇️', '✳️', '❎', '🌐', '💠'
];

Page({
  data: {
    // Conversation info
    convId: '',
    contactName: '',
    contactAvatar: '',
    contactQiaoId: '',
    imConvId: '',
    userAvatar: '',

    // Messages
    messages: [],
    scrollToView: '',

    // Input
    inputText: '',
    inputPlaceholder: '请输入消息',
    inputFocused: false,
    maxMessageLength: MESSAGE_CONFIG.maxLength || 1000,
    prevInputValue: '',

    // Emoji
    showEmojiPicker: false,
    emojiList: EMOJI_LIST,

    // Typing indicator
    isContactTyping: false,
    typingTimer: null
  },

  /**
   * Show error message as CHAT_INFO
   */
  showErrorMessage(error) {
    const errorMsg = {
      msg_id: `error_${Date.now()}`,
      content: getUserFriendlyError(error),
      message_type: MESSAGE_TYPE.CHAT_INFO,
      sent_time: Date.now(),
      from_me: false
    };

    const updatedMessages = [...this.data.messages, errorMsg];
    const processedMessages = this.processMessages(updatedMessages);
    this.setData({
      messages: processedMessages,
      scrollToView: `msg-${errorMsg.msg_id}`
    });
  },

  /**
   * Refresh contact info from backend
   */
  async refreshContactInfo(convId) {
    // Fetch latest conversation info from backend
    const result = await get(`/contacts/${convId}/conversation`);

    if (!result || !result.conversation) {
      throw new Error('CONVERSATION_NOT_FOUND');
    }

    const conversation = result.conversation;

    // Update contact name and avatar
    const contactName = conversation.alias || conversation.nickname || '';
    if (contactName) {
      wx.setNavigationBarTitle({ title: contactName });
    }

    this.setData({
      contactName,
      contactAvatar: getAvatarUrl(conversation.avatar_url),
      contactQiaoId: conversation.contact_qiao_id,
      imConvId: conversation.im_conv_id
    });

    // Update local cache with latest contact info
    const contacts = await getContacts();
    const contactIndex = contacts.findIndex(c => c.conv_id === convId);

    if (contactIndex !== -1) {
      contacts[contactIndex] = {
        ...contacts[contactIndex],
        im_conv_id: conversation.im_conv_id,
        contact_qiao_id: conversation.contact_qiao_id,
        avatar_url: conversation.avatar_url,
        nickname: conversation.nickname,
        alias: conversation.alias
      };
      await saveContacts(contacts);
      logger.info('Contact info refreshed and cached', { convId });
    }
  },

  handleChatInfoAction(message) {
    if (!message.action) return;

    if (message.action.type === 'mark_message_failed' && message.action.target_msg_id) {
      this.updateMessageStatus(message.action.target_msg_id, MESSAGE_STATUS.FAILED);
    }
  },

  /**
   * Page lifecycle - Load
   */
  async onLoad(options) {
    const convId = options.id;
    if (!convId) {
      wx.showToast({ title: '参数错误', icon: 'none' });
      wx.navigateBack();
      return;
    }

    this.setData({ convId });

    try {
      // Load user info
      const userInfo = await getUserInfo();
      this.setData({ userAvatar: getAvatarUrl(userInfo.avatar_url) });

      // Load contact info from cache
      const contact = await getContactByConvId(convId);
      if (!contact) {
        logger.error('Contact not found', { convId });
        wx.showToast({ title: '联系人不存在', icon: 'none' });
        return;
      }

      const contactName = contact.alias || contact.nickname || '';
      if (contactName) {
        wx.setNavigationBarTitle({ title: contactName });
      }

      this.setData({
        contactName,
        contactAvatar: getAvatarUrl(contact.avatar_url),
        contactQiaoId: contact.contact_qiao_id,
        imConvId: contact.im_conv_id
      });

      // Load messages
      await this.loadMessages();
    } catch (error) {
      logger.error('Failed to load chat page', { error });
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  /**
   * Page lifecycle - Unload
   */
  onUnload() {
    // Clean up typing manager
    typingManager.cleanup(this.data.convId);

    // Clear typing timer
    if (this.typingTimer) {
      clearTimeout(this.typingTimer);
      this.typingTimer = null;
    }
  },

  /**
   * Load messages from storage
   */
  async loadMessages() {
    try {
      const messages = await getMessages(this.data.convId);
      const userInfo = await getUserInfo();

      // Mark messages as from_me
      const markedMessages = messages.map(msg => ({
        ...msg,
        from_me: msg.from === userInfo.qiao_id
      }));

      // Process messages for display
      const processedMessages = this.processMessages(markedMessages);

      this.setData({ messages: processedMessages });

      // Scroll to bottom
      if (processedMessages.length > 0) {
        const lastMsg = processedMessages[processedMessages.length - 1];
        this.setData({ scrollToView: `msg-${lastMsg.msg_id}` });
      }
    } catch (error) {
      logger.error('Failed to load messages', { error });
      wx.showToast({ title: '加载消息失败', icon: 'none' });
    }
  },

  /**
   * Process messages - add timestamp display logic
   */
  processMessages(messages) {
    const processed = [];
    let prevMsg = null;

    for (const msg of messages) {
      const processedMsg = { ...msg };
      processedMsg.sent_time = processedMsg.sent_time || Date.now();

      // Show timestamp if gap > 5 minutes
      if (!prevMsg || processedMsg.sent_time - prevMsg.sent_time > 5 * 60 * 1000) {
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

  isSystemMessage(message) {
    return (
      message.message_type === MESSAGE_TYPE.CHAT_INFO ||
      message.message_type === MESSAGE_TYPE.NOTIFICATION
    );
  },

  getSystemMessageContent(message) {
    if (message.message_type === MESSAGE_TYPE.NOTIFICATION) {
      const notificationMessage = message.data && message.data.message;
      return notificationMessage || message.content || '系统通知';
    }
    return message.content || '';
  },

  /**
   * Format timestamp for display
   */
  formatTimestamp(timestamp) {
    const now = Date.now();
    const diff = now - timestamp;
    const date = new Date(timestamp);

    // Within 1 minute
    if (diff < 60000) return '刚刚';

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
  onInputChange(e) {
    const newValue = e.detail.value;
    const oldValue = this.data.prevInputValue;

    this.setData({
      inputText: newValue,
      prevInputValue: newValue
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
      showEmojiPicker: false
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

  onCompositionEnd(e) {
    const value = (e && e.detail && e.detail.value) || this.data.inputText;
    typingManager.onCompositionEnd(this.data.convId, value);
  },

  /**
   * Toggle emoji picker
   */
  onToggleEmoji() {
    const show = !this.data.showEmojiPicker;
    this.setData({
      showEmojiPicker: show,
      inputFocused: !show
    });
  },

  /**
   * Select emoji
   */
  onSelectEmoji(e) {
    const emoji = e.currentTarget.dataset.emoji;
    const newText = this.data.inputText + emoji;

    // Check length
    if (newText.length > this.data.maxMessageLength) {
      wx.showToast({
        title: `消息长度不能超过${this.data.maxMessageLength}字`,
        icon: 'none'
      });
      return;
    }

    const oldValue = this.data.inputText;
    this.setData({
      inputText: newText,
      prevInputValue: newText
    });

    // Notify typing manager
    typingManager.onInputChange(this.data.convId, newText, oldValue);
  },

  /**
   * Send message
   */
  async onSendMessage() {
    const content = this.data.inputText.trim();
    if (!content) return;

    // Check length
    if (content.length > this.data.maxMessageLength) {
      wx.showToast({
        title: `消息长度不能超过${this.data.maxMessageLength}字`,
        icon: 'none'
      });
      return;
    }

    // Check contact info
    if (!this.data.contactQiaoId || !this.data.imConvId) {
      logger.error('Missing contact info', {
        contactQiaoId: this.data.contactQiaoId,
        imConvId: this.data.imConvId
      });
      this.showErrorMessage('CONVERSATION_NOT_FOUND');
      return;
    }

    // Stop typing state
    typingManager.forceStopTyping(this.data.convId);
    this.hideTypingIndicator();

    let clientMsgId = '';

    try {
      const userInfo = await getUserInfo();

      // Create optimistic message
      clientMsgId = `client_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
      const optimisticMsg = {
        msg_id: clientMsgId,
        from: userInfo.qiao_id,
        to: this.data.contactQiaoId,
        conv_id: this.data.convId,
        content,
        message_type: MESSAGE_TYPE.TEXT,
        supports_typing: true,
        sent_time: Date.now(),
        status: MESSAGE_STATUS.SENDING,
        from_me: true
      };

      // Add to UI immediately
      const updatedMessages = [...this.data.messages, optimisticMsg];
      const processedMessages = this.processMessages(updatedMessages);
      this.setData({
        messages: processedMessages,
        inputText: '',
        prevInputValue: '',
        scrollToView: `msg-${clientMsgId}`
      });

      // Save to storage
      await addMessage(this.data.convId, optimisticMsg);

      // Send via message service
      const app = getApp();
      const messageService = app.getMessageService();

      if (!messageService) {
        throw new Error('MESSAGE_SERVICE_DISCONNECTED');
      }

      await messageService.sendMessage({
        client_msg_id: clientMsgId,
        from: userInfo.qiao_id,
        to: this.data.contactQiaoId,
        conv_id: this.data.convId,
        im_conv_id: this.data.imConvId,
        content,
        message_type: MESSAGE_TYPE.TEXT,
        supports_typing: true
      });

      // Update status to SENT
      const sentMessages = this.data.messages.map(msg =>
        msg.msg_id === clientMsgId ? { ...msg, status: MESSAGE_STATUS.SENT } : msg
      );
      this.setData({ messages: sentMessages });

      logger.info('Message sent', { msg_id: clientMsgId });
    } catch (error) {
      logger.error('Failed to send message', { error });

      // If conversation not found, try to refresh contact info and retry once
      if (error.message === 'CONVERSATION_NOT_FOUND' && !this._sendRetried) {
        this._sendRetried = true;
        logger.info('Refreshing contact info and retrying send', { convId: this.data.convId });

        try {
          await this.refreshContactInfo(this.data.convId);

          // Retry send with updated im_conv_id
          const app = getApp();
          const messageService = app.getMessageService();
          const userInfo = await getUserInfo();

          await messageService.sendMessage({
            client_msg_id: clientMsgId,
            from: userInfo.qiao_id,
            to: this.data.contactQiaoId,
            conv_id: this.data.convId,
            im_conv_id: this.data.imConvId,
            content,
            message_type: MESSAGE_TYPE.TEXT,
            supports_typing: true
          });

          const sentMessages = this.data.messages.map(msg =>
            msg.msg_id === clientMsgId ? { ...msg, status: MESSAGE_STATUS.SENT } : msg
          );
          this.setData({ messages: sentMessages });
          this._sendRetried = false;
          logger.info('Message sent after refresh', { msg_id: clientMsgId });
          return;
        } catch (retryError) {
          logger.error('Retry send failed after refresh', { error: retryError });
          this._sendRetried = false;
        }
      }

      const failedMessages = this.data.messages.map(msg =>
        msg.msg_id === clientMsgId ? { ...msg, status: MESSAGE_STATUS.FAILED } : msg
      );

      this.setData({ messages: this.processMessages(failedMessages) });
      this.showErrorMessage(error);
    }
  },

  /**
   * Retry failed message
   */
  async onRetryMessage(e) {
    const msgId = e.currentTarget.dataset.msgid;
    const message = this.data.messages.find(msg => msg.msg_id === msgId);

    if (!message || message.status !== MESSAGE_STATUS.FAILED) {
      return;
    }

    // Update status to SENDING
    const retryingMessages = this.data.messages.map(msg =>
      msg.msg_id === msgId ? { ...msg, status: MESSAGE_STATUS.SENDING } : msg
    );
    this.setData({ messages: retryingMessages });

    try {
      const app = getApp();
      const messageService = app.getMessageService();

      if (!messageService) {
        throw new Error('MESSAGE_SERVICE_DISCONNECTED');
      }

      const userInfo = await getUserInfo();

      await messageService.sendMessage({
        from: userInfo.qiao_id,
        to: this.data.contactQiaoId,
        conv_id: this.data.convId,
        im_conv_id: this.data.imConvId,
        content: message.content,
        message_type: message.message_type || MESSAGE_TYPE.TEXT,
        supports_typing: message.supports_typing !== false
      });

      // Update status to SENT
      const sentMessages = this.data.messages.map(msg =>
        msg.msg_id === msgId ? { ...msg, status: MESSAGE_STATUS.SENT } : msg
      );
      this.setData({ messages: sentMessages });

      logger.info('Message retry successful', { msg_id: msgId });
    } catch (error) {
      logger.error('Failed to retry message', { error });

      // Mark as FAILED again
      const failedMessages = this.data.messages.map(msg =>
        msg.msg_id === msgId ? { ...msg, status: MESSAGE_STATUS.FAILED } : msg
      );
      this.setData({ messages: failedMessages });

      this.showErrorMessage(error);
    }
  },

  /**
   * Handle incoming message (called by app.js)
   */
  async onMessageReceived(message) {
    try {
      if (message.conv_id !== this.data.convId) {
        return;
      }

      logger.info('Message received', { msg_id: message.msg_id });

      const userInfo = await getUserInfo();

      // Hide typing indicator
      this.hideTypingIndicator();

      // Add to messages
      const newMessage = {
        ...message,
        from_me: message.from === userInfo.qiao_id
      };

      if (newMessage.message_type === MESSAGE_TYPE.CHAT_INFO) {
        this.handleChatInfoAction(newMessage);
      }

      const updatedMessages = [...this.data.messages, newMessage];
      const processedMessages = this.processMessages(updatedMessages);
      this.setData({
        messages: processedMessages,
        scrollToView: `msg-${message.msg_id}`
      });
    } catch (error) {
      logger.error('Failed to handle received message', { error });
    }
  },

  /**
   * Handle typing indicator (called by app.js)
   */
  onTypingReceived(typing) {
    try {
      if (typing.conv_id !== this.data.convId) {
        return;
      }

      if (typing.isTyping) {
        this.showTypingIndicator();
      } else {
        this.hideTypingIndicator();
      }
    } catch (error) {
      logger.error('Failed to handle typing indicator', { error });
    }
  },

  /**
   * Show typing indicator
   */
  showTypingIndicator() {
    // Clear existing timer
    if (this.typingTimer) {
      clearTimeout(this.typingTimer);
    }

    this.setData({ isContactTyping: true });

    // Update title
    wx.setNavigationBarTitle({ title: '对方正在输入...' });

    // Auto hide after 30 seconds
    this.typingTimer = setTimeout(() => {
      this.hideTypingIndicator();
    }, 30000);
  },

  /**
   * Hide typing indicator
   */
  hideTypingIndicator() {
    if (this.typingTimer) {
      clearTimeout(this.typingTimer);
      this.typingTimer = null;
    }

    this.setData({ isContactTyping: false });

    // Restore title
    if (this.data.contactName) {
      wx.setNavigationBarTitle({ title: this.data.contactName });
    }
  }
});
