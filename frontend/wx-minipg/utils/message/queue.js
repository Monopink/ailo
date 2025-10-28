/**
 * Message Queue
 * Manages message sending queue with retry mechanism
 */

import { getLogger } from '../logger';
import { MESSAGE_CONFIG } from '../config';
import { updateMessage } from '../storage';

const logger = getLogger('MessageQueue');

/**
 * Message queue class
 */
export class MessageQueue {
  constructor(provider) {
    this.provider = provider;
    this.queue = [];
    this.processing = false;
    this.rateLimitCount = 0;
    this.rateLimitResetTime = 0;
  }

  /**
   * Add message to queue
   * @param {Object} message - Message object
   * @returns {Promise<void>}
   */
  async add(message) {
    logger.debug('Adding message to queue', { messageId: message.id });

    this.queue.push(message);
    await this.process();
  }

  /**
   * Process message queue
   * @returns {Promise<void>}
   */
  async process() {
    if (this.processing) {
      logger.debug('Queue already processing');
      return;
    }

    this.processing = true;

    while (this.queue.length > 0) {
      const message = this.queue[0];

      try {
        // Check rate limit
        if (!this.checkRateLimit()) {
          logger.warn('Rate limit exceeded, waiting...');
          await this.waitForRateLimit();
          continue;
        }

        // Send message
        await this.sendMessage(message);

        // Remove from queue
        this.queue.shift();

        // Increment rate limit counter
        this.incrementRateLimit();
      } catch (error) {
        logger.error('Send message failed', { messageId: message.id, error });

        // Increment retry count
        message.retryCount = (message.retryCount || 0) + 1;

        // Check if max retries reached
        if (message.retryCount >= MESSAGE_CONFIG.maxRetryCount) {
          logger.error('Max retries reached', { messageId: message.id });

          // Mark as failed
          message.status = 'failed';
          await updateMessage(message.convId, message.id, { status: 'failed' });

          // Remove from queue
          this.queue.shift();
        } else {
          // Wait before retry
          await this.sleep(MESSAGE_CONFIG.retryDelay);
        }
      }
    }

    this.processing = false;
  }

  /**
   * Send message
   * @param {Object} message - Message object
   * @returns {Promise<void>}
   */
  async sendMessage(message) {
    logger.debug('Sending message', { messageId: message.id });

    // Send via provider
    const sentMessage = await this.provider.sendMessage(
      message.convId,
      message.content,
      message.type
    );

    // Update message with sent data
    message.id = sentMessage.id;
    message.timestamp = sentMessage.timestamp;
    message.status = 'sent';

    // Update in storage
    await updateMessage(message.convId, message.id, {
      id: sentMessage.id,
      timestamp: sentMessage.timestamp,
      status: 'sent'
    });

    logger.info('Message sent', { messageId: message.id });
  }

  /**
   * Check rate limit
   * @returns {boolean} True if within rate limit
   */
  checkRateLimit() {
    const now = Date.now();

    // Reset counter if window expired
    if (now >= this.rateLimitResetTime) {
      this.rateLimitCount = 0;
      this.rateLimitResetTime = now + MESSAGE_CONFIG.rateLimitWindow;
    }

    return this.rateLimitCount < MESSAGE_CONFIG.rateLimit;
  }

  /**
   * Increment rate limit counter
   */
  incrementRateLimit() {
    this.rateLimitCount++;
  }

  /**
   * Wait for rate limit to reset
   * @returns {Promise<void>}
   */
  async waitForRateLimit() {
    const now = Date.now();
    const waitTime = this.rateLimitResetTime - now;

    if (waitTime > 0) {
      await this.sleep(waitTime);
    }

    // Reset counter
    this.rateLimitCount = 0;
    this.rateLimitResetTime = Date.now() + MESSAGE_CONFIG.rateLimitWindow;
  }

  /**
   * Sleep for specified time
   * @param {number} ms - Milliseconds to sleep
   * @returns {Promise<void>}
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Get queue length
   * @returns {number} Queue length
   */
  getLength() {
    return this.queue.length;
  }

  /**
   * Clear queue
   */
  clear() {
    this.queue = [];
    this.processing = false;
    logger.info('Queue cleared');
  }
}

export default MessageQueue;

