import { MESSAGE_CONFIG } from '../config';
import { MESSAGE_TYPE, type MessageType } from '../constants/message';
import { normalizeError } from '../errors';
import { isNonEmptyString } from '../guards';
import { getLogger } from '../logger';
import { getUserInfo } from '../storage';
import messageEventBus from './event-bus';
import type { StoredMessage } from '../storage';

const logger = getLogger('ConversationPresenceStore');

type TypingChangeSubscriber = (isTyping: boolean) => void;

type ConversationPresenceState = {
  isTyping: boolean;
  expiresAtMs: number | null;
  timer: ReturnType<typeof setTimeout> | null;
  lastTypingReceivedAtMs: number;
  lastNonTypingActivityAtMs: number;
};

const createInitialState = (): ConversationPresenceState => ({
  isTyping: false,
  expiresAtMs: null,
  timer: null,
  lastTypingReceivedAtMs: 0,
  lastNonTypingActivityAtMs: 0,
});

class ConversationPresenceStore {
  private currentUserId = '';
  private presenceByConvId = new Map<string, ConversationPresenceState>();
  private typingSubscribersByConvId = new Map<string, Set<TypingChangeSubscriber>>();

  constructor() {
    messageEventBus.onTyping((payload) => {
      void this.handleTyping(payload);
    });
    messageEventBus.onMessage((message) => {
      void this.handleNonTypingMessage(message);
    });
  }

  getTyping(convId: string): boolean {
    if (!isNonEmptyString(convId)) {
      return false;
    }
    this.cleanupExpiredIfNeeded(convId);
    return this.getState(convId).isTyping;
  }

  subscribeTyping(convId: string, subscriber: TypingChangeSubscriber): () => void {
    if (!isNonEmptyString(convId)) {
      return () => {};
    }
    const subscribers = this.getTypingSubscribers(convId);
    subscribers.add(subscriber);
    return () => {
      const current = this.typingSubscribersByConvId.get(convId);
      current?.delete(subscriber);
    };
  }

  clearTyping(convId: string): void {
    if (!isNonEmptyString(convId)) {
      return;
    }
    const now = Date.now();
    const state = this.getState(convId);
    state.lastNonTypingActivityAtMs = now;
    this.setTypingState(convId, false, { clearExpires: true });
  }

  clearAll(): void {
    for (const [convId, state] of this.presenceByConvId.entries()) {
      if (state.timer !== null) {
        clearTimeout(state.timer);
      }
      state.timer = null;
      const wasTyping = state.isTyping;
      state.isTyping = false;
      state.expiresAtMs = null;
      state.lastTypingReceivedAtMs = 0;
      state.lastNonTypingActivityAtMs = 0;
      if (wasTyping) {
        this.emitTypingChange(convId, false);
      }
    }
    this.presenceByConvId.clear();
    this.typingSubscribersByConvId.clear();
    this.currentUserId = '';
  }

  private getTypingSubscribers(convId: string): Set<TypingChangeSubscriber> {
    const existing = this.typingSubscribersByConvId.get(convId);
    if (existing !== undefined) {
      return existing;
    }
    const subscribers = new Set<TypingChangeSubscriber>();
    this.typingSubscribersByConvId.set(convId, subscribers);
    return subscribers;
  }

  private getState(convId: string): ConversationPresenceState {
    const existing = this.presenceByConvId.get(convId);
    if (existing !== undefined) {
      return existing;
    }
    const state = createInitialState();
    this.presenceByConvId.set(convId, state);
    return state;
  }

  private cleanupExpiredIfNeeded(convId: string): void {
    const state = this.presenceByConvId.get(convId);
    if (!state?.isTyping) {
      return;
    }
    if (state.expiresAtMs === null) {
      return;
    }
    if (Date.now() < state.expiresAtMs) {
      return;
    }
    this.setTypingState(convId, false, { clearExpires: true });
  }

  private emitTypingChange(convId: string, isTyping: boolean): void {
    const subscribers = this.typingSubscribersByConvId.get(convId);
    if (subscribers === undefined) {
      return;
    }
    for (const subscriber of subscribers) {
      try {
        subscriber(isTyping);
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.error('Typing subscriber threw', { errorMessage: err.message });
      }
    }
  }

