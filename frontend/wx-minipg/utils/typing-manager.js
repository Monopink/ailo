/**
 * Typing Manager
 * Manages typing state and sends typing indicators
 */

import { MESSAGE_TYPE } from './message/constants';
import logger from './logger';

const DEBOUNCE_DELAY = 1000; // 1 second debounce

class TypingManager {
  constructor() {
    // Map of convId -> typing state
    this.typingStates = new Map();
  }

  /**
   * Get or create typing state for a conversation
   */
  getState(convId) {
    if (!this.typingStates.has(convId)) {
      this.typingStates.set(convId, {
        status: 'idle', // 'idle' | 'typing'
        lastSendTime: 0,
        timer: null,
        isComposing: false // Input method composing state
      });
    }
    return this.typingStates.get(convId);
  }

  /**
   * Handle composition start (input method starts)
   */
  onCompositionStart(convId, currentValue) {
    const state = this.getState(convId);
    state.isComposing = true;

    // If input is empty, send typing start
    if (!currentValue || currentValue.length === 0) {
      this.sendTypingStartDebounced(convId);
    }
  }

  /**
   * Handle composition end (input method ends)
   */
  onCompositionEnd(convId, currentValue) {
    const state = this.getState(convId);
    state.isComposing = false;

    // If input is still empty after composition, send typing end
    if (!currentValue || currentValue.length === 0) {
      this.sendTypingEnd(convId);
    }
  }

  /**
   * Handle input change
   */
  onInputChange(convId, newValue, oldValue) {
    const state = this.getState(convId);

    // If changed from non-empty to empty, send typing end
    if (oldValue && oldValue.length > 0 && (!newValue || newValue.length === 0)) {
      this.sendTypingEnd(convId);
    }
    // If changed from empty to non-empty and not composing, send typing start
    else if ((!oldValue || oldValue.length === 0) && newValue && newValue.length > 0 && !state.isComposing) {
      this.sendTypingStartDebounced(convId);
    }
  }

  /**
   * Handle input focus
   */
  onInputFocus(convId, currentValue) {
    // If input has content, send typing start
    if (currentValue && currentValue.length > 0) {
      this.sendTypingStartDebounced(convId);
    }
  }

  /**
   * Handle input blur
   */
  onInputBlur(convId) {
    // Always send typing end when input loses focus
    this.sendTypingEnd(convId);
  }

  /**
   * Send typing start with debounce
   */
  sendTypingStartDebounced(convId) {
    const state = this.getState(convId);

    // If already typing, do nothing
    if (state.status === 'typing') {
      return;
    }

    const now = Date.now();
    const timeSinceLastSend = now - state.lastSendTime;

    // If within debounce delay, schedule for later
    if (timeSinceLastSend < DEBOUNCE_DELAY) {
      if (state.timer) {
        clearTimeout(state.timer);
      }
      state.timer = setTimeout(() => {
        this.sendTypingStart(convId);
      }, DEBOUNCE_DELAY - timeSinceLastSend);
      return;
    }

    // Send immediately
    this.sendTypingStart(convId);
  }

  /**
   * Send typing start message
   */
  async sendTypingStart(convId) {
    const state = this.getState(convId);

    try {
      // Get message service from app
      const app = getApp();
      const messageService = app.getMessageService();

      if (!messageService) {
        logger.warn('Message service not available for typing indicator');
        return;
      }

      // Get contact info
      const contact = await this.getContactByConvId(convId);
      if (!contact) {
        logger.warn('Contact not found for typing indicator', { convId });
        return;
      }

      // Get user info
      const userInfo = await this.getUserInfo();
      if (!userInfo) {
        logger.warn('User info not found for typing indicator');
        return;
      }

      // Send typing start message
      await messageService.sendMessage({
        from: userInfo.qiao_id,
        to: contact.contact_qiao_id,
        conv_id: convId,
        im_conv_id: contact.im_conv_id,
        content: '',
        message_type: MESSAGE_TYPE.TYPING_START,
        supports_typing: true
      });

      state.status = 'typing';
      state.lastSendTime = Date.now();

      logger.debug('Typing start sent', { convId });
    } catch (error) {
      logger.error('Failed to send typing start', { error, convId });
    }
  }

  /**
   * Send typing end message
   */
  async sendTypingEnd(convId) {
    const state = this.getState(convId);

    // If not typing, do nothing
    if (state.status !== 'typing') {
      return;
    }

    // Clear any pending timer
    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }

    try {
      // Get message service from app
      const app = getApp();
      const messageService = app.getMessageService();

      if (!messageService) {
        logger.warn('Message service not available for typing indicator');
        return;
      }

      // Get contact info
      const contact = await this.getContactByConvId(convId);
      if (!contact) {
        logger.warn('Contact not found for typing indicator', { convId });
        return;
      }

      // Get user info
      const userInfo = await this.getUserInfo();
      if (!userInfo) {
        logger.warn('User info not found for typing indicator');
        return;
      }

      // Send typing end message
      await messageService.sendMessage({
        from: userInfo.qiao_id,
        to: contact.contact_qiao_id,
        conv_id: convId,
        im_conv_id: contact.im_conv_id,
        content: '',
        message_type: MESSAGE_TYPE.TYPING_END,
        supports_typing: true
      });

      state.status = 'idle';
      state.lastSendTime = Date.now();

      logger.debug('Typing end sent', { convId });
    } catch (error) {
      logger.error('Failed to send typing end', { error, convId });
    }
  }

  /**
   * Force stop typing state (e.g., when sending message)
   */
  forceStopTyping(convId) {
    const state = this.getState(convId);

    // Clear timer
    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }

    // Reset state
    state.status = 'idle';
    state.isComposing = false;
  }

  /**
   * Clean up typing state for a conversation
   */
  cleanup(convId) {
    const state = this.typingStates.get(convId);
    if (state && state.timer) {
      clearTimeout(state.timer);
    }
    this.typingStates.delete(convId);
  }

  /**
   * Helper: Get contact by convId from storage
   */
  async getContactByConvId(convId) {
    const { getContactByConvId } = require('./storage');
    return await getContactByConvId(convId);
  }

  /**
   * Helper: Get user info from storage
   */
  async getUserInfo() {
    const { getUserInfo } = require('./storage');
    return await getUserInfo();
  }
}

// Export singleton instance
export default new TypingManager();
