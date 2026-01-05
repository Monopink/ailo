/**
 * Environment Configuration
 * Controls behavior based on development/production environment
 */

/**
 * Environment type
 * Set to 'development' for local development
 * Set to 'production' for release
 */
export type Environment = 'development' | 'production';

export type LogLevel = 'DEBUG' | 'NONE';

const resolveEnvironment = (): Environment => {
  try {
    if (typeof wx !== 'undefined' && typeof wx.getAccountInfoSync === 'function') {
      const accountInfo = wx.getAccountInfoSync();
      const envVersion = accountInfo.miniProgram.envVersion;
      if (envVersion === 'release') {
        return 'production';
      }
      if (envVersion === 'trial' || envVersion === 'develop') {
        return 'development';
      }
    }
  } catch {
    // Silent fallback to default
  }
  return 'development';
};

export const ENV: Environment = resolveEnvironment();

/**
 * Check if in development mode
 */
export const IS_DEV: boolean = ENV === 'development';

/**
 * Check if in production mode
 */
export const IS_PROD: boolean = ENV === 'production';

/**
 * Log level configuration
 * - development: 'DEBUG' (all logs)
 * - production: 'NONE' (no logs to save storage)
 */
export const LOG_LEVEL: LogLevel = IS_DEV ? 'DEBUG' : 'NONE';

/**
 * Enable debug tools
 * - development: true (enable checkStorage, checkGlobalData, etc.)
 * - production: false (disable all debug tools)
 */
export const ENABLE_DEBUG_TOOLS: boolean = IS_DEV;

/**
 * Enable LeanCloud SDK debug logging
 * - development: false (disable to reduce log noise)
 * - production: false (always disabled)
 */
export const ENABLE_LEANCLOUD_DEBUG: boolean = false;
