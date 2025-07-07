/**
 * Smart Retry Strategy for Message Sending
 * 
 * Implements intelligent retry logic with exponential backoff,
 * error classification, and conversation health awareness.
 */

import { MessageFailureReason, ConversationErrorType } from './types'
import { conversationErrorReporter } from './conversationErrorReporter'

class SmartRetryStrategy {
  constructor() {
    this.retryAttempts = new Map() // messageId -> retry info
    this.conversationHealth = new Map() // conversationId -> health info
    
    // Retry configuration
    this.maxRetries = 3
    this.baseDelayMs = 1000 // 1 second
    this.maxDelayMs = 30000 // 30 seconds
    this.backoffMultiplier = 2
  }

  /**
   * Determine if a message should be retried based on error type and history
   * 
   * @param {string} messageId - Unique message identifier
   * @param {Error} error - The error that occurred
   * @param {number} currentRetryCount - Current number of retries
   * @returns {Object} Retry decision with delay and should retry flag
   */
  shouldRetry(messageId, error, currentRetryCount = 0) {
    const errorType = this._classifyError(error)
    const retryInfo = this.retryAttempts.get(messageId) || {
      attempts: 0,
      lastAttempt: 0,
      errorHistory: []
    }

    // Update retry info
    retryInfo.attempts = currentRetryCount
    retryInfo.lastAttempt = Date.now()
    retryInfo.errorHistory.push({
      error: error.message,
      type: errorType,
      timestamp: Date.now()
    })
    this.retryAttempts.set(messageId, retryInfo)

    // Check if we've exceeded max retries
    if (currentRetryCount >= this.maxRetries) {
      console.log(`❌ Max retries (${this.maxRetries}) exceeded for message ${messageId}`)
      return { shouldRetry: false, delay: 0, reason: 'max_retries_exceeded' }
    }

    // Check if error type is retryable
    if (!this._isRetryableError(errorType)) {
      console.log(`❌ Non-retryable error for message ${messageId}:`, errorType)
      return { shouldRetry: false, delay: 0, reason: 'non_retryable_error' }
    }

    // Calculate delay with exponential backoff
    const delay = this._calculateDelay(currentRetryCount)

    console.log(`🔄 Will retry message ${messageId} in ${delay}ms (attempt ${currentRetryCount + 1}/${this.maxRetries})`)

    return {
      shouldRetry: true,
      delay,
      reason: 'retryable_error',
      errorType
    }
  }

  /**
   * Execute retry with smart delay and error reporting
   * 
   * @param {string} messageId - Message identifier
   * @param {Function} retryFunction - Function to execute for retry
   * @param {Object} retryDecision - Decision from shouldRetry
   * @param {string} conversationId - Conversation ID for error reporting
   * @returns {Promise} Promise that resolves when retry is complete
   */
  async executeRetry(messageId, retryFunction, retryDecision, conversationId) {
    if (!retryDecision.shouldRetry) {
      throw new Error(`Retry not allowed: ${retryDecision.reason}`)
    }

    // Wait for calculated delay
    if (retryDecision.delay > 0) {
      console.log(`⏳ Waiting ${retryDecision.delay}ms before retry...`)
      await this._delay(retryDecision.delay)
    }

    // Report error to backend if it's conversation-related
    if (this._isConversationError(retryDecision.errorType)) {
      const retryInfo = this.retryAttempts.get(messageId)
      const lastError = retryInfo?.errorHistory[retryInfo.errorHistory.length - 1]
      
      await this._reportConversationError(
        conversationId,
        retryDecision.errorType,
        lastError?.error || 'Unknown error',
        retryInfo?.attempts || 0
      )
    }

    // Execute the retry
    try {
      console.log(`🔄 Executing retry for message ${messageId}`)
      const result = await retryFunction()
      
      // Clear retry info on success
      this.retryAttempts.delete(messageId)
      console.log(`✅ Retry successful for message ${messageId}`)
      
      return result
    } catch (error) {
      console.error(`❌ Retry failed for message ${messageId}:`, error)
      throw error
    }
  }

