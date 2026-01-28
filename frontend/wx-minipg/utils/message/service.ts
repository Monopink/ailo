/**
 * Message Service
 * High-level message service that manages message adapter interactions.
 */

import { getMessageClientSignature } from '../message-signature';
import { getLogger } from '../logger';
import { addMessage, getUserInfo } from '../storage';
import type { StoredMessage } from '../storage';
import { MESSAGE_STATUS, MESSAGE_TYPE } from '../constants/message';
import type { MessageType } from '../constants/message';
import conversationStore from './conversation-store';
import type {
  AdapterMessage,
  AdapterSendResult,
  AdapterTypingPayload,
  BusinessMessagePayload,
  ConnectionState,
  MessageAdapter,
  MessageSignature,
} from './adapter-types';
import { getMessageAdapter } from './provider';
import messageEventBus from './event-bus';
import unreadStore from './unread-store';
import { isDefined, isNonEmptyString } from '../guards';
import { ackOfflineMessages, fetchOfflineMessages } from './offline';
import type { OfflineMessage } from '../schemas';

const logger = getLogger('MessageService');

type MessageStatus = (typeof MESSAGE_STATUS)[keyof typeof MESSAGE_STATUS];

const RECONNECT_BASE_DELAY = 1000;
const RECONNECT_MAX_DELAY = 30000;
const RECONNECT_BACKOFF = 2;
const RECONNECT_JITTER = 0.2;

const createBusinessMessage = (
  base: MessageData,
  msgId: string,
  status: MessageStatus
): BusinessMessage => ({
  msg_id: msgId,
  from_qiao_id: base.from_qiao_id,
  to_qiao_id: base.to_qiao_id,
  conv_id: base.conv_id,
  content: base.content,
  message_type: base.message_type ?? MESSAGE_TYPE.TEXT,
  supports_typing: base.supports_typing ?? true,
  sent_time: Date.now(),
  status,
});

interface MessageData {
  from_qiao_id: string;
  to_qiao_id: string;
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
  private userId: string | null = null;
  private connectionState: ConnectionState = 'disconnected';
  private connectPromise: Promise<void> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private suspended = false;
  private lastAcked: { sentTime: number; msgId: string } | null = null;
  private offlineSyncPromise: Promise<void> | null = null;
  private offlineSyncReady = false;
  private pendingAck: { message: StoredMessage; sentTime: number; msgId: string } | null = null;

  constructor(adapter: MessageAdapter = getMessageAdapter()) {
    this.adapter = adapter;
    this.adapter.onConnectionChange((state) => {
      this.handleAdapterConnectionState(state);
    });
    if (this.adapter.isConnected()) {
      this.setConnectionState('connected');
    }
  }

  private async persistMessage(convId: string, message: StoredMessage): Promise<void> {
    await addMessage(convId, message);
  }

