/**
 * Storage utility
 * Wrapper for wx.storage with error handling and type safety
 *
 * All user-specific data is stored with qiao_id prefix to support multi-account
 */

import { STORAGE_KEYS } from './config';
import { getLogger } from './logger';
import { MESSAGE_TYPE } from './message/constants';

const logger = getLogger('Storage');

type JsonRecord = Record<string, unknown>;

interface WxError {
  errMsg?: string;
}

const isWxError = (error: unknown): error is WxError =>
  typeof error === 'object' && error !== null && 'errMsg' in error;

const wxSetStorage = async <T>(key: string, data: T): Promise<void> =>
  await new Promise((resolve, reject) => {
    void wx.setStorage({
      key,
      data,
      success: () => resolve(),
      fail: reject,
    });
  });

const wxGetStorage = async <T>(key: string): Promise<T | undefined> =>
  await new Promise((resolve, reject) => {
    void wx.getStorage<T>({
      key,
      success: (res: WechatMiniprogram.GetStorageSuccessCallbackResult<T>) => resolve(res.data),
      fail: (error) => {
        if (
          isWxError(error) &&
          typeof error.errMsg === 'string' &&
          error.errMsg.includes('data not found')
        ) {
          resolve(undefined);
          return;
        }
        reject(error);
      },
    });
  });

const wxRemoveStorage = async (key: string): Promise<void> =>
  await new Promise((resolve, reject) => {
    void wx.removeStorage({
      key,
      success: () => resolve(),
      fail: reject,
    });
  });

const wxClearStorage = async (): Promise<void> =>
  await new Promise((resolve, reject) => {
    void wx.clearStorage({
      success: () => resolve(),
      fail: reject,
    });
  });

const wxGetStorageInfo = async (): Promise<WechatMiniprogram.GetStorageInfoSuccessCallbackOption> =>
  await new Promise((resolve, reject) => {
    void wx.getStorageInfo({
      success: resolve,
      fail: reject,
    });
  });

export interface ContactProfile {
  nickname?: string | null;
  avatar_url?: string | null;
  gender?: number | null;
  bio?: string | null;
  region?: string | null;
}

export interface StoredContact extends JsonRecord {
  conv_id?: string;
  contact_qiao_id?: string;
  alias?: string | null;
  tags?: string[];
  is_pinned?: boolean;
  is_muted?: boolean;
  is_blocked?: boolean;
  profile?: ContactProfile;
  custom_avatar_url?: string;
  // Legacy fields for backward compatibility
  qiao_id?: string;
  nickname?: string;
  avatar_url?: string;
  gender?: number | null;
  contact_qiaoid?: string;
  contact_profile?: JsonRecord;
}

export type StoredContacts = StoredContact[];

export interface StoredMessage extends JsonRecord {
  msg_id: string;
  conv_id: string;
  from?: string;
  to?: string;
  content?: string;
  message_type?: number;
  supports_typing?: boolean;
  sent_time?: number;
  status?: number;
  action?: string | null;
  notification_type?: string | null;
  data?: JsonRecord | null;
  id?: string;
  text?: string;
  created_at?: number;
  timestamp?: number;
}

export type StoredMessages = StoredMessage[];

export interface LatestRenderableMessage {
  content: string;
  sent_time: number | string | null;
}

export interface LocalSettings {
  notification: boolean;
  sound: boolean;
  vibrate: boolean;
  [key: string]: unknown;
}

export interface StoredAuthUser extends JsonRecord {
  qiao_id: string;
  nickname?: string;
  avatar?: string;
}

function normalizeContact(contact: unknown): StoredContact {
  if (!contact || typeof contact !== 'object') {
    return {} as StoredContact;
  }

  const record = contact as JsonRecord;
  const profile = (record.profile as JsonRecord) || (record.contact_profile as JsonRecord) || {};
  const normalized: StoredContact = { ...record } as StoredContact;

  normalized.profile = profile;
  normalized.contact_profile = profile;

  if (!Array.isArray(normalized.tags)) {
    const maybeTags = (normalized.tags as unknown as { tags?: unknown })?.tags;
    normalized.tags = Array.isArray(maybeTags) ? (maybeTags as string[]) : [];
  }

  const profileNickname = typeof profile.nickname === 'string' ? profile.nickname : '';
  const alias = typeof normalized.alias === 'string' ? normalized.alias : '';
  const contactId =
    typeof normalized.contact_qiao_id === 'string' ? normalized.contact_qiao_id : '';
  const nickname = typeof normalized.nickname === 'string' ? normalized.nickname : '';
  normalized.nickname = nickname || profileNickname || alias || contactId || '';

  const resolvedAvatar =
    (typeof normalized.custom_avatar_url === 'string' ? normalized.custom_avatar_url : '') ||
    (typeof normalized.avatar_url === 'string' ? normalized.avatar_url : '') ||
    (profile.avatar_url as string) ||
    '';
  normalized.avatar_url = resolvedAvatar;

  if (normalized.gender === undefined || normalized.gender === null) {
    normalized.gender = typeof profile.gender === 'number' ? profile.gender : null;
  }

  return normalized;
}

