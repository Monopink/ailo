import { getLogger } from './logger';

const logger = getLogger('AuthGuard');

/**
 * Check if user is authenticated
 * @returns {boolean} True if authenticated
 */
export function isAuthenticated() {
  const app = getApp();
  return app.globalData.isAuthenticated || false;
}

/**
 * Require authentication
 * If not authenticated, show login prompt and return false
 * @param {Object} options - Options
 * @param {string} options.title - Modal title
 * @param {string} options.content - Modal content
 * @returns {boolean} True if authenticated
 */
export function requireAuth(options = {}) {
  if (isAuthenticated()) {
    return true;
  }

  const {
    title = '提示',
    content = '请先登录后再继续操作'
  } = options;

  logger.info('User not authenticated, showing login prompt');

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
}

/**
 * Require authentication for page
 * If not authenticated, redirect to login page
 * Call this in page's onLoad or onShow
 * @param {Object} page - Page instance
 * @param {Object} options - Options
 * @param {boolean} options.redirect - Whether to redirect to login (default: true)
 * @param {string} options.fallbackUrl - Fallback URL if not redirect
 * @returns {boolean} True if authenticated
 */
export function requireAuthForPage(page, options = {}) {
  if (isAuthenticated()) {
    return true;
  }

  const {
    redirect = true,
    fallbackUrl = '/pages/welcome/welcome'
  } = options;

  logger.info('Page requires auth but user not authenticated', {
    route: page.route,
    redirect
  });

  if (redirect) {
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
          // User cancelled, go back or to fallback
          const pages = getCurrentPages();
          if (pages.length > 1) {
            wx.navigateBack();
          } else {
            wx.reLaunch({
              url: fallbackUrl
            });
          }
        }
      }
    });
  } else {
    // Just go to fallback
    wx.reLaunch({
      url: fallbackUrl
    });
  }

  return false;
}

