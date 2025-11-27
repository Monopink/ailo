/**
 * Conversation Store
 * Single source of truth for IM provider conversation identifiers.
 */

import { get } from '../api';
import { getLogger } from '../logger';

const STORAGE_KEY = 'conversation_state';

class ConversationStore {
  constructor() {
    this.state = null;
    this.subscribers = new Set();
    this.initializing = null;
    this.refreshPromise = null;
  }

  /**
   * Load cached state from storage.
   */
  loadFromStorage() {
    try {
      const stored = wx.getStorageSync(STORAGE_KEY);
      if (stored && stored.im_conv_id && stored.version) {
        this.state = stored;
      }
    } catch (error) {
      logger.warn('Failed to load conversation state from storage', { error });
    }
  }

  /**
   * Persist state to storage.
   */
  persist(state) {
    try {
      wx.setStorageSync(STORAGE_KEY, state);
    } catch (error) {
      logger.warn('Failed to persist conversation state', { error });
    }
  }

  notify(state) {
    this.subscribers.forEach(callback => {
      try {
        callback(state);
      } catch (error) {
        logger.error('ConversationStore subscriber error', { error });
      }
    });
  }

  subscribe(callback) {
    if (typeof callback === 'function') {
      this.subscribers.add(callback);
      if (this.state) {
        callback(this.state);
      }
    }
    return () => {
      this.subscribers.delete(callback);
    };
  }

  async init(force = false) {
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

  async getState() {
    if (this.state) {
      return this.state;
    }
    await this.init();
    return this.state;
  }

  async getImConvId() {
    const state = await this.getState();
    return state ? state.im_conv_id : '';
  }

  async refresh() {
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = (async () => {
      const response = await get('/conversation/current');
      const nextState = {
        im_conv_id: response.im_conv_id,
        version: response.version,
        updated_at: response.updated_at || null
      };
      this.state = nextState;
      this.persist(nextState);
      this.notify(nextState);
      logger.info('Conversation state refreshed', {
        version: response.version,
        updated_at: response.updated_at
      });
      return nextState;
    })().finally(() => {
      this.refreshPromise = null;
    });

    return this.refreshPromise;
  }
}

const logger = getLogger('ConversationStore');

const conversationStore = new ConversationStore();

export default conversationStore;
