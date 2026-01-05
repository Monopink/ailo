import { requestValidated } from '../api';
import { getLogger } from '../logger';
import { ConversationConfigSchema } from '../schemas';

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
      const stored = wx.getStorageSync<ConversationState>(STORAGE_KEY);
      if (stored && stored.im_conv_id && stored.signature_algorithm) {
        this.state = stored;
      }
    } catch (error) {
      logger.warn('Failed to load conversation state from storage', { error });
    }
  }

  private persist(state: ConversationState): void {
    try {
      wx.setStorageSync(STORAGE_KEY, state);
    } catch (error) {
      logger.warn('Failed to persist conversation state', { error });
    }
  }

  private notify(state: ConversationState | null): void {
    this.subscribers.forEach((callback) => {
      try {
        callback(state);
      } catch (error) {
        logger.error('ConversationStore subscriber error', { error });
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
    if (this.state && !force) {
      return this.state;
    }

    if (!this.initializing) {
      this.initializing = (async () => {
        this.loadFromStorage();
        if (!this.state || force) {
          await this.refresh();
        }
        return this.state;
      })().finally(() => {
        this.initializing = null;
      });
    }

    return this.initializing;
  }

  async getState(): Promise<ConversationState | null> {
    if (this.state) {
      return this.state;
    }
    await this.init();
    return this.state;
  }

  async getImConvId(): Promise<string> {
    const state = await this.getState();
    return state ? state.im_conv_id : '';
  }

  async refresh(): Promise<ConversationState> {
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = (async () => {
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

    return this.refreshPromise;
  }
}

export default new ConversationStore();
