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
  ConversationReadState,
  ConversationReadStateSchema,
  ConversationUnreadCounts,
  ConversationUnreadCountsSchema,
  ConversationUnreadMarks,
  ConversationUnreadMarksSchema,
  type ConversationReadStateItem,
  ConversationViewState,
  ConversationViewStateSchema,
  type ConversationViewStateItem,
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

const normalizeContactProfile = (
  normalizedProfile: JsonRecord,
  profileSource: JsonRecord
): void => {
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

const ensureConversationUnreadCounts = (value: unknown): ConversationUnreadCounts => {
  const parsed = safeParse(ConversationUnreadCountsSchema, value);
  if (parsed !== null) {
    return parsed;
  }
  logger.warn('Conversation unread counts schema validation failed, resetting to empty map', {
    value,
  });
  return {};
};

const ensureConversationReadState = (value: unknown): ConversationReadState => {
  const parsed = safeParse(ConversationReadStateSchema, value);
  if (parsed !== null) {
    return parsed;
  }
  logger.warn('Conversation read state schema validation failed, resetting to empty map', {
    value,
  });
  return {};
};

const ensureConversationViewState = (value: unknown): ConversationViewState => {
  const parsed = safeParse(ConversationViewStateSchema, value);
  if (parsed !== null) {
    return parsed;
  }
  logger.warn('Conversation view state schema validation failed, resetting to empty map', {
    value,
  });
  return {};
};

const ensureConversationUnreadMarks = (value: unknown): ConversationUnreadMarks => {
  const parsed = safeParse(ConversationUnreadMarksSchema, value);
  if (parsed !== null) {
    return parsed;
  }
  logger.warn('Conversation unread marks schema validation failed, resetting to empty map', {
    value,
  });
  return {};
};

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
  from_qiao_id: string | null;
}

export interface LocalSettings {
  notification: boolean;
  sound: boolean;
  vibrate: boolean;
  [key: string]: unknown;
}

export interface StoredAuthUser extends JsonRecord {
  qiao_id: string;
  account_segment?: number;
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
  normalizeContactProfile(normalizedProfile, profileSource);

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
  const latestMessages = await getLatestTwoRenderableMessages(convId);
  return latestMessages.length > 0 ? latestMessages[0] : null;
}

const shouldSkipRenderableMessage = (message: StoredMessage): boolean => {
  const type = typeof message.message_type === 'number' ? message.message_type : MESSAGE_TYPE.TEXT;
  return (
    type === MESSAGE_TYPE.CHAT_INFO ||
    type === MESSAGE_TYPE.TYPING_START ||
    type === MESSAGE_TYPE.TYPING_END ||
    type === MESSAGE_TYPE.NOTIFICATION
  );
};

const toLatestRenderableMessage = (message: StoredMessage): LatestRenderableMessage => {
  const messageContent = isNonEmptyString(message.content) ? message.content : undefined;
  const messageText = isNonEmptyString(message.text) ? message.text : undefined;
  return {
    content: firstNonEmptyString(messageContent, messageText) ?? '',
    sent_time: message.sent_time ?? message.created_at ?? message.timestamp ?? null,
    from_qiao_id: isNonEmptyString(message.from_qiao_id) ? message.from_qiao_id : null,
  };
};

export async function getLatestTwoRenderableMessages(
  convId: string
): Promise<LatestRenderableMessage[]> {
  const messages = await getMessages(convId);
  const latestMessages: LatestRenderableMessage[] = [];

  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (shouldSkipRenderableMessage(message)) {
      continue;
    }
    latestMessages.push(toLatestRenderableMessage(message));
    if (latestMessages.length === 2) {
      return latestMessages;
    }
  }

  return latestMessages;
}

export interface LatestMessageMeta {
  msg_id: string;
  sent_time: number;
}

export async function getLatestMessageMeta(convId: string): Promise<LatestMessageMeta | null> {
  const messages = await getMessages(convId);
  let latest: LatestMessageMeta | null = null;

  for (const message of messages) {
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

    const timestamp = message.sent_time ?? message.created_at ?? message.timestamp;
    if (typeof timestamp !== 'number') {
      continue;
    }

    if (latest === null || timestamp > latest.sent_time) {
      latest = { msg_id: message.msg_id, sent_time: timestamp };
    }
  }

  return latest;
}

