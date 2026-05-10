import { getLogger } from '../logger';
import { isNonEmptyString } from '../guards';
import { normalizeError } from '../errors';
import { bootstrapMessageSession } from '../message-signature';

const logger = getLogger('ConversationStore');
const STORAGE_KEY = 'message_session_state';
const WS_TICKET_REFRESH_SKEW_MS = 15_000;

type MessageSessionState = {
  config_version: string;
  session: {
    client_id: string;
    provider: string;
    server_url: string;
    session_hint: string;
    auth: {
      scheme: string;
      version: string;
      ws_ticket: string;
      issued_at_ms: number;
      device_id: string;
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
        isNonEmptyString(stored.session.session_hint) &&
        isNonEmptyString(stored.session.provider) &&
        isNonEmptyString(stored.session.server_url) &&
        isNonEmptyString(stored.session.auth.ws_ticket)
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

  async getSessionHint(): Promise<string> {
    const state = await this.getState();
    if (state === null) {
      return '';
    }
    return state.session.session_hint;
  }

  async getConnectPayload(): Promise<{
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
  }> {
    const state = await this.resolveStateForConnect();
    return {
      userId: state.session.client_id,
      provider: state.session.provider,
      serverUrl: state.session.server_url,
      sessionHint: state.session.session_hint,
      auth: {
        wsTicket: state.session.auth.ws_ticket,
        issuedAtMs: state.session.auth.issued_at_ms,
        deviceId: state.session.auth.device_id,
      },
      configVersion: state.config_version,
    };
  }

  private shouldRefreshTicket(state: MessageSessionState, nowMs: number): boolean {
    const auth = state.session.auth;
    if (!isNonEmptyString(auth.ws_ticket)) {
      return true;
    }
    if (!Number.isFinite(auth.issued_at_ms) || !Number.isFinite(auth.expires_in_ms)) {
      return true;
    }
    const expiresAtMs = auth.issued_at_ms + auth.expires_in_ms;
    const refreshAtMs = expiresAtMs - WS_TICKET_REFRESH_SKEW_MS;
    return nowMs >= refreshAtMs;
  }

  private async resolveStateForConnect(): Promise<MessageSessionState> {
    const nowMs = Date.now();
    const current = this.state;
    if (current !== null && !this.shouldRefreshTicket(current, nowMs)) {
      return current;
    }

    try {
      return await this.refresh();
    } catch (error: unknown) {
      const err = normalizeError(error);
      if (current !== null && !this.shouldRefreshTicket(current, nowMs)) {
        logger.warn('Message session refresh failed, fallback to cached ticket', {
          errorMessage: err.message,
          config_version: current.config_version,
        });
        return current;
      }
      throw err;
    }
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
        session_hint: response.session.session_hint,
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
