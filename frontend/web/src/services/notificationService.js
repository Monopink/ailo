/**
 * Browser notification service
 * Handles browser notification permissions and message notifications
 */

import localStorageService from './localStorage'

class NotificationService {
  constructor() {
    this.isSupported = 'Notification' in window
    this.permission = this.isSupported ? Notification.permission : 'denied'
    this.hasRequestedPermission = this.loadPermissionRequestStatus()
  }

  /**
   * Check if notifications are supported by the browser
   */
  isNotificationSupported() {
    return this.isSupported
  }

  /**
   * Get current notification permission status
   */
  getPermissionStatus() {
    if (!this.isSupported) return 'unsupported'
    return Notification.permission
  }

  /**
   * Check if user has been asked for permission before
   */
  hasAskedForPermission() {
    return this.hasRequestedPermission
  }

  /**
   * Request notification permission from user
   */
  async requestPermission() {
    if (!this.isSupported) {
      console.warn('Notifications not supported by this browser')
      return 'unsupported'
    }

    if (Notification.permission === 'granted') {
      return 'granted'
    }

    try {
      const permission = await Notification.requestPermission()
      this.permission = permission

      // Mark that we've requested permission
      this.hasRequestedPermission = true
      this.savePermissionRequestStatus(true)

      console.log('📢 Notification permission:', permission)
      return permission
    } catch (error) {
      console.error('Failed to request notification permission:', error)
      return 'denied'
    }
  }

  /**
   * Show a notification for received message
   */
  showMessageNotification(message, chatName) {
    if (!this.canShowNotifications()) {
      return null
    }

    try {
      const showContent = this.isNotificationShowContent()
      const brandName = import.meta.env.VITE_BRAND_NAME || '敲敲'

      const title = showContent ? `来自 ${chatName} 的新消息` : `你有一条${brandName}新消息`
      const body = showContent ? message.text : ''

      const notification = new Notification(title, {
        body: body,
        icon: '/favicon.ico', // You can customize this icon
        badge: '/favicon.ico',
        tag: `chat-${message.from}`, // Prevent duplicate notifications from same chat
        requireInteraction: false,
        silent: false
      })

      // Auto close after 5 seconds
      setTimeout(() => {
        notification.close()
      }, 5000)

      // Handle notification click - focus window and navigate to chat
      notification.onclick = () => {
        window.focus()
        notification.close()

        // Emit custom event to navigate to the chat
        window.dispatchEvent(new CustomEvent('notification-chat-click', {
          detail: { chatId: message.from, message }
        }))
      }

      console.log('📢 Notification shown for message from:', chatName)
      return notification
    } catch (error) {
      console.error('Failed to show notification:', error)
      return null
    }
  }

  /**
   * Check if we can show notifications
   */
  canShowNotifications() {
    return this.isSupported &&
      Notification.permission === 'granted' &&
      this.isNotificationEnabled()
  }

  /**
   * Check if notifications are enabled in user settings
   */
  isNotificationEnabled() {
    const settings = localStorageService.loadUserSettings()
    return settings?.notifications?.enabled !== false // Default to true
  }

  /**
   * Enable/disable notifications in user settings
   */
  setNotificationEnabled(enabled) {
    const settings = localStorageService.loadUserSettings() || {}
    if (!settings.notifications) {
      settings.notifications = {}
    }
    settings.notifications.enabled = enabled
    localStorageService.saveUserSettings(settings)

    console.log('📢 Notifications', enabled ? 'enabled' : 'disabled')
  }

  /**
   * Check if notifications should show content
   */
  isNotificationShowContent() {
    const settings = localStorageService.loadUserSettings()
    return settings?.notifications?.showContent !== false // Default to true
  }

  /**
   * Enable/disable showing notification content
   */
  setNotificationShowContent(showContent) {
    const settings = localStorageService.loadUserSettings() || {}
    if (!settings.notifications) {
      settings.notifications = {}
    }
    settings.notifications.showContent = showContent
    localStorageService.saveUserSettings(settings)

    console.log('📢 Notification show content:', showContent)
  }

  /**
   * Load permission request status from localStorage
   */
  loadPermissionRequestStatus() {
    const settings = localStorageService.loadUserSettings()
    return settings?.notifications?.hasRequestedPermission || false
  }

  /**
   * Save permission request status to localStorage
   */
  savePermissionRequestStatus(hasRequested) {
    const settings = localStorageService.loadUserSettings() || {}
    if (!settings.notifications) {
      settings.notifications = {}
    }
    settings.notifications.hasRequestedPermission = hasRequested
    localStorageService.saveUserSettings(settings)
  }

  /**
   * Get notification settings summary for UI
   */
  getNotificationSettings() {
    return {
      isSupported: this.isSupported,
      permission: this.getPermissionStatus(),
      hasAskedBefore: this.hasAskedForPermission(),
      isEnabled: this.isNotificationEnabled(),
      canShow: this.canShowNotifications(),
      showContent: this.isNotificationShowContent()
    }
  }

  /**
   * Reset notification settings (for testing)
   */
  resetSettings() {
    const settings = localStorageService.loadUserSettings() || {}
    if (settings.notifications) {
      delete settings.notifications
      localStorageService.saveUserSettings(settings)
    }
    this.hasRequestedPermission = false
    console.log('📢 Notification settings reset')
  }
}

// Create singleton instance
export const notificationService = new NotificationService()
