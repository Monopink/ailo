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
 * - onConnectionChange(callback): void
 * - isConnected(): boolean
 *
 * Installation:
 * npm install leancloud-realtime leancloud-realtime-plugin-typed-messages --save
 */

import { LEANCLOUD_CONFIG } from '../config';
import { ENABLE_LEANCLOUD_DEBUG } from '../env';
import { getLogger } from '../logger';
import { MESSAGE_STATUS, MESSAGE_TYPE } from '../constants/message';
import type { MessageType } from '../constants/message';
import { isNonEmptyString } from '../guards';
import type {
  AdapterMessage,
  AdapterSendResult,
  AdapterTypingPayload,
  ConnectionState,
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

const isMessageTypeValue = (value: unknown): value is MessageType =>
  typeof value === 'number' && Object.values(MESSAGE_TYPE).includes(value as MessageType);

type AttributeRecord = Record<string, unknown>;
type ResolvedPayload = Omit<AdapterMessage, 'status' | 'lc_msg_id' | 'lc_timestamp'>;

const asRecord = (value: unknown): Record<string, unknown> | null =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null;

const getStringAttr = (attrs: AttributeRecord | null, key: string, fallback: string): string => {
  const value = attrs?.[key];
  return typeof value === 'string' ? value : fallback;
};

const getOptionalStringAttr = (
  attrs: AttributeRecord | null,
  key: string,
  fallback: string | null
): string | null => {
  const value = attrs?.[key];
  return typeof value === 'string' ? value : fallback;
};

const getBooleanAttr = (attrs: AttributeRecord | null, key: string, fallback: boolean): boolean => {
  const value = attrs?.[key];
  return typeof value === 'boolean' ? value : fallback;
};

const getNumberAttr = (attrs: AttributeRecord | null, key: string, fallback: number): number => {
  const value = attrs?.[key];
  return typeof value === 'number' ? value : fallback;
};

const getMessageTypeAttr = (
  attrs: AttributeRecord | null,
  key: string,
  fallback: MessageType
): MessageType => {
  const value = attrs?.[key];
  return isMessageTypeValue(value) ? value : fallback;
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
  from_qiao_id = '';
  to_qiao_id = '';
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
    if (data.msg_id !== undefined) {
      this.msg_id = data.msg_id;
    }
    if (data.from_qiao_id !== undefined) {
      this.from_qiao_id = data.from_qiao_id;
    }
    if (data.to_qiao_id !== undefined) {
      this.to_qiao_id = data.to_qiao_id;
    }
    if (data.conv_id !== undefined) {
      this.conv_id = data.conv_id;
    }
    if (data.content !== undefined) {
      this.content = data.content;
    }
    if (data.message_type !== undefined) {
      this.message_type = data.message_type;
    }
    if (data.supports_typing !== undefined) {
      this.supports_typing = data.supports_typing;
    }
    if (data.sent_time !== undefined) {
      this.sent_time = data.sent_time;
    }
    if (data.action !== undefined) {
      this.action = data.action;
    }
    if (data.notification_type !== undefined) {
      this.notification_type = data.notification_type;
    }
    if (data.data !== undefined) {
      this.data = data.data;
    }
  }
}

