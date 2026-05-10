import { getLogger } from '../../../utils/logger';
import { parse, StoredMessage, StoredMessageSchema, StoredMessages } from '../../../utils/schemas';
import {
  getMessages,
  getUserInfo,
  patchMessageByIdentity,
  saveMessages,
} from '../../../utils/storage';
import messageEventBus from '../../../utils/message/event-bus';
import { buildMessageViewModels, MessageViewModel } from './message-view-model';
import { isNonEmptyString } from '../../../utils/guards';
import { normalizeError } from '../../../utils/errors';
import {
  MESSAGE_FAILURE_CATEGORY,
  MessageFailureCategory,
  MessageStatus,
  MESSAGE_STATUS,
  MESSAGE_TYPE,
} from '../../../utils/constants/message';

const logger = getLogger('MessageStateStore');

export interface MessageStoreState {
  convId: string;
  messages: MessageViewModel[];
}

type Subscriber = (state: MessageStoreState) => void;

export interface UpdateMessageStatusOptions {
  failureCategory?: MessageFailureCategory | null;
  failureReason?: string | null;
  retryable?: boolean | null;
}

type ResolvedFailureState = {
  failureCategory: string | null;
  failureReason: string | null;
  retryable: boolean | null;
};

type MarkMessageFailedAction = {
  targetMsgId: string;
  reason: string | null;
};

