import { getLogger } from '../logger';
import { MESSAGE_STATUS, MESSAGE_TYPE } from '../constants/message';
import { isNonEmptyString } from '../guards';
import type { MessageType } from '../constants/message';
import type {
  AdapterMessage,
  AdapterSendResult,
  AdapterTypingPayload,
  BusinessMessagePayload,
  ConnectionState,
  MessageConnectConfig,
  MessageAdapter,
  MessageAuthPayload,
} from './adapter-types';

type MessageCallback = (payload: AdapterMessage) => void;
type TypingCallback = (payload: AdapterTypingPayload) => void;
type ErrorCallback = (error: Error) => void;
type PendingAck = {
  resolve: (payload: Record<string, unknown>) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
};

const logger = getLogger('WSAdapter');
const SOCKET_OPEN_TIMEOUT_MS = 8000;
const AUTH_ACK_TIMEOUT_MS = 5000;
const SEND_MESSAGE_ACK_TIMEOUT_MS = 600;
const TYPING_ACK_TIMEOUT_MS = 500;
const PING_ACK_TIMEOUT_MS = 3000;
const PING_INTERVAL_MS = 25000;
const LOCALHOST_BASE_URL_PATTERN =
  /^(?:https?:\/\/|wss?:\/\/)?(?:localhost|127\.0\.0\.1|\[::1\]|::1)(?::\d+)?(?:\/|$)/i;

const isDevtoolsRuntime = (): boolean => {
  try {
    if (typeof wx.getSystemInfoSync !== 'function') {
      return false;
    }
    const info = wx.getSystemInfoSync();
    return info.platform === 'devtools';
  } catch {
    return false;
  }
};

const isLoopbackBaseUrl = (baseUrl: string): boolean =>
  LOCALHOST_BASE_URL_PATTERN.test(baseUrl.trim());

