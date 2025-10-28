import { getAvatarUrl } from '../../utils/avatar';
import { MESSAGE_CONFIG } from '../../utils/config';
import logger from '../../utils/logger';
import { MESSAGE_STATUS, MESSAGE_TYPE } from '../../utils/message/constants';
import { addMessage, getContactByConvId, getMessages, getUserInfo } from '../../utils/storage';

Page({
  data: {
    convId: '',
    contactName: '',
    contactAvatar: '',
    contactQiaoId: '',
    imConvId: '',
    userAvatar: '',
    messages: [],
    inputText: '',
    maxMessageLength: MESSAGE_CONFIG.maxLength || 1000,
    scrollToView: '',
    loading: false
  },

  async onLoad(options) {
    const convId = options.id;
    if (!convId) {
      wx.showToast({
        title: '参数错误',
        icon: 'none'
      });
      wx.navigateBack();
      return;
    }

    this.setData({ convId });

    // Load user info
    const userInfo = await getUserInfo();
    this.setData({
      userAvatar: getAvatarUrl(userInfo.avatar_url)
    });

    // Load contact info from local storage
    const contact = await getContactByConvId(convId);
    if (contact) {
      // Set navigation bar title
      const contactName = contact.alias || contact.nickname || '';
      if (contactName) {
        wx.setNavigationBarTitle({
          title: contactName
        });
      }

      this.setData({
        contactName: contactName,
        contactAvatar: getAvatarUrl(contact.avatar_url),
        contactQiaoId: contact.contact_qiao_id,
        imConvId: contact.im_conv_id
      });
    } else {
      // Contact not found in local storage
      logger.error('Contact not found in local storage', { convId });
      wx.showToast({
        title: '联系人信息不存在',
        icon: 'none'
      });
    }

    // Load messages
    await this.loadMessages();
  },


  /**
   * Format timestamp for message display
   */
  formatMessageTime(timestamp) {
    const now = Date.now();
    const diff = now - timestamp;
    const date = new Date(timestamp);

    // Within 1 minute: just now
    if (diff < 60000) return '刚刚';

    // Within 1 hour: X minutes ago
    if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;

    // Today: HH:MM
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
      const hours = date.getHours();
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `${hours}:${minutes}`;
    }

    // Yesterday: Yesterday HH:MM
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) {
      const hours = date.getHours();
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `昨天 ${hours}:${minutes}`;
    }

    // This week: WeekDay HH:MM
    const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    if (diff < 7 * 24 * 3600000) {
      const hours = date.getHours();
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `${weekDays[date.getDay()]} ${hours}:${minutes}`;
    }

    // This year: MM-DD
    if (date.getFullYear() === today.getFullYear()) {
      const month = date.getMonth() + 1;
      const day = date.getDate();
      return `${month}-${day}`;
    }

    // Previous years: YYYY-MM-DD
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${year}-${month}-${day}`;
  },

  /**
   * Process messages for display
   * Add timestamp display logic
   */
  processMessages(messages) {
    const processed = [];
    let previousMsg = null;

    for (const msg of messages) {
      const processedMsg = Object.assign({}, msg);

      // Determine if timestamp should be shown (>5 minutes gap)
      if (!previousMsg || msg.sent_time - previousMsg.sent_time > 5 * 60 * 1000) {
        processedMsg.showTimestamp = true;
        processedMsg.timestampText = this.formatMessageTime(msg.sent_time);
      } else {
        processedMsg.showTimestamp = false;
      }

      processed.push(processedMsg);
      previousMsg = msg;
    }

    return processed;
  },

  async loadMessages() {
    try {
      this.setData({ loading: true });

      // Load messages from local storage
      const messages = await getMessages(this.data.convId);

      const userInfo = await getUserInfo();
      const formattedMessages = messages.map(function (m) {
        const obj = Object.assign({}, m);
        obj.from_me = (m.from === userInfo.qiao_id);
        return obj;
      });

      // Process messages to add timestamp display logic
      const processedMessages = this.processMessages(formattedMessages);

      this.setData({
        messages: processedMessages,
        loading: false
      });

      // Scroll to bottom
      if (processedMessages.length > 0) {
        const lastMsg = processedMessages[processedMessages.length - 1];
        this.setData({ scrollToView: `msg-${lastMsg.msg_id}` });
      }
    } catch (error) {
      logger.error('Failed to load messages', { error });
      this.setData({ loading: false });
      wx.showToast({
        title: '加载消息失败',
        icon: 'none'
      });
    }
  },

  onInput(e) {
    this.setData({ inputText: e.detail.value });
  },

  async sendMessage() {
    const content = this.data.inputText.trim();
    if (!content) {
      return;
    }

    // Check message length
    if (content.length > this.data.maxMessageLength) {
      wx.showToast({
        title: `消息长度不能超过${this.data.maxMessageLength}字`,
        icon: 'none'
      });
      return;
    }

    // Check required data
    if (!this.data.contactQiaoId || !this.data.imConvId) {
      logger.error('Missing contact info', {
        contactQiaoId: this.data.contactQiaoId,
        imConvId: this.data.imConvId
      });
      wx.showToast({
        title: '联系人信息不完整',
        icon: 'none'
      });
      return;
    }

    try {
      // Get user info
      const userInfo = await getUserInfo();

      // Prepare optimistic local message
      const clientMsgId = `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      const localMessage = {
        msg_id: clientMsgId,
        from: userInfo.qiao_id,
        to: this.data.contactQiaoId,
        conv_id: this.data.convId,
        content,
        message_type: MESSAGE_TYPE.TEXT,
        supports_typing: true,
        sent_time: Date.now(),
        status: MESSAGE_STATUS.SENDING
      };

      // Push to UI immediately
      const optimisticList = this.data.messages.concat([Object.assign({}, localMessage, { from_me: true })]);
      this.setData({
        messages: optimisticList,
        inputText: '',
        scrollToView: `msg-${clientMsgId}`
      });

      // Persist locally
      await addMessage(this.data.convId, localMessage);

      // Get message service from app
      const app = getApp();
      const messageService = app.getMessageService();

      if (!messageService) {
        throw new Error('消息通道未连接');
      }

      // Send via service with client_msg_id to update same bubble
      const sent = await messageService.sendMessage({
        client_msg_id: clientMsgId,
        from: userInfo.qiao_id,
        to: this.data.contactQiaoId,
        conv_id: this.data.convId,
        im_conv_id: this.data.imConvId,
        content,
        message_type: MESSAGE_TYPE.TEXT,
        supports_typing: true
      });

      // Update UI status to SENT
      const updated = this.data.messages.map(function (m) {
        if (m.msg_id === clientMsgId) {
          return Object.assign({}, m, { status: MESSAGE_STATUS.SENT });
        }
        return m;
      });
      this.setData({
        messages: updated,
        scrollToView: `msg-${clientMsgId}`
      });

      logger.info('Message sent successfully', { msg_id: clientMsgId });
    } catch (error) {
      logger.error('Failed to send message', {
        error: error.message || String(error)
      });

      // Mark last optimistic message as FAILED
      const last = this.data.messages[this.data.messages.length - 1];
      if (last && last.from_me && last.status === MESSAGE_STATUS.SENDING) {
        const failedList = this.data.messages.map(function (m, idx, arr) {
          if (idx === arr.length - 1) {
            return Object.assign({}, m, { status: MESSAGE_STATUS.FAILED });
          }
          return m;
        });
        // Append chat-info system message with reason
        const infoMsg = {
          msg_id: `sys_${Date.now()}`,
          conv_id: this.data.convId,
          content: `消息发送失败：${error.message || '未知错误'}`,
          message_type: MESSAGE_TYPE.NOTIFICATION,
          sent_time: Date.now(),
          from_me: false
        };
        this.setData({
          messages: [...failedList, infoMsg],
          scrollToView: `msg-${last.msg_id}`
        });
      }

      wx.showToast({ title: error.message || '发送失败', icon: 'none' });
    }
  },

  async retryMessage(e) {
    const msgId = e.currentTarget.dataset.id;
    const message = this.data.messages.find(msg => msg.msg_id === msgId);

    if (!message || message.status !== 3) {  // Only retry FAILED messages
      return;
    }

    // Update status to SENDING
    const messages = this.data.messages.map(msg =>
      msg.msg_id === msgId ? { ...msg, status: 1 } : msg
    );
    this.setData({ messages });

    try {
      // Get message service from app
      const app = getApp();
      const messageService = app.getMessageService();

      if (!messageService) {
        throw new Error('Message service not initialized');
      }

      // Get user info
      const userInfo = await getUserInfo();

      // Build message data (reuse original message data)
      const messageData = {
        from: userInfo.qiao_id,
        to: this.data.contactQiaoId,
        conv_id: this.data.convId,
        im_conv_id: this.data.imConvId,
        content: message.content,
        message_type: message.message_type || MESSAGE_TYPE.TEXT,
        supports_typing: message.supports_typing !== undefined ? message.supports_typing : true
      };

      // Retry sending
      const sentMessage = await messageService.sendMessage(messageData);

      // Update message in list
      const updatedMessages = messages.map(function (msg) {
        if (msg.msg_id === msgId) {
          return Object.assign({}, sentMessage, { from_me: true });
        }
        return msg;
      });
      this.setData({ messages: updatedMessages });

      logger.info('Message retry successful', { msg_id: sentMessage.msg_id });
    } catch (error) {
      logger.error('Failed to retry message', { error });

      // Mark as FAILED again
      const updatedMessages = messages.map(function (m) {
        if (m.msg_id === msgId) {
          return Object.assign({}, m, { status: 3 });
        }
        return m;
      });
      this.setData({ messages: updatedMessages });

      wx.showToast({
        title: error.message || '发送失败',
        icon: 'none'
      });
    }
  },

  /**
   * Handle incoming message
   * Called by app.js when message is received
   */
  async onMessageReceived(message) {
    try {
      // Check if message belongs to current conversation
      if (message.conv_id !== this.data.convId) {
        return;
      }

      logger.info('Message received in chat page', {
        msg_id: message.msg_id,
        from: message.from
      });

      // Get user info to determine if message is from me
      const userInfo = await getUserInfo();

      // Add to message list
      const messages = this.data.messages.concat([
        Object.assign({}, message, { from_me: message.from === userInfo.qiao_id })
      ]);

      this.setData({
        messages,
        scrollToView: `msg-${message.msg_id}`
      });

      logger.debug('Message added to chat', {
        msg_id: message.msg_id,
        total_messages: messages.length
      });
    } catch (error) {
      logger.error('Handle received message failed', { error });
    }
  },

  /**
   * Handle typing indicator
   * Called by app.js when typing indicator is received
   */
  onTypingReceived(typing) {
    try {
      // Check if typing belongs to current conversation
      if (typing.conv_id !== this.data.convId) {
        return;
      }

      logger.debug('Typing indicator received', {
        from: typing.from,
        isTyping: typing.isTyping
      });

      // Update navigation bar title
      if (typing.isTyping) {
        wx.setNavigationBarTitle({
          title: '对方正在输入...'
        });

        // Auto restore after 10 seconds
        if (this.typingTimer) {
          clearTimeout(this.typingTimer);
        }
        this.typingTimer = setTimeout(() => {
          if (this.data.contactName) {
            wx.setNavigationBarTitle({
              title: this.data.contactName
            });
          }
        }, 10000);
      } else {
        // Restore contact name
        if (this.data.contactName) {
          wx.setNavigationBarTitle({
            title: this.data.contactName
          });
        }
      }
    } catch (error) {
      logger.error('Handle typing indicator failed', { error });
    }
  },

  goBack() {
    wx.navigateBack();
  },

  showContactInfo() {
    wx.navigateTo({
      url: `/pages/contact-info/contact-info?id=${this.data.convId}`
    });
  },

  goToChatDetail() {
    wx.navigateTo({
      url: `/pages/chat-detail/chat-detail?id=${this.data.convId}`
    });
  }
});
