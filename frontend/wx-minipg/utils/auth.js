/**
 * Authentication utility
 * Handles user authentication, token management, and auth state
 */

import { get, post } from './api';
import { STORAGE_KEYS } from './config';
import { getLogger } from './logger';
import { saveUserInfo } from './storage';

const logger = getLogger('Auth');

/**
 * Check if user is authenticated
 * @returns {Promise<boolean>} True if authenticated
 */
export async function checkAuth() {
  try {
    const token = wx.getStorageSync(STORAGE_KEYS.AUTH_TOKEN);
    logger.info('Checking auth', {
      hasToken: !!token,
      tokenLength: token ? token.length : 0,
      tokenPrefix: token ? token.substring(0, 10) + '...' : 'none'
    });

    if (!token) {
      logger.info('No token found in storage');
      return false;
    }

    // Verify token with backend
    logger.info('Verifying token with backend');
    const userInfo = await get('/user/profile');
    logger.info('Token verified successfully', { qiao_id: userInfo.qiao_id });

    // Save user info
    await saveUserInfo(userInfo);

    // Update global data
    const app = getApp();
    app.setUserInfo(userInfo);

    logger.info('User authenticated', { qiao_id: userInfo.qiao_id });
    return true;
  } catch (error) {
    logger.error('Check auth failed', {
      error: error.message || error,
      statusCode: error.statusCode,
      errorDetail: error.detail
    });

    // Clear invalid token
    logger.warn('Clearing invalid token from storage');
    wx.removeStorageSync(STORAGE_KEYS.AUTH_TOKEN);

    return false;
  }
}

/**
 * Login with WeChat
 * @returns {Promise<Object>} User info and token
 */
export async function loginWithWeChat() {
  try {
    // Get WeChat login code
    const loginRes = await wx.login();

    if (!loginRes.code) {
      throw new Error('获取微信登录凭证失败');
    }

    logger.info('WeChat login code obtained', { code: loginRes.code });

    // Login with backend
    const data = await post('/auth/wechat-login', {
      code: loginRes.code,
      device_type: 4 // MiniProgram
    }, { auth: false });

    // Save token
    wx.setStorageSync(STORAGE_KEYS.AUTH_TOKEN, data.access_token);

    // Save user info
    await saveUserInfo(data.user);

    // Update global data
    const app = getApp();
    app.setToken(data.access_token);
    app.setUserInfo(data.user);

    logger.info('WeChat login successful', { qiao_id: data.user.qiao_id });

    return data;
  } catch (error) {
    logger.error('WeChat login failed', { error });
    throw error;
  }
}

/**
 * Send SMS verification code
 * @param {string} phone - Phone number
 * @param {string} captchaKey - CAPTCHA key
 * @param {string} captchaCode - CAPTCHA code
 * @returns {Promise<void>}
 */
export async function sendSmsCode(phone, captchaKey, captchaCode) {
  try {
    await post('/auth/send-sms', {
      phone,
      captcha_key: captchaKey,
      captcha_code: captchaCode
    }, { auth: false });

    logger.info('SMS code sent', { phone });
  } catch (error) {
    logger.error('Send SMS code failed', { phone, error });
    throw error;
  }
}

/**
 * Bind phone number to WeChat account
 * @param {string} phone - Phone number
 * @param {string} smsCode - SMS verification code
 * @returns {Promise<Object>} Updated user info
 */
export async function bindPhone(phone, smsCode) {
  try {
    const data = await post('/auth/bind-phone', {
      phone,
      code: smsCode
    });

    // Update user info
    await saveUserInfo(data);

    // Update global data
    const app = getApp();
    app.setUserInfo(data);

    logger.info('Phone bound successfully', { phone });

    return data;
  } catch (error) {
    logger.error('Bind phone failed', { phone, error });
    throw error;
  }
}

/**
 * Refresh auth token
 * @returns {Promise<string>} New token
 */
export async function refreshToken() {
  try {
    const data = await post('/auth/refresh-token');

    // Save new token
    wx.setStorageSync(STORAGE_KEYS.AUTH_TOKEN, data.access_token);

    // Update global data
    const app = getApp();
    app.setToken(data.access_token);

    logger.info('Token refreshed');

    return data.access_token;
  } catch (error) {
    logger.error('Refresh token failed', { error });
    throw error;
  }
}

/**
 * Logout
 * @returns {Promise<void>}
 */
export async function logout() {
  try {
    // Call logout API
    await post('/auth/logout');

    logger.info('Logout successful');
  } catch (error) {
    logger.error('Logout failed', { error });
  } finally {
    // Clear local data
    const app = getApp();
    app.clearAuth();

    // Redirect to login page
    wx.reLaunch({
      url: '/pages/login/login'
    });
  }
}

/**
 * Get CAPTCHA image
 * @returns {Promise<Object>} CAPTCHA data
 */
export async function getCaptcha() {
  try {
    const data = await get('/auth/captcha', {}, { auth: false });
    logger.info('CAPTCHA obtained', { key: data.key });
    return data;
  } catch (error) {
    logger.error('Get CAPTCHA failed', { error });
    throw error;
  }
}

/**
 * Get message client signature
 * @param {string} clientId - Client ID (user's qiao_id)
 * @returns {Promise<Object>} Signature data
 */
export async function getMessageClientSignature(clientId) {
  try {
    const data = await post('/auth/message-client', { client_id: clientId });
    logger.info('Message client signature obtained');
    return data;
  } catch (error) {
    logger.error('Get message client signature failed', { error });
    throw error;
  }
}

export default {
  checkAuth,
  loginWithWeChat,
  sendSmsCode,
  bindPhone,
  refreshToken,
  logout,
  getCaptcha,
  getMessageClientSignature
};

