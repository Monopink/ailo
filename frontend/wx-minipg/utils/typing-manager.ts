/**
 * Typing Manager
 * Manages typing state and sends typing indicators
 */

import { MESSAGE_TYPE } from './constants/message';
import { getLogger } from './logger';
import { MESSAGE_CONFIG } from './config';
import { getContactByConvId, getUserInfo as getStoredUserInfo } from './storage';

const logger = getLogger('TypingManager');

type TypingStatus = 'idle' | 'typing';

interface TypingState {
  status: TypingStatus;
  lastSendTime: number;
  timer: ReturnType<typeof setTimeout> | null;
  isComposing: boolean;
}

interface MessageService {
  sendMessage(payload: Partial<Ailo.MessagePayload>): Promise<void>;
}

class TypingManager {
  private typingStates = new Map<string, TypingState>();

  private getState(convId: string): TypingState {
    if (!this.typingStates.has(convId)) {
      this.typingStates.set(convId, {
        status: 'idle',
        lastSendTime: 0,
        timer: null,
        isComposing: false,
      });
    }
    return this.typingStates.get(convId)!;
  }

  /**
   * Handle composition start (input method starts)
   */
  onCompositionStart(convId: string, currentValue: string): void {
    const state = this.getState(convId);
    state.isComposing = true;

    if (!currentValue || currentValue.length === 0) {
      this.sendTypingStartDebounced(convId);
    }
  }

  /**
   * Handle composition end (input method ends)
   */
  onCompositionEnd(convId: string, currentValue: string): void {
    const state = this.getState(convId);
    state.isComposing = false;

    if (!currentValue || currentValue.length === 0) {
      void this.sendTypingEnd(convId);
    }
  }

  /**
   * Handle input change
   */
  onInputChange(convId: string, newValue: string, oldValue: string): void {
    const state = this.getState(convId);

    if (oldValue && oldValue.length > 0 && (!newValue || newValue.length === 0)) {
      void this.sendTypingEnd(convId);
    } else if (
      (!oldValue || oldValue.length === 0) &&
      newValue &&
      newValue.length > 0 &&
      !state.isComposing
    ) {
      this.sendTypingStartDebounced(convId);
    }
  }

  /**
   * Handle input focus
   */
  onInputFocus(convId: string, currentValue: string): void {
    if (currentValue && currentValue.length > 0) {
      this.sendTypingStartDebounced(convId);
    }
  }

  /**
   * Handle input blur
   */
  onInputBlur(convId: string): void {
    void this.sendTypingEnd(convId);
  }

  /**
   * Send typing start with debounce
   */
  sendTypingStartDebounced(convId: string): void {
    const state = this.getState(convId);

    if (state.status === 'typing') {
      return;
    }

    const now = Date.now();
    const timeSinceLastSend = now - state.lastSendTime;

    // If within debounce delay, schedule for later
    if (timeSinceLastSend < MESSAGE_CONFIG.typingDebounce) {
      if (state.timer) {
        clearTimeout(state.timer);
      }
      state.timer = setTimeout(() => {
        void this.sendTypingStart(convId);
      }, MESSAGE_CONFIG.typingDebounce - timeSinceLastSend);
      return;
    }

    // Send immediately
    void this.sendTypingStart(convId);
  }

  /**
   * Send typing start message
   */
  async sendTypingStart(convId: string): Promise<void> {
    const state = this.getState(convId);

    try {
      const app = getApp<AppInstance>();
      const messageService = app.getMessageService() as MessageService | null;

      if (!messageService) {
        logger.warn('Message service not available for typing indicator');
        return;
      }

      const contact = await getContactByConvId(convId);
      if (!contact) {
        logger.warn('Contact not found for typing indicator', { convId });
        return;
      }
      const contactQiaoId = contact.contact_qiao_id;
      if (!contactQiaoId) {
        logger.warn('Contact lacks qiao id for typing indicator', { convId });
        return;
      }

      const userInfo = await getStoredUserInfo();
      if (!userInfo) {
        logger.warn('User info not found for typing indicator');
        return;
      }

      await messageService.sendMessage({
        from: userInfo.qiao_id,
        to: contactQiaoId,
        conv_id: convId,
        content: '',
        message_type: MESSAGE_TYPE.TYPING_START,
        supports_typing: true,
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
  async sendTypingEnd(convId: string): Promise<void> {
    const state = this.getState(convId);

    if (state.status !== 'typing') {
      return;
    }

    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }

    try {
      const app = getApp<AppInstance>();
      const messageService = app.getMessageService() as MessageService | null;

      if (!messageService) {
        logger.warn('Message service not available for typing indicator');
        return;
      }

      const contact = await getContactByConvId(convId);
      if (!contact) {
        logger.warn('Contact not found for typing indicator', { convId });
        return;
      }
      const contactQiaoId = contact.contact_qiao_id;
      if (!contactQiaoId) {
        logger.warn('Contact lacks qiao id for typing indicator', { convId });
        return;
      }

      const userInfo = await getStoredUserInfo();
      if (!userInfo) {
        logger.warn('User info not found for typing indicator');
        return;
      }

      await messageService.sendMessage({
        from: userInfo.qiao_id,
        to: contactQiaoId,
        conv_id: convId,
        content: '',
        message_type: MESSAGE_TYPE.TYPING_END,
        supports_typing: true,
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
  forceStopTyping(convId: string): void {
    const state = this.getState(convId);

    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }

    state.status = 'idle';
    state.isComposing = false;
  }

  /**
   * Clean up typing state for a conversation
   */
  cleanup(convId: string): void {
    const state = this.typingStates.get(convId);
    if (state?.timer) {
      clearTimeout(state.timer);
    }
    this.typingStates.delete(convId);
  }
}

export default new TypingManager();
