import { post, registerAuthRefreshHandler, registerAuthTokenProvider } from './api';
import { STORAGE_KEYS } from './config';
import { getLogger } from './logger';
import { fetchCurrentUserProfile, type UserProfileResponse } from './profile';
import profileService from './profile-service';
import { saveUserInfo, StoredAuthUser } from './storage';
import { isNonEmptyString } from './guards';
import { normalizeError } from './errors';
import conversationPresenceStore from './message/conversation-presence-store';

const logger = getLogger('AuthService');

interface RefreshTokenResponse {
  access_token: string;
  expires_in: number;
}

type ErrorLike = {
  statusCode?: number;
  status?: number;
  reason?: string;
  errorCode?: string | number;
  data?: unknown;
  message?: string;
};

const toRecord = (value: unknown): Record<string, unknown> | null => {
  if (value === null || typeof value !== 'object') {
    return null;
  }
  return value as Record<string, unknown>;
};

const toNumberCode = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
};

const resolveStatusCode = (error: unknown): number | null => {
  const errorLike = error as ErrorLike;
  if (typeof errorLike.statusCode === 'number') {
    return errorLike.statusCode;
  }
  if (typeof errorLike.status === 'number') {
    return errorLike.status;
  }
  return null;
};

const resolveErrorReason = (error: unknown): string => {
  const errorLike = error as ErrorLike;
  if (typeof errorLike.reason === 'string') {
    return errorLike.reason;
  }
  const data = toRecord(errorLike.data);
  if (typeof data?.reason === 'string') {
    return data.reason;
  }
  const detail = toRecord(data?.detail);
  if (typeof detail?.reason === 'string') {
    return detail.reason;
  }
  return '';
};

const resolveErrorCode = (error: unknown): number | null => {
  const errorLike = error as ErrorLike;
  const directCode = toNumberCode(errorLike.errorCode);
  if (directCode !== null) {
    return directCode;
  }
  const data = toRecord(errorLike.data);
  const dataCode = toNumberCode(data?.error_code);
  if (dataCode !== null) {
    return dataCode;
  }
  const detail = toRecord(data?.detail);
  return toNumberCode(detail?.error_code);
};

const isAuthInvalidError = (error: unknown): boolean => {
  const statusCode = resolveStatusCode(error);
  if (statusCode === 401 || statusCode === 403) {
    return true;
  }

  const errorCode = resolveErrorCode(error);
  if (errorCode !== null && errorCode % 10000 === 2001) {
    return true;
  }

  const reason = resolveErrorReason(error).toUpperCase();
  return (
    reason === 'UNAUTHORIZED' ||
    reason === 'AUTH_REQUIRED' ||
    reason === 'TOKEN_INVALID' ||
    reason === 'TOKEN_EXPIRED' ||
    reason === 'REFRESH_TOKEN_INVALID'
  );
};

const isTransientAuthError = (error: unknown): boolean => {
  const statusCode = resolveStatusCode(error);
  if (
    statusCode === 408 ||
    statusCode === 429 ||
    statusCode === 502 ||
    statusCode === 503 ||
    statusCode === 504
  ) {
    return true;
  }
  if (statusCode !== null && statusCode >= 500) {
    return true;
  }

  const err = normalizeError(error);
  const message = err.message.toLowerCase();
  return (
    message.includes('timeout') ||
    message.includes('time out') ||
    message.includes('request:fail') ||
    message.includes('network') ||
    message.includes('请求超时') ||
    message.includes('网络')
  );
};

const getStoredUserInfoSync = (): StoredAuthUser | null => {
  try {
    const stored = wx.getStorageSync<StoredAuthUser | null>(STORAGE_KEYS.USER_INFO);
    if (stored !== null && typeof stored === 'object' && isNonEmptyString(stored.qiao_id)) {
      return stored;
    }
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.warn('Read stored user info failed', { error: err.message });
  }
  return null;
};

const mapProfileToStoredUser = (profile: UserProfileResponse): StoredAuthUser => ({
  qiao_id: profile.qiao_id,
});

