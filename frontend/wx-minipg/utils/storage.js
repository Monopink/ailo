/**
 * Storage utility
 * Wrapper for wx.storage with error handling and type safety
 *
 * All user-specific data is stored with qiao_id prefix to support multi-account
 */

import { STORAGE_KEYS } from './config';
import { getLogger } from './logger';

const logger = getLogger('Storage');

/**
 * Get current user's qiao_id from storage
 * @returns {Promise<string|null>} User qiao_id or null
 */
async function getCurrentQiaoId() {
  try {
    const userInfo = await getStorage(STORAGE_KEYS.USER_INFO, null);
    return userInfo?.qiao_id || null;
  } catch (error) {
    logger.error('Get current qiao_id failed', { error });
    return null;
  }
}

/**
 * Build storage key with qiao_id prefix
 * @param {string} baseKey - Base storage key
 * @param {string} qiaoId - User qiao_id
 * @returns {string} Storage key with qiao_id prefix
 */
function buildUserKey(baseKey, qiaoId) {
  return `${qiaoId}_${baseKey}`;
}

/**
 * Set storage data
 * @param {string} key - Storage key
 * @param {any} data - Data to store
 * @returns {Promise<void>}
 */
export async function setStorage(key, data) {
  try {
    await wx.setStorage({
      key,
      data
    });
    logger.debug('Storage set', { key });
  } catch (error) {
    logger.error('Set storage failed', { key, error });
    throw error;
  }
}

/**
 * Get storage data
 * @param {string} key - Storage key
 * @param {any} defaultValue - Default value if key not found
 * @returns {Promise<any>} Stored data or default value
 */
export async function getStorage(key, defaultValue = null) {
  try {
    const res = await wx.getStorage({ key });
    logger.debug('Storage get', { key });
    return res.data;
  } catch (error) {
    if (error.errMsg && error.errMsg.includes('data not found')) {
      logger.debug('Storage key not found', { key });
      return defaultValue;
    }
    logger.error('Get storage failed', { key, error });
    throw error;
  }
}

/**
 * Remove storage data
 * @param {string} key - Storage key
 * @returns {Promise<void>}
 */
export async function removeStorage(key) {
  try {
    await wx.removeStorage({ key });
    logger.debug('Storage removed', { key });
  } catch (error) {
    logger.error('Remove storage failed', { key, error });
    throw error;
  }
}

/**
 * Clear all storage
 * @returns {Promise<void>}
 */
export async function clearStorage() {
  try {
    await wx.clearStorage();
    logger.info('Storage cleared');
  } catch (error) {
    logger.error('Clear storage failed', { error });
    throw error;
  }
}

/**
 * Get storage info
 * @returns {Promise<Object>} Storage info
 */
export async function getStorageInfo() {
  try {
    const info = await wx.getStorageInfo();
    logger.debug('Storage info', { info });
    return info;
  } catch (error) {
    logger.error('Get storage info failed', { error });
    throw error;
  }
}

/**
 * Save messages for a conversation
 * @param {string} convId - Conversation ID
 * @param {Array} messages - Messages array
 * @returns {Promise<void>}
 */
export async function saveMessages(convId, messages) {
  const qiaoId = await getCurrentQiaoId();
  if (!qiaoId) {
    throw new Error('User not logged in');
  }

  const key = buildUserKey(`${STORAGE_KEYS.MESSAGES}${convId}`, qiaoId);
  await setStorage(key, messages);
}

/**
 * Get messages for a conversation
 * @param {string} convId - Conversation ID
 * @returns {Promise<Array>} Messages array
 */
export async function getMessages(convId) {
  const qiaoId = await getCurrentQiaoId();
  if (!qiaoId) {
    return [];
  }

  const key = buildUserKey(`${STORAGE_KEYS.MESSAGES}${convId}`, qiaoId);
  return await getStorage(key, []);
}

