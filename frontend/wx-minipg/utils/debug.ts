/**
 * Debug utilities for development
 */

import { getLogger } from './logger';
import { STORAGE_KEYS } from './config';
import { isDefined, isNonEmptyString } from './guards';
import { normalizeError } from './errors';

const logger = getLogger('Debug');

interface StorageStatusField {
  exists: boolean;
}

interface TokenStatus extends StorageStatusField {
  length: number;
  prefix: string;
}

interface UserInfoStatus extends StorageStatusField {
  data: Record<string, unknown> | null;
}

interface VerifiedFieldStatus extends StorageStatusField {
  length?: number;
  value?: string;
}

interface StorageStatus {
  token: TokenStatus;
  userInfo: UserInfoStatus;
  verifiedPhoneToken: VerifiedFieldStatus;
  verifiedPhone: VerifiedFieldStatus;
}

interface GlobalDataStatus {
  token: boolean;
  userInfo: boolean;
  messageService: boolean;
  systemInfo: boolean;
}

interface AppGlobalData {
  token?: boolean;
  userInfo?: unknown;
  messageService?: unknown;
  systemInfo?: unknown;
}

/**
 * Check storage status
 * @returns {Object} Storage status
 */
export function checkStorage(): StorageStatus | null {
  try {
    const storedToken = wx.getStorageSync<string>(STORAGE_KEYS.AUTH_TOKEN);
    const token = isNonEmptyString(storedToken) ? storedToken : '';
    const storedUserInfo = wx.getStorageSync<string>(STORAGE_KEYS.USER_INFO);
    const userInfoRaw = isNonEmptyString(storedUserInfo) ? storedUserInfo : '';
    const storedVerifiedPhoneToken = wx.getStorageSync<string>('verified_phone_token');
    const verifiedPhoneToken = isNonEmptyString(storedVerifiedPhoneToken)
      ? storedVerifiedPhoneToken
      : '';
    const storedVerifiedPhone = wx.getStorageSync<string>('verified_phone');
    const verifiedPhone = isNonEmptyString(storedVerifiedPhone) ? storedVerifiedPhone : '';

    const hasToken = isNonEmptyString(token);
    const hasUserInfo = isNonEmptyString(userInfoRaw);
    const hasVerifiedPhoneToken = isNonEmptyString(verifiedPhoneToken);
    const hasVerifiedPhone = isNonEmptyString(verifiedPhone);

    const status: StorageStatus = {
      token: {
        exists: hasToken,
        length: token.length,
        prefix: hasToken ? `${token.substring(0, 10)}...` : 'none',
      },
      userInfo: {
        exists: hasUserInfo,
        data: hasUserInfo ? (JSON.parse(userInfoRaw) as Record<string, unknown>) : null,
      },
      verifiedPhoneToken: {
        exists: hasVerifiedPhoneToken,
        length: verifiedPhoneToken.length,
      },
      verifiedPhone: {
        exists: hasVerifiedPhone,
        value: hasVerifiedPhone ? verifiedPhone : 'none',
      },
    };

    logger.info('=== Storage Status ===');
    logger.info('Token:', status.token);
    logger.info('User Info:', status.userInfo);
    logger.info('Verified Phone Token:', status.verifiedPhoneToken);
    logger.info('Verified Phone:', status.verifiedPhone);
    logger.info('=====================');

    return status;
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('Check storage failed', {
      errorMessage: err.message,
    });
    return null;
  }
}

/**
 * Clear all storage
 */
export function clearAllStorage(): void {
  try {
    wx.clearStorageSync();
    logger.info('All storage cleared');
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('Clear storage failed', {
      errorMessage: err.message,
    });
  }
}

/**
 * Show storage status in modal
 */
export function showStorageStatus(): void {
  const status = checkStorage();

  if (status === null) {
    void wx.showModal({
      title: 'Storage Status',
      content: 'Failed to check storage',
      showCancel: false,
    });
    return;
  }

  const content = `
Token: ${status.token.exists ? 'EXISTS' : 'NOT FOUND'}
User Info: ${status.userInfo.exists ? 'EXISTS' : 'NOT FOUND'}
Verified Phone Token: ${status.verifiedPhoneToken.exists ? 'EXISTS' : 'NOT FOUND'}
Verified Phone: ${status.verifiedPhone.value}
  `.trim();

  void wx.showModal({
    title: 'Storage Status',
    content: content,
    showCancel: false,
  });
}

/**
 * Check global data
 */
export function checkGlobalData(): GlobalDataStatus | null {
  try {
    const app = getApp();
    const typedApp = app as { globalData?: AppGlobalData };
    const globalData = typedApp.globalData ?? {};

    const status: GlobalDataStatus = {
      token: globalData.token === true,
      userInfo: isDefined(globalData.userInfo),
      messageService: isDefined(globalData.messageService),
      systemInfo: isDefined(globalData.systemInfo),
    };

    logger.info('=== Global Data Status ===');
    logger.info('Token:', status.token);
    logger.info('User Info:', status.userInfo);
    logger.info('Message Service:', status.messageService);
    logger.info('System Info:', status.systemInfo);
    logger.info('=========================');

    return status;
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('Check global data failed', {
      errorMessage: err.message,
    });
    return null;
  }
}

/**
 * Show global data status in modal
 */
export function showGlobalDataStatus(): void {
  const status = checkGlobalData();

  if (status === null) {
    void wx.showModal({
      title: 'Global Data Status',
      content: 'Failed to check global data',
      showCancel: false,
    });
    return;
  }

  const content = `
Token: ${status.token ? 'EXISTS' : 'NOT FOUND'}
User Info: ${status.userInfo ? 'EXISTS' : 'NOT FOUND'}
Message Service: ${status.messageService ? 'INITIALIZED' : 'NOT INITIALIZED'}
System Info: ${status.systemInfo ? 'EXISTS' : 'NOT FOUND'}
  `.trim();

  void wx.showModal({
    title: 'Global Data Status',
    content: content,
    showCancel: false,
  });
}

/**
 * Show all debug info
 */
export function showDebugInfo(): void {
  void checkStorage();
  void checkGlobalData();

  void wx.showModal({
    title: 'Debug Info',
    content: 'Check console for detailed debug info',
    showCancel: false,
  });
}

export default {
  checkStorage,
  clearAllStorage,
  showStorageStatus,
  checkGlobalData,
  showGlobalDataStatus,
  showDebugInfo,
};
