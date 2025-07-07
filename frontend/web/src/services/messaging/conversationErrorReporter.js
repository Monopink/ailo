/**
 * Conversation Error Reporter Service
 * 
 * Provides error reporting functionality for conversation ID issues.
 * Uses numeric enums for security and implements rate limiting to prevent spam.
 */

import { ConversationErrorType } from './types'

class ConversationErrorReporter {
  constructor() {
    this.reportQueue = []
    this.isReporting = false
    this.lastReportTime = 0
    this.reportCooldown = 30000 // 30 seconds cooldown between reports
    this.maxQueueSize = 10
  }

  /**
   * Report a conversation error to the backend
   * 
   * @param {Object} errorInfo - Error information
   * @param {number} errorInfo.errorType - Error type from ConversationErrorType enum
   * @param {string} errorInfo.conversationId - The conversation ID that failed
   * @param {string} errorInfo.errorMessage - Error message
   * @param {number} errorInfo.retryCount - Number of retries attempted
   */
  async reportError(errorInfo) {
    try {
      // Validate error type
      if (!this._isValidErrorType(errorInfo.errorType)) {
        console.warn('Invalid error type for reporting:', errorInfo.errorType)
        return
      }

      // Rate limiting - prevent spam
      const now = Date.now()
      if (now - this.lastReportTime < this.reportCooldown) {
        console.log('Error reporting rate limited, queuing for later')
        this._queueReport(errorInfo)
        return
      }

      // Send report immediately
      await this._sendReport(errorInfo)
      this.lastReportTime = now

    } catch (error) {
      console.error('Failed to report conversation error:', error)
      // Don't throw - error reporting should not break the main flow
    }
  }

  /**
   * Report conversation connection failure
   */
  async reportConnectionFailed(conversationId, errorMessage, retryCount = 0) {
    await this.reportError({
      errorType: ConversationErrorType.CONNECTION_FAILED,
      conversationId,
      errorMessage,
      retryCount
    })
  }

  /**
   * Report conversation not found
   */
  async reportConversationNotFound(conversationId, errorMessage, retryCount = 0) {
    await this.reportError({
      errorType: ConversationErrorType.CONVERSATION_NOT_FOUND,
      conversationId,
      errorMessage,
      retryCount
    })
  }

  /**
   * Report permission denied
   */
  async reportPermissionDenied(conversationId, errorMessage, retryCount = 0) {
    await this.reportError({
      errorType: ConversationErrorType.PERMISSION_DENIED,
      conversationId,
      errorMessage,
      retryCount
    })
  }

  /**
   * Report timeout error
   */
  async reportTimeout(conversationId, errorMessage, retryCount = 0) {
    await this.reportError({
      errorType: ConversationErrorType.TIMEOUT,
      conversationId,
      errorMessage,
      retryCount
    })
  }

  /**
   * Report unknown error
   */
  async reportUnknownError(conversationId, errorMessage, retryCount = 0) {
    await this.reportError({
      errorType: ConversationErrorType.UNKNOWN,
      conversationId,
      errorMessage,
      retryCount
    })
  }

  /**
   * Process queued reports
   */
  async processQueuedReports() {
    if (this.isReporting || this.reportQueue.length === 0) {
      return
    }

    const now = Date.now()
    if (now - this.lastReportTime < this.reportCooldown) {
      return
    }

    this.isReporting = true
    try {
      const report = this.reportQueue.shift()
      await this._sendReport(report)
      this.lastReportTime = now
    } catch (error) {
      console.error('Failed to process queued report:', error)
    } finally {
      this.isReporting = false
    }

    // Process next report if available
    if (this.reportQueue.length > 0) {
      setTimeout(() => this.processQueuedReports(), this.reportCooldown)
    }
  }

  /**
   * Get current queue status
   */
  getQueueStatus() {
    return {
      queueLength: this.reportQueue.length,
      isReporting: this.isReporting,
      lastReportTime: this.lastReportTime,
      cooldownRemaining: Math.max(0, this.reportCooldown - (Date.now() - this.lastReportTime))
    }
  }

  // Private methods

  /**
   * Validate error type
   */
  _isValidErrorType(errorType) {
    return Object.values(ConversationErrorType).includes(errorType)
  }

  /**
   * Queue a report for later sending
   */
  _queueReport(errorInfo) {
    if (this.reportQueue.length >= this.maxQueueSize) {
      console.warn('Error report queue is full, dropping oldest report')
      this.reportQueue.shift()
    }

    this.reportQueue.push({
      ...errorInfo,
      queuedAt: Date.now()
    })

    // Schedule processing
    setTimeout(() => this.processQueuedReports(), this.reportCooldown)
  }

  /**
   * Send error report to backend
   */
  async _sendReport(errorInfo) {
    const reportData = {
      error_type: errorInfo.errorType,
      conversation_id: errorInfo.conversationId || '',
      error_message: errorInfo.errorMessage || '',
      timestamp: new Date().toISOString(),
      retry_count: errorInfo.retryCount || 0,
      user_agent: navigator.userAgent || ''
    }

    console.log('📤 Sending conversation error report:', reportData)

    const response = await fetch('/api/v1/system/conversation-error-report', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(reportData)
    })

    if (!response.ok) {
      throw new Error(`Failed to send error report: ${response.status}`)
    }

    const result = await response.json()
    console.log('✅ Error report sent successfully:', result)
    return result
  }
}

// Export singleton instance
export const conversationErrorReporter = new ConversationErrorReporter()

// Start processing queued reports periodically
setInterval(() => {
  conversationErrorReporter.processQueuedReports()
}, 60000) // Check every minute
