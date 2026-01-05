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
import type { MessageType } from './constants';
import type {
  AdapterMessage,
  AdapterSendResult,
  AdapterTypingPayload,
  BusinessMessagePayload,
  MessageAdapter,
  MessageSignature,
} from './adapter-types';

import * as IM from '../../libs/im.min.js';
import type { Conversation } from '../../libs/im.min.js';
import initTypedMessages from '../../libs/typed-messages.min.js';
import * as adapters from '../../libs/leancloud-adapters-weapp.js';

const { Realtime, setAdapters, TypedMessage, messageType, messageField, debug } = IM;
const { TypedMessagesPlugin } = initTypedMessages(null, IM);

setAdapters(adapters);

const logger = getLogger('LCAdapter');

const toError = (error: unknown): Error => {
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

type MessageCallback = (payload: AdapterMessage) => void;
type TypingCallback = (payload: AdapterTypingPayload) => void;
type ErrorCallback = (error: Error) => void;

/**
 * LeanCloud message type for business messages (internal use only)
 */
const BUSINESS_MESSAGE_TYPE = 1;

/**
 * Business message class (internal use only)
 * Wraps business layer message structure in LeanCloud TypedMessage
 */
class BusinessMessage extends TypedMessage {
  id?: string;
  timestamp?: number;
  msg_id = '';
  from = '';
  to = '';
  conv_id = '';
  content = '';
  message_type: MessageType = MESSAGE_TYPE.TEXT;
  supports_typing = true;
  sent_time = 0;
  action: string | null = null;
  notification_type: string | null = null;
  data: Record<string, unknown> | null = null;

  constructor(data: Partial<BusinessMessagePayload> = {}) {
    super();
    Object.assign(this, data);
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
  'data',
])(BusinessMessage);

// Specify LeanCloud message type
messageType(BUSINESS_MESSAGE_TYPE)(BusinessMessage);

/**
 * LeanCloud message adapter
 */
export class LCAdapter implements MessageAdapter {
  private connected = false;
  private realtime: IM.Realtime | null = null;
  private imClient: IM.IMClient | null = null;
  private conversations = new Map<string, Conversation>();
  private messageCallbacks: MessageCallback[] = [];
  private typingCallbacks: TypingCallback[] = [];
  private errorCallbacks: ErrorCallback[] = [];

  constructor() {
    if (!ENABLE_LEANCLOUD_DEBUG && debug && typeof debug.disable === 'function') {
      debug.disable();
      logger.info('LeanCloud debug logging disabled');
    } else if (ENABLE_LEANCLOUD_DEBUG && debug && typeof debug.enable === 'function') {
      debug.enable();
      logger.info('LeanCloud debug logging enabled');
    }
  }

  /**
   * Connect to LeanCloud
   * @param {string} userId - User ID
   * @param {Object} signature - Authentication signature
   * @returns {Promise<void>}
   */
  async connect(userId: string, signature: MessageSignature): Promise<void> {
    try {
      logger.info('Connecting to LeanCloud', { userId });

      this.realtime = new Realtime({
        appId: LEANCLOUD_CONFIG.appId,
        appKey: LEANCLOUD_CONFIG.appKey,
        server: LEANCLOUD_CONFIG.serverUrl,
        plugins: [TypedMessagesPlugin],
      });

      this.realtime.register(BusinessMessage);

      this.imClient = await this.realtime.createIMClient(userId, {
        signatureFactory: () =>
          Promise.resolve({
            signature: signature.signature,
            timestamp: signature.timestamp,
            nonce: signature.nonce,
          }),
      });

      this.imClient.on('message', this.handleMessage.bind(this));
      this.imClient.on('disconnect', this.handleDisconnect.bind(this));
      this.imClient.on('error', (err: unknown) => this.handleError(toError(err)));

      this.connected = true;
      logger.info('Connected to LeanCloud');
    } catch (error) {
      const err = toError(error);
      logger.error('Connect to LeanCloud failed', {
        error: err.message,
        stack: err.stack,
      });
      throw err;
    }
  }

  /**
   * Disconnect from LeanCloud
   * @returns {Promise<void>}
   */
  async disconnect(): Promise<void> {
    try {
      if (this.imClient) {
        await this.imClient.close();
        this.imClient = null;
      }

      this.conversations.clear();
      this.connected = false;

      logger.info('Disconnected from LeanCloud');
    } catch (error) {
      const err = toError(error);
      logger.error('Disconnect from LeanCloud failed', {
        error: err.message,
        stack: err.stack,
      });
      throw err;
    }
  }

  /**
   * Register message callback
   * @param {Function} callback - Callback function
   */
  onMessage(callback: MessageCallback): void {
    if (typeof callback === 'function') {
      this.messageCallbacks.push(callback);
    }
  }

  /**
   * Register typing callback
   * @param {Function} callback - Callback function
   */
  onTyping(callback: TypingCallback): void {
    if (typeof callback === 'function') {
      this.typingCallbacks.push(callback);
    }
  }

  /**
   * Register error callback
   * @param {Function} callback - Callback function
   */
  onError(callback: ErrorCallback): void {
    if (typeof callback === 'function') {
      this.errorCallbacks.push(callback);
    }
  }

  /**
   * Check if connected
   * @returns {boolean} True if connected
   */
  isConnected(): boolean {
    return this.connected;
  }

  private async getConversationInstance(
    imConvId: string,
    forceRefresh = false
  ): Promise<IM.Conversation> {
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
      const conversation = await this.imClient!.getConversation(imConvId);
      if (!conversation) {
        logger.error('Conversation lookup returned empty result', { imConvId });
        throw new Error('CONVERSATION_NOT_FOUND');
      }
      this.conversations.set(imConvId, conversation);
      logger.info('Conversation fetched from LeanCloud', { imConvId });
      return conversation;
    } catch (error) {
      const err = toError(error);
      const rawDetails = error as { code?: unknown; constructor?: { name?: string } };
      logger.error('Get conversation failed', {
        imConvId,
        error: err.message,
        errorCode: rawDetails.code,
        errorType: rawDetails.constructor?.name,
        stack: err.stack,
      });
      const wrappedError = new Error('CONVERSATION_NOT_FOUND') as Error & {
        originalError?: unknown;
      };
      wrappedError.originalError = error;
      throw wrappedError;
    }
  }

  async sendMessage(
    messageData: BusinessMessagePayload,
    imConvId: string
  ): Promise<AdapterSendResult> {
    try {
      if (!this.connected || !this.imClient) {
        throw new Error('MESSAGE_SERVICE_DISCONNECTED');
      }

      logger.debug('Sending message', {
        msg_id: messageData.msg_id,
        imConvId,
      });

      const conversation = await this.getConversationInstance(imConvId);

      const businessMessage = new BusinessMessage(messageData);

      type SendResult = { id?: string; timestamp?: number };
      let sentMessage: SendResult;
      try {
        sentMessage = (await conversation.send(businessMessage)) as SendResult;
      } catch (sendError) {
        const err = toError(sendError);
        const rawDetails = sendError as { code?: unknown; constructor?: { name?: string } };
        logger.error('Conversation send failed', {
          imConvId,
          error: err.message,
          errorCode: rawDetails.code,
          errorType: rawDetails.constructor?.name,
          stack: err.stack,
        });
        this.invalidateConversation(imConvId);
        const wrappedError = new Error('CONVERSATION_NOT_FOUND') as Error & {
          originalError?: unknown;
        };
        wrappedError.originalError = sendError;
        throw wrappedError;
      }

      const lcMsgId =
        typeof sentMessage.id === 'string' && sentMessage.id ? sentMessage.id : messageData.msg_id;
      const lcTimestamp =
        typeof sentMessage.timestamp === 'number' && Number.isFinite(sentMessage.timestamp)
          ? sentMessage.timestamp
          : Date.now();

      logger.info('Message sent successfully', {
        msg_id: messageData.msg_id,
        lc_msg_id: lcMsgId,
      });

      return {
        ...messageData,
        lc_msg_id: lcMsgId,
        lc_timestamp: lcTimestamp,
      };
    } catch (error) {
      const err = toError(error);
      logger.error('Send message failed', {
        msg_id: messageData.msg_id,
        imConvId,
        error: err.message,
        stack: err.stack,
      });
      throw err;
    }
  }

  /**
   * Invalidate cached conversation
   * @param {string} imConvId
   */
  invalidateConversation(imConvId?: string | null): void {
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
  private triggerMessageCallbacks(message: Parameters<MessageCallback>[0]): void {
    this.messageCallbacks.forEach((callback) => {
      try {
        callback(message);
      } catch (error) {
        const err = toError(error);
        logger.error('Message callback error', {
          error: err.message,
          stack: err.stack,
        });
      }
    });
  }

  /**
   * Trigger typing callbacks
   * @param {Object} typing - Typing object
   */
  private triggerTypingCallbacks(typing: Parameters<TypingCallback>[0]): void {
    this.typingCallbacks.forEach((callback) => {
      try {
        callback(typing);
      } catch (error) {
        const err = toError(error);
        logger.error('Typing callback error', {
          error: err.message,
          stack: err.stack,
        });
      }
    });
  }

  /**
   * Trigger error callbacks
   * @param {Error} error - Error object
   */
  private triggerErrorCallbacks(error: Error): void {
    this.errorCallbacks.forEach((callback) => {
      try {
        callback(error);
      } catch (err) {
        const normalized = toError(err);
        logger.error('Error callback error', {
          error: normalized.message,
          stack: normalized.stack,
        });
      }
    });
  }

  /**
   * Handle incoming message (internal)
   * @param {Object} message - LeanCloud message object
   */
  private handleMessage(message: unknown): void {
    try {
      logger.debug('Message received', {
        type: (message as { constructor: { name: string } }).constructor.name,
        from: (message as { from?: string }).from,
      });

      if (message instanceof BusinessMessage) {
        const lcMsgId = typeof message.id === 'string' && message.id ? message.id : message.msg_id;
        const lcTimestamp =
          typeof message.timestamp === 'number' && Number.isFinite(message.timestamp)
            ? message.timestamp
            : Date.now();

        const businessData: AdapterMessage = {
          msg_id: message.msg_id,
          from: message.from,
          to: message.to,
          conv_id: message.conv_id,
          content: message.content,
          message_type: message.message_type,
          supports_typing: message.supports_typing,
          sent_time: message.sent_time,
          status: MESSAGE_STATUS.RECEIVED,
          lc_msg_id: lcMsgId,
          lc_timestamp: lcTimestamp,
          action: message.action || null,
          notification_type: message.notification_type ?? null,
          data: message.data ?? null,
        };

        if (
          businessData.message_type === MESSAGE_TYPE.TYPING_START ||
          businessData.message_type === MESSAGE_TYPE.TYPING_END
        ) {
          this.triggerTypingCallbacks({
            from: businessData.from,
            conv_id: businessData.conv_id,
            isTyping: businessData.message_type === MESSAGE_TYPE.TYPING_START,
          });
        } else {
          this.triggerMessageCallbacks(businessData);
        }
      } else {
        const nonBusinessType =
          typeof message === 'object' && message !== null && 'constructor' in message
            ? ((message as { constructor?: { name?: string } }).constructor?.name ?? 'Unknown')
            : typeof message;
        logger.warn('Received non-business message', {
          type: nonBusinessType,
        });
      }
    } catch (error) {
      const err = toError(error);
      logger.error('Handle message error', {
        error: err.message,
        stack: err.stack,
      });
    }
  }

  /**
   * Handle disconnect (internal)
   */
  private handleDisconnect(): void {
    logger.warn('Disconnected from LeanCloud');
    this.connected = false;
  }

  /**
   * Handle error (internal)
   * @param {Error} error - Error object
   */
  private handleError(error: Error): void {
    logger.error('LeanCloud error', {
      error: error.message || String(error),
      stack: error.stack,
    });
    this.triggerErrorCallbacks(error);
  }
}

export default new LCAdapter();
