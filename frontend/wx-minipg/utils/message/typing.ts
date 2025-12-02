import { getLogger } from '../logger';
import { MESSAGE_CONFIG } from '../config';
import { MESSAGE_TYPE } from './constants';

const logger = getLogger('TypingManager');

interface TypingState {
  isTyping: boolean;
  timeout: ReturnType<typeof setTimeout> | null;
}

interface TypingManagerOptions {
  typingDebounce?: number;
  typingTimeout?: number;
}

interface MessageService {
  sendMessage(convId: string, content: string, type: number): Promise<void>;
}

export class TypingManager {
  private messageService: MessageService;
  private typingStates = new Map<string, TypingState>();
  private debounceTimers = new Map<string, ReturnType<typeof setTimeout>>();
  private debounceDelay: number;
  private typingTimeout: number;

  constructor(messageService: MessageService, options: TypingManagerOptions = {}) {
    this.messageService = messageService;
    this.debounceDelay = options.typingDebounce ?? MESSAGE_CONFIG.typingDebounce;
    this.typingTimeout = options.typingTimeout ?? MESSAGE_CONFIG.typingTimeout;
  }

  handleInput(convId: string, text: string, isComposing = false): void {
    if (isComposing) {
      return;
    }

    const existingTimer = this.debounceTimers.get(convId);
    if (existingTimer) {
      clearTimeout(existingTimer);
    }

    if (!text || text.trim().length === 0) {
      void this.stopTyping(convId);
      return;
    }

    const timer = setTimeout(() => {
      void this.startTyping(convId);
    }, this.debounceDelay);

    this.debounceTimers.set(convId, timer);
  }

  private async startTyping(convId: string): Promise<void> {
    try {
      const state = this.typingStates.get(convId);
      if (state?.isTyping) {
        this.resetTimeout(convId);
        return;
      }

      logger.debug('Start typing', { convId });
      await this.messageService.sendMessage(convId, '', MESSAGE_TYPE.TYPING_START);

      const timeout = setTimeout(() => {
        void this.stopTyping(convId);
      }, this.typingTimeout);

      this.typingStates.set(convId, {
        isTyping: true,
        timeout,
      });
    } catch (error) {
      logger.error('Start typing failed', { convId, error });
    }
  }

  async stopTyping(convId: string): Promise<void> {
    try {
      const state = this.typingStates.get(convId);
      if (!state?.isTyping) {
        return;
      }

      logger.debug('Stop typing', { convId });
      if (state.timeout) {
        clearTimeout(state.timeout);
      }

      await this.messageService.sendMessage(convId, '', MESSAGE_TYPE.TYPING_END);
      this.typingStates.delete(convId);
    } catch (error) {
      logger.error('Stop typing failed', { convId, error });
    }
  }

  private resetTimeout(convId: string): void {
    const state = this.typingStates.get(convId);
    if (!state) {
      return;
    }

    if (state.timeout) {
      clearTimeout(state.timeout);
    }

    state.timeout = setTimeout(() => {
      void this.stopTyping(convId);
    }, this.typingTimeout);
  }

  isTyping(convId: string): boolean {
    return Boolean(this.typingStates.get(convId)?.isTyping);
  }

  clear(): void {
    this.debounceTimers.forEach((timer) => clearTimeout(timer));
    this.debounceTimers.clear();

    this.typingStates.forEach((state) => {
      if (state.timeout) {
        clearTimeout(state.timeout);
      }
    });
    this.typingStates.clear();

    logger.info('Typing states cleared');
  }
}

export default TypingManager;
