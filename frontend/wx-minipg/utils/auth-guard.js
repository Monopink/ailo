/**
 * Authentication Guard
 * Provides page-level authentication checks
 * Waits for AuthService initialization before checking auth state
 */

import authService from './auth-service';
import { getLogger } from './logger';

const logger = getLogger('AuthGuard');

/**
 * Require authentication for page
 * Async function that waits for auth initialization
 * Call this in page's onLoad or onShow
 *
 * @param {Object} page - Page instance
 * @param {Object} options - Options
 * @param {boolean} options.showModal - Whether to show login modal (default: true)
 * @param {string} options.redirectUrl - URL to redirect if not authenticated
 * @returns {Promise<boolean>} True if authenticated
 */
export async function requireAuth(page, options = {}) {
  const {
    showModal = true,
    redirectUrl = null
  } = options;

  try {
    // Wait for auth service initialization
    logger.debug('Waiting for auth initialization', { route: page.route });
    const isAuthenticated = await authService.waitForInit();

    if (isAuthenticated) {
      logger.debug('User authenticated', { route: page.route });
      return true;
    }

    // User not authenticated
    logger.info('User not authenticated, handling redirect', {
      route: page.route,
      showModal,
      redirectUrl
    });

    if (showModal) {
      // Show login prompt
      wx.showModal({
        title: '提示',
        content: '请先登录后再访问此页面',
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            wx.navigateTo({
              url: '/pages/login/login'
            });
          } else {
            // User cancelled, go back or to welcome
            handleCancelRedirect(redirectUrl);
          }
        }
      });
    } else {
      // Direct redirect without modal
      if (redirectUrl) {
        wx.reLaunch({ url: redirectUrl });
      } else {
        handleCancelRedirect(redirectUrl);
      }
    }

    return false;
  } catch (error) {
    logger.error('Auth check failed', {
      route: page.route,
      error: error.message || error
    });

    // On error, assume not authenticated
    wx.showToast({
      title: '认证检查失败',
      icon: 'none'
    });

    return false;
  }
}

/**
 * Require authentication for action (not page)
 * Shows a simpler prompt for actions like "add contact"
 *
 * @param {Object} options - Options
 * @param {string} options.title - Modal title
 * @param {string} options.content - Modal content
 * @returns {Promise<boolean>} True if authenticated
 */
export async function requireAuthForAction(options = {}) {
  const {
    title = '提示',
    content = '请先登录后再继续操作'
  } = options;

  try {
    // Wait for auth initialization
    const isAuthenticated = await authService.waitForInit();

    if (isAuthenticated) {
      return true;
    }

    // User not authenticated
    logger.info('User not authenticated for action');

    wx.showModal({
      title,
      content,
      confirmText: '去登录',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) {
          wx.navigateTo({
            url: '/pages/login/login'
          });
        }
      }
    });

    return false;
  } catch (error) {
    logger.error('Auth check for action failed', {
      error: error.message || error
    });

    return false;
  }
}

/**
 * Check if user is authenticated (synchronous)
 * WARNING: Only use this after auth initialization is complete
 * For most cases, use requireAuth() instead
 *
 * @returns {boolean} True if authenticated
 */
export function isAuthenticated() {
  return authService.isAuthenticated();
}

/**
 * Handle cancel redirect
 * Go back if possible, otherwise go to welcome page
 * @private
 */
function handleCancelRedirect(redirectUrl) {
  if (redirectUrl) {
    wx.reLaunch({ url: redirectUrl });
    return;
  }

  const pages = getCurrentPages();
  if (pages.length > 1) {
    wx.navigateBack();
  } else {
    wx.reLaunch({ url: '/pages/welcome/welcome' });
  }
}

export default {
  requireAuth,
  requireAuthForAction,
  isAuthenticated
};
