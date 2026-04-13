import { getLogger } from '../../../utils/logger';
import { parse, StoredMessage, StoredMessageSchema, StoredMessages } from '../../../utils/schemas';
import { getMessages, getUserInfo } from '../../../utils/storage';
import messageEventBus from '../../../utils/message/event-bus';
import { buildMessageViewModels, MessageViewModel } from './message-view-model';
import { isNonEmptyString } from '../../../utils/guards';
import { normalizeError } from '../../../utils/errors';
import { MessageStatus } from '../../../utils/constants/message';

const logger = getLogger('MessageStateStore');

export interface MessageStoreState {
  convId: string;
  messages: MessageViewModel[];
}

type Subscriber = (state: MessageStoreState) => void;

class MessageStateStore {
  private state: MessageStoreState = {
    convId: '',
    messages: [],
  };
  private subscribers = new Set<Subscriber>();
  private errorHandlers = new Set<(error: Error) => void>();
  private storedMessages: StoredMessages = [];
  private currentUserId = '';

  constructor() {
    messageEventBus.onMessage((message) => {
      void this.handleAdapterMessage(message);
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
    this.state = { ...this.state, convId, messages: [] };
    this.storedMessages = [];
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

  removeMessage(messageId: string): void {
    const nextMessages = this.storedMessages.filter((item) => item.msg_id !== messageId);
    if (nextMessages.length === this.storedMessages.length) {
      return;
    }
    this.storedMessages = nextMessages;
    this.emit();
  }

  clearConversation(): void {
    this.state = { convId: '', messages: [] };
    this.storedMessages = [];
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
