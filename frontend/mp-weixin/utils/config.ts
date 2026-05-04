/**
 * Configuration
 * Centralized configuration for the miniprogram
 */

import { ENV, IS_DEV } from './env';
import { LOCAL_CONFIG_OVERRIDE as GENERATED_LOCAL_CONFIG_OVERRIDE } from './config.local.generated';

const normalizeBaseUrl = (value: string): string => value.trim().replace(/\/+$/, '');

const normalizePath = (value: string): string => {
  const normalized = value.trim();
  if (normalized === '') {
    return '';
  }
  return normalized.startsWith('/') ? normalized : `/${normalized}`;
};

const buildAssetUrl = (baseUrl: string, path: string): string => {
  if (baseUrl === '' || path === '') {
    return '';
  }
  return `${baseUrl.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`;
};

export interface ApiConfig {
  baseUrl: string;
  timeout: number;
  version: string;
}

const API_BASE_URLS = {
  develop: 'http://localhost:8000',
  trial: 'https://synapse.qiaoqiaoai.cn',
  release: 'https://synapse.qiaoqiaoai.cn',
} as const;

const ASSET_COS_BASE_URLS = {
  trial: 'https://cortex.qiaoqiaoai.cn',
  release: 'https://cortex.qiaoqiaoai.cn',
} as const;

const DEFAULT_ASSET_PATHS = {
  avatarPlaceholderPath: '/assets/avatar-placeholder.webp',
  demoAvatarDirPath: '/demo/avatars',
  loginBackgroundPath: '/login/bg.webp',
  officialAccountQrCodePath: '/official-account/qrcode.webp',
} as const;

export interface AssetConfig {
  cosBaseUrl: string;
  avatarPlaceholderPath: string;
  demoAvatarDirPath: string;
  loginBackgroundPath: string;
  officialAccountQrCodePath: string;
  avatarPlaceholderUrl: string;
  demoAvatarBaseUrl: string;
  loginBackgroundUrl: string;
  officialAccountQrCodeUrl: string;
}

export interface OfficialAccountConfig {
  originalId: string;
  username: string;
}

export interface LocalConfigOverride {
  API_CONFIG?: {
    baseUrl?: string;
  };
  ASSET_CONFIG?: {
    cosBaseUrl?: string;
    avatarPlaceholderPath?: string;
    demoAvatarDirPath?: string;
    loginBackgroundPath?: string;
    officialAccountQrCodePath?: string;
  };
}

const toLocalOverrideCandidate = (moduleValue: unknown): Record<string, unknown> | null => {
  if (typeof moduleValue !== 'object' || moduleValue === null) {
    return null;
  }

  const moduleRecord = moduleValue as Record<string, unknown>;
  const directCandidate = moduleRecord.LOCAL_CONFIG_OVERRIDE ?? moduleRecord.default;
  if (directCandidate === undefined) {
    return moduleRecord;
  }
  if (typeof directCandidate !== 'object' || directCandidate === null) {
    return null;
  }
  return directCandidate as Record<string, unknown>;
};

const normalizeLocalApiConfig = (
  source: Record<string, unknown>
): LocalConfigOverride['API_CONFIG'] => {
  const rawApiConfig = source.API_CONFIG;
  if (typeof rawApiConfig !== 'object' || rawApiConfig === null) {
    return undefined;
  }
  const apiRecord = rawApiConfig as Record<string, unknown>;
  if (typeof apiRecord.baseUrl !== 'string') {
    return undefined;
  }
  const baseUrl = normalizeBaseUrl(apiRecord.baseUrl);
  if (baseUrl === '') {
    return undefined;
  }
  return { baseUrl };
};

