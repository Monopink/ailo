/**
 * Message Service
 * High-level message service that manages message adapter interactions.
 */

import { getMessageClientSignature } from '../message-signature';
import { getLogger } from '../logger';
import { addMessage, getUserInfo } from '../storage';
import type { StoredMessage } from '../storage';
import { MESSAGE_STATUS, MESSAGE_TYPE } from './constants';
import type { MessageType } from './constants';
import conversationStore from './conversation-store';
import type {
  AdapterMessage,
  AdapterSendResult,
  AdapterTypingPayload,
  BusinessMessagePayload,
  MessageAdapter,
  MessageSignature,
} from './adapter-types';
import { getMessageAdapter } from './provider';
import messageEventBus from './event-bus';

const logger = getLogger('MessageService');

type MessageStatus = (typeof MESSAGE_STATUS)[keyof typeof MESSAGE_STATUS];

const createBusinessMessage = (
  base: MessageData,
  msgId: string,
  status: MessageStatus
): BusinessMessage => ({
  msg_id: msgId,
  from: base.from,
  to: base.to,
  conv_id: base.conv_id,
  content: base.content,
  message_type: base.message_type ?? MESSAGE_TYPE.TEXT,
  supports_typing:
    base.supports_typing !== undefined ? base.supports_typing : true,
  sent_time: Date.now(),
  status,
});

interface MessageData {
  from: string;
  to: string;
  conv_id: string;
  content: string;
  message_type?: MessageType;
  supports_typing?: boolean;
  client_msg_id?: string;
}