  private scheduleTypingExpiry(convId: string, state: ConversationPresenceState): void {
    if (state.expiresAtMs === null) {
      return;
    }
    if (state.timer !== null) {
      clearTimeout(state.timer);
      state.timer = null;
    }
    const delay = Math.max(0, state.expiresAtMs - Date.now());
    state.timer = setTimeout(() => {
      state.timer = null;
      this.cleanupExpiredIfNeeded(convId);
    }, delay);
  }

  private setTypingState(
    convId: string,
    nextTyping: boolean,
    options?: { clearExpires?: boolean }
  ): void {
    const state = this.getState(convId);
    if (state.timer !== null && !nextTyping) {
      clearTimeout(state.timer);
      state.timer = null;
    }
    if (options?.clearExpires === true && !nextTyping) {
      state.expiresAtMs = null;
    }
    if (state.isTyping === nextTyping) {
      return;
    }
    state.isTyping = nextTyping;
    this.emitTypingChange(convId, nextTyping);
  }

  private async ensureCurrentUser(): Promise<boolean> {
    if (isNonEmptyString(this.currentUserId)) {
      return true;
    }
    try {
      const userInfo = await getUserInfo();
      const qiaoId = userInfo?.qiao_id ?? '';
      if (!isNonEmptyString(qiaoId)) {
        return false;
      }
      this.currentUserId = qiaoId;
      return true;
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to load current user', { errorMessage: err.message });
      return false;
    }
  }

  private async handleTyping(payload: {
    conv_id: string;
    from_qiao_id: string;
    to_qiao_id: string;
    typing: boolean;
    sent_time: number;
    received_time: number;
  }): Promise<void> {
    const convId = payload.conv_id;
    if (!isNonEmptyString(convId)) {
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

    const hasUser = await this.ensureCurrentUser();
    if (!hasUser) {
      logger.warn('Dropping typing event without current user', { conv_id: convId });
      return;
    }

    if (!isNonEmptyString(payload.to_qiao_id) || payload.to_qiao_id !== this.currentUserId) {
      return;
    }
    if (isNonEmptyString(payload.from_qiao_id) && payload.from_qiao_id === this.currentUserId) {
      return;
    }

    const state = this.getState(convId);
    const dropBeforeMs = Math.max(state.lastNonTypingActivityAtMs, state.lastTypingReceivedAtMs);
    if (payload.received_time < dropBeforeMs) {
      return;
    }

    state.lastTypingReceivedAtMs = payload.received_time;

    if (payload.typing) {
      state.expiresAtMs = Date.now() + MESSAGE_CONFIG.typingTimeout;
      this.setTypingState(convId, true);
      this.scheduleTypingExpiry(convId, state);
      return;
    }

    this.setTypingState(convId, false, { clearExpires: true });
  }

  private resolveMessageType(message: StoredMessage): MessageType | null {
    const type = message.message_type as MessageType | undefined;
    if (type === undefined) {
      return null;
    }
    return type;
  }

  private shouldIgnoreNonTypingMessage(message: StoredMessage): boolean {
    const type = this.resolveMessageType(message);
    if (type === null) {
      return true;
    }
    return (
      type === MESSAGE_TYPE.TYPING_START ||
      type === MESSAGE_TYPE.TYPING_END ||
      type === MESSAGE_TYPE.NOTIFICATION ||
      type === MESSAGE_TYPE.CHAT_INFO
    );
  }

  private async handleNonTypingMessage(message: StoredMessage): Promise<void> {
    const convId = message.conv_id;
    if (!isNonEmptyString(convId)) {
      return;
    }

    if (this.shouldIgnoreNonTypingMessage(message)) {
      return;
    }

    const hasUser = await this.ensureCurrentUser();
    if (!hasUser) {
      logger.warn('Dropping message event without current user', { conv_id: convId });
      return;
    }

    const toQiaoId = message.to_qiao_id ?? '';
    const fromQiaoId = message.from_qiao_id ?? '';
    if (!isNonEmptyString(toQiaoId) || !isNonEmptyString(fromQiaoId)) {
      return;
    }

    if (toQiaoId !== this.currentUserId) {
      return;
    }
    if (fromQiaoId === this.currentUserId) {
      return;
    }

    const state = this.getState(convId);
    state.lastNonTypingActivityAtMs = Date.now();
    this.setTypingState(convId, false, { clearExpires: true });
  }
}

const conversationPresenceStore = new ConversationPresenceStore();
export default conversationPresenceStore;
