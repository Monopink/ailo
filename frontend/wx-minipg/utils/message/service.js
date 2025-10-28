/**
 * Message Service
 * High-level message service that manages message adapter and message queue
 *
 * Design: Uses dependency injection for message adapter (default: LeanCloud)
 * To replace adapter: import different adapter and pass to constructor
 */

import { getMessageClientSignature } from '../auth';
import { getLogger } from '../logger';
import { addMessage, getUserInfo } from '../storage';
import { MESSAGE_STATUS, MESSAGE_TYPE } from './constants';
import leancloudAdapter from './leancloud';
import { MessageQueue } from './queue';

const logger = getLogger('MessageService');

/**
 * Message service class
 */
class MessageService {
  constructor(adapter = leancloudAdapter) {
    this.adapter = adapter;
    this.queue = null;
    this.initialized = false;
  }

  /**
   * Initialize message service
   * @param {string} userId - User ID (qiao_id)
   * @returns {Promise<void>}
   */
  async initialize(userId) {
    try {
      if (this.initialized) {
        logger.warn('Message service already initialized');
        return;
      }

      logger.info('Initializing message service', { userId });

      // Get signature from backend
      const signature = await getMessageClientSignature(userId);

      // Connect to adapter
      await this.adapter.connect(userId, signature);

      // Create message queue
      this.queue = new MessageQueue(this.adapter);

      // Register message handler
      this.adapter.onMessage(this.handleMessage.bind(this));

      // Register typing handler
      this.adapter.onTyping(this.handleTyping.bind(this));

      // Register error handler
      this.adapter.onError(this.handleError.bind(this));

      this.initialized = true;
      logger.info('Message service initialized');
    } catch (error) {
      logger.error('Initialize message service failed', { error });
      throw error;
    }
  }

  /**
   * Send message
   * @param {Object} messageData - Message data
   * @param {string} messageData.from - Sender qiao_id
   * @param {string} messageData.to - Receiver qiao_id
   * @param {string} messageData.conv_id - Conversation ID
   * @param {string} messageData.im_conv_id - LeanCloud conversation ID
   * @param {string} messageData.content - Message content
   * @param {number} messageData.message_type - Message type
   * @param {boolean} messageData.supports_typing - Supports typing indicator
   * @returns {Promise<Object>} Message object
   */
  async sendMessage(messageData) {
    try {
      if (!this.initialized) {
        throw new Error('Message service not initialized');
      }

      logger.debug('Sending message', {
        conv_id: messageData.conv_id,
        message_type: messageData.message_type
      });

      // Generate message ID (allow client-provided id for optimistic UI)
      const msg_id = messageData.client_msg_id || `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      // Build complete message object
      const message = {
        msg_id,
        from: messageData.from,
        to: messageData.to,
        conv_id: messageData.conv_id,
        content: messageData.content,
        message_type: messageData.message_type || MESSAGE_TYPE.TEXT,
        supports_typing: messageData.supports_typing !== undefined ? messageData.supports_typing : true,
        sent_time: Date.now(),
        status: MESSAGE_STATUS.SENDING
      };

      // Save to local storage with SENDING status
      await addMessage(messageData.conv_id, message);

      // Send via adapter
      try {
        const sentMessage = await this.adapter.sendMessage(message, messageData.im_conv_id);

        // Update status to SENT
        message.status = MESSAGE_STATUS.SENT;

        // Store adapter-specific metadata
        message.adapter_metadata = {
          msg_id: sentMessage.lc_msg_id,
          timestamp: sentMessage.lc_timestamp
        };

        // Update in local storage
        await addMessage(messageData.conv_id, message);

        logger.info('Message sent successfully', { msg_id });
      } catch (error) {
        // Update status to FAILED
        message.status = MESSAGE_STATUS.FAILED;

        // Update in local storage
        await addMessage(messageData.conv_id, message);

        logger.error('Send message via adapter failed', {
          msg_id,
          error: error.message || String(error)
        });

        // Mark failed locally and persist
        try {
          message.status = MESSAGE_STATUS.FAILED;
          message.error_reason = error && (error.message || String(error));
          await addMessage(messageData.conv_id, message);
        } catch (_) {}
        throw error;
      }

      return message;
    } catch (error) {
      logger.error('Send message failed', {
        conv_id: messageData.conv_id,
        error: error.message || String(error)
      });
      throw error;
    }
  }

  /**
   * Handle incoming message
   * @param {Object} message - Business message object
   */
  async handleMessage(message) {
    try {
      logger.debug('Message received', {
        msg_id: message.msg_id,
        from: message.from
      });

      // Save to local storage
      await addMessage(message.conv_id, message);

      // Notify app
      const app = getApp();
      if (app.onMessageReceived) {
        app.onMessageReceived(message);
      }
    } catch (error) {
      logger.error('Handle message error', {
        error: error.message || String(error)
      });
    }
  }

  /**
   * Handle typing indicator
   * @param {Object} typing - Typing object
   */
  handleTyping(typing) {
    try {
      logger.debug('Typing indicator received', { typing });

      // Notify app
      const app = getApp();
      if (app.onTypingReceived) {
        app.onTypingReceived(typing);
      }
    } catch (error) {
      logger.error('Handle typing error', { error });
    }
  }

  /**
   * Handle error
   * @param {Error} error - Error object
   */
  handleError(error) {
    logger.error('Message service error', { error });

    // Notify app
    const app = getApp();
    if (app.onMessageError) {
      app.onMessageError(error);
    }
  }

  /**
   * Disconnect
   * @returns {Promise<void>}
   */
  async disconnect() {
    try {
      if (this.adapter) {
        await this.adapter.disconnect();
      }

      this.queue = null;
      this.initialized = false;

      logger.info('Message service disconnected');
    } catch (error) {
      logger.error('Disconnect message service failed', { error });
      throw error;
    }
  }

  /**
   * Check if initialized
   * @returns {boolean} True if initialized
   */
  isInitialized() {
    return this.initialized;
  }
}

// Singleton instance
let messageServiceInstance = null;

/**
 * Initialize message service
 * @returns {Promise<MessageService>} Message service instance
 */
export async function initMessageService() {
  if (messageServiceInstance) {
    logger.info('Message service already initialized');
    return messageServiceInstance;
  }

  logger.info('Initializing message service');

  // Get user info from storage
  const userInfo = await getUserInfo();

  if (!userInfo || !userInfo.qiao_id) {
    const error = new Error('User info not found or invalid');
    logger.error('Cannot initialize message service', {
      hasUserInfo: !!userInfo,
      hasQiaoId: userInfo ? !!userInfo.qiao_id : false
    });
    throw error;
  }

  logger.info('User info loaded', { qiao_id: userInfo.qiao_id });

  // Create and initialize message service
  messageServiceInstance = new MessageService();
  await messageServiceInstance.initialize(userInfo.qiao_id);

  logger.info('Message service initialized successfully');

  return messageServiceInstance;
}

/**
 * Get message service instance
 * @returns {MessageService} Message service instance
 */
export function getMessageService() {
  return messageServiceInstance;
}

// Export default instance for direct use
export default messageServiceInstance;
