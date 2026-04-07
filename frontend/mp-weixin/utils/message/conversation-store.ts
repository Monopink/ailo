import { getLogger } from '../logger';
import { isNonEmptyString } from '../guards';
import { normalizeError } from '../errors';
import { bootstrapMessageSession } from '../message-signature';

const logger = getLogger('ConversationStore');
const STORAGE_KEY = 'message_session_state';

type MessageSessionState = {
  config_version: string;
  session: {
    client_id: string;
    app_id: string;
    app_key: string;
    server_url: string;
    im_conv_id: string;
    signature: {
      algorithm: string;
      version: string;
      value: string;
      timestamp: number;
      nonce: string;
      expires_in_ms: number;
    };
  };
  presence: {
    endpoint_id: number;
    lease_ttl_days: number;
    lease_expires_at_ms: number;
  };
  fetched_at: number;
};

type Subscriber = (state: MessageSessionState | null) => void;

class ConversationStore {
  private state: MessageSessionState | null = null;
  private subscribers = new Set<Subscriber>();
  private initializing: Promise<MessageSessionState | null> | null = null;
  private refreshPromise: Promise<MessageSessionState> | null = null;

  constructor() {
    this.loadFromStorage();
  }

  private loadFromStorage(): void {
    try {
      const stored = wx.getStorageSync<MessageSessionState | null | undefined>(STORAGE_KEY);
      if (
        stored !== null &&
        stored !== undefined &&
        isNonEmptyString(stored.config_version) &&
        isNonEmptyString(stored.session.im_conv_id) &&
        isNonEmptyString(stored.session.app_id) &&
        isNonEmptyString(stored.session.app_key) &&
        isNonEmptyString(stored.session.server_url) &&
        isNonEmptyString(stored.session.signature.value)
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

  private persist(state: MessageSessionState): void {
    try {
      wx.setStorageSync(STORAGE_KEY, state);
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.warn('Failed to persist conversation state', {
        errorMessage: err.message,
      });
    }
  }

  private notify(state: MessageSessionState | null): void {
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

  async init(force = false): Promise<MessageSessionState | null> {
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

  async getState(): Promise<MessageSessionState | null> {
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
    return state.session.im_conv_id;
  }

  async getConnectPayload(): Promise<{
    userId: string;
    appId: string;
    appKey: string;
    serverUrl: string;
    imConvId: string;
    signature: {
      signature: string;
      timestamp: number;
      nonce: string;
    };
    configVersion: string;
  }> {
    const state = await this.refresh();
    return {
      userId: state.session.client_id,
      appId: state.session.app_id,
      appKey: state.session.app_key,
      serverUrl: state.session.server_url,
      imConvId: state.session.im_conv_id,
      signature: {
        signature: state.session.signature.value,
        timestamp: state.session.signature.timestamp,
        nonce: state.session.signature.nonce,
      },
      configVersion: state.config_version,
    };
  }

  async refresh(): Promise<MessageSessionState> {
    if (this.refreshPromise !== null) {
      return this.refreshPromise;
    }

    const refreshing = (async () => {
      const response = await bootstrapMessageSession();
      const nextState: MessageSessionState = {
        config_version: response.config_version,
        session: response.session,
        presence: response.presence,
        fetched_at: Date.now(),
      };
      this.state = nextState;
      this.persist(nextState);
      this.notify(nextState);
      logger.info('Message session refreshed', {
        config_version: response.config_version,
        im_conv_id: response.session.im_conv_id,
        client_id: response.session.client_id,
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