messageField([
  'msg_id',
  'from_qiao_id',
  'to_qiao_id',
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

const getAttributeRecord = (message: BusinessMessage): AttributeRecord | null => {
  const candidate = message as unknown;
  if (
    typeof candidate === 'object' &&
    candidate !== null &&
    'getAttributes' in candidate &&
    typeof (candidate as { getAttributes?: unknown }).getAttributes === 'function'
  ) {
    const rawAttributes = (candidate as { getAttributes: () => unknown }).getAttributes();
    return asRecord(rawAttributes);
  }

  if (typeof candidate === 'object' && candidate !== null && 'attributes' in candidate) {
    const rawAttributes = (candidate as { attributes?: unknown }).attributes;
    return asRecord(rawAttributes);
  }

  return null;
};

const resolveBusinessPayload = (message: BusinessMessage): ResolvedPayload | null => {
  const attrs = getAttributeRecord(message);

  const msgIdValue = isNonEmptyString(message.msg_id)
    ? message.msg_id
    : getStringAttr(attrs, 'msg_id', '');
  if (!isNonEmptyString(msgIdValue)) {
    logger.error('Business message missing msg_id', {
      msg_id: msgIdValue,
      lc_id: message.id,
      lc_timestamp: message.timestamp,
      message_type: message.message_type,
    });
    return null;
  }

  const fallbackFrom = isNonEmptyString(message.from_qiao_id) ? message.from_qiao_id : '';
  const fallbackTo = isNonEmptyString(message.to_qiao_id) ? message.to_qiao_id : '';
  const fallbackConv = isNonEmptyString(message.conv_id) ? message.conv_id : '';

  return {
    msg_id: msgIdValue,
    from_qiao_id: getStringAttr(attrs, 'from_qiao_id', fallbackFrom),
    to_qiao_id: getStringAttr(attrs, 'to_qiao_id', fallbackTo),
    conv_id: getStringAttr(attrs, 'conv_id', fallbackConv),
    content: getStringAttr(attrs, 'content', message.content),
    message_type: getMessageTypeAttr(attrs, 'message_type', message.message_type),
    supports_typing: getBooleanAttr(attrs, 'supports_typing', message.supports_typing),
    sent_time: getNumberAttr(attrs, 'sent_time', message.sent_time),
    action: getOptionalStringAttr(attrs, 'action', message.action),
    notification_type: getOptionalStringAttr(attrs, 'notification_type', message.notification_type),
    data: asRecord(attrs?.data) ?? message.data,
  };
};

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
  private connectionCallbacks: Array<(state: ConnectionState) => void> = [];

  constructor() {
    if (!ENABLE_LEANCLOUD_DEBUG && typeof debug?.disable === 'function') {
      debug.disable();
      logger.info('LeanCloud debug logging disabled');
    } else if (ENABLE_LEANCLOUD_DEBUG && typeof debug?.enable === 'function') {
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

      if (this.realtime === null) {
        this.realtime = new Realtime({
          appId: LEANCLOUD_CONFIG.appId,
          appKey: LEANCLOUD_CONFIG.appKey,
          server: LEANCLOUD_CONFIG.serverUrl,
          plugins: [TypedMessagesPlugin],
        });
        this.realtime.register(BusinessMessage);
      }

      if (this.imClient !== null) {
        await this.imClient.close();
        this.imClient = null;
      }

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
      this.triggerConnectionCallbacks('connected');
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
      if (this.imClient !== null) {
        await this.imClient.close();
        this.imClient = null;
      }

      this.conversations.clear();
      this.connected = false;

      logger.info('Disconnected from LeanCloud');
      this.triggerConnectionCallbacks('disconnected');
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

  /** Register connection callback */
  onConnectionChange(callback: (state: ConnectionState) => void): void {
    if (typeof callback === 'function') {
      this.connectionCallbacks.push(callback);
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
    if (imConvId === '') {
      throw new Error('IM_CONVERSATION_ID_REQUIRED');
    }

    if (forceRefresh) {
      this.conversations.delete(imConvId);
    }

    const cachedConversation = this.conversations.get(imConvId);
    if (cachedConversation !== undefined) {
      logger.debug('Using cached conversation', { imConvId });
      return cachedConversation;
    }

    try {
      const conversation = await this.imClient!.getConversation(imConvId);
      if (conversation === null) {
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
      if (!this.connected || this.imClient === null) {
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
        typeof sentMessage.id === 'string' && sentMessage.id !== ''
          ? sentMessage.id
          : messageData.msg_id;
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
    if (imConvId === null || imConvId === undefined || imConvId === '') {
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

  private triggerConnectionCallbacks(state: ConnectionState): void {
    this.connectionCallbacks.forEach((callback) => {
      try {
        callback(state);
      } catch (error) {
        const err = toError(error);
        logger.error('Connection callback error', {
          error: err.message,
          stack: err.stack,
        });
      }
    });
  }

  /**
   * Process business message
   * @param {BusinessMessage} message - Business message instance
   */
  private processBusinessMessage(message: BusinessMessage): void {
    const resolvedPayload = resolveBusinessPayload(message);
    if (resolvedPayload === null) {
      return;
    }
    const lcMsgId =
      typeof message.id === 'string' && message.id !== '' ? message.id : message.msg_id;
    const lcTimestamp =
      typeof message.timestamp === 'number' && Number.isFinite(message.timestamp)
        ? message.timestamp
        : Date.now();

    const businessData: AdapterMessage = {
      ...resolvedPayload,
      status: MESSAGE_STATUS.RECEIVED,
      lc_msg_id: lcMsgId,
      lc_timestamp: lcTimestamp,
    };

    if (
      businessData.message_type === MESSAGE_TYPE.TYPING_START ||
      businessData.message_type === MESSAGE_TYPE.TYPING_END
    ) {
      this.triggerTypingCallbacks({
        from_qiao_id: businessData.from_qiao_id,
        conv_id: businessData.conv_id,
        isTyping: businessData.message_type === MESSAGE_TYPE.TYPING_START,
      });
    } else {
      this.triggerMessageCallbacks(businessData);
    }
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
        this.processBusinessMessage(message);
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
    this.triggerConnectionCallbacks('disconnected');
  }

  /**
   * Handle error (internal)
   * @param {Error} error - Error object
   */
  private handleError(error: Error): void {
    logger.error('LeanCloud error', {
      error: error.message !== '' ? error.message : String(error),
      stack: error.stack,
    });
    this.triggerErrorCallbacks(error);
  }
}

export default new LCAdapter();
