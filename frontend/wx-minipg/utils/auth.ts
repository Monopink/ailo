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

interface CaptchaResponse {
  key: string;
  image: string;
  expire_at?: number;
}

export async function sendSmsCode(
  phone: string,
  captchaKey: string,
  captchaCode: string
): Promise<void> {
  try {
    await post(
      '/auth/send-sms',
      {
        phone,
        captcha_key: captchaKey,
        captcha_code: captchaCode,
      },
      { auth: false }
    );

    logger.info('SMS code sent', { phone });
  } catch (error) {
    logger.error('Send SMS code failed', { phone, error });
    throw error;
  }
}

export async function getCaptcha(): Promise<CaptchaResponse> {
  try {
    const data = await get<CaptchaResponse>('/auth/captcha', {}, { auth: false });
    logger.info('CAPTCHA obtained', { key: data.key });
    return data;
  } catch (error) {
    logger.error('Get CAPTCHA failed', { error });
    throw error;
  }
}

export async function getMessageClientSignature(clientId: string): Promise<Says.MessageSignature> {
  try {
    const data = await post<Says.MessageSignature>('/lc-im/signature', { client_id: clientId });
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
  getMessageClientSignature,
};
