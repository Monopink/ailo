/**
 * Storage utility
 * Wrapper for wx.storage with error handling and type safety
 *
 * All user-specific data is stored with qiao_id prefix to support multi-account
 */

import { STORAGE_KEYS } from './config';
import { getLogger } from './logger';
import { MESSAGE_TYPE } from './constants/message';
import { generateDeviceId } from './device-id';
import {
  parse,
  safeParse,
  StoredContact,
  StoredContactSchema,
  StoredContacts,
  StoredContactsSchema,
  StoredMessage,
  StoredMessageSchema,
  StoredMessages,
  StoredMessagesSchema,
} from './schemas';
import { firstNonEmptyString, isNonEmptyString } from './guards';
import { normalizeError } from './errors';

const logger = getLogger('Storage');

type JsonRecord = Record<string, unknown>;

const isJsonObject = (value: unknown): value is JsonRecord =>
  typeof value === 'object' && value !== null;

const ensureStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string');
};

interface WxError {
  errMsg?: string;
}

const isWxError = (error: unknown): error is WxError =>
  typeof error === 'object' && error !== null && 'errMsg' in error;

const ensureJsonObject = (value: unknown): JsonRecord => {
  if (value === null || typeof value !== 'object') {
    return {};
  }
  return value as JsonRecord;
};

const ensureStoredMessages = (value: unknown): StoredMessages => {
  const parsed = safeParse(StoredMessagesSchema, value);
  if (parsed !== null) {
    return parsed;
  }
  logger.warn('Stored messages schema validation failed, resetting to empty array', {
    value,
  });
  return [];
};

const ensureStoredContacts = (value: unknown): StoredContacts => {
  const parsed = safeParse(StoredContactsSchema, value);
  if (parsed !== null) {
    return parsed;
  }
  logger.warn('Stored contacts schema validation failed, resetting to empty list', {
    value,
  });
  return [];
};

const ensureStoredMessage = (value: unknown): StoredMessage => parse(StoredMessageSchema, value);

const ensureStoredContact = (value: unknown): StoredContact => parse(StoredContactSchema, value);

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
        reject(
          error instanceof Error
            ? error
            : new Error(typeof error === 'string' ? error : 'wx.getStorage failed')
        );
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
  if (contact === null || typeof contact !== 'object') {
    return {} as StoredContact;
  }

  const record = contact as JsonRecord;
  const profileSource = ensureJsonObject(record.profile);
  const normalizedProfile = { ...profileSource };
  const normalizedBase = ensureStoredContact(record);
  normalizedBase.tags = ensureStringArray(record.tags);
  normalizedBase.profile = normalizedProfile;

  const normalizedNickname =
    typeof normalizedProfile.nickname === 'string' ? normalizedProfile.nickname : null;
  const profileNicknameValue =
    typeof profileSource.nickname === 'string' ? profileSource.nickname : null;
  const contactNickname = isNonEmptyString(normalizedNickname) ? normalizedNickname : undefined;
  const profileNickname = isNonEmptyString(profileNicknameValue) ? profileNicknameValue : undefined;
  normalizedProfile.nickname = firstNonEmptyString(contactNickname, profileNickname) ?? '';

  const normalizedAvatar =
    typeof normalizedProfile.avatar_url === 'string' ? normalizedProfile.avatar_url : null;
  const profileAvatarValue =
    typeof profileSource.avatar_url === 'string' ? profileSource.avatar_url : null;
  const contactAvatar = isNonEmptyString(normalizedAvatar) ? normalizedAvatar : undefined;
  const profileAvatar = isNonEmptyString(profileAvatarValue) ? profileAvatarValue : undefined;
  normalizedProfile.avatar_url = firstNonEmptyString(contactAvatar, profileAvatar) ?? '';

  normalizedProfile.gender ??=
    typeof profileSource.gender === 'number' ? profileSource.gender : null;

  return normalizedBase;
}

export function extractContactsFromPayload(payload: unknown): StoredContacts {
  if (payload === null || payload === undefined) {
    return [];
  }
  if (Array.isArray(payload)) {
    return payload as StoredContacts;
  }
  if (!isJsonObject(payload)) {
    return [];
  }
  if (Array.isArray(payload.items)) {
    return ensureStoredContacts(payload.items);
  }
  if (Array.isArray(payload.contacts)) {
    return ensureStoredContacts(payload.contacts);
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
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('Get current qiao_id failed', {
      errorMessage: err.message,
    });
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
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('Set storage failed', {
      key,
      errorMessage: err.message,
    });
    throw err;
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
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('Get storage failed', {
      key,
      errorMessage: err.message,
    });
    throw err;
  }
}

