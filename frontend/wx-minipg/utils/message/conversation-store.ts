import { requestValidated } from '../api';
import { getLogger } from '../logger';
import { ConversationConfigSchema } from '../schemas';
import { isNonEmptyString } from '../guards';
import { normalizeError } from '../errors';

const logger = getLogger('ConversationStore');
const STORAGE_KEY = 'conversation_state';

interface ConversationState {
  im_conv_id: string;
  signature_algorithm: string;
  signature_version: string;
  signature_ttl_ms: number;
  fetched_at: number;
}

type Subscriber = (state: ConversationState | null) => void;

class ConversationStore {
  private state: ConversationState | null = null;
  private subscribers = new Set<Subscriber>();
  private initializing: Promise<ConversationState | null> | null = null;
  private refreshPromise: Promise<ConversationState> | null = null;

  constructor() {
    this.loadFromStorage();
  }

  private loadFromStorage(): void {
    try {
      const stored = wx.getStorageSync<ConversationState | null | undefined>(STORAGE_KEY);
      if (
        stored !== null &&
        stored !== undefined &&
        isNonEmptyString(stored.im_conv_id) &&
        isNonEmptyString(stored.signature_algorithm)
      ) {
        this.state = stored;
      }
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.warn('Failed to load conversation state from storage', {
        errorMessage: err.message,
      });
    }
  }

  private persist(state: ConversationState): void {
    try {
      wx.setStorageSync(STORAGE_KEY, state);
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.warn('Failed to persist conversation state', {
        errorMessage: err.message,
      });
    }
  }

  private notify(state: ConversationState | null): void {
    this.subscribers.forEach((callback) => {
      try {
        callback(state);
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.error('ConversationStore subscriber error', {
          errorMessage: err.message,
        });
      }
    });
  }

  subscribe(callback: Subscriber): () => void {
    this.subscribers.add(callback);
    callback(this.state);
    return () => {
      this.subscribers.delete(callback);
    };
  }

  async init(force = false): Promise<ConversationState | null> {
    if (this.state !== null && !force) {
      return this.state;
    }

    if (this.initializing === null) {
      const initializing = (async () => {
        this.loadFromStorage();
        if (this.state === null || force) {
          await this.refresh();
        }
        return this.state;
      })().finally(() => {
        this.initializing = null;
      });
      this.initializing = initializing;
    }

    return this.initializing;
  }

  async getState(): Promise<ConversationState | null> {
    if (this.state !== null) {
      return this.state;
    }
    await this.init();
    return this.state;
  }

  async getImConvId(): Promise<string> {
    const state = await this.getState();
    if (state === null) {
      return '';
    }
    return state.im_conv_id;
  }

  async refresh(): Promise<ConversationState> {
    if (this.refreshPromise !== null) {
      return this.refreshPromise;
    }

    const refreshing = (async () => {
      const response = await requestValidated(ConversationConfigSchema, {
        url: '/lc-im/config',
        method: 'GET',
      });
      const nextState: ConversationState = {
        im_conv_id: response.im_conv_id,
        signature_algorithm: response.signature_algorithm,
        signature_version: response.signature_version,
        signature_ttl_ms: response.signature_ttl_ms,
        fetched_at: Date.now(),
      };
      this.state = nextState;
      this.persist(nextState);
      this.notify(nextState);
      logger.info('Conversation state refreshed', {
        signature_version: response.signature_version,
        im_conv_id: response.im_conv_id,
      });
      return nextState;
    })().finally(() => {
      this.refreshPromise = null;
    });

    this.refreshPromise = refreshing;
    return refreshing;
  }
}

export default new ConversationStore();
