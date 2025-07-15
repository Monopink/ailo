/**
 * Time utilities for handling timezone conversions and message timestamps
 */

/**
 * Parse server timestamp to Date object
 * Handles both UTC timestamps with timezone info and legacy timestamps without timezone
 * @param {string} timestamp - Server timestamp (e.g., "2025-07-14T12:21:31.490418+00:00" or "2025-07-14T12:21:31.490418")
 * @returns {Date} - JavaScript Date object in local timezone
 */
export function parseServerTimestamp(timestamp) {
  if (!timestamp) {
    return new Date()
  }

  try {
    // If timestamp already has timezone info, parse directly
    if (timestamp.includes('+') || timestamp.includes('Z')) {
      return new Date(timestamp)
    }

    // Legacy timestamp without timezone - assume UTC
    // Add 'Z' suffix to indicate UTC
    const utcTimestamp = timestamp.endsWith('Z') ? timestamp : timestamp + 'Z'
    return new Date(utcTimestamp)
  } catch (error) {
    console.warn('Failed to parse timestamp:', timestamp, error)
    return new Date()
  }
}

/**
 * Get current client timestamp for real-time messages
 * @returns {Date} - Current local time
 */
export function getClientTimestamp() {
  return new Date()
}

/**
 * Check if a timestamp is from an offline message
 * Offline messages should be sorted by server time, real-time messages by client time
 * @param {string} messageSource - Source of the message ('offline', 'realtime', etc.)
 * @returns {boolean} - True if message is from offline source
 */
export function isOfflineMessage(messageSource) {
  return messageSource === 'offline'
}

/**
 * Create a message timestamp based on message source
 * @param {string} serverTimestamp - Server timestamp string
 * @param {string} messageSource - Message source ('offline', 'realtime', etc.)
 * @returns {Date} - Appropriate timestamp for sorting
 */
export function createMessageTimestamp(serverTimestamp, messageSource = 'realtime') {
  if (isOfflineMessage(messageSource)) {
    // For offline messages, use server timestamp (converted to local time)
    return parseServerTimestamp(serverTimestamp)
  } else {
    // For real-time messages, use client timestamp for better ordering
    return getClientTimestamp()
  }
}

/**
 * Format timestamp for display in chat
 * @param {Date} timestamp - Date object
 * @param {Object} options - Formatting options
 * @param {boolean} options.showDate - Whether to show date
 * @param {boolean} options.showSeconds - Whether to show seconds
 * @returns {string} - Formatted time string
 */
export function formatMessageTime(timestamp, options = {}) {
  const { showDate = false, showSeconds = false } = options

  if (!timestamp || !(timestamp instanceof Date)) {
    return ''
  }

  const now = new Date()
  const isToday = timestamp.toDateString() === now.toDateString()
  const isYesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000).toDateString() === timestamp.toDateString()

  let timeFormat = showSeconds ? 'HH:mm:ss' : 'HH:mm'

  if (showDate || !isToday) {
    if (isYesterday) {
      return `昨天 ${timestamp.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })}`
    } else if (timestamp.getFullYear() === now.getFullYear()) {
      return timestamp.toLocaleDateString('zh-CN', {
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      })
    } else {
      return timestamp.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      })
    }
  }

  return timestamp.toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    ...(showSeconds && { second: '2-digit' })
  })
}

/**
 * Compare two message timestamps for sorting
 * @param {Object} messageA - First message object
 * @param {Object} messageB - Second message object
 * @returns {number} - Comparison result for Array.sort()
 */
export function compareMessageTimestamps(messageA, messageB) {
  const timeA = messageA.timestamp instanceof Date ? messageA.timestamp : new Date(messageA.timestamp)
  const timeB = messageB.timestamp instanceof Date ? messageB.timestamp : new Date(messageB.timestamp)

  return timeA.getTime() - timeB.getTime()
}

/**
 * Check if two timestamps are close enough to be considered duplicates
 * @param {Date|string} timestamp1 - First timestamp
 * @param {Date|string} timestamp2 - Second timestamp
 * @param {number} thresholdMs - Threshold in milliseconds (default: 5000ms)
 * @returns {boolean} - True if timestamps are within threshold
 */
export function areTimestampsClose(timestamp1, timestamp2, thresholdMs = 5000) {
  const time1 = timestamp1 instanceof Date ? timestamp1 : new Date(timestamp1)
  const time2 = timestamp2 instanceof Date ? timestamp2 : new Date(timestamp2)

  return Math.abs(time1.getTime() - time2.getTime()) < thresholdMs
}

/**
 * Get timezone offset string for debugging
 * @returns {string} - Timezone offset (e.g., "+08:00")
 */
export function getTimezoneOffset() {
  const offset = new Date().getTimezoneOffset()
  const hours = Math.floor(Math.abs(offset) / 60)
  const minutes = Math.abs(offset) % 60
  const sign = offset <= 0 ? '+' : '-'

  return `${sign}${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`
}

/**
 * Generate a content-based message fingerprint for deduplication
 * @param {Object} message - Message object
 * @returns {string} - Unique fingerprint for the message
 */
export function generateMessageFingerprint(message) {
  const content = message.text || message.content || ''
  const sender = message.sender || message.from || ''
  const type = message.messageType || message.type || 'chat'

  // Create a hash-like fingerprint from content + sender + type
  const fingerprint = `${type}:${sender}:${content.length}:${content.substring(0, 20)}:${content.substring(-10)}`
  return fingerprint
}

/**
 * Check if two messages are duplicates based on multiple criteria
 * @param {Object} messageA - First message
 * @param {Object} messageB - Second message
 * @param {Object} options - Comparison options
 * @returns {boolean} - True if messages are duplicates
 */
export function areMessagesDuplicate(messageA, messageB, options = {}) {
  const {
    useStrictId = true,
    useContentFingerprint = true,
    useTimestampProximity = true,
    timestampThreshold = 5000 // 5 seconds
  } = options

  // 1. Strict ID matching (most reliable)
  if (useStrictId) {
    // Check localId (for sent messages)
    if (messageA.localId && messageB.localId && messageA.localId === messageB.localId) {
      return true
    }

    // Check backend message ID (if available)
    if (messageA.id && messageB.id && messageA.id === messageB.id) {
      return true
    }
  }

  // 2. Content fingerprint matching (for received messages)
  if (useContentFingerprint) {
    const fingerprintA = generateMessageFingerprint(messageA)
    const fingerprintB = generateMessageFingerprint(messageB)

    if (fingerprintA === fingerprintB) {
      // If fingerprints match, check timestamp proximity for final confirmation
      if (useTimestampProximity) {
        return areTimestampsClose(messageA.timestamp, messageB.timestamp, timestampThreshold)
      }
      return true
    }
  }

  return false
}

/**
 * Debug function to log timestamp conversion details
 * @param {string} serverTimestamp - Original server timestamp
 * @param {Date} parsedTimestamp - Parsed timestamp
 * @param {string} messageSource - Message source
 */
export function debugTimestamp(serverTimestamp, parsedTimestamp, messageSource) {
  if (process.env.NODE_ENV === 'development') {
    console.log('🕐 Timestamp Debug:', {
      original: serverTimestamp,
      parsed: parsedTimestamp.toISOString(),
      local: parsedTimestamp.toLocaleString(),
      source: messageSource,
      clientOffset: getTimezoneOffset()
    })
  }
}
