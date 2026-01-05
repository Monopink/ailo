import { getLogger } from '../logger';
import { parse, StoredMessage, StoredMessageSchema, StoredMessages } from '../schemas';
import { getMessages, getUserInfo } from '../storage';
import messageEventBus from './event-bus';
import { buildMessageViewModels, MessageViewModel } from './message-view-model';
import { hasValue, isNonEmptyString } from '../guards';
import { MessageStatus } from './constants';

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

  constructor() {
    messageEventBus.onMessage((message) => {
      void this.handleAdapterMessage(message);
    });
    messageEventBus.onTyping((payload) => {
      this.handleTypingEvent(payload.typing);
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

  async setConversation(convId: string): Promise<void> {
    if (!isNonEmptyString(convId)) {
      this.clearConversation();
      return;
    }
    if (this.state.convId === convId) {
      return;
    }
    this.state = { ...this.state, convId, messages: [], isTyping: false };
    this.storedMessages = [];
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

  clearConversation(): void {
    this.state = { convId: '', messages: [], isTyping: false };
    this.storedMessages = [];
    this.clearTypingTimer();
    this.emit();
  }

  private async handleAdapterMessage(message: StoredMessage): Promise<void> {
    if (!hasValue(message)) {
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
    const index = this.storedMessages.findIndex((item) => item.msg_id === message.msg_id);
    if (index !== -1) {
      this.storedMessages[index] = {
        ...this.storedMessages[index],
        ...message,
      };
    } else {
      this.storedMessages.push(message);
    }
  }

  private handleTypingEvent(isTyping: boolean): void {
    if (this.state.isTyping === isTyping) {
      return;
    }
    if (isTyping) {
      if (this.typingTimer !== null) {
        clearTimeout(this.typingTimer);
      }
      this.typingTimer = setTimeout(() => {
        this.handleTypingEvent(false);
      }, 30_000);
    } else if (this.typingTimer !== null) {
      clearTimeout(this.typingTimer);
      this.typingTimer = null;
    }
    this.state = { ...this.state, isTyping };
    this.emit();
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
    } catch (error) {
      logger.error('Message validation failed', { error });
      return null;
    }
  }

  private emit(): void {
    const viewModels = buildMessageViewModels(this.storedMessages, this.currentUserId);
    this.state = { ...this.state, messages: viewModels };
    this.subscribers.forEach((subscriber) => {
      try {
        subscriber(this.state);
      } catch (error) {
        logger.error('MessageStateStore subscriber threw', { error });
      }
    });
  }

  private emitError(error: Error): void {
    this.errorHandlers.forEach((handler) => {
      try {
        handler(error);
      } catch (err) {
        logger.error('MessageStateStore error handler threw', { error: err });
      }
    });
  }
}

const messageStateStore = new MessageStateStore();
export default messageStateStore;
