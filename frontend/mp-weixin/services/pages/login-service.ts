import { requestValidated } from '../../utils/api';
import authService from '../../utils/auth-service';
import { BUILD_INFO } from '../../utils/build-info';
import { fetchAllContactsFromApi } from '../../utils/contact-sync';
import { normalizeError } from '../../utils/errors';
import { isNonEmptyString } from '../../utils/guards';
import { getLogger } from '../../utils/logger';
import { getInvitationRuntimeContext, reportRuntimeObservation } from '../../utils/runtime-segment';
import { getDeviceId, saveContacts, type StoredAuthUser } from '../../utils/storage';
import {
  type AuthUserPayload,
  InvitationPublicIntakeResponseSchema,
  WechatBindPhoneResponseSchema,
  WechatLoginCheckSchema,
} from '../../utils/schemas';
import { BasePageService } from './base-page-service';

const logger = getLogger('LoginPageService');
const PUBLIC_INVITATION_INTAKE_ENDPOINT = '/public/invitations/intake';

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

export type WechatPhoneAuthPayload = { phoneCode: string } | { encryptedData: string; iv: string };

const normalizeAuthUser = (payload: AuthUserPayload): StoredAuthUser => ({
  qiao_id: payload.qiao_id,
  account_segment: payload.account_segment,
});

export class LoginPageService extends BasePageService {
  private voidReportLoginObservation(
    eventName: 'login_bootstrap_failed' | 'login_status_check_failed' | 'login_bind_failed',
    eventPayload: Record<string, unknown>
  ): void {
    void reportRuntimeObservation({
      eventName,
      pagePath: '/pages/login/login',
      entrySource: 'login',
      eventPayload,
    });
  }
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

      if (authService.shouldBlockSilentLoginCheck()) {
        logger.info('Silent login check skipped due to manual logout block');
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
      this.voidReportLoginObservation('login_bootstrap_failed', {
        phase: 'bootstrap',
        source: source ?? '',
        error_message: err.message,
      });
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

  async bindPhone(
    phoneAuthPayload: WechatPhoneAuthPayload,
    currentLoginCode: string
  ): Promise<LoginBindResult> {
    try {
      const loginCode = await this.getFreshLoginCode(currentLoginCode);
      if (!isNonEmptyString(loginCode)) {
        throw new Error('登录失败，请重试');
      }
      const deviceId = await getDeviceId();
      const bindPayload =
        'phoneCode' in phoneAuthPayload
          ? { phone_code: phoneAuthPayload.phoneCode }
          : {
              encrypted_data: phoneAuthPayload.encryptedData,
              iv: phoneAuthPayload.iv,
            };
      const response = await requestValidated(WechatBindPhoneResponseSchema, {
        url: '/auth/wechat/bind-phone',
        method: 'POST',
        data: {
          login_code: loginCode,
          ...bindPayload,
          device_id: deviceId,
          build_id: BUILD_INFO.id,
          build_time: BUILD_INFO.builtAt,
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
    } catch (error: unknown) {
      const err = normalizeError(error);
      this.voidReportLoginObservation('login_bind_failed', {
        phase: 'bind_phone',
        error_message: err.message,
        has_phone_code: 'phoneCode' in phoneAuthPayload,
        has_encrypted_data: 'encryptedData' in phoneAuthPayload,
      });
      throw error;
    }
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

    await Promise.all([loadContactsTask, initMessagingTask]);
  }

  async intakeInviteCode(options: {
    source: 'login' | 'link';
    trigger: 'clipboard' | 'link_param' | 'manual_input';
    rawText?: string;
    inviteCode?: string;
  }): Promise<string> {
    const seq = this.startRequest();
    const deviceId = await getDeviceId();
    const runtimeContext = getInvitationRuntimeContext();
    const runtimeObservationId = await reportRuntimeObservation({
      eventName: 'invite_intake_attempt',
      pagePath: '/pages/login/login',
      entrySource: options.source,
      eventPayload: {
        trigger: options.trigger,
        invite_code: options.inviteCode ?? '',
        clipboard_raw_text: options.trigger === 'clipboard' ? (options.rawText ?? '') : '',
      },
    });
    const response = await requestValidated(InvitationPublicIntakeResponseSchema, {
      url: PUBLIC_INVITATION_INTAKE_ENDPOINT,
      method: 'POST',
      data: {
        source: options.source,
        trigger: options.trigger,
        raw_text: options.rawText,
        invite_code: options.inviteCode,
        device_id: deviceId,
        ...runtimeContext,
        runtime_observation_id: runtimeObservationId ?? runtimeContext.runtime_observation_id,
      },
      auth: false,
    });
    if (!this.isRequestActive(seq)) {
      return '';
    }
    if (!response.valid || !isNonEmptyString(response.recognized_code)) {
      return '';
    }
    return response.recognized_code;
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
          build_id: BUILD_INFO.id,
          build_time: BUILD_INFO.builtAt,
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
      this.voidReportLoginObservation('login_status_check_failed', {
        phase: 'wechat_login_status_check',
        error_message: err.message,
      });
      return {
        loginStatus: 'idle',
        authSuccess: null,
        errorMessage: isNonEmptyString(err.message) ? err.message : '登录失败，请重试',
      };
    }
  }
}

export const createLoginPageService = (): LoginPageService => new LoginPageService();