class AuthService {
  private _isAuthenticated = false;

  private _token: string | null = null;

  private _userInfo: StoredAuthUser | null = null;

  private _initialized = false;

  private _initPromise: Promise<boolean> | null = null;

  private _needsProfileSetup = false;

  private _refreshPromise: Promise<string> | null = null;

  async initialize(): Promise<boolean> {
    if (this._initPromise !== null) {
      logger.info('Initialization already in progress, waiting...');
      return this._initPromise;
    }

    this._initPromise = this._doInitialize();
    return this._initPromise;
  }

  private async _doInitialize(): Promise<boolean> {
    try {
      logger.info('=== AuthService Initialization Start ===');

      const storedToken = wx.getStorageSync<string>(STORAGE_KEYS.AUTH_TOKEN);
      const token = isNonEmptyString(storedToken) ? storedToken : '';
      const storedProfileSetupFlag = wx.getStorageSync<boolean>(
        STORAGE_KEYS.PROFILE_SETUP_REQUIRED
      );
      this._needsProfileSetup = storedProfileSetupFlag === true;

      if (!isNonEmptyString(token)) {
        logger.info('No token found, user not authenticated');
        this._clearStoredSession();
        this._initialized = true;
        return false;
      }

      const storedUser = getStoredUserInfoSync();

      logger.info('Token found, verifying with backend', {
        tokenLength: token.length,
        hasStoredUser: storedUser !== null,
      });

      try {
        const profile = await fetchCurrentUserProfile();
        const verifiedUser = mapProfileToStoredUser(profile);
        await saveUserInfo(verifiedUser);
        this._setAuthState(true, token, verifiedUser);
        this._initialized = true;
        logger.info('=== AuthService Initialization Complete (Authenticated) ===');
        return true;
      } catch (error: unknown) {
        const err = normalizeError(error);
        const statusCode = resolveStatusCode(error);

        if (isAuthInvalidError(error)) {
          logger.warn('Token verification failed with invalid auth, clearing session', {
            errorMessage: err.message,
            statusCode,
          });
          this._clearStoredSession();
          this._initialized = true;
          logger.info('=== AuthService Initialization Complete (Not Authenticated) ===');
          return false;
        }

        logger.warn('Token verification unavailable, entering degraded auth mode', {
          errorMessage: err.message,
          statusCode,
          transient: isTransientAuthError(error),
        });

        this._setAuthState(true, token, storedUser);
        this._initialized = true;
        logger.info('=== AuthService Initialization Complete (Degraded Auth) ===');
        return true;
      }
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Initialization failed', {
        errorMessage: err.message,
      });