const normalizeLocalAssetConfig = (
  source: Record<string, unknown>
): LocalConfigOverride['ASSET_CONFIG'] => {
  const rawAssetConfig = source.ASSET_CONFIG;
  if (typeof rawAssetConfig !== 'object' || rawAssetConfig === null) {
    return undefined;
  }

  const assetRecord = rawAssetConfig as Record<string, unknown>;
  const normalized: NonNullable<LocalConfigOverride['ASSET_CONFIG']> = {};

  if (typeof assetRecord.cosBaseUrl === 'string') {
    const cosBaseUrl = normalizeBaseUrl(assetRecord.cosBaseUrl);
    if (cosBaseUrl !== '') {
      normalized.cosBaseUrl = cosBaseUrl;
    }
  }

  if (typeof assetRecord.avatarPlaceholderPath === 'string') {
    const avatarPlaceholderPath = normalizePath(assetRecord.avatarPlaceholderPath);
    if (avatarPlaceholderPath !== '') {
      normalized.avatarPlaceholderPath = avatarPlaceholderPath;
    }
  }

  if (typeof assetRecord.demoAvatarDirPath === 'string') {
    const demoAvatarDirPath = normalizePath(assetRecord.demoAvatarDirPath);
    if (demoAvatarDirPath !== '') {
      normalized.demoAvatarDirPath = demoAvatarDirPath;
    }
  }

  if (typeof assetRecord.loginBackgroundPath === 'string') {
    const loginBackgroundPath = normalizePath(assetRecord.loginBackgroundPath);
    if (loginBackgroundPath !== '') {
      normalized.loginBackgroundPath = loginBackgroundPath;
    }
  }

  if (typeof assetRecord.officialAccountQrCodePath === 'string') {
    const officialAccountQrCodePath = normalizePath(assetRecord.officialAccountQrCodePath);
    if (officialAccountQrCodePath !== '') {
      normalized.officialAccountQrCodePath = officialAccountQrCodePath;
    }
  }

  return Object.keys(normalized).length > 0 ? normalized : undefined;
};

const normalizeLocalConfigOverride = (moduleValue: unknown): LocalConfigOverride => {
  const source = toLocalOverrideCandidate(moduleValue);
  if (source === null) {
    return {};
  }

  const API_CONFIG = normalizeLocalApiConfig(source);
  const ASSET_CONFIG = normalizeLocalAssetConfig(source);

  const normalized: LocalConfigOverride = {};
  if (API_CONFIG !== undefined) {
    normalized.API_CONFIG = API_CONFIG;
  }
  if (ASSET_CONFIG !== undefined) {
    normalized.ASSET_CONFIG = ASSET_CONFIG;
  }
  return normalized;
};

const localConfigOverride = normalizeLocalConfigOverride(GENERATED_LOCAL_CONFIG_OVERRIDE);
const hasLocalOverride = Object.keys(localConfigOverride).length > 0;

if (!IS_DEV && hasLocalOverride) {
  console.warn('[config] local override is ignored outside develop environment');
}

const effectiveLocalOverride: LocalConfigOverride = IS_DEV ? localConfigOverride : {};

const effectiveApiBaseUrl = effectiveLocalOverride.API_CONFIG?.baseUrl ?? API_BASE_URLS[ENV];

const resolveAssetCosBaseUrl = (): string => {
  const localCosBaseUrl = effectiveLocalOverride.ASSET_CONFIG?.cosBaseUrl;
  if (IS_DEV) {
    if (localCosBaseUrl === undefined) {
      throw new Error(
        '[config] develop environment requires local ASSET_CONFIG.cosBaseUrl in utils/config.local.ts'
      );
    }
    return localCosBaseUrl;
  }
  if (ENV === 'trial' || ENV === 'release') {
    return ASSET_COS_BASE_URLS[ENV];
  }
  throw new Error(`[config] unsupported environment for ASSET_CONFIG: ${ENV}`);
};

const effectiveAssetCosBaseUrl = resolveAssetCosBaseUrl();
const effectiveAssetAvatarPlaceholderPath =
  effectiveLocalOverride.ASSET_CONFIG?.avatarPlaceholderPath ??
  DEFAULT_ASSET_PATHS.avatarPlaceholderPath;
const effectiveAssetDemoAvatarDirPath =
  effectiveLocalOverride.ASSET_CONFIG?.demoAvatarDirPath ?? DEFAULT_ASSET_PATHS.demoAvatarDirPath;
const effectiveAssetLoginBackgroundPath =
  effectiveLocalOverride.ASSET_CONFIG?.loginBackgroundPath ??
  DEFAULT_ASSET_PATHS.loginBackgroundPath;
const effectiveAssetOfficialAccountQrCodePath =
  effectiveLocalOverride.ASSET_CONFIG?.officialAccountQrCodePath ??
  DEFAULT_ASSET_PATHS.officialAccountQrCodePath;

export const API_CONFIG: ApiConfig = {
  // Base URL for API requests
  baseUrl: effectiveApiBaseUrl,

  // API timeout (ms)
  timeout: 10000,

  // API version
  version: 'v1',
};

