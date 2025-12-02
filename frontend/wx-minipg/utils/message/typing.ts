/**
 * Typing Manager
 * Manages typing indicator state with debounce and timeout
 */

import { getLogger } from '../logger';
import { MESSAGE_CONFIG } from '../config';
import { MESSAGE_TYPES } from './provider/base';

const logger = getLogger('TypingManager');

/**
 * Typing manager class
 */
export class TypingManager {
  constructor(messageService) {
    this.messageService = messageService;
    this.typingStates = new Map(); // convId -> { isTyping, timer, timeout }
    this.debounceTimers = new Map(); // convId -> timer
  }

  /**
   * Handle input change
   * @param {string} convId - Conversation ID
   * @param {string} text - Input text
   * @param {boolean} isComposing - Whether composing (IME active)
   */
  handleInput(convId, text, isComposing = false) {
    // Don't send typing indicator during composition
    if (isComposing) {
      return;
    }

    // Clear existing debounce timer
    if (this.debounceTimers.has(convId)) {
      clearTimeout(this.debounceTimers.get(convId));
    }

    // If text is empty, stop typing
    if (!text || text.trim().length === 0) {
      this.stopTyping(convId);
      return;
    }

    // Set debounce timer
    const timer = setTimeout(() => {
      this.startTyping(convId);
    }, MESSAGE_CONFIG.typingDebounce);

    this.debounceTimers.set(convId, timer);
  }

  /**
   * Start typing indicator
   * @param {string} convId - Conversation ID
   */
  async startTyping(convId) {
    try {
      const state = this.typingStates.get(convId);

      // If already typing, just reset timeout
      if (state && state.isTyping) {
        this.resetTimeout(convId);
        return;
      }

      logger.debug('Start typing', { convId });

      // Send typing start message
      await this.messageService.sendMessage(
        convId,
        '',
        MESSAGE_TYPES.TYPING_START
      );

      // Set typing state
      const timeout = setTimeout(() => {
        this.stopTyping(convId);
      }, MESSAGE_CONFIG.typingTimeout);

      this.typingStates.set(convId, {
        isTyping: true,
        timeout
      });
    } catch (error) {
      logger.error('Start typing failed', { convId, error });
    }
  }

  /**
   * Stop typing indicator
   * @param {string} convId - Conversation ID
   */
  async stopTyping(convId) {
    try {
      const state = this.typingStates.get(convId);

      // If not typing, do nothing
      if (!state || !state.isTyping) {
        return;
      }

      logger.debug('Stop typing', { convId });

      // Clear timeout
      if (state.timeout) {
        clearTimeout(state.timeout);
      }

      // Send typing end message
      await this.messageService.sendMessage(
        convId,
        '',
        MESSAGE_TYPES.TYPING_END
      );

      // Clear typing state
      this.typingStates.delete(convId);
    } catch (error) {
      logger.error('Stop typing failed', { convId, error });
    }
  }

  /**
   * Reset typing timeout
   * @param {string} convId - Conversation ID
   */
  resetTimeout(convId) {
    const state = this.typingStates.get(convId);

    if (!state) {
      return;
    }

    // Clear existing timeout
    if (state.timeout) {
      clearTimeout(state.timeout);
    }

    // Set new timeout
    const timeout = setTimeout(() => {
      this.stopTyping(convId);
    }, MESSAGE_CONFIG.typingTimeout);

    state.timeout = timeout;
  }

  /**
   * Check if typing
   * @param {string} convId - Conversation ID
   * @returns {boolean} True if typing
   */
  isTyping(convId) {
    const state = this.typingStates.get(convId);
    return state ? state.isTyping : false;
  }

  /**
   * Clear all typing states
   */
  clear() {
    // Clear all debounce timers
    this.debounceTimers.forEach(timer => clearTimeout(timer));
    this.debounceTimers.clear();

    // Clear all typing timeouts
    this.typingStates.forEach(state => {
      if (state.timeout) {
        clearTimeout(state.timeout);
      }
    });
    this.typingStates.clear();

    logger.info('Typing states cleared');
  }
}

export default TypingManager;