      this._clearStoredSession();
      this._initialized = true;
      return false;
    }
  }

  async waitForInit(): Promise<boolean> {
    if (this._initialized) {
      return this._isAuthenticated;
    }

    if (this._initPromise !== null) {
      return this._initPromise;
    }

    return this.initialize();
  }

  isAuthenticated(): boolean {
    if (!this._initialized) {
      logger.warn('isAuthenticated() called before initialization complete');
    }
    return this._isAuthenticated;
  }

  getToken(): string | null {
    return this._token;
  }

  getUserInfo(): StoredAuthUser | null {
    return this._userInfo;
  }

  needsProfileSetup(): boolean {
    return this._needsProfileSetup;
  }

  setNeedsProfileSetup(flag: boolean): void {
    this._needsProfileSetup = flag;
    if (flag) {
      wx.setStorageSync(STORAGE_KEYS.PROFILE_SETUP_REQUIRED, true);
    } else {
      wx.removeStorageSync(STORAGE_KEYS.PROFILE_SETUP_REQUIRED);
    }
  }

  shouldBlockSilentLoginCheck(): boolean {
    return wx.getStorageSync<boolean>(STORAGE_KEYS.MANUAL_LOGOUT_BLOCK_SILENT_LOGIN) === true;
  }

  async login(
    accessToken: string,
    refreshToken: string,
    userInfo: StoredAuthUser,
    options?: { needsProfileSetup?: boolean; expiresIn?: number }
  ): Promise<void> {
    logger.info('Login called', { qiao_id: userInfo.qiao_id });
    wx.setStorageSync(STORAGE_KEYS.AUTH_TOKEN, accessToken);
    wx.setStorageSync(STORAGE_KEYS.REFRESH_TOKEN, refreshToken);
    wx.removeStorageSync(STORAGE_KEYS.MANUAL_LOGOUT_BLOCK_SILENT_LOGIN);
    await saveUserInfo(userInfo);
    this._setAuthState(true, accessToken, userInfo);
    this.setNeedsProfileSetup(Boolean(options?.needsProfileSetup));
    logger.info('Login successful', { qiao_id: userInfo.qiao_id });
    void profileService.loadProfile().catch((error: unknown) => {
      logger.warn('Preload profile failed after login', {
        error: error instanceof Error ? error.message : String(error),
      });
    });
  }

  async updateUserInfo(userInfo: StoredAuthUser): Promise<void> {
    logger.info('Updating user info', { qiao_id: userInfo.qiao_id });
    await saveUserInfo(userInfo);
    this._userInfo = userInfo;
    logger.info('User info updated');
  }

  async logout(): Promise<void> {
    logger.info('Logout called');
    wx.setStorageSync(STORAGE_KEYS.MANUAL_LOGOUT_BLOCK_SILENT_LOGIN, true);

    try {
      await post('/auth/logout');
      logger.info('Logout API call successful');
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Logout API call failed', {
        errorMessage: err.message,
      });
    }

    profileService.clearProfile();
    this._clearStoredSession();
    logger.info('Logout complete');
  }

  async refreshToken(): Promise<string> {
    if (this._refreshPromise !== null) {
      return this._refreshPromise;
    }

    this._refreshPromise = (async () => {
      const storedRefresh = wx.getStorageSync<string>(STORAGE_KEYS.REFRESH_TOKEN);
      if (!isNonEmptyString(storedRefresh)) {
        throw new Error('无法获取刷新凭证');
      }
      logger.info('Refreshing token');
      const data = await post<RefreshTokenResponse>(
        '/auth/refresh-token',
        { refresh_token: storedRefresh },
        { auth: false, retryAuth: false }
      );
      wx.setStorageSync(STORAGE_KEYS.AUTH_TOKEN, data.access_token);
      this._token = data.access_token;
      logger.info('Token refreshed successfully');
      return data.access_token;
    })();

    try {
      return await this._refreshPromise;
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Refresh token failed', {
        errorMessage: err.message,
      });
      if (isAuthInvalidError(error)) {
        this._clearStoredSession();
      }
      throw err;
    } finally {
      this._refreshPromise = null;
    }
  }

  private _setAuthState(
    isAuthenticated: boolean,
    token: string | null,
    userInfo: StoredAuthUser | null
  ): void {
    this._isAuthenticated = isAuthenticated;
    this._token = token;
    this._userInfo = userInfo;
    if (!isAuthenticated) {
      this.setNeedsProfileSetup(false);
    }

    logger.debug('Auth state updated', {
      isAuthenticated,
      hasToken: Boolean(token),
      hasUserInfo: Boolean(userInfo),
      qiao_id: userInfo?.qiao_id,
    });
  }

  private _clearStoredSession(): void {
    conversationPresenceStore.clearAll();
    profileService.clearProfile();
    wx.removeStorageSync(STORAGE_KEYS.AUTH_TOKEN);
    wx.removeStorageSync(STORAGE_KEYS.REFRESH_TOKEN);
    wx.removeStorageSync(STORAGE_KEYS.USER_INFO);
    wx.removeStorageSync(STORAGE_KEYS.PROFILE_SETUP_REQUIRED);
    this._setAuthState(false, null, null);
  }

  _resetForTesting(): void {
    this._initialized = false;
    this._initPromise = null;
    this._setAuthState(false, null, null);
  }
}

const authService = new AuthService();
registerAuthRefreshHandler(() => authService.refreshToken());
registerAuthTokenProvider(() => authService.getToken());

export default authService;
export { AuthService };
