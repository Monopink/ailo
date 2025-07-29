/**
 * Theme management utility for admin panel
 * Handles light/dark/auto theme switching with system preference detection
 */

class ThemeManager {
  constructor() {
    this.currentTheme = 'light'
    this.systemTheme = 'light'
    this.mediaQuery = null
    this.listeners = new Set()

    this.init()
  }

  /**
   * Initialize theme manager
   */
  init() {
    // Setup system theme detection
    this.setupSystemThemeDetection()

    // Load saved theme preference
    const savedTheme = localStorage.getItem('admin_theme') || 'auto'
    this.setTheme(savedTheme)
  }

  /**
   * Setup system theme detection using media query
   */
  setupSystemThemeDetection() {
    if (typeof window !== 'undefined' && window.matchMedia) {
      this.mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      this.systemTheme = this.mediaQuery.matches ? 'dark' : 'light'

      // Listen for system theme changes
      this.mediaQuery.addEventListener('change', (e) => {
        this.systemTheme = e.matches ? 'dark' : 'light'
        this.updateTheme()
        this.notifyListeners()
      })
    }
  }

  /**
   * Set theme preference
   * @param {string} theme - 'light', 'dark', or 'auto'
   */
  setTheme(theme) {
    if (!['light', 'dark', 'auto'].includes(theme)) {
      console.warn(`Invalid theme: ${theme}. Using 'light' as fallback.`)
      theme = 'light'
    }

    this.currentTheme = theme
    localStorage.setItem('admin_theme', theme)
    this.updateTheme()
    this.notifyListeners()
  }

  /**
   * Get current theme preference
   * @returns {string} Current theme setting ('light', 'dark', or 'auto')
   */
  getTheme() {
    return this.currentTheme
  }

  /**
   * Get effective theme (resolves 'auto' to actual theme)
   * @returns {string} Effective theme ('light' or 'dark')
   */
  getEffectiveTheme() {
    if (this.currentTheme === 'auto') {
      return this.systemTheme
    }
    return this.currentTheme
  }

  /**
   * Update DOM with current theme
   */
  updateTheme() {
    if (typeof document !== 'undefined') {
      // Set data-theme to the actual theme setting (including 'auto')
      // CSS media queries will handle the auto mode
      document.documentElement.setAttribute('data-theme', this.currentTheme)

      // Also set a class for easier CSS targeting with effective theme
      const effectiveTheme = this.getEffectiveTheme()
      document.documentElement.classList.remove('theme-light', 'theme-dark', 'theme-auto')
      document.documentElement.classList.add(`theme-${this.currentTheme}`)
      document.documentElement.classList.add(`effective-theme-${effectiveTheme}`)
    }
  }

  /**
   * Add theme change listener
   * @param {Function} callback - Function to call when theme changes
   */
  addListener(callback) {
    this.listeners.add(callback)
  }

  /**
   * Remove theme change listener
   * @param {Function} callback - Function to remove
   */
  removeListener(callback) {
    this.listeners.delete(callback)
  }

  /**
   * Notify all listeners of theme change
   */
  notifyListeners() {
    const themeData = {
      theme: this.currentTheme,
      effectiveTheme: this.getEffectiveTheme(),
      systemTheme: this.systemTheme
    }

    this.listeners.forEach(callback => {
      try {
        callback(themeData)
      } catch (error) {
        console.error('Error in theme listener:', error)
      }
    })
  }

  /**
   * Toggle between light and dark themes
   */
  toggleTheme() {
    const newTheme = this.getEffectiveTheme() === 'light' ? 'dark' : 'light'
    this.setTheme(newTheme)
  }

  /**
   * Check if current effective theme is dark
   * @returns {boolean}
   */
  isDark() {
    return this.getEffectiveTheme() === 'dark'
  }

  /**
   * Check if current effective theme is light
   * @returns {boolean}
   */
  isLight() {
    return this.getEffectiveTheme() === 'light'
  }

  /**
   * Get theme options for UI
   * @returns {Array} Array of theme options
   */
  getThemeOptions() {
    return [
      { value: 'light', label: 'Light' },
      { value: 'dark', label: 'Dark' },
      { value: 'auto', label: 'Auto (System)' }
    ]
  }
}

// Create singleton instance
const themeManager = new ThemeManager()

// Export both the instance and the class
export default themeManager
export { ThemeManager }