  /**
   * Update conversation health status
   */
  updateConversationHealth(conversationId, isHealthy, errorInfo = null) {
    const health = this.conversationHealth.get(conversationId) || {
      isHealthy: true,
      lastCheck: 0,
      errorCount: 0,
      lastError: null
    }

    health.isHealthy = isHealthy
    health.lastCheck = Date.now()
    
    if (!isHealthy && errorInfo) {
      health.errorCount++
      health.lastError = errorInfo
    } else if (isHealthy) {
      health.errorCount = 0
      health.lastError = null
    }

    this.conversationHealth.set(conversationId, health)
  }

  /**
   * Get conversation health status
   */
  getConversationHealth(conversationId) {
    return this.conversationHealth.get(conversationId) || {
      isHealthy: true,
      lastCheck: 0,
      errorCount: 0,
      lastError: null
    }
  }

  /**
   * Clear retry history for a message
   */
  clearRetryHistory(messageId) {
    this.retryAttempts.delete(messageId)
  }

  /**
   * Get retry statistics
   */
  getRetryStats() {
    const stats = {
      activeRetries: this.retryAttempts.size,
      conversationsTracked: this.conversationHealth.size,
      unhealthyConversations: 0
    }

    for (const health of this.conversationHealth.values()) {
      if (!health.isHealthy) {
        stats.unhealthyConversations++
      }
    }

    return stats
  }

  // Private methods

  /**
   * Classify error type based on error message
   */
  _classifyError(error) {
    const message = error.message.toLowerCase()

    if (message.includes('conversation') && message.includes('not found')) {
      return ConversationErrorType.CONVERSATION_NOT_FOUND
    }
    if (message.includes('permission') || message.includes('unauthorized')) {
      return ConversationErrorType.PERMISSION_DENIED
    }
    if (message.includes('timeout')) {
      return ConversationErrorType.TIMEOUT
    }
    if (message.includes('conversation') || message.includes('connect')) {
      return ConversationErrorType.CONNECTION_FAILED
    }

    return ConversationErrorType.UNKNOWN
  }

  /**
   * Check if error type is retryable
   */
  _isRetryableError(errorType) {
    // Don't retry permission errors
    if (errorType === ConversationErrorType.PERMISSION_DENIED) {
      return false
    }

    // Retry network and connection issues
    return [
      ConversationErrorType.CONNECTION_FAILED,
      ConversationErrorType.TIMEOUT,
      ConversationErrorType.UNKNOWN
    ].includes(errorType)
  }

  /**
   * Check if error is conversation-related
   */
  _isConversationError(errorType) {
    return Object.values(ConversationErrorType).includes(errorType)
  }

  /**
   * Calculate retry delay with exponential backoff
   */
  _calculateDelay(retryCount) {
    const delay = this.baseDelayMs * Math.pow(this.backoffMultiplier, retryCount)
    return Math.min(delay, this.maxDelayMs)
  }

  /**
   * Promise-based delay
   */
  _delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  /**
   * Report conversation error to backend
   */
  async _reportConversationError(conversationId, errorType, errorMessage, retryCount) {
    try {
      switch (errorType) {
        case ConversationErrorType.CONNECTION_FAILED:
          await conversationErrorReporter.reportConnectionFailed(conversationId, errorMessage, retryCount)
          break
        case ConversationErrorType.CONVERSATION_NOT_FOUND:
          await conversationErrorReporter.reportConversationNotFound(conversationId, errorMessage, retryCount)
          break
        case ConversationErrorType.PERMISSION_DENIED:
          await conversationErrorReporter.reportPermissionDenied(conversationId, errorMessage, retryCount)
          break
        case ConversationErrorType.TIMEOUT:
          await conversationErrorReporter.reportTimeout(conversationId, errorMessage, retryCount)
          break
        default:
          await conversationErrorReporter.reportUnknownError(conversationId, errorMessage, retryCount)
      }
    } catch (error) {
      console.error('Failed to report conversation error:', error)
      // Don't throw - error reporting should not break retry flow
    }
  }
}

// Export singleton instance
export const smartRetryStrategy = new SmartRetryStrategy()
