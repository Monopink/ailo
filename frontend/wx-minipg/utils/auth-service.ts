import { post, registerAuthRefreshHandler, registerAuthTokenProvider } from './api';
import { STORAGE_KEYS } from './config';
import { getAvatarUrl } from './avatar';
import { getLogger } from './logger';
import { fetchCurrentUserProfile, type UserProfileResponse } from './profile';
import { saveUserInfo, StoredAuthUser } from './storage';
import { isNonEmptyString } from './guards';
import { normalizeError } from './errors';

const logger = getLogger('AuthService');

interface RefreshTokenResponse {
  access_token: string;
  expires_in: number;
}

const mapProfileToStoredUser = (profile: UserProfileResponse): StoredAuthUser => ({
  qiao_id: profile.qiao_id,
  nickname: profile.nickname ?? '',
  avatar: getAvatarUrl(profile.avatar_url ?? ''),
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
      const storedProfileSetupFlag =
        wx.getStorageSync<boolean>(STORAGE_KEYS.PROFILE_SETUP_REQUIRED);
      this._needsProfileSetup = storedProfileSetupFlag === true;

      if (!isNonEmptyString(token)) {
        logger.info('No token found, user not authenticated');
        this._clearStoredSession();
        this._initialized = true;
        return false;
      }

      logger.info('Token found, verifying with backend', {
        tokenLength: token.length,
        tokenPrefix: `${token.substring(0, 10)}...`,
      });

      const profile = await fetchCurrentUserProfile();
      const storedUser = mapProfileToStoredUser(profile);

      try {
        await saveUserInfo(storedUser);
        this._setAuthState(true, token, storedUser);
        this._initialized = true;
        logger.info('=== AuthService Initialization Complete (Authenticated) ===');
        return true;
      } catch (error: unknown) {
        const statusCandidate = error as { statusCode?: number };
        const statusCode =
          typeof statusCandidate.statusCode === 'number'
            ? statusCandidate.statusCode
            : undefined;
        const err = normalizeError(error);
        logger.warn('Token verification failed, clearing invalid token', {
          errorMessage: err.message,
          statusCode,
        });

        this._clearStoredSession();
        this._initialized = true;
        logger.info('=== AuthService Initialization Complete (Not Authenticated) ===');
        return false;
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

  async login(
    accessToken: string,
    refreshToken: string,
    userInfo: StoredAuthUser,
    options?: { needsProfileSetup?: boolean; expiresIn?: number }
  ): Promise<void> {
    logger.info('Login called', { qiao_id: userInfo.qiao_id });
    wx.setStorageSync(STORAGE_KEYS.AUTH_TOKEN, accessToken);
    wx.setStorageSync(STORAGE_KEYS.REFRESH_TOKEN, refreshToken);
    await saveUserInfo(userInfo);
    this._setAuthState(true, accessToken, userInfo);
    this.setNeedsProfileSetup(Boolean(options?.needsProfileSetup));
    logger.info('Login successful', { qiao_id: userInfo.qiao_id });
  }

  async updateUserInfo(userInfo: StoredAuthUser): Promise<void> {
    logger.info('Updating user info', { qiao_id: userInfo.qiao_id });
    await saveUserInfo(userInfo);
    this._userInfo = userInfo;
    logger.info('User info updated');
  }

  async logout(): Promise<void> {
    logger.info('Logout called');

    try {
      await post('/auth/logout');
      logger.info('Logout API call successful');
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Logout API call failed', {
        errorMessage: err.message,
      });
    }

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
      this._clearStoredSession();
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
