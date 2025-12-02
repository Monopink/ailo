/**
 * Environment Configuration
 * Controls behavior based on development/production environment
 */

/**
 * Environment type
 * Set to 'development' for local development
 * Set to 'production' for release
 */
export const ENV = 'development';  // Change to 'production' before release

/**
 * Check if in development mode
 */
export const IS_DEV = ENV === 'development';

/**
 * Check if in production mode
 */
export const IS_PROD = ENV === 'production';

/**
 * Log level configuration
 * - development: 'DEBUG' (all logs)
 * - production: 'NONE' (no logs to save storage)
 */
export const LOG_LEVEL = IS_DEV ? 'DEBUG' : 'NONE';

/**
 * Enable debug tools
 * - development: true (enable checkStorage, checkGlobalData, etc.)
 * - production: false (disable all debug tools)
 */
export const ENABLE_DEBUG_TOOLS = IS_DEV;

/**
 * Enable LeanCloud SDK debug logging
 * - development: false (disable to reduce log noise)
 * - production: false (always disabled)
 */
export const ENABLE_LEANCLOUD_DEBUG = true;