const toError = (error: unknown): Error => {
  if (error instanceof Error) {
    return error;
  }
  if (typeof error === 'object' && error !== null) {
    const record = error as Record<string, unknown>;
    if (typeof record.errMsg === 'string' && record.errMsg !== '') {
      return new Error(record.errMsg);
    }
    if (typeof record.message === 'string' && record.message !== '') {
      return new Error(record.message);
    }
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

const toWsUrl = (baseUrl: string): string => {
  const normalized = baseUrl.trim().replace(/\/+$/, '');
  if (normalized.startsWith('https://')) {
    return `wss://${normalized.slice('https://'.length)}/ws/messages`;
  }
  if (normalized.startsWith('http://')) {
    return `ws://${normalized.slice('http://'.length)}/ws/messages`;
  }
  if (normalized.startsWith('wss://') || normalized.startsWith('ws://')) {
    return `${normalized}/ws/messages`;
  }
  throw new Error('WS_BASE_URL_INVALID');
};

const randomFrameId = (prefix: string): string =>
  `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;

const asRecord = (value: unknown): Record<string, unknown> | null =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null;

const isMessageTypeValue = (value: unknown): value is MessageType =>
  typeof value === 'number' && Object.values(MESSAGE_TYPE).includes(value as MessageType);

const readString = (value: unknown): string => (typeof value === 'string' ? value : '');

const readOptionalClientMsgId = (value: unknown): string | null =>
  typeof value === 'string' && value !== '' ? value : null;

const readSentTimeMs = (value: unknown): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : Date.now();

const readMessageType = (value: unknown): MessageType =>
  isMessageTypeValue(value) ? value : MESSAGE_TYPE.TEXT;

const readActionPayload = (
  metadata: Record<string, unknown> | null
): Record<string, unknown> | null => {
  if (metadata === null) {
    return null;
  }
  const action = metadata.action;
  if (typeof action !== 'object' || action === null) {
    return null;
  }
  return action as Record<string, unknown>;
};

const readNotificationType = (metadata: Record<string, unknown> | null): number | string | null => {
  if (metadata === null) {
    return null;
  }
  const notificationType = metadata.notification_type;
  if (typeof notificationType === 'number' || typeof notificationType === 'string') {
    return notificationType;
  }
  return null;
};

export class WSAdapter implements MessageAdapter {
  private socketTask: WechatMiniprogram.SocketTask | null = null;
  private connected = false;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private messageCallbacks: MessageCallback[] = [];
  private typingCallbacks: TypingCallback[] = [];
  private errorCallbacks: ErrorCallback[] = [];
  private connectionCallbacks: Array<(state: ConnectionState) => void> = [];
  private pendingAcks = new Map<string, PendingAck>();
  private currentSocketVersion = 0;
  private resettingSocket = false;

  async connect(
    userId: string,
    auth: MessageAuthPayload,
    config: MessageConnectConfig
  ): Promise<void> {
    await this.disposeSocket({ emitDisconnected: false });
    this.triggerConnectionCallbacks('connecting');

    if (isLoopbackBaseUrl(config.server_url) && isDevtoolsRuntime()) {
      logger.warn('Using localhost websocket base URL in devtools runtime', {
        server_url: config.server_url,
      });
    }

    if (isLoopbackBaseUrl(config.server_url) && !isDevtoolsRuntime()) {
      throw new Error('WS_BASE_URL_LOCALHOST_UNSUPPORTED_ON_DEVICE');
    }

    const wsUrl = toWsUrl(config.server_url);
    const socketVersion = this.currentSocketVersion + 1;
    this.currentSocketVersion = socketVersion;

    const socketTask = wx.connectSocket({
      url: wsUrl,
    });
    this.socketTask = socketTask;
    this.bindSocketHandlers(socketTask, socketVersion);

    await this.waitForOpen(socketTask, socketVersion);

    const authPayload = await this.sendFrameWithAck(
      {
        type: 'auth',
        ws_frame_id: randomFrameId('auth'),
        payload: {
          ws_ticket: auth.wsTicket,
          device_id: auth.deviceId,
        },
      },
      socketVersion,
      AUTH_ACK_TIMEOUT_MS
    );

    if (authPayload.ok !== true) {
      throw new Error('WS_AUTH_FAILED');
    }

    if (!isNonEmptyString(userId)) {
      throw new Error('MESSAGE_USER_ID_REQUIRED');
    }

    this.connected = true;
    this.triggerConnectionCallbacks('connected');
    this.startPingLoop(socketVersion);

    logger.info('WebSocket connected', {
      userId,
      wsUrl,
      configVersion: config.config_version,
    });
  }

  async disconnect(): Promise<void> {
    await this.disposeSocket({ emitDisconnected: true });
  }

  private async disposeSocket(options: { emitDisconnected: boolean }): Promise<void> {
    const emitDisconnected = options.emitDisconnected;
    this.connected = false;
    this.stopPingLoop();
    this.rejectAllPendingAcks(new Error('WS_DISCONNECTED'));

    const socket = this.socketTask;
    this.socketTask = null;
    if (socket !== null) {
      try {
        await new Promise<void>((resolve) => {
          socket.close({
            complete: () => resolve(),
          });
        });
      } catch (error) {
        const err = toError(error);
        logger.warn('WebSocket close failed', { error: err.message });
      }
    }

    if (emitDisconnected) {
      this.triggerConnectionCallbacks('disconnected');
    }
  }

  private forceResetConnection(error: Error): void {
    if (this.resettingSocket) {
      return;
    }
    this.resettingSocket = true;
    this.triggerErrorCallbacks(error);
    void this.disposeSocket({ emitDisconnected: true }).finally(() => {
      this.resettingSocket = false;
    });
  }

  onMessage(callback: MessageCallback): void {
    this.messageCallbacks.push(callback);
  }

  onTyping(callback: TypingCallback): void {
    this.typingCallbacks.push(callback);
  }

  onError(callback: ErrorCallback): void {
    this.errorCallbacks.push(callback);
  }

  onConnectionChange(callback: (state: ConnectionState) => void): void {
    this.connectionCallbacks.push(callback);
  }

  isConnected(): boolean {
    return this.connected;
  }

  invalidateConversation(_sessionHint?: string | null): void {
    // WebSocket provider does not cache per-conversation handles.
  }

  async sendMessage(
    messageData: BusinessMessagePayload,
    _sessionHint: string
  ): Promise<AdapterSendResult> {
    if (!this.connected || this.socketTask === null) {
      throw new Error('MESSAGE_SERVICE_DISCONNECTED');
    }

    const isTypingStart = messageData.message_type === MESSAGE_TYPE.TYPING_START;
    const isTypingEnd = messageData.message_type === MESSAGE_TYPE.TYPING_END;

    if (isTypingStart || isTypingEnd) {
      const ackPayload = await this.sendFrameWithAck(
        {
          type: 'typing',
          ws_frame_id: randomFrameId('typing'),
          payload: {
            msg_id_client: messageData.msg_id,
            conversation_id: messageData.conv_id,
            typing_state: isTypingStart ? 'start' : 'end',
            supports_typing: messageData.supports_typing,
            client_sent_time_ms: messageData.sent_time,
          },
        },
        this.currentSocketVersion,
        TYPING_ACK_TIMEOUT_MS
      );

      if (ackPayload.ok !== true) {
        throw new Error('WS_TYPING_ACK_FAILED');
      }

      return {
        ...messageData,
        provider_msg_id: messageData.msg_id,
        provider_timestamp_ms: Date.now(),
      };
    }

    const ackPayload = await this.sendFrameWithAck(
      {
        type: 'send_message',
        ws_frame_id: randomFrameId('send'),
        payload: {
          msg_id_client: messageData.msg_id,
          conversation_id: messageData.conv_id,
          content: messageData.content,
          supports_typing: messageData.supports_typing,
          client_sent_time_ms: messageData.sent_time,
        },
      },
      this.currentSocketVersion,
      SEND_MESSAGE_ACK_TIMEOUT_MS
    );

    const msgIdServer =
      typeof ackPayload.msg_id_server === 'string' && ackPayload.msg_id_server.length > 0
        ? ackPayload.msg_id_server
        : messageData.msg_id;
    const sentTimeMs =
      typeof ackPayload.sent_time_ms === 'number' && Number.isFinite(ackPayload.sent_time_ms)
        ? ackPayload.sent_time_ms
        : Date.now();

    return {
      ...messageData,
      msg_id_server: msgIdServer,
      provider_msg_id: msgIdServer,
      provider_timestamp_ms: sentTimeMs,
    };
  }

  private bindSocketHandlers(
    socketTask: WechatMiniprogram.SocketTask,
    socketVersion: number
  ): void {
    socketTask.onMessage((res) => {
      this.handleSocketMessage(res.data, socketVersion);
    });

    socketTask.onClose(() => {
      if (socketVersion !== this.currentSocketVersion) {
        return;
      }
      this.handleSocketClosed();
    });

    socketTask.onError((error) => {
      if (socketVersion !== this.currentSocketVersion) {
        return;
      }
      const err = toError(error);
      this.forceResetConnection(err);
    });
  }

  private waitForOpen(
    socketTask: WechatMiniprogram.SocketTask,
    socketVersion: number
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      let settled = false;
      const settle = (cb: () => void): void => {
        if (settled) {
          return;
        }
        settled = true;
        cb();
      };

      const timer = setTimeout(() => {
        settle(() => reject(new Error('WS_OPEN_TIMEOUT')));
      }, SOCKET_OPEN_TIMEOUT_MS);

      socketTask.onOpen(() => {
        if (socketVersion !== this.currentSocketVersion) {
          clearTimeout(timer);
          settle(() => reject(new Error('WS_SOCKET_STALE')));
          return;
        }
        clearTimeout(timer);
        settle(() => resolve());
      });

      socketTask.onError((error) => {
        clearTimeout(timer);
        settle(() => reject(toError(error)));
      });

      socketTask.onClose(() => {
        clearTimeout(timer);
        settle(() => reject(new Error('WS_CLOSED_BEFORE_OPEN')));
      });
    });
  }

  private sendFrameWithAck(
    frame: { type: string; ws_frame_id: string; payload: Record<string, unknown> },
    socketVersion: number,
    timeoutMs: number
  ): Promise<Record<string, unknown>> {
    if (this.socketTask === null) {
      return Promise.reject(new Error('MESSAGE_SERVICE_DISCONNECTED'));
    }

    if (socketVersion !== this.currentSocketVersion) {
      return Promise.reject(new Error('WS_SOCKET_STALE'));
    }

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingAcks.delete(frame.ws_frame_id);
        const error = new Error('WS_ACK_TIMEOUT');
        reject(error);
        this.forceResetConnection(error);
      }, timeoutMs);

      this.pendingAcks.set(frame.ws_frame_id, {
        resolve,
        reject,
        timer,
      });

      this.socketTask!.send({
        data: JSON.stringify(frame),
        fail: (error) => {
          const pending = this.pendingAcks.get(frame.ws_frame_id);
          if (pending !== undefined) {
            clearTimeout(pending.timer);
            this.pendingAcks.delete(frame.ws_frame_id);
          }
          const err = toError(error);
          reject(err);
          this.forceResetConnection(err);
        },
      });
    });
  }

  private resolvePendingAck(wsFrameId: string, payload: Record<string, unknown>): boolean {
    const pending = this.pendingAcks.get(wsFrameId);
    if (pending === undefined) {
      return false;
    }
    clearTimeout(pending.timer);
    this.pendingAcks.delete(wsFrameId);
    pending.resolve(payload);
    return true;
  }

  private rejectPendingAck(wsFrameId: string, error: Error): boolean {
    const pending = this.pendingAcks.get(wsFrameId);
    if (pending === undefined) {
      return false;
    }
    clearTimeout(pending.timer);
    this.pendingAcks.delete(wsFrameId);
    pending.reject(error);
    return true;
  }

  private rejectAllPendingAcks(error: Error): void {
    this.pendingAcks.forEach((pending, wsFrameId) => {
      clearTimeout(pending.timer);
      pending.reject(error);
      this.pendingAcks.delete(wsFrameId);
    });
  }

  private handleSocketMessage(rawData: unknown, socketVersion: number): void {
    if (socketVersion !== this.currentSocketVersion) {
      return;
    }

    let frame: Record<string, unknown>;
    try {
      frame =
        typeof rawData === 'string'
          ? (JSON.parse(rawData) as Record<string, unknown>)
          : (rawData as Record<string, unknown>);
    } catch (error) {
      this.triggerErrorCallbacks(toError(error));
      return;
    }

    const frameType = typeof frame.type === 'string' ? frame.type : '';
    const wsFrameId = typeof frame.ws_frame_id === 'string' ? frame.ws_frame_id : '';
    const payload = asRecord(frame.payload) ?? {};

    if (frameType === 'ack' && isNonEmptyString(wsFrameId)) {
      this.resolvePendingAck(wsFrameId, payload);
      return;
    }

    if (frameType === 'error') {
      const errorMessage =
        typeof payload.message === 'string' && payload.message !== ''
          ? payload.message
          : 'WS_ERROR';
      const error = new Error(errorMessage);
      if (isNonEmptyString(wsFrameId) && this.rejectPendingAck(wsFrameId, error)) {
        return;
      }
      this.triggerErrorCallbacks(error);
      return;
    }

    if (frameType === 'event') {
      this.handleEventPayload(payload);
    }
  }

  private handleEventPayload(payload: Record<string, unknown>): void {
    const eventType = typeof payload.event_type === 'string' ? payload.event_type : '';
    if (eventType === 'typing') {
      this.handleTypingEvent(payload);
      return;
    }
    if (eventType === 'message') {
      this.handleMessageEvent(payload);
    }
  }

  private handleTypingEvent(payload: Record<string, unknown>): void {
    const typing = asRecord(payload.typing);
    if (typing === null) {
      return;
    }
    const typingState = typing.typing_state === 'start';
    const sentTime =
      typeof typing.time_ms === 'number' && Number.isFinite(typing.time_ms)
        ? typing.time_ms
        : Date.now();
    this.triggerTypingCallbacks({
      conv_id: typeof typing.conversation_id === 'string' ? typing.conversation_id : '',
      from_qiao_id: typeof typing.from_qiao_id === 'string' ? typing.from_qiao_id : '',
      to_qiao_id: typeof typing.to_qiao_id === 'string' ? typing.to_qiao_id : '',
      isTyping: typingState,
      sent_time: sentTime,
    });
  }

  private handleMessageEvent(payload: Record<string, unknown>): void {
    const message = asRecord(payload.message);
    if (message === null) {
      return;
    }

    const metadata = asRecord(message.metadata);
    const msgIdServer = readString(message.msg_id_server);
    const msgIdClient = readOptionalClientMsgId(message.msg_id_client);
    const sentTime = readSentTimeMs(message.sent_time_ms);
    const messageType = readMessageType(message.message_type);

    const adapterMessage: AdapterMessage = {
      msg_id: msgIdServer !== '' ? msgIdServer : randomFrameId('evt'),
      msg_id_server: msgIdServer !== '' ? msgIdServer : null,
      msg_id_client: msgIdClient,
      from_qiao_id: readString(message.from_qiao_id),
      to_qiao_id: readString(message.to_qiao_id),
      conv_id: readString(message.conversation_id),
      content: readString(message.content),
      message_type: messageType,
      supports_typing: true,
      sent_time: sentTime,
      action: readActionPayload(metadata),
      notification_type: readNotificationType(metadata),
      data: metadata,
      status: MESSAGE_STATUS.RECEIVED,
      provider_msg_id: msgIdServer !== '' ? msgIdServer : randomFrameId('evt_msg'),
      provider_timestamp_ms: sentTime,
    };

    this.triggerMessageCallbacks(adapterMessage);
  }

  private handleSocketClosed(): void {
    this.forceResetConnection(new Error('WS_DISCONNECTED'));
  }

  private startPingLoop(socketVersion: number): void {
    this.stopPingLoop();
    this.pingTimer = setInterval(() => {
      if (!this.connected || socketVersion !== this.currentSocketVersion) {
        return;
      }
      void this.sendFrameWithAck(
        {
          type: 'ping',
          ws_frame_id: randomFrameId('ping'),
          payload: {},
        },
        socketVersion,
        PING_ACK_TIMEOUT_MS
      ).catch((error) => {
        const err = toError(error);
        logger.warn('WebSocket ping failed', { error: err.message });
      });
    }, PING_INTERVAL_MS);
  }

  private stopPingLoop(): void {
    if (this.pingTimer !== null) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private triggerMessageCallbacks(message: AdapterMessage): void {
    this.messageCallbacks.forEach((callback) => {
      try {
        callback(message);
      } catch (error) {
        this.triggerErrorCallbacks(toError(error));
      }
    });
  }

  private triggerTypingCallbacks(typing: AdapterTypingPayload): void {
    this.typingCallbacks.forEach((callback) => {
      try {
        callback(typing);
      } catch (error) {
        this.triggerErrorCallbacks(toError(error));
      }
    });
  }

  private triggerErrorCallbacks(error: Error): void {
    this.errorCallbacks.forEach((callback) => {
      try {
        callback(error);
      } catch {
        // Keep best effort, avoid recursive callback failures.
      }
    });
  }

  private triggerConnectionCallbacks(state: ConnectionState): void {
    this.connectionCallbacks.forEach((callback) => {
      try {
        callback(state);
      } catch (error) {
        this.triggerErrorCallbacks(toError(error));
      }
    });
  }
}

export default new WSAdapter();