export function extractContactsFromPayload(payload: unknown): StoredContacts {
  if (!payload) {
    return [];
  }
  if (Array.isArray(payload)) {
    return payload as StoredContacts;
  }
  if (payload && typeof payload === 'object') {
    if (Array.isArray((payload as JsonRecord).items)) {
      return (payload as { items: StoredContacts }).items;
    }
    if (Array.isArray((payload as JsonRecord).contacts)) {
      return (payload as { contacts: StoredContacts }).contacts;
    }
  }
  return [];
}

export function normalizeContactsPayload(payload: unknown): StoredContacts {
  const contacts = extractContactsFromPayload(payload);
  return contacts.map(normalizeContact);
}

async function getCurrentQiaoId(): Promise<string | null> {
  try {
    const userInfo = await getStorage<StoredAuthUser | null>(STORAGE_KEYS.USER_INFO, null);
    return userInfo?.qiao_id ?? null;
  } catch (error) {
    logger.error('Get current qiao_id failed', { error });
    return null;
  }
}

function buildUserKey(baseKey: string, qiaoId: string): string {
  return `${qiaoId}_${baseKey}`;
}

export async function setStorage<T>(key: string, data: T): Promise<void> {
  try {
    await wxSetStorage(key, data);
    logger.debug('Storage set', { key });
  } catch (error) {
    logger.error('Set storage failed', { key, error });
    throw error;
  }
}

export async function getStorage<T>(key: string, defaultValue: T): Promise<T> {
  try {
    const result = await wxGetStorage<T>(key);
    logger.debug('Storage get', { key });
    if (typeof result === 'undefined') {
      logger.debug('Storage key not found', { key });
      return defaultValue;
    }
    return result;
  } catch (error) {
    logger.error('Get storage failed', { key, error });
    throw error;
  }
}

export async function removeStorage(key: string): Promise<void> {
  try {
    await wxRemoveStorage(key);
    logger.debug('Storage removed', { key });
  } catch (error) {
    logger.error('Remove storage failed', { key, error });
    throw error;
  }
}

export async function clearStorage(): Promise<void> {
  try {
    await wxClearStorage();
    logger.info('Storage cleared');
  } catch (error) {
    logger.error('Clear storage failed', { error });
    throw error;
  }
}

export async function getStorageInfo(): Promise<WechatMiniprogram.GetStorageInfoSuccessCallbackOption> {
  try {
    const info = await wxGetStorageInfo();
    logger.debug('Storage info', { info });
    return info;
  } catch (error) {
    logger.error('Get storage info failed', { error });
    throw error;
  }
}

export async function saveMessages(convId: string, messages: StoredMessages): Promise<void> {
  const qiaoId = await getCurrentQiaoId();
  if (!qiaoId) {
    throw new Error('User not logged in');
  }

  const key = buildUserKey(`${STORAGE_KEYS.MESSAGES}${convId}`, qiaoId);
  await setStorage(key, messages);
}

export async function getMessages(convId: string): Promise<StoredMessages> {
  const qiaoId = await getCurrentQiaoId();
  if (!qiaoId) {
    return [];
  }

  const key = buildUserKey(`${STORAGE_KEYS.MESSAGES}${convId}`, qiaoId);
  return await getStorage(key, [] as StoredMessages);
}

