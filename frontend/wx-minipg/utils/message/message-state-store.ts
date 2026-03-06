import { getLogger } from '../logger';
import { MESSAGE_CONFIG } from '../config';
import { parse, StoredMessage, StoredMessageSchema, StoredMessages } from '../schemas';
import { getMessages, getUserInfo } from '../storage';
import messageEventBus from './event-bus';
import { buildMessageViewModels, MessageViewModel } from './message-view-model';
import { isNonEmptyString } from '../guards';
import { normalizeError } from '../errors';
import { MESSAGE_TYPE, MessageStatus } from '../constants/message';

const logger = getLogger('MessageStateStore');

export interface MessageStoreState {
  convId: string;
  messages: MessageViewModel[];
  isTyping: boolean;
}

type Subscriber = (state: MessageStoreState) => void;

class MessageStateStore {
  private state: MessageStoreState = {
    convId: '',
    messages: [],
    isTyping: false,
  };
  private subscribers = new Set<Subscriber>();
  private errorHandlers = new Set<(error: Error) => void>();
  private storedMessages: StoredMessages = [];
  private currentUserId = '';
  private typingTimer: ReturnType<typeof setTimeout> | null = null;
  private lastMessageReceivedTime: number | null = null;

  constructor() {
    messageEventBus.onMessage((message) => {
      void this.handleAdapterMessage(message);
    });
    messageEventBus.onTyping((payload) => {
      void this.handleTypingEvent(payload);
    });
    messageEventBus.onError((error) => {
      this.emitError(error);
    });
  }

  subscribe(subscriber: Subscriber): () => void {
    this.subscribers.add(subscriber);
    subscriber(this.state);
    return () => {
      this.subscribers.delete(subscriber);
    };
  }

  onError(handler: (error: Error) => void): () => void {
    this.errorHandlers.add(handler);
    return () => {
      this.errorHandlers.delete(handler);
    };
  }

  getStateSnapshot(): MessageStoreState {
    return {
      convId: this.state.convId,
      messages: [...this.state.messages],
      isTyping: this.state.isTyping,
    };
  }

  async setConversation(convId: string): Promise<void> {
    if (!isNonEmptyString(convId)) {
      this.clearConversation();
      return;
    }
    if (this.state.convId === convId) {
      await this.reloadMessages(convId);
      return;
    }
    this.state = { ...this.state, convId, messages: [], isTyping: false };
    this.storedMessages = [];
    this.lastMessageReceivedTime = null;
    this.clearTypingTimer();
    await this.reloadMessages(convId);
  }

  async reloadMessages(convId: string): Promise<void> {
    const stored = await getMessages(convId);
    this.storedMessages = stored;
    await this.ensureCurrentUser();
    this.emit();
  }

  async addOptimisticMessage(message: StoredMessage): Promise<void> {
    await this.ensureCurrentUser();
    this.updateLastMessageReceivedTime(Date.now());
    this.setTypingState(false);
    this.mergeMessage(message);
    this.emit();
  }

  updateMessageStatus(messageId: string, status: MessageStatus): void {
    const index = this.storedMessages.findIndex((item) => item.msg_id === messageId);
    if (index === -1) {
      return;
    }
    this.storedMessages[index] = {
      ...this.storedMessages[index],
      status,
    };
    this.emit();
  }

  removeMessage(messageId: string): void {
    const nextMessages = this.storedMessages.filter((item) => item.msg_id !== messageId);
    if (nextMessages.length === this.storedMessages.length) {
      return;
    }
    this.storedMessages = nextMessages;
    this.emit();
  }

  clearConversation(): void {
    this.state = { convId: '', messages: [], isTyping: false };
    this.storedMessages = [];
    this.lastMessageReceivedTime = null;
    this.clearTypingTimer();
    this.emit();
  }

  private async handleAdapterMessage(message: StoredMessage | null | undefined): Promise<void> {
    if (message === null || message === undefined) {
      return;
    }
    if (!isNonEmptyString(message.conv_id)) {
      return;
    }
    if (message.conv_id !== this.state.convId) {
      return;
    }
    const parsed = this.safeParseMessage(message);
    if (parsed === null) {
      return;
    }
    await this.ensureCurrentUser();
    const messageType = parsed.message_type;
    const isTypingMessage =
      messageType === MESSAGE_TYPE.TYPING_START || messageType === MESSAGE_TYPE.TYPING_END;
    if (!isTypingMessage) {
      this.updateLastMessageReceivedTime(Date.now());
      this.setTypingState(false);
    }
    this.mergeMessage(parsed);
    this.emit();
  }