class MessageStateStore {
  private state: MessageStoreState = {
    convId: '',
    messages: [],
  };
  private subscribers = new Set<Subscriber>();
  private errorHandlers = new Set<(error: Error) => void>();
  private storedMessages: StoredMessages = [];
  private currentUserId = '';
  private persistenceQueue: Promise<void> = Promise.resolve();

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
    const reconciledMessages = this.applyBusinessRejectionActionsInMemory();
    if (reconciledMessages.length > 0) {
      await saveMessages(convId, this.storedMessages);
    }
    await this.ensureCurrentUser();
    this.emit();
  }

  async addOptimisticMessage(message: StoredMessage): Promise<void> {
    await this.ensureCurrentUser();
    this.mergeMessage(message);
    this.emit();
  }

  updateMessageStatus(
    messageId: string,
    status: MessageStatus,
    options: UpdateMessageStatusOptions = {}
  ): void {
    const index = this.findMessageIndex(messageId);
    if (index === -1) {
      return;
    }
    const previous = this.storedMessages[index];
    const resolvedFailure = this.resolveFailureState(previous, status, options);
    const shouldUpdate = this.shouldUpdateMessage(previous, status, resolvedFailure);
    if (!shouldUpdate) {
      return;
    }
    const nextMessage: StoredMessage = {
      ...previous,
      status,
      failure_category: resolvedFailure.failureCategory,
      failure_reason: resolvedFailure.failureReason,
      retryable: resolvedFailure.retryable,
    };
    this.storedMessages[index] = nextMessage;
    this.enqueuePersistence(() =>
      this.persistMessageStatus(nextMessage, {
        status,
        failure_category: resolvedFailure.failureCategory,
        failure_reason: resolvedFailure.failureReason,
        retryable: resolvedFailure.retryable,
      })
    );
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

  private findMessageIndex(messageId: string): number {
    return this.storedMessages.findIndex((item) => {
      if (item.msg_id === messageId) {
        return true;
      }
      return isNonEmptyString(item.msg_id_client) && item.msg_id_client === messageId;
    });
  }

  private resolveFailureState(
    previous: StoredMessage,
    status: MessageStatus,
    options: UpdateMessageStatusOptions
  ): ResolvedFailureState {
    if (status !== MESSAGE_STATUS.FAILED) {
      return {
        failureCategory: null,
        failureReason: null,
        retryable: null,
      };
    }

    return {
      failureCategory:
        options.failureCategory === undefined
          ? (previous.failure_category ?? null)
          : options.failureCategory,
      failureReason:
        options.failureReason === undefined
          ? (previous.failure_reason ?? null)
          : options.failureReason,
      retryable: options.retryable === undefined ? (previous.retryable ?? null) : options.retryable,
    };
  }

  private shouldUpdateMessage(
    previous: StoredMessage,
    status: MessageStatus,
    nextFailureState: ResolvedFailureState
  ): boolean {
    return (
      previous.status !== status ||
      (previous.failure_category ?? null) !== nextFailureState.failureCategory ||
      (previous.failure_reason ?? null) !== nextFailureState.failureReason ||
      (previous.retryable ?? null) !== nextFailureState.retryable
    );
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
    const reconciledMessages = this.applyBusinessRejectionActionsInMemory();
    if (reconciledMessages.length > 0) {
      const snapshot = [...this.storedMessages];
      this.enqueuePersistence(() => saveMessages(parsed.conv_id, snapshot));
    }
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

  private resolveMarkMessageFailedAction(message: StoredMessage): MarkMessageFailedAction | null {
    const messageType =
      typeof message.message_type === 'number' ? message.message_type : MESSAGE_TYPE.TEXT;
    if (messageType !== MESSAGE_TYPE.CHAT_INFO) {
      return null;
    }
    const actionPayload = this.parseActionPayload(message.action);
    if (actionPayload === null) {
      return null;
    }
    if (actionPayload.type !== 'mark_message_failed') {
      return null;
    }
    const targetMsgId =
      typeof actionPayload.target_msg_id === 'string' ? actionPayload.target_msg_id : '';
    if (!isNonEmptyString(targetMsgId)) {
      return null;
    }
    return {
      targetMsgId,
      reason: typeof actionPayload.reason === 'string' ? actionPayload.reason : null,
    };
  }

  private parseActionPayload(action: unknown): Record<string, unknown> | null {
    if (typeof action === 'object' && action !== null) {
      return action as Record<string, unknown>;
    }
    if (typeof action !== 'string' || action.trim() === '') {
      return null;
    }
    try {
      const parsed: unknown = JSON.parse(action) as unknown;
      return typeof parsed === 'object' && parsed !== null
        ? (parsed as Record<string, unknown>)
        : null;
    } catch {
      return null;
    }
  }

  private applyBusinessRejectionActionsInMemory(): StoredMessage[] {
    const updatedMessages: StoredMessage[] = [];
    this.storedMessages.forEach((message) => {
      const action = this.resolveMarkMessageFailedAction(message);
      if (action === null) {
        return;
      }
      const applied = this.applyBusinessRejectedStatus(action.targetMsgId, action.reason);
      if (applied !== null) {
        updatedMessages.push(applied);
      }
    });
    return updatedMessages;
  }

  private applyBusinessRejectedStatus(
    targetMessageId: string,
    reason: string | null
  ): StoredMessage | null {
    const index = this.findMessageIndex(targetMessageId);
    if (index === -1) {
      return null;
    }
    const previous = this.storedMessages[index];
    const resolvedFailure = this.resolveFailureState(previous, MESSAGE_STATUS.FAILED, {
      failureCategory: MESSAGE_FAILURE_CATEGORY.BUSINESS_REJECTED,
      failureReason: reason,
      retryable: true,
    });
    if (!this.shouldUpdateMessage(previous, MESSAGE_STATUS.FAILED, resolvedFailure)) {
      return null;
    }
    const nextMessage: StoredMessage = {
      ...previous,
      status: MESSAGE_STATUS.FAILED,
      failure_category: resolvedFailure.failureCategory,
      failure_reason: resolvedFailure.failureReason,
      retryable: resolvedFailure.retryable,
    };
    this.storedMessages[index] = nextMessage;
    return nextMessage;
  }

  private persistMessageStatus(
    message: StoredMessage,
    statusPatch: Pick<StoredMessage, 'status' | 'failure_category' | 'failure_reason' | 'retryable'>
  ): Promise<void> {
    return patchMessageByIdentity(message.conv_id, message.msg_id, statusPatch).then((updated) => {
      if (updated) {
        return;
      }
      logger.warn('Persist message status missed target', {
        convId: message.conv_id,
        msgId: message.msg_id,
        msgIdClient: message.msg_id_client ?? null,
      });
    });
  }

  private enqueuePersistence(task: () => Promise<void>): void {
    this.persistenceQueue = this.persistenceQueue.then(task).catch((error: unknown) => {
      const err = normalizeError(error);
      logger.error('Message persistence task failed', {
        errorMessage: err.message,
      });
    });
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
