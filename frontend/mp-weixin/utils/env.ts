/**
 * Environment Configuration
 * Controls behavior based on WeChat mini program runtime environment
 */

/**
 * WeChat mini program runtime environment.
 * - develop: developer tools / development version
 * - trial: trial version
 * - release: production release
 */
export type Environment = 'develop' | 'trial' | 'release';

export type LogLevel = 'DEBUG' | 'NONE';

const resolveEnvironment = (): Environment => {
  try {
    if (typeof wx !== 'undefined' && typeof wx.getAccountInfoSync === 'function') {
      const accountInfo = wx.getAccountInfoSync();
      const envVersion = accountInfo.miniProgram.envVersion;
      switch (envVersion) {
        case 'develop':
        case 'trial':
        case 'release':
          return envVersion;
        default:
          break;
      }
    }
  } catch {
    // Silent fallback to default
  }
  return 'develop';
};

export const ENV: Environment = resolveEnvironment();

/**
 * Check if in develop mode
 */
export const IS_DEV: boolean = ENV === 'develop';

/**
 * Check if in trial mode
 */
export const IS_TRIAL: boolean = ENV === 'trial';

/**
 * Check if in release mode
 */
export const IS_PROD: boolean = ENV === 'release';

/**
 * Log level configuration
 * - develop/trial: 'DEBUG' (all logs)
 * - release: 'NONE' (no logs to save storage)
 */
export const LOG_LEVEL: LogLevel = IS_PROD ? 'NONE' : 'DEBUG';

/**
 * Enable debug tools
 * - develop: true (enable checkStorage, checkGlobalData, etc.)
 * - trial/release: false (disable all debug tools)
 */
export const ENABLE_DEBUG_TOOLS: boolean = IS_DEV;

/**
 * Enable LeanCloud SDK debug logging
 * - development: false (disable to reduce log noise)
 * - production: false (always disabled)
 */
export const ENABLE_LEANCLOUD_DEBUG: boolean = false;