export async function addMessage(convId: string, message: StoredMessage): Promise<void> {
  const messages = await getMessages(convId);
  const normalizedMessage = ensureStoredMessage(message);
  const shouldCollapseSelfEcho =
    isNonEmptyString(normalizedMessage.msg_id_server) &&
    isNonEmptyString(normalizedMessage.msg_id_client);
  let existingIndex = messages.findIndex((item) => item.msg_id === normalizedMessage.msg_id);

  if (existingIndex === -1 && shouldCollapseSelfEcho) {
    const clientMsgId = normalizedMessage.msg_id_client;
    existingIndex = messages.findIndex((item) => {
      const existingClientMsgId = isNonEmptyString(item.msg_id_client) ? item.msg_id_client : null;
      return item.msg_id === clientMsgId || existingClientMsgId === clientMsgId;
    });
  }

  if (existingIndex !== -1) {
    messages[existingIndex] = ensureStoredMessage({
      ...messages[existingIndex],
      ...normalizedMessage,
    });
  } else {
    messages.push(normalizedMessage);
    existingIndex = messages.length - 1;
  }

  if (shouldCollapseSelfEcho) {
    const dedupedMessages = messages.filter(
      (item, index) => index === existingIndex || item.msg_id !== normalizedMessage.msg_id
    );
    await saveMessages(convId, ensureStoredMessages(dedupedMessages));
    return;
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

export async function patchMessageByIdentity(
  convId: string,
  messageId: string,
  updates: Partial<StoredMessage>
): Promise<boolean> {
  const messages = await getMessages(convId);
  const index = messages.findIndex((message) => {
    if (message.msg_id === messageId) {
      return true;
    }
    return (
      (isNonEmptyString(message.msg_id_client) && message.msg_id_client === messageId) ||
      (isNonEmptyString(message.msg_id_server) && message.msg_id_server === messageId)
    );
  });
  if (index === -1) {
    return false;
  }
  messages[index] = ensureStoredMessage({
    ...messages[index],
    ...updates,
  });
  await saveMessages(convId, ensureStoredMessages(messages));
  return true;
}

export async function removeMessage(convId: string, msgId: string): Promise<void> {
  const messages = await getMessages(convId);
  const nextMessages = messages.filter((message) => message.msg_id !== msgId);
  if (nextMessages.length === messages.length) {
    return;
  }
  await saveMessages(convId, ensureStoredMessages(nextMessages));
}

export async function removeLatestChatInfoMessage(convId: string): Promise<string | null> {
  const messages = await getMessages(convId);
  let removedMsgId: string | null = null;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    const type =
      typeof message.message_type === 'number' ? message.message_type : MESSAGE_TYPE.TEXT;
    if (type === MESSAGE_TYPE.CHAT_INFO) {
      removedMsgId = message.msg_id;
      messages.splice(i, 1);
      break;
    }
  }
  if (removedMsgId === null) {
    return null;
  }
  await saveMessages(convId, ensureStoredMessages(messages));
  return removedMsgId;
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
  return contacts.find((c) => c.conversation_id === convId) ?? null;
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

export async function getConversationUnreadCounts(): Promise<ConversationUnreadCounts> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    return {};
  }
  const key = buildUserKey(STORAGE_KEYS.CONVERSATION_UNREAD_COUNTS, qiaoId);
  const stored = await getStorage<ConversationUnreadCounts | null>(key, null);
  if (stored === null) {
    return {};
  }
  return ensureConversationUnreadCounts(stored);
}

export async function setConversationUnreadCounts(counts: ConversationUnreadCounts): Promise<void> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    throw new Error('User not logged in');
  }
  const key = buildUserKey(STORAGE_KEYS.CONVERSATION_UNREAD_COUNTS, qiaoId);
  await setStorage(key, ensureConversationUnreadCounts(counts));
}

export async function getConversationUnreadMarks(): Promise<ConversationUnreadMarks> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    return {};
  }
  const key = buildUserKey(STORAGE_KEYS.CONVERSATION_UNREAD_MARKS, qiaoId);
  const stored = await getStorage<ConversationUnreadMarks | null>(key, null);
  if (stored === null) {
    return {};
  }
  return ensureConversationUnreadMarks(stored);
}

