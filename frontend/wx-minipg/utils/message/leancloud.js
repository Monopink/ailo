/**
 * LeanCloud Message Adapter
 * Adapter for LeanCloud Realtime messaging service
 *
 * Interface Contract (any message adapter must implement):
 * - connect(userId, signature): Promise<void>
 * - disconnect(): Promise<void>
 * - sendMessage(convId, content, type): Promise<Object>
 * - onMessage(callback): void
 * - onTyping(callback): void
 * - onError(callback): void
 * - isConnected(): boolean
 *
 * Installation:
 * npm install leancloud-realtime leancloud-realtime-plugin-typed-messages --save
 */

import { LEANCLOUD_CONFIG } from '../config';
import { ENABLE_LEANCLOUD_DEBUG } from '../env';
import { getLogger } from '../logger';
import { MESSAGE_STATUS, MESSAGE_TYPE } from './constants';

// Import LeanCloud SDK from local files
const IM = require('../../libs/im.min.js');
const initTypedMessages = require('../../libs/typed-messages.min.js');
const adapters = require('../../libs/leancloud-adapters-weapp.js');

// Extract SDK components
const { Realtime, setAdapters, TypedMessage, messageType, messageField, debug } = IM;

// Initialize typed messages plugin
const { TypedMessagesPlugin } = initTypedMessages(null, IM);

// Set adapters for WeChat MiniProgram
setAdapters(adapters);

const logger = getLogger('LCAdapter');

/**
 * LeanCloud message type for business messages (internal use only)
 */
const BUSINESS_MESSAGE_TYPE = 1;

/**
 * Business message class (internal use only)
 * Wraps business layer message structure in LeanCloud TypedMessage
 */
class BusinessMessage extends TypedMessage {
  /**
   * Constructor
   * @param {Object} data - Message data
   */
  constructor(data = {}) {
    super();
    this.msg_id = data.msg_id || '';
    this.from = data.from || '';
    this.to = data.to || '';
    this.conv_id = data.conv_id || '';
    this.content = data.content || '';
    this.message_type = data.message_type || 1;
    this.supports_typing = data.supports_typing !== undefined ? data.supports_typing : true;
    this.sent_time = data.sent_time || 0;
    this.action = data.action || null;
    this.notification_type = data.notification_type ?? null;
    this.data = data.data ?? null;
  }
}

// Declare fields to send
messageField([
  'msg_id',
  'from',
  'to',
  'conv_id',
  'content',
  'message_type',
  'supports_typing',
  'sent_time',
  'action',
  'notification_type',
  'data'
])(BusinessMessage);

// Specify LeanCloud message type
messageType(BUSINESS_MESSAGE_TYPE)(BusinessMessage);

/**
 * LeanCloud message adapter
 */
export class LCAdapter {
  constructor() {
    // Disable LeanCloud SDK debug logging based on environment
    if (!ENABLE_LEANCLOUD_DEBUG && debug && typeof debug.disable === 'function') {
      debug.disable();
      logger.info('LeanCloud debug logging disabled');
    } else if (ENABLE_LEANCLOUD_DEBUG && debug && typeof debug.enable === 'function') {
      debug.enable();
      logger.info('LeanCloud debug logging enabled');
    }

    this.connected = false;
    this.realtime = null;
    this.imClient = null;
    this.conversations = new Map();
    this.messageCallbacks = [];
    this.typingCallbacks = [];
    this.errorCallbacks = [];
  }

  /**
   * Connect to LeanCloud
   * @param {string} userId - User ID
   * @param {Object} signature - Authentication signature
   * @returns {Promise<void>}
   */
  async connect(userId, signature) {
    try {
      logger.info('Connecting to LeanCloud', { userId });

      // Initialize Realtime (SDK already imported at top level)
      this.realtime = new Realtime({
        appId: LEANCLOUD_CONFIG.appId,
        appKey: LEANCLOUD_CONFIG.appKey,
        server: LEANCLOUD_CONFIG.serverUrl,
        plugins: [TypedMessagesPlugin]
      });

      // Register BusinessMessage type
      this.realtime.register(BusinessMessage);

      // Create IM client with signature
      this.imClient = await this.realtime.createIMClient(userId, {
        signatureFactory: () => Promise.resolve({
          signature: signature.signature,
          timestamp: signature.timestamp,
          nonce: signature.nonce
        })
      });

      // Register message handler
      this.imClient.on('message', this.handleMessage.bind(this));

      // Register error handler
      this.imClient.on('disconnect', this.handleDisconnect.bind(this));
      this.imClient.on('error', this.handleError.bind(this));

      this.connected = true;
      logger.info('Connected to LeanCloud');
    } catch (error) {
      logger.error('Connect to LeanCloud failed', {
        error: error.message || String(error),
        stack: error.stack
      });
      throw error;
    }
  }