  private async ensureCurrentUser(): Promise<void> {
    if (isNonEmptyString(this.currentUserId)) {
      return;
    }
    const userInfo = await getUserInfo();
    const qiaoId = userInfo?.qiao_id;
    if (isNonEmptyString(qiaoId)) {
      this.currentUserId = qiaoId;
    }
  }

  private mergeMessage(message: StoredMessage): void {
    const shouldCollapseSelfEcho =
      isNonEmptyString(message.msg_id_server) && isNonEmptyString(message.msg_id_client);
    let index = this.storedMessages.findIndex((item) => item.msg_id === message.msg_id);
    if (index === -1 && shouldCollapseSelfEcho) {
      const clientMsgId = message.msg_id_client;
      index = this.storedMessages.findIndex((item) => {
        const existingClientMsgId = isNonEmptyString(item.msg_id_client)
          ? item.msg_id_client
          : null;
        return item.msg_id === clientMsgId || existingClientMsgId === clientMsgId;
      });
    }
    if (index !== -1) {
      this.storedMessages[index] = {
        ...this.storedMessages[index],
        ...message,
      };
    } else {
      this.storedMessages.push(message);
      index = this.storedMessages.length - 1;
    }
    if (shouldCollapseSelfEcho) {
      this.storedMessages = this.storedMessages.filter(
        (item, currentIndex) => currentIndex === index || item.msg_id !== message.msg_id
      );
    }
  }

  private async handleTypingEvent(payload: {
    conv_id: string;
    from_qiao_id: string;
    to_qiao_id: string;
    typing: boolean;
    sent_time: number;
    received_time: number;
  }): Promise<void> {
    if (payload.conv_id !== this.state.convId) {
      return;
    }
    if (!Number.isFinite(payload.received_time)) {
      logger.error('Typing payload missing received_time', {
        conv_id: payload.conv_id,
        from_qiao_id: payload.from_qiao_id,
        to_qiao_id: payload.to_qiao_id,
      });
      return;
    }
    await this.ensureCurrentUser();
    if (isNonEmptyString(this.currentUserId) && payload.to_qiao_id !== this.currentUserId) {
      return;
    }
    if (isNonEmptyString(this.currentUserId) && payload.from_qiao_id === this.currentUserId) {
      return;
    }
    if (
      this.lastMessageReceivedTime !== null &&
      payload.received_time < this.lastMessageReceivedTime
    ) {
      return;
    }
    this.setTypingState(payload.typing);
  }

  private setTypingState(isTyping: boolean): void {
    if (isTyping) {
      if (this.typingTimer !== null) {
        clearTimeout(this.typingTimer);
      }
      this.typingTimer = setTimeout(() => {
        this.setTypingState(false);
      }, MESSAGE_CONFIG.typingTimeout);
      if (this.state.isTyping) {
        return;
      }
    } else {
      if (this.typingTimer !== null) {
        clearTimeout(this.typingTimer);
        this.typingTimer = null;
      }
      if (!this.state.isTyping) {
        return;
      }
    }
    this.state = { ...this.state, isTyping };
    this.emit();
  }

  private updateLastMessageReceivedTime(receivedTime: number): void {
    if (!Number.isFinite(receivedTime)) {
      return;
    }
    if (this.lastMessageReceivedTime === null || receivedTime > this.lastMessageReceivedTime) {
      this.lastMessageReceivedTime = receivedTime;
    }
  }

  private clearTypingTimer(): void {
    if (this.typingTimer !== null) {
      clearTimeout(this.typingTimer);
      this.typingTimer = null;
    }
  }

  private safeParseMessage(message: unknown): StoredMessage | null {
    try {
      return parse(StoredMessageSchema, message);
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Message validation failed', {
        errorMessage: err.message,
      });
      return null;
    }
  }

  private emit(): void {
    const viewModels = buildMessageViewModels(this.storedMessages, this.currentUserId);
    this.state = { ...this.state, messages: viewModels };
    this.subscribers.forEach((subscriber) => {
      try {
        subscriber(this.state);
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.error('MessageStateStore subscriber threw', {
          errorMessage: err.message,
        });
      }
    });
  }

  private emitError(error: Error): void {
    this.errorHandlers.forEach((handler) => {
      try {
        handler(error);
      } catch (err: unknown) {
        const normalizedErr = normalizeError(err);
        logger.error('MessageStateStore error handler threw', {
          errorMessage: normalizedErr.message,
        });
      }
    });
  }
}

const messageStateStore = new MessageStateStore();
export default messageStateStore;
