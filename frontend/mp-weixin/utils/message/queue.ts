import { getLogger } from '../logger';
import { MESSAGE_CONFIG } from '../config';
import type { AdapterSendResult, BusinessMessagePayload, MessageAdapter } from './adapter-types';
import { isDefined } from '../guards';

const logger = getLogger('MessageQueue');

interface QueueMessage {
  payload: BusinessMessagePayload;
  sessionHint: string;
  status?: 'pending' | 'sent' | 'failed';
  retryCount?: number;
}

interface MessageProvider {
  sendMessage(message: BusinessMessagePayload, sessionHint: string): Promise<AdapterSendResult>;
}

export class MessageQueue {
  private provider: MessageProvider;
  private queue: QueueMessage[] = [];
  private processing = false;
  private rateLimitCount = 0;
  private rateLimitResetTime = 0;

  constructor(provider: MessageAdapter) {
    this.provider = provider;
  }

  async add(message: QueueMessage): Promise<void> {
    logger.debug('Adding message to queue', { messageId: message.payload.msg_id });
    this.queue.push(message);
    await this.process();
  }

  async process(): Promise<void> {
    if (this.processing) {
      logger.debug('Queue already processing');
      return;
    }

    this.processing = true;
    await this.processNext();
  }

  private async processNext(): Promise<void> {
    const message = this.queue[0];

    if (!isDefined(message)) {
      this.processing = false;
      return;
    }

    try {
      if (!this.checkRateLimit()) {
        logger.warn('Rate limit exceeded, waiting...');
        await this.waitForRateLimit();
        await this.processNext();
        return;
      }

      await this.sendMessage(message);
      this.queue.shift();
      this.incrementRateLimit();
      await this.processNext();
    } catch (error) {
      logger.error('Send message failed', { messageId: message.payload.msg_id, error });
      const retries = (message.retryCount ?? 0) + 1;
      message.retryCount = retries;

      if (retries >= MESSAGE_CONFIG.maxRetryCount) {
        logger.error('Max retries reached', { messageId: message.payload.msg_id });
        message.status = 'failed';
        this.queue.shift();
        await this.processNext();
      } else {
        await this.sleep(MESSAGE_CONFIG.retryDelay);
        await this.processNext();
      }
    }
  }

  private sendMessage(message: QueueMessage): Promise<void> {
    const messageId = message.payload.msg_id;
    logger.debug('Sending message', { messageId });
    return this.provider.sendMessage(message.payload, message.sessionHint).then(() => {
      message.status = 'sent';
      logger.info('Message sent', { messageId });
    });
  }

  private checkRateLimit(): boolean {
    const now = Date.now();
    if (now >= this.rateLimitResetTime) {
      this.rateLimitCount = 0;
      this.rateLimitResetTime = now + MESSAGE_CONFIG.rateLimitWindow;
    }
    return this.rateLimitCount < MESSAGE_CONFIG.rateLimit;
  }

  private incrementRateLimit(): void {
    this.rateLimitCount += 1;
  }

  private async waitForRateLimit(): Promise<void> {
    const now = Date.now();
    const waitTime = this.rateLimitResetTime - now;
    if (waitTime > 0) {
      await this.sleep(waitTime);
    }
    this.rateLimitCount = 0;
    this.rateLimitResetTime = Date.now() + MESSAGE_CONFIG.rateLimitWindow;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  getLength(): number {
    return this.queue.length;
  }

  clear(): void {
    this.queue = [];
    this.processing = false;
    logger.info('Queue cleared');
  }
}

export default MessageQueue;