/**
 * Add or update message in conversation
 * @param {string} convId - Conversation ID
 * @param {Object} message - Message object
 * @returns {Promise<void>}
 */
export async function addMessage(convId, message) {
  const messages = await getMessages(convId);

  // Check if message already exists
  const existingIndex = messages.findIndex(m => m.msg_id === message.msg_id);

  if (existingIndex !== -1) {
    // Update existing message
    messages[existingIndex] = message;
  } else {
    // Add new message
    messages.push(message);
  }

  await saveMessages(convId, messages);
}

/**
 * Update message in conversation
 * @param {string} convId - Conversation ID
 * @param {string} messageId - Message ID
 * @param {Object} updates - Message updates
 * @returns {Promise<void>}
 */
export async function updateMessage(convId, messageId, updates) {
  const messages = await getMessages(convId);
  const index = messages.findIndex(m => m.id === messageId);

  if (index !== -1) {
    messages[index] = { ...messages[index], ...updates };
    await saveMessages(convId, messages);
  }
}

/**
 * Clear messages for a conversation
 * @param {string} convId - Conversation ID
 * @returns {Promise<void>}
 */
export async function clearMessages(convId) {
  const qiaoId = await getCurrentQiaoId();
  if (!qiaoId) {
    return;
  }

  const key = buildUserKey(`${STORAGE_KEYS.MESSAGES}${convId}`, qiaoId);
  await removeStorage(key);
}

/**
 * Save contacts list
 * @param {Array} contacts - Contacts array
 * @returns {Promise<void>}
 */
export async function saveContacts(contacts) {
  const qiaoId = await getCurrentQiaoId();
  if (!qiaoId) {
    throw new Error('User not logged in');
  }

  const key = buildUserKey(STORAGE_KEYS.CONTACTS, qiaoId);
  await setStorage(key, contacts);
}

/**
 * Get contacts list
 * @returns {Promise<Array>} Contacts array
 */
export async function getContacts() {
  const qiaoId = await getCurrentQiaoId();
  if (!qiaoId) {
    return [];
  }

  const key = buildUserKey(STORAGE_KEYS.CONTACTS, qiaoId);
  return await getStorage(key, []);
}

/**
 * Get contact by conv_id
 * @param {string} convId - Conversation ID
 * @returns {Promise<Object|null>} Contact object or null
 */
export async function getContactByConvId(convId) {
  const contacts = await getContacts();
  return contacts.find(c => c.conv_id === convId) || null;
}

/**
 * Save user info
 * @param {Object} userInfo - User info object
 * @returns {Promise<void>}
 */
export async function saveUserInfo(userInfo) {
  await setStorage(STORAGE_KEYS.USER_INFO, userInfo);
}

/**
 * Get user info
 * @returns {Promise<Object>} User info object
 */
export async function getUserInfo() {
  return await getStorage(STORAGE_KEYS.USER_INFO, null);
}

/**
 * Save local settings
 * @param {Object} settings - Settings object
 * @returns {Promise<void>}
 */
export async function saveSettings(settings) {
  await setStorage(STORAGE_KEYS.SETTINGS, settings);
}

/**
 * Get local settings
 * @returns {Promise<Object>} Settings object
 */
export async function getSettings() {
  return await getStorage(STORAGE_KEYS.SETTINGS, {
    notification: true,
    sound: true,
    vibrate: true
  });
}

/**
 * Save search history
 * @param {Array} history - Search history array
 * @returns {Promise<void>}
 */
export async function saveSearchHistory(history) {
  await setStorage(STORAGE_KEYS.SEARCH_HISTORY, history);
}

/**
 * Get search history
 * @returns {Promise<Array>} Search history array
 */
export async function getSearchHistory() {
  return await getStorage(STORAGE_KEYS.SEARCH_HISTORY, []);
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
  getContacts,
  saveUserInfo,
  getUserInfo,
  saveSettings,
  getSettings,
  saveSearchHistory,
  getSearchHistory
};

