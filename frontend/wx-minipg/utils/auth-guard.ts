/**
 * Authentication Guard
 * Provides page-level authentication checks
 * Waits for AuthService initialization before checking auth state
 */

import authService from './auth-service';
import { getLogger } from './logger';

const logger = getLogger('AuthGuard');

interface RequireAuthOptions {
  showModal?: boolean;
  redirectUrl?: string | null;
}

interface RequireAuthForActionOptions {
  title?: string;
  content?: string;
}

const getPageRoute = (
  page: WechatMiniprogram.Page.Instance<Record<string, unknown>, Record<string, unknown>>
): string => (page as { route?: string }).route ?? '';

export async function requireAuth(
  page: WechatMiniprogram.Page.Instance<Record<string, unknown>, Record<string, unknown>>,
  options: RequireAuthOptions = {}
): Promise<boolean> {
  const { showModal = true, redirectUrl = null } = options;

  try {
    logger.debug('Waiting for auth initialization', { route: getPageRoute(page) });
    const authenticated = await authService.waitForInit();

    if (authenticated) {
      logger.debug('User authenticated', { route: getPageRoute(page) });
      return true;
    }

    logger.info('User not authenticated, handling redirect', {
      route: getPageRoute(page),
      showModal,
      redirectUrl,
    });

    if (showModal) {
      void wx.showModal({
        title: '提示',
        content: '请先登录后再访问此页面',
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            void wx.navigateTo({
              url: '/pages/login/login',
            });
          } else {
            handleCancelRedirect(redirectUrl);
          }
        },
      });
    } else if (redirectUrl) {
      void wx.reLaunch({ url: redirectUrl });
    } else {
      handleCancelRedirect(redirectUrl);
    }

    return false;
  } catch (error) {
    logger.error('Auth check failed', {
      route: getPageRoute(page),
      error,
    });

    void wx.showToast({
      title: '认证检查失败',
      icon: 'none',
    });

    return false;
  }
}

export async function requireAuthForAction(
  options: RequireAuthForActionOptions = {}
): Promise<boolean> {
  const { title = '提示', content = '请先登录后再继续操作' } = options;

  try {
    const authenticated = await authService.waitForInit();

    if (authenticated) {
      return true;
    }

    logger.info('User not authenticated for action');

    void wx.showModal({
      title,
      content,
      confirmText: '去登录',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) {
          void wx.navigateTo({
            url: '/pages/login/login',
          });
        }
      },
    });

    return false;
  } catch (error) {
    logger.error('Auth check for action failed', {
      error,
    });

    return false;
  }
}

export function isAuthenticated(): boolean {
  return authService.isAuthenticated();
}

function handleCancelRedirect(redirectUrl?: string | null): void {
  if (redirectUrl) {
    void wx.reLaunch({ url: redirectUrl });
    return;
  }

  const pages = getCurrentPages();
  if (pages.length > 1) {
    void wx.navigateBack();
  } else {
    void wx.reLaunch({ url: '/pages/login/login' });
  }
}

export default {
  requireAuth,
  requireAuthForAction,
  isAuthenticated,
};
