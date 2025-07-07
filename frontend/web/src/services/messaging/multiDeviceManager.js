/**
 * Multi-device login management for messaging service
 * Handles device tagging, login conflicts, and multi-device state
 */

import { DeviceType, LoginStrategy, ConflictAction, DeviceTypeLabels, LoginStrategyLabels, ConflictActionLabels } from './types'
import { useToast } from 'vue-toastification'
import { multiDeviceConfig } from './multiDeviceConfig'

class MultiDeviceManager {
  constructor() {
    this.currentDeviceTag = null
    this.toast = useToast()

    // Device detection and management
    this.deviceInfo = this._detectDevice()
    this.sessionId = this._generateSessionId()

    // Event listeners for multi-device events
    this.conflictCallbacks = new Set()
    this.deviceChangeCallbacks = new Set()

    console.log('🔧 [MultiDeviceManager] Initialized with device:', this.deviceInfo)
  }

  /**
   * Get device tag for login
   */
  getDeviceTag() {
    if (this.currentDeviceTag) {
      return this.currentDeviceTag
    }

    // Get strategy from config
    const loginStrategy = multiDeviceConfig.getLoginStrategy()

    // Auto-detect device tag based on strategy
    switch (loginStrategy) {
      case LoginStrategy.UNLIMITED:
        // No tag - allow unlimited devices
        return undefined

      case LoginStrategy.SINGLE_DEVICE:
        // Same tag for all - only one device allowed
        return 'SingleDevice'

      case LoginStrategy.LIMITED_MULTI:
      default:
        // Different tags for different device types - use label for LeanCloud
        const deviceType = multiDeviceConfig.getDeviceType()
        return DeviceTypeLabels[deviceType] || 'Web'
    }
  }

  /**
   * Set custom device tag
   */
  setDeviceTag(tag) {
    this.currentDeviceTag = tag
    console.log('🔧 [MultiDeviceManager] Device tag set to:', tag)
  }

  /**
   * Set login strategy
   */
  setLoginStrategy(strategy) {
    multiDeviceConfig.setLoginStrategy(strategy)
    console.log('🔧 [MultiDeviceManager] Login strategy set to:', strategy)
  }

  /**
   * Set conflict action
   */
  setConflictAction(action) {
    multiDeviceConfig.setConflictAction(action)
    console.log('🔧 [MultiDeviceManager] Conflict action set to:', action)
  }

  /**
   * Handle login conflict event
   */
  handleLoginConflict(conflictInfo = {}) {
    console.warn('⚠️ [MultiDeviceManager] Login conflict detected:', conflictInfo)

    // Notify callbacks
    this.conflictCallbacks.forEach(callback => {
      try {
        callback(conflictInfo)
      } catch (error) {
        console.error('Error in conflict callback:', error)
      }
    })

    // Handle based on conflict action from config
    const conflictAction = multiDeviceConfig.getConflictAction()
    switch (conflictAction) {
      case ConflictAction.FORCE_LOGOUT:
        this._handleForceLogout(conflictInfo)
        break

      case ConflictAction.REJECT_NEW:
        this._handleRejectNew(conflictInfo)
        break

      case ConflictAction.NOTIFY_ONLY:
        this._handleNotifyOnly(conflictInfo)
        break
    }
  }

  /**
   * Get login options for provider
   */
  getLoginOptions(userId) {
    const options = {
      tag: this.getDeviceTag()
    }

    // Add session info for tracking
    options.sessionInfo = {
      sessionId: this.sessionId,
      deviceInfo: this.deviceInfo,
      timestamp: new Date().toISOString()
    }

    console.log('🔧 [MultiDeviceManager] Login options for', userId, ':', options)
    return options
  }

  /**
   * Register conflict callback
   */
  onConflict(callback) {
    this.conflictCallbacks.add(callback)
  }

  /**
   * Unregister conflict callback
   */
  offConflict(callback) {
    this.conflictCallbacks.delete(callback)
  }

  /**
   * Register device change callback
   */
  onDeviceChange(callback) {
    this.deviceChangeCallbacks.add(callback)
  }

  /**
   * Unregister device change callback
   */
  offDeviceChange(callback) {
    this.deviceChangeCallbacks.delete(callback)
  }

  /**
   * Get current device information
   */
  getDeviceInfo() {
    return {
      ...this.deviceInfo,
      sessionId: this.sessionId,
      deviceTag: this.getDeviceTag(),
      loginStrategy: multiDeviceConfig.getLoginStrategy(),
      conflictAction: multiDeviceConfig.getConflictAction(),
      config: multiDeviceConfig.getConfig()
    }
  }

  /**
   * Check if reconnect should be attempted after conflict
   */
  shouldReconnect(conflictInfo) {
    // For MVP, simple logic: don't reconnect on conflicts
    // In production, this could be more sophisticated
    return false
  }

  // Private methods

  /**
   * Detect current device type and capabilities (returns numeric device type)
   */
  _detectDevice() {
    const userAgent = navigator.userAgent.toLowerCase()
    const platform = navigator.platform.toLowerCase()

    let type = DeviceType.WEB
    let isMobile = false
    let isTablet = false

    // Mobile detection
    if (/android|iphone|ipod|blackberry|iemobile|opera mini/i.test(userAgent)) {
      isMobile = true
      type = DeviceType.MOBILE
    }

    // Tablet detection
    if (/ipad|android(?!.*mobile)/i.test(userAgent)) {
      isTablet = true
      type = DeviceType.PAD
    }

    // Desktop detection
    if (/electron/i.test(userAgent)) {
      type = DeviceType.DESKTOP
    }

    return {
      type, // Numeric value
      isMobile,
      isTablet,
      userAgent: navigator.userAgent,
      platform: navigator.platform,
      language: navigator.language,
      screenSize: {
        width: window.screen.width,
        height: window.screen.height
      },
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight
      }
    }
  }

  /**
   * Generate unique session ID
   */
  _generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`
  }

  /**
   * Handle force logout conflict action
   */
  _handleForceLogout(conflictInfo) {
    const notificationConfig = multiDeviceConfig.getNotificationConfig()

    if (notificationConfig.showConflictNotifications) {
      this.toast.error('您的账号在其他设备上登录，当前连接已断开', {
        timeout: 5000
      })
    }

    // Emit logout event for app to handle
    const event = new CustomEvent('multi-device-logout', {
      detail: { reason: 'conflict', conflictInfo }
    })
    window.dispatchEvent(event)
  }

  /**
   * Handle reject new conflict action
   */
  _handleRejectNew(conflictInfo) {
    const notificationConfig = multiDeviceConfig.getNotificationConfig()

    if (notificationConfig.showConflictNotifications) {
      this.toast.warning('登录失败：该账号已在其他设备上登录', {
        timeout: 5000
      })
    }
  }

  /**
   * Handle notify only conflict action
   */
  _handleNotifyOnly(conflictInfo) {
    const notificationConfig = multiDeviceConfig.getNotificationConfig()

    if (notificationConfig.showConflictNotifications) {
      this.toast.info('检测到多设备登录', {
        timeout: 3000
      })
    }
  }
}

// Create singleton instance
export const multiDeviceManager = new MultiDeviceManager()

// Export class for testing
export { MultiDeviceManager }