  /**
   * Disconnect from LeanCloud
   * @returns {Promise<void>}
   */
  async disconnect() {
    try {
      if (this.imClient) {
        await this.imClient.close();
        this.imClient = null;
      }

      this.conversations.clear();
      this.connected = false;

      logger.info('Disconnected from LeanCloud');
    } catch (error) {
      logger.error('Disconnect from LeanCloud failed', {
        error: error.message || String(error),
        stack: error.stack
      });
      throw error;
    }
  }

  /**
   * Register message callback
   * @param {Function} callback - Callback function
   */
  onMessage(callback) {
    if (typeof callback === 'function') {
      this.messageCallbacks.push(callback);
    }
  }

  /**
   * Register typing callback
   * @param {Function} callback - Callback function
   */
  onTyping(callback) {
    if (typeof callback === 'function') {
      this.typingCallbacks.push(callback);
    }
  }

  /**
   * Register error callback
   * @param {Function} callback - Callback function
   */
  onError(callback) {
    if (typeof callback === 'function') {
      this.errorCallbacks.push(callback);
    }
  }

  /**
   * Check if connected
   * @returns {boolean} True if connected
   */
  isConnected() {
    return this.connected;
  }

  /**
   * Resolve LeanCloud conversation instance with caching
   * @param {string} imConvId
   * @param {boolean} forceRefresh
   * @returns {Promise<Object>}
   * @private
   */
  async _getConversationInstance(imConvId, forceRefresh = false) {
    if (!imConvId) {
      throw new Error('IM_CONVERSATION_ID_REQUIRED');
    }

    if (forceRefresh) {
      this.conversations.delete(imConvId);
    }

    const cachedConversation = this.conversations.get(imConvId);
    if (cachedConversation) {
      logger.debug('Using cached conversation', { imConvId });
      return cachedConversation;
    }

    try {
      const conversation = await this.imClient.getConversation(imConvId);
      if (!conversation) {
        logger.error('Conversation lookup returned empty result', { imConvId });
        throw new Error('CONVERSATION_NOT_FOUND');
      }
      this.conversations.set(imConvId, conversation);
      logger.info('Conversation fetched from LeanCloud', { imConvId });
      return conversation;
    } catch (error) {
      logger.error('Get conversation failed', {
        imConvId,
        error: error.message || String(error),
        errorCode: error.code,
        errorType: error.constructor?.name
      });
      const wrappedError = new Error('CONVERSATION_NOT_FOUND');
      wrappedError.originalError = error;
      throw wrappedError;
    }
  }

  /**
   * Send message
   * @param {Object} messageData - Business message data
   * @param {string} messageData.msg_id - Message ID
   * @param {string} messageData.from - Sender qiao_id
   * @param {string} messageData.to - Receiver qiao_id
   * @param {string} messageData.conv_id - Conversation ID
   * @param {string} messageData.content - Message content
   * @param {number} messageData.message_type - Message type
   * @param {boolean} messageData.supports_typing - Supports typing indicator
   * @param {number} messageData.sent_time - Sent timestamp
   * @param {string} imConvId - LeanCloud conversation ID
   * @returns {Promise<Object>} Sent message
   */
  async sendMessage(messageData, imConvId) {
    try {
      if (!this.connected || !this.imClient) {
        throw new Error('MESSAGE_SERVICE_DISCONNECTED');
      }

      logger.debug('Sending message', {
        msg_id: messageData.msg_id,
        imConvId
      });

      // Get or create conversation
      const conversation = await this._getConversationInstance(imConvId);

      // Create business message
      const businessMessage = new BusinessMessage(messageData);

      // Send message - wrap in try-catch to catch send errors
      let sentMessage;
      try {
        sentMessage = await conversation.send(businessMessage);
      } catch (sendError) {
        logger.error('Conversation send failed', {
          imConvId,
          error: sendError.message || String(sendError),
          errorCode: sendError.code,
          errorType: sendError.constructor.name
        });
        this.invalidateConversation(imConvId);

        // If send fails, it might be because conversation is invalid
        // Wrap as CONVERSATION_NOT_FOUND to trigger refresh
        const error = new Error('CONVERSATION_NOT_FOUND');
        error.originalError = sendError;
        throw error;
      }

      logger.info('Message sent successfully', {
        msg_id: messageData.msg_id,
        lc_msg_id: sentMessage.id
      });

      // Return sent message data
      return {
        ...messageData,
        lc_msg_id: sentMessage.id,
        lc_timestamp: sentMessage.timestamp
      };
    } catch (error) {
      logger.error('Send message failed', {
        msg_id: messageData.msg_id,
        imConvId,
        error: error.message || String(error),
        stack: error.stack
      });
      throw error;
    }
  }