export async function getLatestRenderableMessage(
  convId: string
): Promise<LatestRenderableMessage | null> {
  const messages = await getMessages(convId);
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (!message) {
      continue;
    }

    const type =
      typeof message.message_type === 'number' ? message.message_type : MESSAGE_TYPE.TEXT;
    if (
      type === MESSAGE_TYPE.CHAT_INFO ||
      type === MESSAGE_TYPE.TYPING_START ||
      type === MESSAGE_TYPE.TYPING_END ||
      type === MESSAGE_TYPE.NOTIFICATION
    ) {
      continue;
    }

    const content =
      (typeof message.content === 'string' && message.content) ||
      (typeof message.text === 'string' ? message.text : '') ||
      '';
    return {
      content,
      sent_time: message.sent_time ?? message.created_at ?? message.timestamp ?? null,
    };
  }
  return null;
}

export async function addMessage(convId: string, message: StoredMessage): Promise<void> {
  const messages = await getMessages(convId);
  const existingIndex = messages.findIndex((m) => m.msg_id === message.msg_id);

  if (existingIndex !== -1) {
    messages[existingIndex] = message;
  } else {
    messages.push(message);
  }

  await saveMessages(convId, messages);
}

export async function updateMessage(
  convId: string,
  messageId: string,
  updates: Partial<StoredMessage>
): Promise<void> {
  const messages = await getMessages(convId);
  const index = messages.findIndex((m) => m.id === messageId);

  if (index !== -1) {
    messages[index] = { ...messages[index], ...updates };
    await saveMessages(convId, messages);
  }
}

export async function clearMessages(convId: string): Promise<void> {
  const qiaoId = await getCurrentQiaoId();
  if (!qiaoId) {
    return;
  }

  const key = buildUserKey(`${STORAGE_KEYS.MESSAGES}${convId}`, qiaoId);
  await removeStorage(key);
}

export async function saveContacts(contacts: unknown): Promise<StoredContacts> {
  const qiaoId = await getCurrentQiaoId();
  if (!qiaoId) {
    throw new Error('User not logged in');
  }

  const normalized = normalizeContactsPayload(contacts);
  const key = buildUserKey(STORAGE_KEYS.CONTACTS, qiaoId);
  await setStorage(key, normalized);

  const legacyKey = buildUserKey('contacts', qiaoId);
  if (legacyKey !== key) {
    try {
      await removeStorage(legacyKey);
    } catch (error) {
      logger.debug('Legacy contacts key cleanup skipped', { legacyKey, error });
    }
  }

  return normalized;
}

export async function getContacts(): Promise<StoredContacts> {
  const qiaoId = await getCurrentQiaoId();
  if (!qiaoId) {
    return [];
  }

  const key = buildUserKey(STORAGE_KEYS.CONTACTS, qiaoId);
  const contacts = await getStorage<StoredContacts | null>(key, null);
  if (contacts !== null) {
    return contacts;
  }

  const legacyKey = buildUserKey('contacts', qiaoId);
  const legacyContacts = await getStorage<StoredContacts | null>(legacyKey, null);
  if (legacyContacts !== null) {
    await setStorage(key, legacyContacts);
    try {
      await removeStorage(legacyKey);
    } catch (error) {
      logger.debug('Legacy contacts key removal failed', { legacyKey, error });
    }
    return legacyContacts;
  }

  return [];
}

export async function getContactByConvId(convId: string): Promise<StoredContact | null> {
  const contacts = await getContacts();
  return contacts.find((c) => c.conv_id === convId) || null;
}

export async function saveUserInfo(userInfo: StoredAuthUser | null): Promise<void> {
  await setStorage<StoredAuthUser | null>(STORAGE_KEYS.USER_INFO, userInfo);
}

export async function getUserInfo(): Promise<StoredAuthUser | null> {
  return await getStorage<StoredAuthUser | null>(STORAGE_KEYS.USER_INFO, null);
}

export async function saveSettings(settings: LocalSettings): Promise<void> {
  await setStorage<LocalSettings>(STORAGE_KEYS.SETTINGS, settings);
}

export async function getSettings(): Promise<LocalSettings> {
  return await getStorage<LocalSettings>(STORAGE_KEYS.SETTINGS, {
    notification: true,
    sound: true,
    vibrate: true,
  });
}

export default {
  setStorage,
  getStorage,
  removeStorage,
  clearStorage,
  getStorageInfo,
  saveMessages,
  getMessages,
  addMessage,
  updateMessage,
  clearMessages,
  saveContacts,
  extractContactsFromPayload,
  normalizeContactsPayload,
  getContacts,
  getLatestRenderableMessage,
  saveUserInfo,
  getUserInfo,
  saveSettings,
  getSettings,
};
