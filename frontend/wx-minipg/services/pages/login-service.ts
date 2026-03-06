import { requestValidated } from '../../utils/api';
import authService from '../../utils/auth-service';
import { fetchAllContactsFromApi } from '../../utils/contact-sync';
import { normalizeError } from '../../utils/errors';
import { isNonEmptyString } from '../../utils/guards';
import { getLogger } from '../../utils/logger';
import { getDeviceId, saveContacts, type StoredAuthUser } from '../../utils/storage';
import {
  type AuthUserPayload,
  WechatBindPhoneResponseSchema,
  WechatLoginCheckSchema,
} from '../../utils/schemas';
import { BasePageService } from './base-page-service';

const logger = getLogger('LoginPageService');

export type LoginStatus = 'idle' | 'need_phone';

export interface AuthSuccessPayload {
  access_token: string;
  refresh_token: string;
  needs_profile_setup?: boolean | null;
  user: AuthUserPayload;
  message?: string | null;
}

export interface LoginBootstrapResult {
  isAuthenticated: boolean;
  loginCode: string;
  loginStatus: LoginStatus;
  authSuccess: AuthSuccessPayload | null;
  errorMessage: string | null;
}

export interface LoginBindResult {
  loginCode: string;
  authSuccess: AuthSuccessPayload;
}

const normalizeAuthUser = (payload: AuthUserPayload): StoredAuthUser => ({
  qiao_id: payload.qiao_id,
});

export class LoginPageService extends BasePageService {
  async bootstrap(source: string | undefined): Promise<LoginBootstrapResult | null> {
    const seq = this.startRequest();
    try {
      const isAuthenticated = await authService.waitForInit();
      if (!this.isRequestActive(seq)) {
        return null;
      }
      if (isAuthenticated) {
        return {
          isAuthenticated: true,
          loginCode: '',
          loginStatus: 'idle',
          authSuccess: null,
          errorMessage: null,
        };
      }

      const loginCode = await this.getFreshLoginCode('');
      if (!this.isRequestActive(seq)) {
        return null;
      }
      if (!isNonEmptyString(loginCode)) {
        return {
          isAuthenticated: false,
          loginCode: '',
          loginStatus: 'idle',
          authSuccess: null,
          errorMessage: '登录失败，请重试',
        };
      }

      if (source === 'logout') {
        return {
          isAuthenticated: false,
          loginCode,
          loginStatus: 'idle',
          authSuccess: null,
          errorMessage: null,
        };
      }

      const check = await this.checkBindingStatus(loginCode);
      if (!this.isRequestActive(seq)) {
        return null;
      }

      return {
        isAuthenticated: false,
        loginCode,
        loginStatus: check.loginStatus,
        authSuccess: check.authSuccess,
        errorMessage: check.errorMessage,
      };
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Login bootstrap failed', { error: err.message });
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        isAuthenticated: false,
        loginCode: '',
        loginStatus: 'idle',
        authSuccess: null,
        errorMessage: isNonEmptyString(err.message) ? err.message : '登录失败，请重试',
      };
    }
  }

  async bindPhone(phoneCode: string, currentLoginCode: string): Promise<LoginBindResult> {
    const loginCode = await this.getFreshLoginCode(currentLoginCode);
    if (!isNonEmptyString(loginCode)) {
      throw new Error('登录失败，请重试');
    }
    const deviceId = await getDeviceId();
    const response = await requestValidated(WechatBindPhoneResponseSchema, {
      url: '/auth/wechat/bind-phone',
      method: 'POST',
      data: {
        login_code: loginCode,
        phone_code: phoneCode,
        device_id: deviceId,
      },
      auth: false,
    });

    return {
      loginCode,
      authSuccess: {
        access_token: response.access_token,
        refresh_token: response.refresh_token,
        needs_profile_setup: response.needs_profile_setup,
        user: response.user,
        message: response.message ?? undefined,
      },
    };
  }

  async persistAuth(authResult: AuthSuccessPayload): Promise<void> {
    const normalizedUser = normalizeAuthUser(authResult.user);
    await authService.login(authResult.access_token, authResult.refresh_token, normalizedUser, {
      needsProfileSetup: Boolean(authResult.needs_profile_setup),
    });
    logger.info('WeChat login success', { qiao_id: normalizedUser.qiao_id });
  }

  async runPostLoginWarmup(): Promise<void> {
    const loadContactsTask = (async () => {
      try {
        const remoteContacts = await fetchAllContactsFromApi();
        const contacts = await saveContacts(remoteContacts);
        logger.info('Contacts loaded and saved', { count: contacts.length });
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.warn('Failed to load contacts after login', { error: err.message });
      }
    })();

    const initMessagingTask = (async () => {
      try {
        const app = getApp<AppInstance>();
        await app.initMessageService();
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.warn('Init message service after login failed', { error: err.message });
      }
    })();

    await Promise.allSettled([loadContactsTask, initMessagingTask]);
  }

  private async getFreshLoginCode(fallback: string): Promise<string> {
    try {
      const { code } = await wx.login();
      if (isNonEmptyString(code)) {
        return code;
      }
      return fallback;
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.warn('Failed to obtain fresh login code', { error: err.message });
      return fallback;
    }
  }

  private async checkBindingStatus(loginCode: string): Promise<{
    loginStatus: LoginStatus;
    authSuccess: AuthSuccessPayload | null;
    errorMessage: string | null;
  }> {
    try {
      const deviceId = await getDeviceId();
      const response = await requestValidated(WechatLoginCheckSchema, {
        url: '/auth/wechat/login',
        method: 'POST',
        data: {
          login_code: loginCode,
          device_id: deviceId,
        },
        auth: false,
      });

      if (response.status !== 'bound') {
        return {
          loginStatus: 'need_phone',
          authSuccess: null,
          errorMessage: null,
        };
      }

      const accessToken = response.access_token ?? '';
      const refreshToken = response.refresh_token ?? '';
      const user = response.user ?? null;
      if (!isNonEmptyString(accessToken) || !isNonEmptyString(refreshToken) || user === null) {
        return {
          loginStatus: 'idle',
          authSuccess: null,
          errorMessage: '登录失败，请重试',
        };
      }

      return {
        loginStatus: 'idle',
        authSuccess: {
          access_token: accessToken,
          refresh_token: refreshToken,
          needs_profile_setup: response.needs_profile_setup ?? false,
          user,
          message: response.message ?? undefined,
        },
        errorMessage: null,
      };
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('WeChat login status check failed', { error: err.message });
      return {
        loginStatus: 'idle',
        authSuccess: null,
        errorMessage: isNonEmptyString(err.message) ? err.message : '登录失败，请重试',
      };
    }
  }
}

export const createLoginPageService = (): LoginPageService => new LoginPageService();
