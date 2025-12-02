/**
 * Configuration
 * Centralized configuration for the miniprogram
 */

export interface ApiConfig {
  baseUrl: string;
  timeout: number;
  version: string;
}

export const API_CONFIG: ApiConfig = {
  // Base URL for API requests
  baseUrl: 'http://localhost:8000',

  // API timeout (ms)
  timeout: 10000,

  // API version
  version: 'v1',
};

export interface LeanCloudConfig {
  appId: string;
  appKey: string;
  serverUrl?: string;
}

export const LEANCLOUD_CONFIG: LeanCloudConfig = {
  // LeanCloud App ID
  appId: 'zcuK19lcF1YirAJbKLI2vr97-gzGzoHsz',

  // LeanCloud App Key
  appKey: 'v8GM18oGSxzQTKpgQvdIfy2I',

  // LeanCloud Server URL (optional)
  serverUrl: 'https://zcuk19lc.lc-cn-n1-shared.com',
};

export interface MessageConfig {
  maxLength: number;
  rateLimit: number;
  rateLimitWindow: number;
  typingDebounce: number;
  typingTimeout: number;
  maxRetryCount: number;
  retryDelay: number;
}

export const MESSAGE_CONFIG: MessageConfig = {
  // Maximum message length
  maxLength: 49,

  // Message send rate limit (messages per 10 seconds)
  rateLimit: 5,

  // Message send rate limit window (ms)
  rateLimitWindow: 10000,

  // Typing indicator debounce time (ms)
  typingDebounce: 1000,

  // Typing indicator timeout (ms)
  typingTimeout: 30000,

  // Message retry count
  maxRetryCount: 3,

  // Message retry delay (ms)
  retryDelay: 2000,
};

export const STORAGE_KEYS = {
  // Auth token
  AUTH_TOKEN: 'auth_token',

  // User info
  USER_INFO: 'user_info',

  // Contacts list
  CONTACTS: 'contact_list',

  // Messages (prefix, append conv_id)
  MESSAGES: 'messages_',

  // Local settings
  SETTINGS: 'local_settings',
} as const;

export type StorageKey = (typeof STORAGE_KEYS)[keyof typeof STORAGE_KEYS];

export interface AppConfig {
  brandName: string;
  maxNicknameLength: number;
  maxBioLength: number;
}

export const APP_CONFIG: AppConfig = {
  // Brand name
  brandName: '敲敲',

  // Max nickname length
  maxNicknameLength: 10,

  // Max bio length
  maxBioLength: 70,
};

export interface AvatarSize {
  small: number;
  medium: number;
  large: number;
  xlarge: number;
}

export interface InputMaxLength {
  nickname: number;
  bio: number;
  message: number;
  verifyMessage: number;
}

export interface UiConfig {
  primaryColor: string;
  accentColor: string;
  avatarSize: AvatarSize;
  inputMaxLength: InputMaxLength;
}

export const UI_CONFIG: UiConfig = {
  // Primary color
  primaryColor: '#42db5a',

  // Accent color
  accentColor: '#fdd700',

  // Avatar size
  avatarSize: {
    small: 32,
    medium: 48,
    large: 64,
    xlarge: 80,
  },

  // Input max length
  inputMaxLength: {
    nickname: 10,
    bio: 70,
    message: 49,
    verifyMessage: 100,
  },
};

export interface ValidationRules {
  phone: RegExp;
  smsCode: RegExp;
  nicknameMinLength: number;
  nicknameMaxLength: number;
  bioMaxLength: number;
  messageMaxLength: number;
  verifyMessageMaxLength: number;
}

export const VALIDATION_RULES: ValidationRules = {
  // Phone number regex
  phone: /^1[3-9]\d{9}$/,

  // SMS code regex
  smsCode: /^\d{6}$/,

  // Nickname length
  nicknameMinLength: 1,
  nicknameMaxLength: 10,

  // Bio length
  bioMaxLength: 70,

  // Message length
  messageMaxLength: 49,

  // Verify message length
  verifyMessageMaxLength: 100,
};

// Captcha (Human Verification)
// Hardcode provider/region/scene for MVP; fill SceneId with your Aliyun value.
export const CAPTCHA_PROVIDER = 'aliyun';
export const CAPTCHA_REGION = 'cn';
// TODO: Replace with your Aliyun Captcha SceneId
export const CAPTCHA_SCENE_ID = '1qtkm8nb';

const config = {
  APP_CONFIG,
  API_CONFIG,
  LEANCLOUD_CONFIG,
  MESSAGE_CONFIG,
  STORAGE_KEYS,
  UI_CONFIG,
  VALIDATION_RULES,
  CAPTCHA_PROVIDER,
  CAPTCHA_REGION,
  CAPTCHA_SCENE_ID,
};

export default config;
