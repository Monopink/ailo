/**
 * Authentication utility (Legacy)
 *
 * DEPRECATED: Most functions have been moved to auth-service.js
 * This file is kept for backward compatibility only
 *
 * New code should use:
 * - authService from './auth-service' for authentication state management
 * - requireAuth from './auth-guard' for page-level authentication checks
 */

import { get, post } from './api';
import { getLogger } from './logger';

const logger = getLogger('Auth');

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
  sendSmsCode,
  getCaptcha,
  getMessageClientSignature
};