const generateClientMessageId = (): string =>
  `client_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;

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

type BusinessMessage = StoredMessage &
  BusinessMessagePayload & {
    status: MessageStatus;
    adapter_metadata?: Record<string, unknown>;
    error_reason?: string;
  };

export class MessageService {
  private adapter: MessageAdapter;
  private initialized = false;

  constructor(adapter: MessageAdapter = getMessageAdapter()) {
    this.adapter = adapter;
  }

  private async persistMessage(convId: string, message: StoredMessage): Promise<void> {
    await addMessage(convId, message);
  }

  async initialize(userId: string): Promise<void> {
    if (this.initialized) {
      logger.warn('Message service already initialized');
      return;
    }

    try {
      logger.info('Initializing message service', { userId });

      const signature = await getMessageClientSignature(userId);
      await this.adapter.connect(userId, signature as MessageSignature);

      this.adapter.onMessage((message) => {
        void this.handleMessage(message);
      });
      this.adapter.onTyping(this.handleTyping.bind(this));
      this.adapter.onError(this.handleError.bind(this));

      this.initialized = true;
      logger.info('Message service initialized');
    } catch (error) {
      logger.error('Initialize message service failed', { error });
      throw error;
    }
  }

  async sendMessage(messageData: MessageData): Promise<BusinessMessage> {
    if (!this.initialized) {
      throw new Error('Message service not initialized');
    }

    logger.info('Sending message', {
      conv_id: messageData.conv_id,
      message_type: messageData.message_type,
      content_length: messageData.content ? messageData.content.length : 0,
      from: messageData.from,
      to: messageData.to,
      client_msg_id: messageData.client_msg_id,
    });

    const msgId = messageData.client_msg_id || generateClientMessageId();

    const message = createBusinessMessage(messageData, msgId, MESSAGE_STATUS.SENDING);

    await this.persistMessage(messageData.conv_id, message);

    try {
      const sentMessage = await this.sendViaAdapter(message);
      const sentPayload: BusinessMessage = {
        ...message,
        status: MESSAGE_STATUS.SENT,
        adapter_metadata: {
          msg_id: sentMessage.lc_msg_id,
          timestamp: sentMessage.lc_timestamp,
        },
      };

      await this.persistMessage(messageData.conv_id, sentPayload);
      messageEventBus.emitMessage(sentPayload);
      logger.info('Message sent successfully', {
        msg_id: msgId,
        conv_id: messageData.conv_id,
        message_type: message.message_type,
        status: sentPayload.status,
      });

      return sentPayload;
    } catch (error) {
      const err = normalizeError(error);
      const failedPayload: BusinessMessage = {
        ...message,
        status: MESSAGE_STATUS.FAILED,
        error_reason: err.message,
      };

      await this.persistMessage(messageData.conv_id, failedPayload);
      messageEventBus.emitMessage(failedPayload);

      logger.error('Send message via adapter failed', {
        msg_id: msgId,
        conv_id: messageData.conv_id,
        message_type: message.message_type,
        error: err.message,
      });

      throw err;
    }
  }

  private async sendViaAdapter(
    message: BusinessMessage,
    options: { allowRetry?: boolean } = { allowRetry: true }
  ): Promise<AdapterSendResult> {
    const allowRetry = options.allowRetry !== false;
    const imConvId = await conversationStore.getImConvId();

    try {
      return await this.adapter.sendMessage(message, imConvId);
    } catch (error) {
      const err = normalizeError(error);
      if (err.message === 'CONVERSATION_NOT_FOUND' && allowRetry) {
        logger.warn('Conversation not found, refreshing conversation state');
        await conversationStore.refresh();
        return this.sendViaAdapter(message, { allowRetry: false });
      }
      throw err;
    }
  }

  async invalidateConversation(imConvId?: string | null): Promise<void> {
    if (this.adapter.invalidateConversation) {
      await Promise.resolve(this.adapter.invalidateConversation(imConvId));
    }
  }

  async handleMessage(message: AdapterMessage): Promise<void> {
    try {
      logger.info('Message received', {
        msg_id: message.msg_id,
        from: message.from,
        to: message.to,
        conv_id: message.conv_id,
        message_type: message.message_type,
        content_length: message.content ? message.content.length : 0,
      });

      const storedMessage: StoredMessage = { ...message };
      await addMessage(message.conv_id, storedMessage);
      messageEventBus.emitMessage(storedMessage);

      const app = getApp<AppInstance>();
      if (typeof app.onMessageReceived === 'function') {
        app.onMessageReceived(message);
      }

      logger.info('Message handled successfully', {
        msg_id: message.msg_id,
        conv_id: message.conv_id,
      });
    } catch (error) {
      const err = normalizeError(error);
      logger.error('Handle message error', {
        msg_id: message.msg_id,
        conv_id: message.conv_id,
        message_type: message.message_type,
        error: err.message,
      });
    }
  }

  handleTyping(typing: AdapterTypingPayload): void {
    try {
      logger.debug('Typing indicator received', { typing });

      const signal = {
        conv_id: typing.conv_id,
        from: typing.from,
        typing: typing.isTyping,
      };

      const app = getApp<AppInstance>();
      if (typeof app.onTypingReceived === 'function') {
        app.onTypingReceived({
          conv_id: typing.conv_id,
          from: typing.from,
          to: '',
          typing: typing.isTyping,
          timestamp: Date.now(),
        });
      }
      messageEventBus.emitTyping(signal);
    } catch (error) {
      const err = normalizeError(error);
      logger.error('Handle typing error', { error: err.message });
    }
  }

  handleError(error: Error): void {
    logger.error('Message service error', { error });

    const app = getApp<AppInstance>();
    if (typeof app.onMessageError === 'function') {
      app.onMessageError(error);
    }
    messageEventBus.emitError(error);
  }

  async disconnect(): Promise<void> {
    try {
      await this.adapter.disconnect();
      this.initialized = false;
      logger.info('Message service disconnected');
    } catch (error) {
      logger.error('Disconnect message service failed', { error });
      throw error;
    }
  }

  isInitialized(): boolean {
    return this.initialized;
  }
}

let messageServiceInstance: MessageService | null = null;

export async function initMessageService(): Promise<MessageService> {
  if (messageServiceInstance) {
    logger.info('Message service already initialized');
    return messageServiceInstance;
  }

  logger.info('Initializing message service');

  const userInfo = await getUserInfo();

  if (!userInfo?.qiao_id) {
    const error = new Error('User info not found or invalid');
    logger.error('Cannot initialize message service', {
      hasUserInfo: Boolean(userInfo),
      hasQiaoId: Boolean(userInfo?.qiao_id),
    });
    throw error;
  }

  logger.info('User info loaded', { qiao_id: userInfo.qiao_id });

  messageServiceInstance = new MessageService();
  await messageServiceInstance.initialize(userInfo.qiao_id);

  logger.info('Message service initialized successfully');

  return messageServiceInstance;
}

export function getMessageService(): MessageService | null {
  return messageServiceInstance;
}

export default messageServiceInstance;
