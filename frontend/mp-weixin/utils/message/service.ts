/**
 * Message Service
 * High-level message service that manages message adapter interactions.
 */

import { getLogger } from '../logger';
import { addMessage, getUserInfo } from '../storage';
import type { StoredMessage } from '../storage';
import { MESSAGE_FAILURE_CATEGORY, MESSAGE_STATUS, MESSAGE_TYPE } from '../constants/message';
import type { MessageType } from '../constants/message';
import conversationStore from './conversation-store';
import type {
  AdapterMessage,
  AdapterSendResult,
  AdapterTypingPayload,
  BusinessMessagePayload,
  ConnectionState,
  MessageAdapter,
  MessageAuthPayload,
} from './adapter-types';
import { getMessageAdapter } from './provider';
import './conversation-presence-store';
import messageEventBus from './event-bus';
import unreadStore from './unread-store';
import { isDefined, isNonEmptyString } from '../guards';
import { ackOfflineMessages, fetchOfflineMessages } from './offline';
import type { OfflineMessage } from '../schemas-core';
import { reportRuntimeObservation } from '../runtime-segment';

const logger = getLogger('MessageService');

type MessageStatus = (typeof MESSAGE_STATUS)[keyof typeof MESSAGE_STATUS];

const RECONNECT_BASE_DELAY = 1000;
const RECONNECT_MAX_DELAY = 30000;
const RECONNECT_BACKOFF = 2;
const RECONNECT_JITTER = 0.2;
const CONFIG_PROBE_INTERVAL_MS = 60000;
const CONFIG_PROBE_JITTER = 0.1;
const SEND_TOTAL_TIMEOUT_MS = 3000;
const SEND_CONNECT_WAIT_TIMEOUT_MS = 900;
const SEND_RETRY_DELAYS_MS = [300, 700] as const;
const RETRYABLE_SEND_ERRORS = new Set<string>([
  'MESSAGE_SERVICE_DISCONNECTED',
  'WS_DISCONNECTED',
  'WS_ACK_TIMEOUT',
  'WS_OPEN_TIMEOUT',
  'WS_CLOSED_BEFORE_OPEN',
  'MESSAGE_CONNECT_TIMEOUT',
  'WS_DOMAIN_NOT_ALLOWED',
]);

