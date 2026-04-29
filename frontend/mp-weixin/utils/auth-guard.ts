/**
 * Authentication Guard
 * Provides page-level authentication checks
 * Waits for AuthService initialization before checking auth state
 */

import authService from './auth-service';
import { getLogger } from './logger';
import { normalizeError } from './errors';
import { promptLoginAndRedirect } from './login-redirect';

const logger = getLogger('AuthGuard');

interface RequireAuthOptions {
  source?: string;
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
  const { source = 'auth_guard' } = options;

  try {
    logger.debug('Waiting for auth initialization', { route: getPageRoute(page) });
    const authenticated = await authService.waitForInit();

    if (authenticated) {
      logger.debug('User authenticated', { route: getPageRoute(page) });
      return true;
    }

    logger.info('User not authenticated, handling redirect', {
      route: getPageRoute(page),
      source,
    });
    await promptLoginAndRedirect({ source });

    return false;
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('Auth check failed', {
      route: getPageRoute(page),
      errorMessage: err.message,
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
  const { title = '提示', content = '请先登录后继续操作' } = options;

  try {
    const authenticated = await authService.waitForInit();

    if (authenticated) {
      return true;
    }

    logger.info('User not authenticated for action');
    logger.debug('Auth action prompt fallback text', { title, content });
    await promptLoginAndRedirect({ source: 'auth_action' });

    return false;
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('Auth check for action failed', {
      errorMessage: err.message,
    });

    return false;
  }
}

export function isAuthenticated(): boolean {
  return authService.isAuthenticated();
}

export default {
  requireAuth,
  requireAuthForAction,
  isAuthenticated,
};