  private setConnectionState(nextState: ConnectionState): void {
    if (this.connectionState === nextState) {
      return;
    }
    this.connectionState = nextState;
    messageEventBus.emitConnection(nextState);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private calculateReconnectDelay(attempt: number): number {
    const exponent = Math.max(attempt - 1, 0);
    const baseDelay = RECONNECT_BASE_DELAY * Math.pow(RECONNECT_BACKOFF, exponent);
    const cappedDelay = Math.min(baseDelay, RECONNECT_MAX_DELAY);
    const jitter = 1 + (Math.random() * 2 - 1) * RECONNECT_JITTER;
    return Math.max(0, Math.round(cappedDelay * jitter));
  }

  private scheduleReconnect(): void {
    if (this.suspended || this.reconnectTimer !== null) {
      return;
    }
    this.reconnectAttempt += 1;
    const delay = this.calculateReconnectDelay(this.reconnectAttempt);
    logger.warn('Scheduling reconnect attempt', { attempt: this.reconnectAttempt, delay });
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      void this.ensureConnected().catch((error) => {
        const err = normalizeError(error);
        logger.warn('Reconnect attempt failed', {
          attempt: this.reconnectAttempt,
          error: err.message,
        });
      });
    }, delay);
  }

  private handleAdapterConnectionState(state: ConnectionState): void {
    if (state === 'connected') {
      this.reconnectAttempt = 0;
      this.clearReconnectTimer();
      this.setConnectionState('connected');
      void this.startOfflineSync().catch((error) => {
        const err = normalizeError(error);
        logger.warn('Offline message sync failed after reconnect', { error: err.message });
      });
      return;
    }

    if (state === 'disconnected') {
      this.setConnectionState('disconnected');
      this.offlineSyncReady = false;
      this.scheduleReconnect();
    }
  }

  async ensureConnected(options: { allowConnect?: boolean } = {}): Promise<void> {
    const allowConnect = options.allowConnect !== false;
    if (this.suspended) {
      throw new Error('MESSAGE_SERVICE_SUSPENDED');
    }
    if (this.adapter.isConnected()) {
      this.setConnectionState('connected');
      return;
    }
    if (!allowConnect) {
      throw new Error('MESSAGE_SERVICE_DISCONNECTED');
    }
    if (this.connectPromise !== null) {
      return this.connectPromise;
    }
    const userId = this.userId;
    if (!isNonEmptyString(userId)) {
      throw new Error('User info not found or invalid');
    }

    this.setConnectionState('connecting');
    this.connectPromise = (async () => {
      const signature = await getMessageClientSignature(userId);
      await this.adapter.connect(userId, signature as MessageSignature);
      this.reconnectAttempt = 0;
      this.clearReconnectTimer();
      this.setConnectionState('connected');
    })()
      .catch((error) => {
        const err = normalizeError(error);
        this.setConnectionState('disconnected');
        this.scheduleReconnect();
        throw err;
      })
      .finally(() => {
        this.connectPromise = null;
      });

    return this.connectPromise;
  }

  async resume(): Promise<void> {
    this.suspended = false;
    this.clearReconnectTimer();
    if (this.connectionState === 'suspending') {
      this.setConnectionState('disconnected');
    }
    await this.ensureConnected();
    try {
      await this.startOfflineSync();
    } catch (error) {
      const err = normalizeError(error);
      logger.warn('Offline message sync failed on resume', { error: err.message });
    }
  }

  suspend(): void {
    this.suspended = true;
    this.clearReconnectTimer();
    this.setConnectionState('suspending');
  }

  getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  async initialize(userId: string): Promise<void> {
    if (this.initialized) {
      logger.warn('Message service already initialized');
      return;
    }

    try {
      logger.info('Initializing message service', { userId });

      this.adapter.onMessage((message) => {
        void this.handleMessage(message);
      });
      this.adapter.onTyping(this.handleTyping.bind(this));
      this.adapter.onError(this.handleError.bind(this));

      this.userId = userId;
      try {
        await this.ensureConnected();
      } catch (error) {
        const err = normalizeError(error);
        logger.warn('Message service connect failed on init', { error: err.message });
      }
      try {
        await this.startOfflineSync();
      } catch (error) {
        const err = normalizeError(error);
        logger.warn('Offline message sync failed', { error: err.message });
      }

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

    const contentLength = typeof messageData.content === 'string' ? messageData.content.length : 0;
    logger.info('Sending message', {
      conv_id: messageData.conv_id,
      message_type: messageData.message_type,
      content_length: contentLength,
      from_qiao_id: messageData.from_qiao_id,
      to_qiao_id: messageData.to_qiao_id,
      client_msg_id: messageData.client_msg_id,
    });

    const msgId = isNonEmptyString(messageData.client_msg_id)
      ? messageData.client_msg_id
      : generateClientMessageId();

    const message = createBusinessMessage(messageData, msgId, MESSAGE_STATUS.SENDING);

    await this.persistMessage(messageData.conv_id, message);

    try {
      if (!this.adapter.isConnected()) {
        throw new Error('MESSAGE_SERVICE_DISCONNECTED');
      }
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
    if (typeof this.adapter.invalidateConversation === 'function') {
      await Promise.resolve(this.adapter.invalidateConversation(imConvId));
    }
  }

  private buildIncomingPayload(message: AdapterMessage): {
    storedMessage: StoredMessage;
    appPayload: Ailo.MessagePayload;
    contentLength: number;
    convId: string;
  } {
    const normalizedContent = typeof message.content === 'string' ? message.content : '';
    const normalizedFrom = typeof message.from_qiao_id === 'string' ? message.from_qiao_id : '';
    const normalizedTo = typeof message.to_qiao_id === 'string' ? message.to_qiao_id : '';
    const normalizedConvId = typeof message.conv_id === 'string' ? message.conv_id : '';

    const lcMsgId =
      'lc_msg_id' in message && typeof message.lc_msg_id === 'string'
        ? message.lc_msg_id
        : undefined;
    const lcTimestamp =
      'lc_timestamp' in message && typeof message.lc_timestamp === 'number'
        ? message.lc_timestamp
        : undefined;

    const storedMessage: StoredMessage = {
      ...message,
      from_qiao_id: normalizedFrom,
      to_qiao_id: normalizedTo,
      conv_id: normalizedConvId,
      content: normalizedContent,
    };

    const appPayload: Ailo.MessagePayload = {
      msg_id: storedMessage.msg_id,
      from_qiao_id: normalizedFrom,
      to_qiao_id: normalizedTo,
      conv_id: normalizedConvId,
      content: normalizedContent,
      message_type: storedMessage.message_type ?? MESSAGE_TYPE.TEXT,
      supports_typing: storedMessage.supports_typing ?? true,
      sent_time: typeof storedMessage.sent_time === 'number' ? storedMessage.sent_time : Date.now(),
      status: storedMessage.status,
      action: storedMessage.action ?? null,
      notification_type: storedMessage.notification_type ?? null,
      data: storedMessage.data ?? null,
      lc_msg_id: lcMsgId,
      lc_timestamp: lcTimestamp,
    };

    return {
      storedMessage,
      appPayload,
      contentLength: normalizedContent.length,
      convId: normalizedConvId,
    };
  }

  private buildOfflinePayload(message: OfflineMessage): {
    storedMessage: StoredMessage;
    appPayload: Ailo.MessagePayload;
    contentLength: number;
    convId: string;
  } {
    const normalizedContent = typeof message.content === 'string' ? message.content : '';
    const storedMessage: StoredMessage = {
      msg_id: message.msg_id_server,
      from_qiao_id: message.from_qiao_id,
      to_qiao_id: message.to_qiao_id,
      conv_id: message.conv_id,
      content: normalizedContent,
      message_type: message.message_type,
      supports_typing: true,
      sent_time: message.sent_time,
      status: MESSAGE_STATUS.RECEIVED,
      action: message.action ?? null,
      notification_type: message.notification_type ?? null,
      data: message.data ?? null,
    };

    const appPayload: Ailo.MessagePayload = {
      msg_id: storedMessage.msg_id,
      from_qiao_id: message.from_qiao_id,
      to_qiao_id: message.to_qiao_id,
      conv_id: message.conv_id,
      content: normalizedContent,
      message_type: message.message_type,
      supports_typing: true,
      sent_time: message.sent_time,
      status: storedMessage.status,
      action: storedMessage.action ?? null,
      notification_type: storedMessage.notification_type ?? null,
      data: storedMessage.data ?? null,
    };

    return {
      storedMessage,
      appPayload,
      contentLength: normalizedContent.length,
      convId: message.conv_id,
    };
  }

  private shouldAck(sentTime: number, msgId: string): boolean {
    if (this.lastAcked === null) {
      return true;
    }
    if (sentTime > this.lastAcked.sentTime) {
      return true;
    }
    return sentTime === this.lastAcked.sentTime && msgId > this.lastAcked.msgId;
  }

  private isAckAhead(
    candidate: { sentTime: number; msgId: string },
    base: { sentTime: number; msgId: string } | null
  ): boolean {
    if (base === null) {
      return true;
    }
    if (candidate.sentTime > base.sentTime) {
      return true;
    }
    return candidate.sentTime === base.sentTime && candidate.msgId > base.msgId;
  }

  private updatePendingAck(message: StoredMessage, sentTime: number): void {
    const candidate = { sentTime, msgId: message.msg_id };
    const pending = this.pendingAck;
    if (
      pending === null ||
      this.isAckAhead(candidate, { sentTime: pending.sentTime, msgId: pending.msgId })
    ) {
      this.pendingAck = { message, sentTime, msgId: message.msg_id };
    }
  }

  private async flushPendingAck(): Promise<void> {
    if (this.pendingAck === null) {
      return;
    }
    const pending = this.pendingAck;
    this.pendingAck = null;
    await this.ackIfNeeded(pending.message, { force: true });
  }

  private async startOfflineSync(): Promise<void> {
    if (this.suspended) {
      return;
    }
    if (!isNonEmptyString(this.userId)) {
      return;
    }
    if (this.offlineSyncPromise !== null) {
      return this.offlineSyncPromise;
    }
    this.offlineSyncReady = false;
    this.offlineSyncPromise = (async () => {
      await this.syncOfflineMessages();
      this.offlineSyncReady = true;
      await this.flushPendingAck();
    })().finally(() => {
      this.offlineSyncPromise = null;
    });
    return this.offlineSyncPromise;
  }

  private async ackIfNeeded(
    message: StoredMessage,
    options: { force?: boolean } = {}
  ): Promise<void> {
    if (!isNonEmptyString(this.userId)) {
      return;
    }
    if (message.to_qiao_id !== this.userId) {
      return;
    }
    if (!isNonEmptyString(message.msg_id)) {
      return;
    }
    if (typeof message.sent_time !== 'number') {
      return;
    }
    const sentTime = message.sent_time;
    if (!options.force && !this.offlineSyncReady) {
      if (this.shouldAck(sentTime, message.msg_id)) {
        this.updatePendingAck(message, sentTime);
      }
      return;
    }
    if (!this.shouldAck(sentTime, message.msg_id)) {
      return;
    }

    try {
      await ackOfflineMessages({
        last_ack_msg_id: message.msg_id,
        last_ack_sent_at: sentTime,
      });
      this.lastAcked = { sentTime, msgId: message.msg_id };
    } catch (error) {
      const err = normalizeError(error);
      logger.warn('Offline ACK failed', {
        msg_id: message.msg_id,
        conv_id: message.conv_id,
        error: err.message,
      });
    }
  }

  private async syncOfflineMessages(): Promise<void> {
    const maxPages = 20;
    const processPage = async (cursor: string | null | undefined, page: number): Promise<void> => {
      if (page >= maxPages) {
        logger.warn('Offline message sync reached max pages', { maxPages });
        return;
      }

      const response = await fetchOfflineMessages({ cursor, limit: 100 });
      if (response.messages.length === 0) {
        return;
      }

      let chain = Promise.resolve();
      for (const message of response.messages) {
        chain = chain.then(async () => {
          const { storedMessage, appPayload, contentLength, convId } =
            this.buildOfflinePayload(message);

          logger.info('Offline message received', {
            msg_id: storedMessage.msg_id,
            conv_id: convId,
            message_type: storedMessage.message_type,
            content_length: contentLength,
          });

          await addMessage(convId, storedMessage);
          await unreadStore.handleIncomingMessage(storedMessage, this.userId);
          messageEventBus.emitMessage(storedMessage);

          const app = getApp<AppInstance>();
          if (typeof app.onMessageReceived === 'function') {
            app.onMessageReceived(appPayload);
          }
        });
      }
      await chain;

      const lastMessage = response.messages[response.messages.length - 1];
      const ackPayload: StoredMessage = {
        msg_id: lastMessage.msg_id_server,
        conv_id: lastMessage.conv_id,
        to_qiao_id: lastMessage.to_qiao_id,
        sent_time: lastMessage.sent_time,
      };
      await this.ackIfNeeded(ackPayload, { force: true });

      if (response.has_more) {
        await processPage(response.next_cursor ?? null, page + 1);
      }
    };

    await processPage(null, 0);
  }

  async handleMessage(message: AdapterMessage): Promise<void> {
    try {
      const { storedMessage, appPayload, contentLength, convId } =
        this.buildIncomingPayload(message);

      logger.info('Message received', {
        msg_id: message.msg_id,
        from_qiao_id: storedMessage.from_qiao_id,
        to_qiao_id: storedMessage.to_qiao_id,
        conv_id: storedMessage.conv_id,
        message_type: message.message_type,
        content_length: contentLength,
      });

      await addMessage(convId, storedMessage);
      await unreadStore.handleIncomingMessage(storedMessage, this.userId);
      messageEventBus.emitMessage(storedMessage);
      await this.ackIfNeeded(storedMessage);

      const app = getApp<AppInstance>();
      if (typeof app.onMessageReceived === 'function') {
        app.onMessageReceived(appPayload);
      }

      logger.info('Message handled successfully', {
        msg_id: message.msg_id,
        conv_id: convId,
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
        from_qiao_id: typing.from_qiao_id,
        typing: typing.isTyping,
        sent_time: typing.sent_time,
        received_time: Date.now(),
      };

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
      this.suspended = true;
      this.userId = null;
      this.reconnectAttempt = 0;
      this.clearReconnectTimer();
      this.connectPromise = null;
      await this.adapter.disconnect();
      this.initialized = false;
      this.setConnectionState('disconnected');
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
let messageServiceInitPromise: Promise<MessageService> | null = null;

export async function initMessageService(): Promise<MessageService> {
  if (isDefined(messageServiceInstance)) {
    logger.info('Message service already initialized');
    return messageServiceInstance;
  }

  if (messageServiceInitPromise !== null) {
    return messageServiceInitPromise;
  }

  messageServiceInitPromise = (async () => {
    logger.info('Initializing message service');

    const userInfo = await getUserInfo();

    if (!isNonEmptyString(userInfo?.qiao_id)) {
      const error = new Error('User info not found or invalid');
      logger.error('Cannot initialize message service', {
        hasUserInfo: isDefined(userInfo),
        hasQiaoId: isNonEmptyString(userInfo?.qiao_id),
      });
      throw error;
    }

    logger.info('User info loaded', { qiao_id: userInfo.qiao_id });

    const service = new MessageService();
    await service.initialize(userInfo.qiao_id);

    messageServiceInstance = service;
    logger.info('Message service initialized successfully');
    return service;
  })().finally(() => {
    messageServiceInitPromise = null;
  });

  return messageServiceInitPromise;
}

export function getMessageService(): MessageService | null {
  return messageServiceInstance;
}

export default messageServiceInstance;