export const ASSET_CONFIG: AssetConfig = {
  // COS/CDN base URL for remote assets
  cosBaseUrl: effectiveAssetCosBaseUrl,

  // Relative path for placeholder avatar image
  avatarPlaceholderPath: effectiveAssetAvatarPlaceholderPath,

  // Relative directory path for demo avatar images
  demoAvatarDirPath: effectiveAssetDemoAvatarDirPath,

  // Relative path for login page background image
  loginBackgroundPath: effectiveAssetLoginBackgroundPath,

  // Relative path for official account QR code image
  officialAccountQrCodePath: effectiveAssetOfficialAccountQrCodePath,

  // Full URL for placeholder avatar image
  avatarPlaceholderUrl: buildAssetUrl(
    effectiveAssetCosBaseUrl,
    effectiveAssetAvatarPlaceholderPath
  ),

  // Full URL for demo avatar directory
  demoAvatarBaseUrl: buildAssetUrl(effectiveAssetCosBaseUrl, effectiveAssetDemoAvatarDirPath),

  // Full URL for login page background image
  loginBackgroundUrl: buildAssetUrl(effectiveAssetCosBaseUrl, effectiveAssetLoginBackgroundPath),

  // Full URL for official account QR code image
  officialAccountQrCodeUrl: buildAssetUrl(
    effectiveAssetCosBaseUrl,
    effectiveAssetOfficialAccountQrCodePath
  ),
};

export const OFFICIAL_ACCOUNT_CONFIG: OfficialAccountConfig = {
  originalId: 'gh_bc8a67c54b1a',
  username: 'qiaoqiaoaichat',
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

  // Refresh token
  REFRESH_TOKEN: 'refresh_token',

  // User info
  USER_INFO: 'user_info',

  // Whether the current user still needs to complete profile setup
  PROFILE_SETUP_REQUIRED: 'profile_setup_required',

  // Whether silent WeChat login check is blocked after manual logout
  MANUAL_LOGOUT_BLOCK_SILENT_LOGIN: 'manual_logout_block_silent_login',

  // Contacts list
  CONTACTS: 'contact_list',

  // Messages (prefix, append conv_id)
  MESSAGES: 'messages_',

  // Conversation unread counts (per user)
  CONVERSATION_UNREAD_COUNTS: 'conversation_unread_counts',

  // Conversation unread marks (per user)
  CONVERSATION_UNREAD_MARKS: 'conversation_unread_marks',

  // Conversation read state (per user)
  CONVERSATION_READ_STATE: 'conversation_read_state',

  // Conversation scroll state (per user)
  CONVERSATION_SCROLL_STATE: 'conversation_scroll_state',
  // Conversation view state (per user)
  CONVERSATION_VIEW_STATE: 'conversation_view_state',

  // Device identifier (installation-level)
  DEVICE_ID: 'device_id',

  // Runtime segment state for startup and preview guard checks
  RUNTIME_SEGMENT_STATE: 'runtime_segment_state',
  // Offline queue for runtime_session_tick replay
  RUNTIME_SESSION_TICK_QUEUE: 'runtime_session_tick_queue',

  // Local settings
  SETTINGS: 'local_settings',
} as const;

export type StorageKey = (typeof STORAGE_KEYS)[keyof typeof STORAGE_KEYS];

export interface AppConfig {
  brandName: string;
  maxNicknameLength: number;
  maxBioLength: number;
  defaultAvatarUrl?: string;
  clientId: string;
}

export const APP_CONFIG: AppConfig = {
  // Brand name
  brandName: '敲敲',

  // Max nickname length
  maxNicknameLength: 24,

  // Max bio length
  maxBioLength: 120,

  // Default avatar CDN URL (override per environment if backend provides specific asset)
  defaultAvatarUrl: '',

  // Client identification for backend headers
  clientId: 'mini-program',
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
    nickname: 24,
    bio: 120,
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
  nicknameMaxLength: 24,

  // Bio length
  bioMaxLength: 120,

  // Message length
  messageMaxLength: 49,

  // Verify message length
  verifyMessageMaxLength: 100,
};

export interface LoginConfig {
  loginBackgroundLoadTimeoutMs: number;
}

export const LOGIN_CONFIG: LoginConfig = {
  loginBackgroundLoadTimeoutMs: 1000,
};

const config = {
  APP_CONFIG,
  API_CONFIG,
  ASSET_CONFIG,
  LOGIN_CONFIG,
  MESSAGE_CONFIG,
  STORAGE_KEYS,
  UI_CONFIG,
  VALIDATION_RULES,
};

export default config;
