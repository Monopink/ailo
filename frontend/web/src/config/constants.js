/**
 * Application configuration constants
 * Supports environment variable overrides for flexible deployment
 */

// API Configuration
export const API_CONFIG = {
  // Request timeout in milliseconds
  TIMEOUT: parseInt(import.meta.env.VITE_API_TIMEOUT) || 10000,

  // Retry configuration
  RETRY_ATTEMPTS: parseInt(import.meta.env.VITE_API_RETRY_ATTEMPTS) || 3,
  RETRY_DELAY: parseInt(import.meta.env.VITE_API_RETRY_DELAY) || 1000,

  // Base URLs (fallback to proxy paths if not specified)
  BASE_URL: import.meta.env.VITE_API_BASE_URL || '',

  // Request headers
  DEFAULT_HEADERS: {
    'Content-Type': 'application/json',
  },
};

// Cache Configuration
export const CACHE_CONFIG = {
  // Chat info cache duration in milliseconds
  CHAT_INFO_DURATION: parseInt(import.meta.env.VITE_CACHE_CHAT_INFO_DURATION) || 5 * 60 * 1000, // 5 minutes

  // Contact list cache duration
  CONTACT_LIST_DURATION: parseInt(import.meta.env.VITE_CACHE_CONTACT_LIST_DURATION) || 2 * 60 * 1000, // 2 minutes

  // User profile cache duration
  USER_PROFILE_DURATION: parseInt(import.meta.env.VITE_CACHE_USER_PROFILE_DURATION) || 10 * 60 * 1000, // 10 minutes

  // Maximum cache size (number of items)
  MAX_CACHE_SIZE: parseInt(import.meta.env.VITE_CACHE_MAX_SIZE) || 100,
};

// Message Configuration
export const MESSAGE_CONFIG = {
  // Message constraints
  MAX_LENGTH: parseInt(import.meta.env.VITE_MESSAGE_MAX_LENGTH) || 1000,
  MIN_LENGTH: parseInt(import.meta.env.VITE_MESSAGE_MIN_LENGTH) || 1,

  // Typing indicator configuration
  TYPING_TIMEOUT: parseInt(import.meta.env.VITE_MESSAGE_TYPING_TIMEOUT) || 3000,
  TYPING_DELAY: parseInt(import.meta.env.VITE_MESSAGE_TYPING_DELAY) || 500,
  TYPING_AUTO_HIDE_DURATION: parseInt(import.meta.env.VITE_MESSAGE_TYPING_AUTO_HIDE) || 10000,

  // Message retry configuration
  RETRY_ATTEMPTS: parseInt(import.meta.env.VITE_MESSAGE_RETRY_ATTEMPTS) || 3,
  RETRY_DELAY: parseInt(import.meta.env.VITE_MESSAGE_RETRY_DELAY) || 2000,
};

// UI Configuration
export const UI_CONFIG = {
  // Toast notification duration
  TOAST_DURATION: parseInt(import.meta.env.VITE_UI_TOAST_DURATION) || 3000,

  // Animation durations
  ANIMATION_FAST: parseInt(import.meta.env.VITE_UI_ANIMATION_FAST) || 150,
  ANIMATION_NORMAL: parseInt(import.meta.env.VITE_UI_ANIMATION_NORMAL) || 300,
  ANIMATION_SLOW: parseInt(import.meta.env.VITE_UI_ANIMATION_SLOW) || 500,

  // Debounce delays
  SEARCH_DEBOUNCE: parseInt(import.meta.env.VITE_UI_SEARCH_DEBOUNCE) || 300,
  INPUT_DEBOUNCE: parseInt(import.meta.env.VITE_UI_INPUT_DEBOUNCE) || 150,
};

// Error Reporting Configuration
export const ERROR_CONFIG = {
  // Error reporting cooldown period
  REPORT_COOLDOWN: parseInt(import.meta.env.VITE_ERROR_REPORT_COOLDOWN) || 5000,

  // Maximum error queue size
  MAX_ERROR_QUEUE: parseInt(import.meta.env.VITE_ERROR_MAX_QUEUE) || 10,

  // Enable error reporting to backend
  ENABLE_REPORTING: import.meta.env.VITE_ERROR_ENABLE_REPORTING !== 'false',
};

// Development Configuration
export const DEV_CONFIG = {
  // Enable debug logging
  ENABLE_DEBUG: import.meta.env.VITE_DEV_ENABLE_DEBUG === 'true' || import.meta.env.DEV,

  // Enable performance monitoring
  ENABLE_PERFORMANCE: import.meta.env.VITE_DEV_ENABLE_PERFORMANCE === 'true',

  // Enable API request logging
  ENABLE_API_LOGGING: import.meta.env.VITE_DEV_ENABLE_API_LOGGING === 'true' || import.meta.env.DEV,
};

// Contact Configuration
export const CONTACT_CONFIG = {
  // Default contact limits
  DEFAULT_LIMIT: parseInt(import.meta.env.VITE_CONTACT_DEFAULT_LIMIT) || 3,

  // Search configuration
  SEARCH_MIN_LENGTH: parseInt(import.meta.env.VITE_CONTACT_SEARCH_MIN_LENGTH) || 2,
  SEARCH_MAX_RESULTS: parseInt(import.meta.env.VITE_CONTACT_SEARCH_MAX_RESULTS) || 20,
};

// Notification Configuration
export const NOTIFICATION_CONFIG = {
  // Permission request timeout
  PERMISSION_TIMEOUT: parseInt(import.meta.env.VITE_NOTIFICATION_PERMISSION_TIMEOUT) || 10000,

  // Notification display duration
  DISPLAY_DURATION: parseInt(import.meta.env.VITE_NOTIFICATION_DISPLAY_DURATION) || 5000,

  // Enable notifications by default
  ENABLE_BY_DEFAULT: import.meta.env.VITE_NOTIFICATION_ENABLE_BY_DEFAULT === 'true',
};

// Validation helpers
export const VALIDATION = {
  // Phone number pattern (Chinese mobile numbers)
  PHONE_PATTERN: /^1[3-9]\d{9}$/,

  // Password requirements
  PASSWORD_MIN_LENGTH: parseInt(import.meta.env.VITE_VALIDATION_PASSWORD_MIN_LENGTH) || 8,
  PASSWORD_MAX_LENGTH: parseInt(import.meta.env.VITE_VALIDATION_PASSWORD_MAX_LENGTH) || 128,

  // Nickname requirements
  NICKNAME_MIN_LENGTH: parseInt(import.meta.env.VITE_VALIDATION_NICKNAME_MIN_LENGTH) || 1,
  NICKNAME_MAX_LENGTH: parseInt(import.meta.env.VITE_VALIDATION_NICKNAME_MAX_LENGTH) || 20,
};

// Export all configurations as a single object for convenience
export const CONFIG = {
  API: API_CONFIG,
  CACHE: CACHE_CONFIG,
  MESSAGE: MESSAGE_CONFIG,
  UI: UI_CONFIG,
  ERROR: ERROR_CONFIG,
  DEV: DEV_CONFIG,
  CONTACT: CONTACT_CONFIG,
  NOTIFICATION: NOTIFICATION_CONFIG,
  VALIDATION: VALIDATION,
};

export default CONFIG;
