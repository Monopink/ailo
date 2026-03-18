import { isNonEmptyString } from '../guards';
import { getLogger } from '../logger';
import { normalizeError } from '../errors';
import {
  clearConversationViewPosition,
  getConversationViewPosition,
  setConversationViewPosition,
} from '../storage';

const logger = getLogger('ViewStore');

export interface ConversationViewPosition {
  lastViewedMsgId?: string;
  isAtBottom: boolean;
  updatedAt: number;
}

const viewStore = {
  async get(convId: string): Promise<ConversationViewPosition | null> {
    if (!isNonEmptyString(convId)) {
      return null;
    }
    try {
      const stored = await getConversationViewPosition(convId);
      if (stored === null) {
        return null;
      }
      return {
        lastViewedMsgId: stored.last_viewed_msg_id,
        isAtBottom: stored.is_at_bottom,
        updatedAt: stored.updated_at,
      };
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.warn('Failed to read conversation view state', { convId, error: err.message });
      return null;
    }
  },

  async set(
    convId: string,
    payload: { lastViewedMsgId?: string; isAtBottom: boolean }
  ): Promise<void> {
    if (!isNonEmptyString(convId)) {
      return;
    }
    try {
      await setConversationViewPosition(convId, {
        last_viewed_msg_id: payload.lastViewedMsgId,
        is_at_bottom: payload.isAtBottom,
      });
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.warn('Failed to persist conversation view state', { convId, error: err.message });
    }
  },

  async clear(convId: string): Promise<void> {
    if (!isNonEmptyString(convId)) {
      return;
    }
    try {
      await clearConversationViewPosition(convId);
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.warn('Failed to clear conversation view state', { convId, error: err.message });
    }
  },
};

export default viewStore;
