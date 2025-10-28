/**
 * Debug utilities for development
 */

import { getLogger } from './logger';
import { STORAGE_KEYS } from './config';

const logger = getLogger('Debug');

/**
 * Check storage status
 * @returns {Object} Storage status
 */
export function checkStorage() {
  try {
    const token = wx.getStorageSync(STORAGE_KEYS.AUTH_TOKEN);
    const userInfo = wx.getStorageSync(STORAGE_KEYS.USER_INFO);
    const verifiedPhoneToken = wx.getStorageSync('verified_phone_token');
    const verifiedPhone = wx.getStorageSync('verified_phone');

    const status = {
      token: {
        exists: !!token,
        length: token ? token.length : 0,
        prefix: token ? token.substring(0, 10) + '...' : 'none'
      },
      userInfo: {
        exists: !!userInfo,
        data: userInfo ? JSON.parse(userInfo) : null
      },
      verifiedPhoneToken: {
        exists: !!verifiedPhoneToken,
        length: verifiedPhoneToken ? verifiedPhoneToken.length : 0
      },
      verifiedPhone: {
        exists: !!verifiedPhone,
        value: verifiedPhone || 'none'
      }
    };

    logger.info('=== Storage Status ===');
    logger.info('Token:', status.token);
    logger.info('User Info:', status.userInfo);
    logger.info('Verified Phone Token:', status.verifiedPhoneToken);
    logger.info('Verified Phone:', status.verifiedPhone);
    logger.info('=====================');

    return status;
  } catch (error) {
    logger.error('Check storage failed', { error });
    return null;
  }
}

/**
 * Clear all storage
 */
export function clearAllStorage() {
  try {
    wx.clearStorageSync();
    logger.info('All storage cleared');
  } catch (error) {
    logger.error('Clear storage failed', { error });
  }
}

/**
 * Show storage status in modal
 */
export function showStorageStatus() {
  const status = checkStorage();
  
  if (!status) {
    wx.showModal({
      title: 'Storage Status',
      content: 'Failed to check storage',
      showCancel: false
    });
    return;
  }

  const content = `
Token: ${status.token.exists ? 'EXISTS' : 'NOT FOUND'}
User Info: ${status.userInfo.exists ? 'EXISTS' : 'NOT FOUND'}
Verified Phone Token: ${status.verifiedPhoneToken.exists ? 'EXISTS' : 'NOT FOUND'}
Verified Phone: ${status.verifiedPhone.value}
  `.trim();

  wx.showModal({
    title: 'Storage Status',
    content: content,
    showCancel: false
  });
}

/**
 * Check global data
 */
export function checkGlobalData() {
  try {
    const app = getApp();
    const globalData = app.globalData;

    const status = {
      token: !!globalData.token,
      userInfo: !!globalData.userInfo,
      messageService: !!globalData.messageService,
      systemInfo: !!globalData.systemInfo
    };

    logger.info('=== Global Data Status ===');
    logger.info('Token:', status.token);
    logger.info('User Info:', status.userInfo);
    logger.info('Message Service:', status.messageService);
    logger.info('System Info:', status.systemInfo);
    logger.info('=========================');

    return status;
  } catch (error) {
    logger.error('Check global data failed', { error });
    return null;
  }
}

/**
 * Show global data status in modal
 */
export function showGlobalDataStatus() {
  const status = checkGlobalData();
  
  if (!status) {
    wx.showModal({
      title: 'Global Data Status',
      content: 'Failed to check global data',
      showCancel: false
    });
    return;
  }

  const content = `
Token: ${status.token ? 'EXISTS' : 'NOT FOUND'}
User Info: ${status.userInfo ? 'EXISTS' : 'NOT FOUND'}
Message Service: ${status.messageService ? 'INITIALIZED' : 'NOT INITIALIZED'}
System Info: ${status.systemInfo ? 'EXISTS' : 'NOT FOUND'}
  `.trim();

  wx.showModal({
    title: 'Global Data Status',
    content: content,
    showCancel: false
  });
}

/**
 * Show all debug info
 */
export function showDebugInfo() {
  checkStorage();
  checkGlobalData();
  
  wx.showModal({
    title: 'Debug Info',
    content: 'Check console for detailed debug info',
    showCancel: false
  });
}

export default {
  checkStorage,
  clearAllStorage,
  showStorageStatus,
  checkGlobalData,
  showGlobalDataStatus,
  showDebugInfo
};