export async function removeStorage(key: string): Promise<void> {
  try {
    await wxRemoveStorage(key);
    logger.debug('Storage removed', { key });
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('Remove storage failed', {
      key,
      errorMessage: err.message,
    });
    throw err;
  }
}

export async function clearStorage(): Promise<void> {
  try {
    await wxClearStorage();
    logger.info('Storage cleared');
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('Clear storage failed', {
      errorMessage: err.message,
    });
    throw err;
  }
}

export async function getStorageInfo(): Promise<WechatMiniprogram.GetStorageInfoSuccessCallbackOption> {
  try {
    const info = await wxGetStorageInfo();
    logger.debug('Storage info', { info });
    return info;
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.error('Get storage info failed', {
      errorMessage: err.message,
    });
    throw err;
  }
}

export async function saveMessages(convId: string, messages: StoredMessages): Promise<void> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    throw new Error('User not logged in');
  }

  const key = buildUserKey(`${STORAGE_KEYS.MESSAGES}${convId}`, qiaoId);
  await setStorage(key, ensureStoredMessages(messages));
}

export async function getMessages(convId: string): Promise<StoredMessages> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    return [];
  }

  const key = buildUserKey(`${STORAGE_KEYS.MESSAGES}${convId}`, qiaoId);
  const stored = await getStorage(key, [] as StoredMessages);
  return ensureStoredMessages(stored);
}

export async function getLatestRenderableMessage(
  convId: string
): Promise<LatestRenderableMessage | null> {
  const messages = await getMessages(convId);
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];

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

    const messageContent = isNonEmptyString(message.content) ? message.content : undefined;
    const messageText = isNonEmptyString(message.text) ? message.text : undefined;
    const content = firstNonEmptyString(messageContent, messageText) ?? '';
    return {
      content,
      sent_time: message.sent_time ?? message.created_at ?? message.timestamp ?? null,
    };
  }
  return null;
}

export async function addMessage(convId: string, message: StoredMessage): Promise<void> {
  const messages = await getMessages(convId);
  const normalizedMessage = ensureStoredMessage(message);
  const existingIndex = messages.findIndex((m) => m.msg_id === normalizedMessage.msg_id);

  if (existingIndex !== -1) {
    messages[existingIndex] = normalizedMessage;
  } else {
    messages.push(normalizedMessage);
  }

  await saveMessages(convId, ensureStoredMessages(messages));
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
    await saveMessages(convId, ensureStoredMessages(messages));
  }
}

export async function clearMessages(convId: string): Promise<void> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    return;
  }

  const key = buildUserKey(`${STORAGE_KEYS.MESSAGES}${convId}`, qiaoId);
  await removeStorage(key);
}

export async function saveContacts(contacts: unknown): Promise<StoredContacts> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    throw new Error('User not logged in');
  }

  const normalized = normalizeContactsPayload(contacts).map(ensureStoredContact);
  const validatedContacts = ensureStoredContacts(normalized);
  const key = buildUserKey(STORAGE_KEYS.CONTACTS, qiaoId);
  await setStorage(key, validatedContacts);

  return normalized;
}

export async function getContacts(): Promise<StoredContacts> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    return [];
  }

  const key = buildUserKey(STORAGE_KEYS.CONTACTS, qiaoId);
  const contacts = await getStorage<StoredContacts | null>(key, null);
  if (contacts !== null) {
    return ensureStoredContacts(contacts);
  }

  return [];
}

export async function getContactByConvId(convId: string): Promise<StoredContact | null> {
  const contacts = await getContacts();
  return contacts.find((c) => c.conv_id === convId) ?? null;
}

export async function saveUserInfo(userInfo: StoredAuthUser | null): Promise<void> {
  await setStorage<StoredAuthUser | null>(STORAGE_KEYS.USER_INFO, userInfo);
}

export async function getUserInfo(): Promise<StoredAuthUser | null> {
  return await getStorage<StoredAuthUser | null>(STORAGE_KEYS.USER_INFO, null);
}

export async function getDeviceId(): Promise<string> {
  const stored = await getStorage<string | null>(STORAGE_KEYS.DEVICE_ID, null);
  if (isNonEmptyString(stored)) {
    return stored;
  }

  const deviceId = generateDeviceId();
  await setStorage(STORAGE_KEYS.DEVICE_ID, deviceId);
  return deviceId;
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
  getDeviceId,
  saveSettings,
  getSettings,
};

export type { StoredContact, StoredContacts, StoredMessage, StoredMessages } from './schemas';