const createBusinessMessage = (
  base: MessageData,
  msgId: string,
  status: MessageStatus
): BusinessMessage => ({
  msg_id: msgId,
  msg_id_server: null,
  msg_id_client: msgId,
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

const requireIncomingServerMsgId = (message: AdapterMessage): string => {
  if (!isNonEmptyString(message.msg_id_server)) {
    throw new Error('MESSAGE_MSG_ID_SERVER_REQUIRED');
  }
  return message.msg_id_server;
};

const resolveIncomingClientMsgId = (message: AdapterMessage): string | null =>
  isNonEmptyString(message.msg_id_client) ? message.msg_id_client : null;

const resolveIncomingAdapterMeta = (
  message: AdapterMessage
): { providerMsgId: string | undefined; providerTimestampMs: number | undefined } => ({
  providerMsgId: typeof message.provider_msg_id === 'string' ? message.provider_msg_id : undefined,
  providerTimestampMs:
    typeof message.provider_timestamp_ms === 'number' ? message.provider_timestamp_ms : undefined,
});

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

const getActivePagePath = (): string => {
  const pages = getCurrentPages();
  if (!Array.isArray(pages) || pages.length === 0) {
    return '/app';
  }
  const current = pages[pages.length - 1] as { route?: unknown };
  const route = typeof current.route === 'string' ? current.route.trim() : '';
  if (route === '') {
    return '/app';
  }
  return route.startsWith('/') ? route : `/${route}`;
};

const reportMessageRuntimeObservation = (
  eventName:
    | 'message_connect_failed'
    | 'message_connect_recovered'
    | 'message_send_failed'
    | 'ws_auth_failed'
    | 'ws_ack_timeout',
  payload: Record<string, unknown>
): void => {
  void reportRuntimeObservation({
    eventName,
    pagePath: getActivePagePath(),
    entrySource: 'message_service',
    eventPayload: payload,
  });
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
  private connectedConfigVersion: string | null = null;
  private connectionState: ConnectionState = 'disconnected';
  private connectPromise: Promise<void> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private suspended = false;
  private lastAcked: { sentTime: number; msgId: string } | null = null;
  private offlineSyncPromise: Promise<void> | null = null;
  private offlineSyncReady = false;
  private pendingAck: { message: StoredMessage; sentTime: number; msgId: string } | null = null;
  private lastConnectFailureReportedAtMs = 0;
  private configProbeTimer: ReturnType<typeof setTimeout> | null = null;
  private configProbeAttempt = 0;

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

  private reportConnectFailure(error: Error, phase: string): void {
    const nowMs = Date.now();
    if (nowMs - this.lastConnectFailureReportedAtMs < 2000) {
      return;
    }
    this.lastConnectFailureReportedAtMs = nowMs;
    const errorCode = this.normalizeRuntimeErrorCode(error);
    reportMessageRuntimeObservation('message_connect_failed', {
      error_code: errorCode,
      error_message: error.message,
      phase,
      connection_state: this.connectionState,
      reconnect_attempt: this.reconnectAttempt,
      recovery_mode: this.resolveRecoveryMode(),
      probe_interval_ms: this.connectionState === 'config_error' ? CONFIG_PROBE_INTERVAL_MS : null,
      probe_attempt: this.connectionState === 'config_error' ? this.configProbeAttempt : null,
      occurred_at_ms: nowMs,
    });
    if (errorCode === 'WS_AUTH_FAILED') {
      reportMessageRuntimeObservation('ws_auth_failed', {
        error_code: errorCode,
        error_message: error.message,
        phase,
        connection_state: this.connectionState,
        reconnect_attempt: this.reconnectAttempt,
        occurred_at_ms: nowMs,
      });
    }
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private clearConfigProbeTimer(): void {
    if (this.configProbeTimer !== null) {
      clearTimeout(this.configProbeTimer);
      this.configProbeTimer = null;
    }
  }

  private calculateReconnectDelay(attempt: number): number {
    const exponent = Math.max(attempt - 1, 0);
    const baseDelay = RECONNECT_BASE_DELAY * Math.pow(RECONNECT_BACKOFF, exponent);
    const cappedDelay = Math.min(baseDelay, RECONNECT_MAX_DELAY);
    const jitter = 1 + (Math.random() * 2 - 1) * RECONNECT_JITTER;
    return Math.max(0, Math.round(cappedDelay * jitter));
  }

  private async sleep(delayMs: number): Promise<void> {
    await new Promise<void>((resolve) => {
      setTimeout(resolve, delayMs);
    });
  }

  private isDomainNotAllowedError(error: Error): boolean {
    const normalized = error.message.toLowerCase();
    return (
      normalized.includes('url not in domain list') || normalized.includes('ws_domain_not_allowed')
    );
  }

  private normalizeRuntimeErrorCode(error: Error): string {
    if (this.isDomainNotAllowedError(error)) {
      return 'WS_DOMAIN_NOT_ALLOWED';
    }
    return error.message;
  }

  private resolveRecoveryMode(): string | null {
    if (this.connectionState === 'config_error') {
      return 'low_frequency_probe';
    }
    return null;
  }

  private isRetryableSendError(error: Error): boolean {
    if (error.message === 'WS_DOMAIN_NOT_ALLOWED') {
      return false;
    }
    if (RETRYABLE_SEND_ERRORS.has(error.message)) {
      return true;
    }
    const lower = error.message.toLowerCase();
    return (
      lower.includes('timeout') ||
      lower.includes('network') ||
      lower.includes('socket') ||
      lower.includes('connect')
    );
  }

  private async ensureConnectedForSend(deadlineMs: number): Promise<void> {
    if (this.connectionState === 'config_error') {
      throw new Error('WS_DOMAIN_NOT_ALLOWED');
    }
    if (this.adapter.isConnected()) {
      return;
    }
    const remaining = deadlineMs - Date.now();
    if (remaining <= 0) {
      throw new Error('MESSAGE_CONNECT_TIMEOUT');
    }
    const waitTimeout = Math.min(SEND_CONNECT_WAIT_TIMEOUT_MS, remaining);
    await Promise.race([
      this.ensureConnected(),
      this.sleep(waitTimeout).then(() => {
        throw new Error('MESSAGE_CONNECT_TIMEOUT');
      }),
    ]);
    if (!this.adapter.isConnected()) {
      throw new Error('MESSAGE_SERVICE_DISCONNECTED');
    }
  }

  private scheduleReconnect(): void {
    if (this.suspended || this.reconnectTimer !== null || this.connectionState === 'config_error') {
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

  private calculateConfigProbeDelay(): number {
    const jitter = 1 + (Math.random() * 2 - 1) * CONFIG_PROBE_JITTER;
    return Math.max(5000, Math.round(CONFIG_PROBE_INTERVAL_MS * jitter));
  }

  private scheduleConfigProbe(): void {
    if (this.suspended || this.configProbeTimer !== null) {
      return;
    }
    const delay = this.calculateConfigProbeDelay();
    const attempt = this.configProbeAttempt + 1;
    this.configProbeTimer = setTimeout(() => {
      this.configProbeTimer = null;
      void this.runConfigProbe(attempt);
    }, delay);
    reportMessageRuntimeObservation('message_connect_failed', {
      error_code: 'WS_DOMAIN_NOT_ALLOWED',
      error_message: 'WS_DOMAIN_NOT_ALLOWED',
      phase: 'config_probe_scheduled',
      recovery_mode: 'low_frequency_probe',
      probe_interval_ms: CONFIG_PROBE_INTERVAL_MS,
      probe_delay_ms: delay,
      probe_attempt: attempt,
      connection_state: this.connectionState,
      reconnect_attempt: this.reconnectAttempt,
      occurred_at_ms: Date.now(),
    });
  }

  private async runConfigProbe(attempt: number): Promise<void> {
    if (this.suspended) {
      return;
    }
    this.configProbeAttempt = attempt;
    try {
      await conversationStore.refresh();
      const connectPayload = await conversationStore.getConnectPayload();
      const userId = this.userId;
      if (!isNonEmptyString(userId) || connectPayload.userId !== userId) {
        throw new Error('MESSAGE_SESSION_USER_MISMATCH');
      }
      await this.adapter.connect(userId, connectPayload.auth as MessageAuthPayload, {
        provider: connectPayload.provider,
        server_url: connectPayload.serverUrl,
        config_version: connectPayload.configVersion,
        session_hint: connectPayload.sessionHint,
      });
      this.connectedConfigVersion = connectPayload.configVersion;
      this.setConnectionState('connected');
      this.configProbeAttempt = 0;
      this.clearConfigProbeTimer();
    } catch (error) {
      const err = normalizeError(error);
      logger.warn('Config probe failed', {
        attempt,
        error: err.message,
      });
      reportMessageRuntimeObservation('message_connect_failed', {
        error_code: this.normalizeRuntimeErrorCode(err),
        error_message: err.message,
        phase: 'config_probe_failed',
        recovery_mode: 'low_frequency_probe',
        probe_interval_ms: CONFIG_PROBE_INTERVAL_MS,
        probe_attempt: attempt,
        connection_state: this.connectionState,
        reconnect_attempt: this.reconnectAttempt,
        occurred_at_ms: Date.now(),
      });
      if (this.connectionState === 'config_error') {
        this.scheduleConfigProbe();
      }
    }
  }

  private async enterConfigErrorMode(triggerError: Error): Promise<void> {
    this.clearReconnectTimer();
    this.reconnectAttempt = 0;
    this.connectedConfigVersion = null;
    this.setConnectionState('config_error');
    reportMessageRuntimeObservation('message_connect_failed', {
      error_code: this.normalizeRuntimeErrorCode(triggerError),
      error_message: triggerError.message,
      phase: 'config_error_enter',
      recovery_mode: 'single_refresh_then_probe',
      probe_interval_ms: CONFIG_PROBE_INTERVAL_MS,
      probe_attempt: this.configProbeAttempt,
      connection_state: this.connectionState,
      reconnect_attempt: this.reconnectAttempt,
      occurred_at_ms: Date.now(),
    });

    try {
      await conversationStore.refresh();
      const connectPayload = await conversationStore.getConnectPayload();
      const userId = this.userId;
      if (!isNonEmptyString(userId) || connectPayload.userId !== userId) {
        throw new Error('MESSAGE_SESSION_USER_MISMATCH');
      }
      await this.adapter.connect(userId, connectPayload.auth as MessageAuthPayload, {
        provider: connectPayload.provider,
        server_url: connectPayload.serverUrl,
        config_version: connectPayload.configVersion,
        session_hint: connectPayload.sessionHint,
      });
      this.connectedConfigVersion = connectPayload.configVersion;
      this.setConnectionState('connected');
      return;
    } catch (error) {
      const err = normalizeError(error);
      logger.warn('Config refresh after domain error failed', { error: err.message });
      this.scheduleConfigProbe();
      throw new Error('WS_DOMAIN_NOT_ALLOWED');
    }
  }

  private handleAdapterConnectionState(state: ConnectionState): void {
    if (state === 'connected') {
      const previousState = this.connectionState;
      this.reconnectAttempt = 0;
      this.clearReconnectTimer();
      this.clearConfigProbeTimer();
      this.configProbeAttempt = 0;
      this.setConnectionState('connected');
      if (previousState !== 'connected') {
        reportMessageRuntimeObservation('message_connect_recovered', {
          previous_state: previousState,
          connection_state: 'connected',
          occurred_at_ms: Date.now(),
        });
      }
      void this.startOfflineSync().catch((error) => {
        const err = normalizeError(error);
        logger.warn('Offline message sync failed after reconnect', { error: err.message });
      });
      return;
    }

    if (state === 'disconnected') {
      if (this.connectionState === 'config_error') {
        this.setConnectionState('config_error');
        this.scheduleConfigProbe();
        return;
      }
      const previousState = this.connectionState;
      this.connectedConfigVersion = null;
      this.setConnectionState('disconnected');
      this.offlineSyncReady = false;
      if (previousState !== 'disconnected') {
        reportMessageRuntimeObservation('message_connect_failed', {
          error_code: 'WS_DISCONNECTED',
          error_message: 'WS_DISCONNECTED',
          phase: 'adapter_connection_change',
          previous_state: previousState,
          connection_state: 'disconnected',
          reconnect_attempt: this.reconnectAttempt,
          occurred_at_ms: Date.now(),
        });
      }
      this.scheduleReconnect();
    }
  }

  async ensureConnected(options: { allowConnect?: boolean } = {}): Promise<void> {
    const allowConnect = options.allowConnect !== false;
    if (this.suspended) {
      throw new Error('MESSAGE_SERVICE_SUSPENDED');
    }
    if (this.connectPromise !== null) {
      return this.connectPromise;
    }
    const userId = this.userId;
    if (!isNonEmptyString(userId)) {
      throw new Error('User info not found or invalid');
    }
    let connectPayload: {
      userId: string;
      provider: string;
      serverUrl: string;
      sessionHint: string;
      auth: {
        wsTicket: string;
        issuedAtMs: number;
        deviceId: string;
      };
      configVersion: string;
    };
    try {
      connectPayload = await conversationStore.getConnectPayload();
    } catch (error) {
      const err = normalizeError(error);
      this.connectedConfigVersion = null;
      this.setConnectionState('disconnected');
      this.reportConnectFailure(err, 'load_connect_payload');
      this.scheduleReconnect();
      throw err;
    }
    if (connectPayload.userId !== userId) {
      throw new Error('MESSAGE_SESSION_USER_MISMATCH');
    }
    if (this.adapter.isConnected()) {
      if (this.connectedConfigVersion === connectPayload.configVersion) {
        this.setConnectionState('connected');
        return;
      }
      logger.warn('Message session version changed, reconnecting adapter', {
        old_config_version: this.connectedConfigVersion,
        new_config_version: connectPayload.configVersion,
      });
      await this.adapter.disconnect();
      this.setConnectionState('disconnected');
    }
    if (!allowConnect) {
      throw new Error('MESSAGE_SERVICE_DISCONNECTED');
    }

    this.setConnectionState('connecting');
    this.connectPromise = (async () => {
      await this.adapter.connect(userId, connectPayload.auth as MessageAuthPayload, {
        provider: connectPayload.provider,
        server_url: connectPayload.serverUrl,
        config_version: connectPayload.configVersion,
        session_hint: connectPayload.sessionHint,
      });
      this.connectedConfigVersion = connectPayload.configVersion;
      this.reconnectAttempt = 0;
      this.clearReconnectTimer();
      this.clearConfigProbeTimer();
      this.configProbeAttempt = 0;
      this.setConnectionState('connected');
    })()
      .catch(async (error) => {
        const err = normalizeError(error);
        if (this.isDomainNotAllowedError(err)) {
          await this.enterConfigErrorMode(err);
          return;
        }
        this.connectedConfigVersion = null;
        this.setConnectionState('disconnected');
        this.reportConnectFailure(err, 'ensure_connected');
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
    this.clearConfigProbeTimer();
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
    this.clearConfigProbeTimer();
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
        if (err.message === 'WS_DOMAIN_NOT_ALLOWED') {
          logger.warn('Message service enters config error mode on init');
        }
        logger.warn('Message service connect failed on init', { error: err.message });
        if (err.message !== 'WS_DOMAIN_NOT_ALLOWED') {
          this.setConnectionState('disconnected');
          this.reportConnectFailure(err, 'initialize');
          this.scheduleReconnect();
        }
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
      const sentMessage = await this.sendWithRetry(messageData, message, msgId);
      const sentPayload: BusinessMessage = {
        ...message,
        status: MESSAGE_STATUS.SENT,
        adapter_metadata: {
          provider_msg_id: sentMessage.provider_msg_id,
          provider_timestamp_ms: sentMessage.provider_timestamp_ms,
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
      await this.handleSendFailure({
        err,
        message,
        msgId,
        convId: messageData.conv_id,
      });
      throw err;
    }
  }

  private async sendWithRetry(
    messageData: MessageData,
    message: BusinessMessage,
    msgId: string
  ): Promise<AdapterSendResult> {
    const deadlineMs = Date.now() + SEND_TOTAL_TIMEOUT_MS;
    const trySend = async (attempt: number): Promise<AdapterSendResult> => {
      try {
        await this.ensureConnectedForSend(deadlineMs);
        return await this.sendViaAdapter(message);
      } catch (error) {
        const err = normalizeError(error);
        const retryDelay =
          attempt < SEND_RETRY_DELAYS_MS.length ? SEND_RETRY_DELAYS_MS[attempt] : null;
        const shouldRetry =
          retryDelay !== null &&
          this.isRetryableSendError(err) &&
          Date.now() + retryDelay < deadlineMs;
        logger.warn('Send message attempt failed', {
          msg_id: msgId,
          conv_id: messageData.conv_id,
          attempt: attempt + 1,
          retry_delay_ms: retryDelay,
          should_retry: shouldRetry,
          error: err.message,
        });
        if (!shouldRetry) {
          throw err;
        }
        await this.sleep(retryDelay);
        return await trySend(attempt + 1);
      }
    };
    return await trySend(0);
  }

  private async handleSendFailure(options: {
    err: Error;
    message: BusinessMessage;
    msgId: string;
    convId: string;
  }): Promise<void> {
    const { err, message, msgId, convId } = options;
    if (err.message === 'WS_ACK_TIMEOUT') {
      reportMessageRuntimeObservation('ws_ack_timeout', {
        error_code: err.message,
        error_message: err.message,
        connection_state: this.connectionState,
        occurred_at_ms: Date.now(),
      });
    }

    const failedPayload: BusinessMessage = {
      ...message,
      status: MESSAGE_STATUS.FAILED,
      failure_category: MESSAGE_FAILURE_CATEGORY.TRANSPORT_FAILED,
      error_reason: err.message,
      failure_reason: err.message,
      retryable: true,
    };
    await this.persistMessage(convId, failedPayload);
    messageEventBus.emitMessage(failedPayload);

    logger.error('Send message via adapter failed', {
      msg_id: msgId,
      conv_id: convId,
      message_type: message.message_type,
      error: err.message,
    });
    reportMessageRuntimeObservation('message_send_failed', {
      error_code: this.normalizeRuntimeErrorCode(err),
      error_message: err.message,
      connection_state: this.connectionState,
      recovery_mode: this.resolveRecoveryMode(),
      probe_interval_ms: this.connectionState === 'config_error' ? CONFIG_PROBE_INTERVAL_MS : null,
      probe_attempt: this.connectionState === 'config_error' ? this.configProbeAttempt : null,
      conv_id: convId,
      msg_id: msgId,
      message_type: message.message_type,
      occurred_at_ms: Date.now(),
    });
  }

  private async sendViaAdapter(
    message: BusinessMessage,
    options: { allowRetry?: boolean } = { allowRetry: true }
  ): Promise<AdapterSendResult> {
    const allowRetry = options.allowRetry !== false;
    const sessionHint = await conversationStore.getSessionHint();

    try {
      return await this.adapter.sendMessage(message, sessionHint);
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

  async invalidateConversation(sessionHint?: string | null): Promise<void> {
    if (typeof this.adapter.invalidateConversation === 'function') {
      await Promise.resolve(this.adapter.invalidateConversation(sessionHint));
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
    const normalizedMsgIdServer = requireIncomingServerMsgId(message);
    const normalizedMsgIdClient = resolveIncomingClientMsgId(message);
    const { providerMsgId, providerTimestampMs } = resolveIncomingAdapterMeta(message);

    const storedMessage: StoredMessage = {
      ...message,
      msg_id: normalizedMsgIdServer,
      msg_id_server: normalizedMsgIdServer,
      msg_id_client: normalizedMsgIdClient,
      from_qiao_id: normalizedFrom,
      to_qiao_id: normalizedTo,
      conv_id: normalizedConvId,
      content: normalizedContent,
    };

    const appPayload: Ailo.MessagePayload = {
      msg_id: storedMessage.msg_id,
      msg_id_server: normalizedMsgIdServer,
      msg_id_client: normalizedMsgIdClient,
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
      provider_msg_id: providerMsgId,
      provider_timestamp_ms: providerTimestampMs,
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
    const metadata = message.metadata ?? {};
    const storedMessage: StoredMessage = {
      msg_id: message.msg_id_server,
      msg_id_server: message.msg_id_server,
      msg_id_client: message.msg_id_client ?? null,
      from_qiao_id: message.from_qiao_id,
      to_qiao_id: message.to_qiao_id,
      conv_id: message.conversation_id,
      content: normalizedContent,
      message_type: message.message_type,
      supports_typing: true,
      sent_time: message.sent_time_ms,
      status: MESSAGE_STATUS.RECEIVED,
      action: metadata.action ?? null,
      notification_type: metadata.notification_type ?? null,
      data: null,
    };

    const appPayload: Ailo.MessagePayload = {
      msg_id: storedMessage.msg_id,
      msg_id_server: storedMessage.msg_id_server ?? null,
      msg_id_client: storedMessage.msg_id_client ?? null,
      from_qiao_id: message.from_qiao_id,
      to_qiao_id: message.to_qiao_id,
      conv_id: message.conversation_id,
      content: normalizedContent,
      message_type: message.message_type,
      supports_typing: true,
      sent_time: message.sent_time_ms,
      status: storedMessage.status,
      action: storedMessage.action ?? null,
      notification_type: storedMessage.notification_type ?? null,
      data: storedMessage.data ?? null,
    };

    return {
      storedMessage,
      appPayload,
      contentLength: normalizedContent.length,
      convId: message.conversation_id,
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

  private updatePendingAck(message: StoredMessage, sentTime: number, msgIdServer: string): void {
    const candidate = { sentTime, msgId: msgIdServer };
    const pending = this.pendingAck;
    if (
      pending === null ||
      this.isAckAhead(candidate, { sentTime: pending.sentTime, msgId: pending.msgId })
    ) {
      this.pendingAck = { message, sentTime, msgId: msgIdServer };
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
    if (!isNonEmptyString(message.msg_id_server)) {
      return;
    }
    if (typeof message.sent_time !== 'number') {
      return;
    }
    const msgIdServer = message.msg_id_server;
    const sentTime = message.sent_time;
    if (!options.force && !this.offlineSyncReady) {
      if (this.shouldAck(sentTime, msgIdServer)) {
        this.updatePendingAck(message, sentTime, msgIdServer);
      }
      return;
    }
    if (!this.shouldAck(sentTime, msgIdServer)) {
      return;
    }

    try {
      await ackOfflineMessages({
        last_ack_msg_id: msgIdServer,
      });
      this.lastAcked = { sentTime, msgId: msgIdServer };
    } catch (error) {
      const err = normalizeError(error);
      logger.warn('Offline ACK failed', {
        msg_id_server: msgIdServer,
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
        msg_id_server: lastMessage.msg_id_server,
        conv_id: lastMessage.conversation_id,
        to_qiao_id: lastMessage.to_qiao_id,
        sent_time: lastMessage.sent_time_ms,
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
        to_qiao_id: typing.to_qiao_id,
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
    const err = normalizeError(error);
    if (this.isDomainNotAllowedError(err)) {
      void this.enterConfigErrorMode(err).catch((modeErr) => {
        logger.warn('Enter config error mode failed', {
          error: normalizeError(modeErr).message,
        });
      });
    }
    logger.error('Message service error', { error: err.message });
    if (err.message === 'WS_ACK_TIMEOUT') {
      reportMessageRuntimeObservation('ws_ack_timeout', {
        error_code: err.message,
        error_message: err.message,
        connection_state: this.connectionState,
        occurred_at_ms: Date.now(),
      });
    }
    this.reportConnectFailure(err, 'adapter_error');

    const app = getApp<AppInstance>();
    if (typeof app.onMessageError === 'function') {
      app.onMessageError(err);
    }
    messageEventBus.emitError(err);
  }

  async disconnect(): Promise<void> {
    try {
      this.suspended = true;
      this.userId = null;
      this.reconnectAttempt = 0;
      this.clearReconnectTimer();
      this.clearConfigProbeTimer();
      this.configProbeAttempt = 0;
      this.connectPromise = null;
      this.connectedConfigVersion = null;
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
