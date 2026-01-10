/**
 * Validator utility
 * Provides validation functions for user input
 */

import { VALIDATION_RULES } from './config';
import { isNonEmptyString } from './guards';

export interface ValidationResult {
  valid: boolean;
  message?: string;
}

/**
 * Validate phone number
 * @param {string} phone - Phone number
 * @returns {Object} Validation result
 */
export function validatePhone(phone: string | null | undefined): ValidationResult {
  if (!isNonEmptyString(phone)) {
    return { valid: false, message: '请输入手机号' };
  }

  if (!VALIDATION_RULES.phone.test(phone)) {
    return { valid: false, message: '请输入正确的手机号' };
  }

  return { valid: true };
}

/**
 * Validate SMS code
 * @param {string} code - SMS code
 * @returns {Object} Validation result
 */
export function validateSmsCode(code: string | null | undefined): ValidationResult {
  if (!isNonEmptyString(code)) {
    return { valid: false, message: '请输入验证码' };
  }

  if (!VALIDATION_RULES.smsCode.test(code)) {
    return { valid: false, message: '请输入6位数字验证码' };
  }

  return { valid: true };
}

/**
 * Validate nickname
 * @param {string} nickname - Nickname
 * @returns {Object} Validation result
 */
export function validateNickname(nickname: string | null | undefined): ValidationResult {
  if (!isNonEmptyString(nickname)) {
    return { valid: false, message: '请输入昵称' };
  }

  if (nickname.length < VALIDATION_RULES.nicknameMinLength) {
    return { valid: false, message: `昵称至少${VALIDATION_RULES.nicknameMinLength}个字符` };
  }

  if (nickname.length > VALIDATION_RULES.nicknameMaxLength) {
    return { valid: false, message: `昵称最多${VALIDATION_RULES.nicknameMaxLength}个字符` };
  }

  return { valid: true };
}

/**
 * Validate bio
 * @param {string} bio - Bio
 * @returns {Object} Validation result
 */
export function validateBio(bio: string | null | undefined): ValidationResult {
  if (!isNonEmptyString(bio)) {
    return { valid: true }; // Bio is optional
  }

  if (bio.length > VALIDATION_RULES.bioMaxLength) {
    return { valid: false, message: `个人简介最多${VALIDATION_RULES.bioMaxLength}个字符` };
  }

  return { valid: true };
}

/**
 * Validate message
 * @param {string} message - Message
 * @returns {Object} Validation result
 */
export function validateMessage(message: string | null | undefined): ValidationResult {
  if (!isNonEmptyString(message)) {
    return { valid: false, message: '请输入消息内容' };
  }

  if (message.length > VALIDATION_RULES.messageMaxLength) {
    return { valid: false, message: `消息最多${VALIDATION_RULES.messageMaxLength}个字符` };
  }

  return { valid: true };
}

/**
 * Validate verify message
 * @param {string} message - Verify message
 * @returns {Object} Validation result
 */
export function validateVerifyMessage(message: string | null | undefined): ValidationResult {
  if (!isNonEmptyString(message)) {
    return { valid: true }; // Verify message is optional
  }

  if (message.length > VALIDATION_RULES.verifyMessageMaxLength) {
    return {
      valid: false,
      message: `验证消息最多${VALIDATION_RULES.verifyMessageMaxLength}个字符`,
    };
  }

  return { valid: true };
}

/**
 * Validate gender
 * @param {number} gender - Gender
 * @returns {Object} Validation result
 */
export function validateGender(gender: number | null | undefined): ValidationResult {
  if (gender === null || gender === undefined) {
    return { valid: false, message: '请选择性别' };
  }

  if (![1, 2].includes(gender)) {
    return { valid: false, message: '性别值无效' };
  }

  return { valid: true };
}

export default {
  validatePhone,
  validateSmsCode,
  validateNickname,
  validateBio,
  validateMessage,
  validateVerifyMessage,
  validateGender,
};