export async function setConversationUnreadMarks(marks: ConversationUnreadMarks): Promise<void> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    throw new Error('User not logged in');
  }
  const key = buildUserKey(STORAGE_KEYS.CONVERSATION_UNREAD_MARKS, qiaoId);
  await setStorage(key, ensureConversationUnreadMarks(marks));
}

export async function getConversationReadState(): Promise<ConversationReadState> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    return {};
  }
  const key = buildUserKey(STORAGE_KEYS.CONVERSATION_READ_STATE, qiaoId);
  const stored = await getStorage<ConversationReadState | null>(key, null);
  if (stored === null) {
    return {};
  }
  return ensureConversationReadState(stored);
}

export async function setConversationReadState(state: ConversationReadState): Promise<void> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    throw new Error('User not logged in');
  }
  const key = buildUserKey(STORAGE_KEYS.CONVERSATION_READ_STATE, qiaoId);
  await setStorage(key, ensureConversationReadState(state));
}

export async function getConversationViewState(): Promise<ConversationViewState> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    return {};
  }
  const key = buildUserKey(STORAGE_KEYS.CONVERSATION_VIEW_STATE, qiaoId);
  const stored = await getStorage<ConversationViewState | null>(key, null);
  if (stored === null) {
    return {};
  }
  return ensureConversationViewState(stored);
}

export async function setConversationViewState(state: ConversationViewState): Promise<void> {
  const qiaoId = await getCurrentQiaoId();
  if (qiaoId === null) {
    throw new Error('User not logged in');
  }
  const key = buildUserKey(STORAGE_KEYS.CONVERSATION_VIEW_STATE, qiaoId);
  await setStorage(key, ensureConversationViewState(state));
}

export async function getConversationViewPosition(
  convId: string
): Promise<ConversationViewStateItem | null> {
  const state = await getConversationViewState();
  return state[convId] ?? null;
}

export async function setConversationViewPosition(
  convId: string,
  payload: { last_viewed_msg_id?: string; is_at_bottom: boolean }
): Promise<void> {
  const state = await getConversationViewState();
  const item: ConversationViewStateItem = {
    is_at_bottom: payload.is_at_bottom,
    updated_at: Date.now(),
  };
  if (isNonEmptyString(payload.last_viewed_msg_id)) {
    item.last_viewed_msg_id = payload.last_viewed_msg_id;
  }
  state[convId] = item;
  await setConversationViewState(state);
}

export async function clearConversationViewPosition(convId: string): Promise<void> {
  const state = await getConversationViewState();
  if (!(convId in state)) {
    return;
  }
  delete state[convId];
  await setConversationViewState(state);
}

export async function setConversationLastRead(
  convId: string,
  payload: { last_read_sent_time: number; last_read_msg_id?: string }
): Promise<void> {
  const state = await getConversationReadState();
  const updated: ConversationReadStateItem = {
    last_read_sent_time: payload.last_read_sent_time,
    last_read_msg_id: payload.last_read_msg_id,
    updated_at: Date.now(),
  };
  state[convId] = updated;
  await setConversationReadState(state);
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
  patchMessageByIdentity,
  clearMessages,
  saveContacts,
  extractContactsFromPayload,
  normalizeContactsPayload,
  getContacts,
  getLatestRenderableMessage,
  getLatestTwoRenderableMessages,
  getLatestMessageMeta,
  saveUserInfo,
  getUserInfo,
  getDeviceId,
  saveSettings,
  getSettings,
  getConversationUnreadCounts,
  setConversationUnreadCounts,
  getConversationUnreadMarks,
  setConversationUnreadMarks,
  getConversationReadState,
  setConversationReadState,
  getConversationViewState,
  setConversationViewState,
  getConversationViewPosition,
  setConversationViewPosition,
  clearConversationViewPosition,
  setConversationLastRead,
};

export type {
  StoredContact,
  StoredContacts,
  StoredMessage,
  StoredMessages,
  ConversationViewState,
  ConversationViewStateItem,
} from './schemas';