  /**
   * Invalidate cached conversation
   * @param {string} imConvId
   */
  invalidateConversation(imConvId) {
    if (!imConvId) {
      this.conversations.clear();
      logger.warn('Conversation cache cleared (no id provided)');
      return;
    }

    if (this.conversations.delete(imConvId)) {
      logger.info('Conversation cache invalidated', { imConvId });
    }
  }

  /**
   * Trigger message callbacks
   * @param {Object} message - Message object
   */
  triggerMessageCallbacks(message) {
    this.messageCallbacks.forEach(callback => {
      try {
        callback(message);
      } catch (error) {
        logger.error('Message callback error', {
          error: error.message || String(error),
          stack: error.stack
        });
      }
    });
  }

  /**
   * Trigger typing callbacks
   * @param {Object} typing - Typing object
   */
  triggerTypingCallbacks(typing) {
    this.typingCallbacks.forEach(callback => {
      try {
        callback(typing);
      } catch (error) {
        logger.error('Typing callback error', {
          error: error.message || String(error),
          stack: error.stack
        });
      }
    });
  }

  /**
   * Trigger error callbacks
   * @param {Error} error - Error object
   */
  triggerErrorCallbacks(error) {
    this.errorCallbacks.forEach(callback => {
      try {
        callback(error);
      } catch (err) {
        logger.error('Error callback error', {
          error: err.message || String(err),
          stack: err.stack
        });
      }
    });
  }

  /**
   * Handle incoming message (internal)
   * @param {Object} message - LeanCloud message object
   */
  handleMessage(message) {
    try {
      logger.debug('Message received', {
        type: message.constructor.name,
        from: message.from
      });

      // Check if it's a BusinessMessage
      if (message instanceof BusinessMessage) {
        // Extract business data
        const businessData = {
          msg_id: message.msg_id,
          from: message.from,
          to: message.to,
          conv_id: message.conv_id,
          content: message.content,
          message_type: message.message_type,
          supports_typing: message.supports_typing,
          sent_time: message.sent_time,
          status: MESSAGE_STATUS.RECEIVED,
          lc_msg_id: message.id,
          lc_timestamp: message.timestamp,
          action: message.action || null,
          notification_type: message.notification_type ?? null,
          data: message.data ?? null
        };

        // Check if it's a typing indicator
        if (businessData.message_type === MESSAGE_TYPE.TYPING_START ||
          businessData.message_type === MESSAGE_TYPE.TYPING_END) {
          this.triggerTypingCallbacks({
            from: businessData.from,
            conv_id: businessData.conv_id,
            isTyping: businessData.message_type === MESSAGE_TYPE.TYPING_START
          });
        } else {
          // Trigger message callbacks
          this.triggerMessageCallbacks(businessData);
        }
      } else {
        logger.warn('Received non-business message', {
          type: message.constructor.name
        });
      }
    } catch (error) {
      logger.error('Handle message error', {
        error: error.message || String(error),
        stack: error.stack
      });
    }
  }

  /**
   * Handle disconnect (internal)
   */
  handleDisconnect() {
    logger.warn('Disconnected from LeanCloud');
    this.connected = false;
  }

  /**
   * Handle error (internal)
   * @param {Error} error - Error object
   */
  handleError(error) {
    logger.error('LeanCloud error', {
      error: error.message || String(error),
      stack: error.stack
    });
    this.triggerErrorCallbacks(error);
  }
}

// Export default instance
export default new LCAdapter();
