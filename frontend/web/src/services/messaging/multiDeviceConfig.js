/**
 * Multi-device login configuration management
 * Provides centralized configuration for multi-device behavior
 */

import { LoginStrategy, ConflictAction, DeviceType } from './types'

class MultiDeviceConfig {
  constructor() {
    this.config = this._getDefaultConfig()
    this._loadFromStorage()
  }

  /**
   * Get default configuration
   */
  _getDefaultConfig() {
    return {
      // Login strategy - default to limited multi-device (recommended)
      loginStrategy: LoginStrategy.LIMITED_MULTI,

      // Conflict handling
      conflictAction: ConflictAction.FORCE_LOGOUT,

      // Device type mapping
      deviceTypeMapping: {
        web: DeviceType.WEB,
        mobile: DeviceType.MOBILE,
        tablet: DeviceType.PAD,
        desktop: DeviceType.DESKTOP
      },

      // Auto-reconnect settings
      autoReconnect: {
        enabled: true,
        maxAttempts: 3,
        baseDelay: 1000,
        maxDelay: 30000,
        backoffMultiplier: 2
      },

      // Session management
      session: {
        trackSessions: true,
        maxConcurrentSessions: 3,
        sessionTimeout: 24 * 60 * 60 * 1000 // 24 hours
      },

      // Notification settings
      notifications: {
        showConflictNotifications: true,
        showReconnectNotifications: true,
        showDeviceChangeNotifications: false
      },

      // Development settings
      development: {
        enableDebugLogs: true,
        simulateConflicts: false,
        mockDeviceType: null
      }
    }
  }

  /**
   * Load configuration from localStorage
   */
  _loadFromStorage() {
    try {
      const stored = localStorage.getItem('multiDeviceConfig')
      if (stored) {
        const parsedConfig = JSON.parse(stored)
        this.config = { ...this.config, ...parsedConfig }
        console.log('📱 [MultiDeviceConfig] Loaded from storage:', this.config)
      }
    } catch (error) {
      console.warn('⚠️ [MultiDeviceConfig] Failed to load from storage:', error)
    }
  }

  /**
   * Save configuration to localStorage
   */
  _saveToStorage() {
    try {
      localStorage.setItem('multiDeviceConfig', JSON.stringify(this.config))
      console.log('💾 [MultiDeviceConfig] Saved to storage')
    } catch (error) {
      console.warn('⚠️ [MultiDeviceConfig] Failed to save to storage:', error)
    }
  }

  /**
   * Get current configuration
   */
  getConfig() {
    return { ...this.config }
  }

  /**
   * Update configuration
   */
  updateConfig(updates) {
    this.config = { ...this.config, ...updates }
    this._saveToStorage()
    console.log('🔧 [MultiDeviceConfig] Configuration updated:', updates)
  }

  /**
   * Get login strategy
   */
  getLoginStrategy() {
    return this.config.loginStrategy
  }

  /**
   * Set login strategy
   */
  setLoginStrategy(strategy) {
    if (!Object.values(LoginStrategy).includes(strategy)) {
      throw new Error(`Invalid login strategy: ${strategy}`)
    }

    this.updateConfig({ loginStrategy: strategy })
  }

  /**
   * Get conflict action
   */
  getConflictAction() {
    return this.config.conflictAction
  }

  /**
   * Set conflict action
   */
  setConflictAction(action) {
    if (!Object.values(ConflictAction).includes(action)) {
      throw new Error(`Invalid conflict action: ${action}`)
    }

    this.updateConfig({ conflictAction: action })
  }

  /**
   * Get device type for current environment (returns numeric value)
   */
  getDeviceType() {
    // Check for mock device type in development
    if (this.config.development.mockDeviceType) {
      return this.config.development.mockDeviceType
    }

    // Auto-detect device type
    const userAgent = navigator.userAgent.toLowerCase()

    if (/android|iphone|ipod|blackberry|iemobile|opera mini/i.test(userAgent)) {
      return this.config.deviceTypeMapping.mobile
    }

    if (/ipad|android(?!.*mobile)/i.test(userAgent)) {
      return this.config.deviceTypeMapping.tablet
    }

    if (/electron/i.test(userAgent)) {
      return this.config.deviceTypeMapping.desktop
    }

    return this.config.deviceTypeMapping.web
  }

  /**
   * Get auto-reconnect settings
   */
  getAutoReconnectConfig() {
    return { ...this.config.autoReconnect }
  }

  /**
   * Enable/disable auto-reconnect
   */
  setAutoReconnect(enabled) {
    this.updateConfig({
      autoReconnect: { ...this.config.autoReconnect, enabled }
    })
  }

  /**
   * Get session management settings
   */
  getSessionConfig() {
    return { ...this.config.session }
  }

  /**
   * Get notification settings
   */
  getNotificationConfig() {
    return { ...this.config.notifications }
  }

  /**
   * Update notification settings
   */
  setNotificationConfig(updates) {
    this.updateConfig({
      notifications: { ...this.config.notifications, ...updates }
    })
  }

  /**
   * Check if debug logs are enabled
   */
  isDebugEnabled() {
    return this.config.development.enableDebugLogs
  }

  /**
   * Enable/disable debug logs
   */
  setDebugEnabled(enabled) {
    this.updateConfig({
      development: { ...this.config.development, enableDebugLogs: enabled }
    })
  }

  /**
   * Reset to default configuration
   */
  resetToDefaults() {
    this.config = this._getDefaultConfig()
    this._saveToStorage()
    console.log('🔄 [MultiDeviceConfig] Reset to defaults')
  }

  /**
   * Get configuration for specific environment
   */
  getEnvironmentConfig() {
    const isDevelopment = import.meta.env.DEV

    return {
      ...this.config,
      // Override settings for development
      ...(isDevelopment && {
        development: {
          ...this.config.development,
          enableDebugLogs: true
        }
      })
    }
  }

  /**
   * Validate configuration
   */
  validateConfig() {
    const errors = []

    if (!Object.values(LoginStrategy).includes(this.config.loginStrategy)) {
      errors.push(`Invalid login strategy: ${this.config.loginStrategy}`)
    }

    if (!Object.values(ConflictAction).includes(this.config.conflictAction)) {
      errors.push(`Invalid conflict action: ${this.config.conflictAction}`)
    }

    if (this.config.autoReconnect.maxAttempts < 0) {
      errors.push('Auto-reconnect max attempts must be >= 0')
    }

    if (this.config.session.maxConcurrentSessions < 1) {
      errors.push('Max concurrent sessions must be >= 1')
    }

    return {
      isValid: errors.length === 0,
      errors
    }
  }
}

// Create singleton instance
export const multiDeviceConfig = new MultiDeviceConfig()

// Export class for testing
export { MultiDeviceConfig }
