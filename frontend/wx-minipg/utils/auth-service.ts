import { get, post } from './api';
import { STORAGE_KEYS } from './config';
import { getLogger } from './logger';
import { saveUserInfo, StoredAuthUser } from './storage';

const logger = getLogger('AuthService');

interface RefreshTokenResponse {
  access_token: string;
}

class AuthService {
  private _isAuthenticated = false;

  private _token: string | null = null;

  private _userInfo: StoredAuthUser | null = null;

  private _initialized = false;

  private _initPromise: Promise<boolean> | null = null;

  async initialize(): Promise<boolean> {
    if (this._initPromise) {
      logger.info('Initialization already in progress, waiting...');
      return this._initPromise;
    }

    this._initPromise = this._doInitialize();
    return this._initPromise;
  }

  private async _doInitialize(): Promise<boolean> {
    try {
      logger.info('=== AuthService Initialization Start ===');

      const token = wx.getStorageSync<string>(STORAGE_KEYS.AUTH_TOKEN) ?? null;

      if (!token) {
        logger.info('No token found, user not authenticated');
        this._setAuthState(false, null, null);
        this._initialized = true;
        return false;
      }

      logger.info('Token found, verifying with backend', {
        tokenLength: token.length,
        tokenPrefix: `${token.substring(0, 10)}...`,
      });

      try {
        const userInfo = await get<StoredAuthUser>('/user/profile');
        await saveUserInfo(userInfo);
        this._setAuthState(true, token, userInfo);
        this._initialized = true;
        logger.info('=== AuthService Initialization Complete (Authenticated) ===');
        return true;
      } catch (error) {
        logger.warn('Token verification failed, clearing invalid token', {
          error: error instanceof Error ? error.message : String(error),
          statusCode: (error as { statusCode?: number }).statusCode,
        });

        wx.removeStorageSync(STORAGE_KEYS.AUTH_TOKEN);
        this._setAuthState(false, null, null);
        this._initialized = true;
        logger.info('=== AuthService Initialization Complete (Not Authenticated) ===');
        return false;
      }
    } catch (error) {
      logger.error('Initialization failed', {
        error: error instanceof Error ? error.message : String(error),
      });

      this._setAuthState(false, null, null);
      this._initialized = true;
      return false;
    }
  }

  async waitForInit(): Promise<boolean> {
    if (this._initialized) {
      return this._isAuthenticated;
    }

    if (this._initPromise) {
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

  async login(token: string, userInfo: StoredAuthUser): Promise<void> {
    logger.info('Login called', { qiao_id: userInfo.qiao_id });
    wx.setStorageSync(STORAGE_KEYS.AUTH_TOKEN, token);
    await saveUserInfo(userInfo);
    this._setAuthState(true, token, userInfo);
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
    } catch (error) {
      logger.error('Logout API call failed', {
        error: error instanceof Error ? error.message : String(error),
      });
    }

    wx.removeStorageSync(STORAGE_KEYS.AUTH_TOKEN);
    wx.removeStorageSync(STORAGE_KEYS.USER_INFO);
    this._setAuthState(false, null, null);
    logger.info('Logout complete');
  }

  async refreshToken(): Promise<string> {
    try {
      logger.info('Refreshing token');
      const data = await post<RefreshTokenResponse>('/auth/refresh-token');
      wx.setStorageSync(STORAGE_KEYS.AUTH_TOKEN, data.access_token);
      this._token = data.access_token;
      logger.info('Token refreshed successfully');
      return data.access_token;
    } catch (error) {
      logger.error('Refresh token failed', {
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
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

    logger.debug('Auth state updated', {
      isAuthenticated,
      hasToken: Boolean(token),
      hasUserInfo: Boolean(userInfo),
      qiao_id: userInfo?.qiao_id,
    });
  }

  _resetForTesting(): void {
    this._initialized = false;
    this._initPromise = null;
    this._setAuthState(false, null, null);
  }
}

const authService = new AuthService();

export default authService;
export { AuthService };
