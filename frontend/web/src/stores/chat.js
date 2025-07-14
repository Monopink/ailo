import { defineStore } from 'pinia';
import { ref } from 'vue'
import localStorageService from '../services/localStorage';
import { apiClient } from '../utils/apiHelpers';
import { useAuthStore } from './auth';

import { chatLogger } from '../utils/logger.js';
import { handleError } from '../utils/errorHandler.js';
import { CACHE_CONFIG, CONTACT_CONFIG } from '../config/constants.js';

export const useChatStore = defineStore('chat', () => {
  // Initialize with empty state - data will be loaded when user context is set
  const chats = ref([]);
  const selectedChatId = ref(null);
  const isLoaded = ref(false);
  const currentUserId = ref(null);

  // Contact limits information
  const contactLimits = ref({
    contact_limit: CONTACT_CONFIG.DEFAULT_LIMIT,
    current_count: 0,
    can_add_more: true
  });

  /**
   * Initialize chat store with user context
   */
  async function initializeWithUser(userId) {
    if (!userId) {
      throw new Error('User ID is required for chat store initialization')
    }

    currentUserId.value = userId

    // Set user context in localStorage service
    localStorageService.setCurrentUser(userId)

    // Load user-specific chat data
    await loadUserData()

    chatLogger.info('Chat store initialized for user', { userId })
  }

  /**
   * Load user-specific data from localStorage
   */
  async function loadUserData() {
    if (!currentUserId.value) {
      chatLogger.warn('Cannot load user data: no user context set')
      return
    }

    try {
      const data = localStorageService.loadChats()
      if (data && data.chats) {
        chats.value = data.chats
        chatLogger.info('Loaded user chat data', {
          userId: currentUserId.value,
          chatCount: data.chats.length
        })
      } else {
        chats.value = []
        chatLogger.info('No existing chat data for user', { userId: currentUserId.value })
      }
    } catch (error) {
      chatLogger.error('Failed to load user chat data', error)
      chats.value = []
    }
  }

  /**
   * Clear user context and data
   */
  function clearUserContext() {
    currentUserId.value = null
    chats.value = []
    selectedChatId.value = null
    isLoaded.value = false

    // Clear localStorage user context
    localStorageService.clearCurrentUser()

    chatLogger.info('Chat store user context cleared')
  }

  // Save chats to localStorage
  function saveToStorage() {
    if (!currentUserId.value) {
      chatLogger.warn('Cannot save to storage: no user context set')
      return
    }

    try {
      localStorageService.saveChats(chats.value)
    } catch (error) {
      chatLogger.error('Failed to save chats to storage', error)
    }
  }

  // Add message to chat and save to localStorage
  function addMessage(chatId, message) {
    chatLogger.debug('Adding message to chat', { chatId, messageId: message.id || message.localId });

    const chat = chats.value.find(c => c.id === chatId);
    if (chat) {
      if (!chat.messages) {
        chat.messages = [];
      }

      // Initialize unread count if not exists
      if (typeof chat.unreadCount !== 'number') {
        chat.unreadCount = 0;
      }

      // Avoid duplicate messages
      let existingMessage = null;

      if (message.localId) {
        // Sent message: check by localId (most reliable for sent messages)
        existingMessage = chat.messages.find(m => m.localId === message.localId);
      } else {
        // Received message: use content + sender for duplicate detection
        // Don't use timestamp as offline messages may have different timestamps
        const messageKey = `${message.text}_${message.sender}`;
        existingMessage = chat.messages.find(m => {
          const existingKey = `${m.text}_${m.sender}`;
          // Only consider it duplicate if the timestamps are very close (within 5 seconds)
          const timeDiff = Math.abs(new Date(m.timestamp).getTime() - new Date(message.timestamp).getTime());
          return existingKey === messageKey && timeDiff < 5000;
        });
      }

      const isDuplicate = !!existingMessage;
      chatLogger.debug('Message duplicate check', {
        isDuplicate,
        messageId: message.id || message.localId,
        text: message.text?.substring(0, 50) + '...',
        sender: message.sender,
        isReceived: !message.localId
      });

      if (!existingMessage) {
        const newMessage = {
          ...message,
          timestamp: message.timestamp || new Date()
        };

        // Insert message at correct position based on timestamp
        const messageTimestamp = new Date(newMessage.timestamp).getTime();
        let insertIndex = chat.messages.length; // Default to end

        // Find correct insertion position by comparing timestamps
        for (let i = chat.messages.length - 1; i >= 0; i--) {
          const existingTimestamp = new Date(chat.messages[i].timestamp).getTime();
          if (messageTimestamp >= existingTimestamp) {
            insertIndex = i + 1;
            break;
          }
          insertIndex = i;
        }

        // Insert message at the correct position
        chat.messages.splice(insertIndex, 0, newMessage);

        // Update unread count for received messages (not sent by current user)
        if (message.sender === 'other' && chatId !== selectedChatId.value) {
          chat.unreadCount = (chat.unreadCount || 0) + 1;
          chatLogger.debug('Unread count updated', { chatId, unreadCount: chat.unreadCount });
        }

        chatLogger.debug('Message added to chat', {
          chatId,
          insertIndex,
          totalMessages: chat.messages.length,
          messageTimestamp: newMessage.timestamp,
          unreadCount: chat.unreadCount
        });

        // Save to localStorage
        localStorageService.addMessage(chatId, message);
        chatLogger.debug('Message saved to localStorage', { chatId });
      } else {
        chatLogger.debug('Message skipped - duplicate detected', {
          messageId: message.id || message.localId
        });
      }
    }
  }

  // Update message status
  function updateMessageStatus(chatId, localId, updatedMessage) {
    const chat = chats.value.find(c => c.id === chatId);
    if (chat && chat.messages) {
      const messageIndex = chat.messages.findIndex(m => m.localId === localId);
      if (messageIndex !== -1) {
        // Update the message with new status information
        chat.messages[messageIndex] = {
          ...chat.messages[messageIndex],
          ...updatedMessage,
          timestamp: chat.messages[messageIndex].timestamp // Preserve original timestamp
        };

        // Save to localStorage
        saveToStorage();

        console.log('📊 Message status updated in store:', localId, updatedMessage.status);
      }
    }
  }

  // Move message to bottom (for retry functionality)
  function moveMessageToBottom(chatId, localId, updatedMessage) {
    const chat = chats.value.find(c => c.id === chatId);
    if (chat && chat.messages) {
      const messageIndex = chat.messages.findIndex(m => m.localId === localId);
      if (messageIndex !== -1) {
        // Remove the message from its current position
        const [message] = chat.messages.splice(messageIndex, 1);

        // Update the message with new information and timestamp
        const updatedMsg = {
          ...message,
          ...updatedMessage,
          timestamp: new Date() // New timestamp to place at bottom
        };

        // Add it to the end
        chat.messages.push(updatedMsg);

        // Save to localStorage
        saveToStorage();

        console.log('📊 Message moved to bottom:', localId);
      }
    }
  }

  async function fetchContacts() {
    const authStore = useAuthStore();
    if (!authStore.token) {
      chatLogger.warn('No auth token available for fetching contacts');
      return;
    }

    if (!currentUserId.value) {
      chatLogger.warn('No user context set for fetching contacts');
      return;
    }

    try {
      chatLogger.debug('Fetching contacts and limits', { userId: currentUserId.value });

      // Clear failed chat info cache when fetching contacts
      chatInfoCache.forEach((cached, contactId) => {
        if (cached.failed) {
          chatInfoCache.delete(contactId);
          chatLogger.debug('Cleared failed cache for contact', { contactId });
        }
      });

      // Fetch both contacts and contact limits
      const [contactsResponse, limitsResponse] = await Promise.all([
        apiClient.get('/contacts'),
        apiClient.get('/contacts/limits')
      ]);

      // Update contact limits (handle both direct data and wrapped format)
      contactLimits.value = limitsResponse.data.data || limitsResponse.data;
      chatLogger.debug('Contact limits updated', contactLimits.value);

      // Extract contact data from response (handle both direct array and wrapped format)
      const contactData = contactsResponse.data.data || contactsResponse.data;

      // Merge with existing chat data from localStorage
      const existingChats = chats.value;

      // Transform contact data to fit the chat structure
      const contactChats = contactData.map(contact => {
        // Find existing chat data by id
        const existingChat = existingChats.find(c => c.id === contact.id);

        return {
          id: contact.id, // Contact ID from backend
          name: contact.nickname, // Use nickname for display only
          avatar: contact.avatar_url || String(contact.id).charAt(0).toUpperCase(),
          contact_type: contact.contact_type, // numeric: 1=TYPE1, 2=TYPE2
          messages: existingChat?.messages || [], // Preserve existing messages
        };
      });

      // Only use contacts from the current API response to avoid showing other users' contacts
      // Clear any existing chats to prevent cross-user data contamination
      chats.value = contactChats;

      if (chats.value.length > 0 && !selectedChatId.value) {
        selectedChatId.value = chats.value[0].id;
      }

      // Save updated chats to localStorage
      saveToStorage();
      isLoaded.value = true;

      chatLogger.info('Contacts fetched successfully', {
        contactCount: chats.value.length,
        selectedChatId: selectedChatId.value
      });

    } catch (error) {
      chatLogger.error('Failed to fetch contacts', error);
      handleError(error, {
        operation: 'load_contacts',
        context: 'fetchContacts',
        showToast: true,
      });
    }
  }

  async function selectChat(chatId) {
    selectedChatId.value = chatId;

    // Clear unread count for selected chat
    const chat = chats.value.find(c => c.id === chatId);
    if (chat && chat.unreadCount > 0) {
      chat.unreadCount = 0;
      saveToStorage(); // Save the updated unread count
      chatLogger.debug('Unread count cleared for selected chat', { chatId });
    }

    // Only update chat info for contacts (not for non-contact conversations)
    if (chat && chat.contact_type) {
      await updateContactChatInfo(chatId);
    } else {
      chatLogger.debug('Skipping chat info update for non-contact conversation', { chatId });
    }
  }

  // Cache mechanism to prevent repeated requests in a short period of time
  // Storage format: {contactId: {timestamp: number, promise: Promise, failed: boolean}}
  const chatInfoCache = new Map();

  async function updateContactChatInfo(contactId) {
    const authStore = useAuthStore();
    if (!authStore.token) {
      chatLogger.warn('No auth token available for chat info update');
      return;
    }

    // Check the cache to prevent repeated requests in a short period of time
    const now = Date.now();
    const cached = chatInfoCache.get(contactId);

    if (cached) {
      // If previous request failed, don't retry
      if (cached.failed) {
        chatLogger.debug('Skipping chat info update - previous request failed', { contactId });
        return;
      }

      // If within cache duration, return cached promise
      if ((now - cached.timestamp) < CACHE_CONFIG.CHAT_INFO_DURATION) {
        const remainingTime = Math.round((CACHE_CONFIG.CHAT_INFO_DURATION - (now - cached.timestamp)) / 1000);
        chatLogger.debug('Using cached chat info', { contactId, remainingTime });
        return cached.promise;
      }
    }

    // Creating a new Promise request
    const requestPromise = (async () => {
      try {
        const response = await apiClient.get(`/contacts/${contactId}/chat-info`);
        const chatInfo = response.data.data || response.data;

        // Find and update the specific chat
        const chatIndex = chats.value.findIndex(c => c.id === contactId);
        if (chatIndex !== -1) {
          // Update chat info while preserving messages
          chats.value[chatIndex] = {
            ...chats.value[chatIndex],
            name: chatInfo.nickname,
            avatar: chatInfo.avatar_url || String(chatInfo.id).charAt(0).toUpperCase(),
            last_updated: chatInfo.last_updated
          };

          // Save updated chats to localStorage
          saveToStorage();

          chatLogger.info('Chat info updated successfully', { contactId });
        } else {
          chatLogger.warn('Chat not found for contact info update', { contactId });
        }

        return chatInfo;
      } catch (error) {
        chatLogger.error('Failed to update chat info', { contactId, error: error.message });

        // Mark as failed in cache to prevent retries, but preserve previous data
        const previousCached = chatInfoCache.get(contactId);
        chatInfoCache.set(contactId, {
          timestamp: now,
          promise: previousCached?.promise || null, // Keep previous promise if exists
          failed: true
        });

        // Handle error with user notification
        handleError(error, {
          operation: 'load_chat',
          context: 'updateContactChatInfo',
          showToast: false, // Don't show toast for background updates
        });

        // Don't throw error to avoid breaking the UI, just log it
        return null;
      }
    })();

    // Cache the request's Promise and timestamp
    chatInfoCache.set(contactId, {
      timestamp: now,
      promise: requestPromise,
      failed: false
    });

    return requestPromise;
  }

  // Clear current user's chat data
  function clearUserChats() {
    if (!currentUserId.value) {
      chatLogger.warn('Cannot clear chats: no user context set');
      return;
    }

    chats.value = [];
    selectedChatId.value = null;

    try {
      localStorageService.clearUserData();
      chatLogger.info('Cleared chat data for user', { userId: currentUserId.value });
    } catch (error) {
      chatLogger.error('Failed to clear user chat data', error);
    }

    // Clear the chat-info request cache
    chatInfoCache.clear();
  }

  // Clear all chat messages (keep contacts, clear messages only)
  function clearAllChatMessages() {
    if (!currentUserId.value) {
      chatLogger.warn('Cannot clear chat messages: no user context set');
      return false;
    }

    try {
      // Clear messages from all chats in memory
      chats.value.forEach(chat => {
        chat.messages = [];
      });

      // Clear messages in localStorage
      const success = localStorageService.clearAllChatMessages();

      if (success) {
        chatLogger.info('Cleared all chat messages for user', { userId: currentUserId.value });
        return true;
      }
      return false;
    } catch (error) {
      chatLogger.error('Failed to clear all chat messages', error);
      return false;
    }
  }

  // Clear specific contact's chat messages
  function clearContactChat(contactId) {
    if (!currentUserId.value) {
      chatLogger.warn('Cannot clear contact chat: no user context set');
      return false;
    }

    try {
      const chatIndex = chats.value.findIndex(c => c.id === contactId);
      if (chatIndex !== -1) {
        // Clear messages for this contact in memory
        chats.value[chatIndex].messages = [];

        // Clear messages in localStorage
        const success = localStorageService.clearContactMessages(contactId);

        if (success) {
          chatLogger.info('Cleared chat messages for contact', {
            userId: currentUserId.value,
            contactId
          });
          return true;
        }
      }
      return false;
    } catch (error) {
      chatLogger.error('Failed to clear contact chat messages', error);
      return false;
    }
  }

  // Legacy method for backward compatibility - now clears current user data only
  function clearChats() {
    clearUserChats();
  }

  // Setup periodic refresh of contacts (every 5 minutes)
  // Enable or disable the feature to periodically refresh the contact list: Currently set to off.
  // Purpose: To address the issue where user A's nickname may not be updated promptly 
  //          in user B's conversation list after user A updates their profile information.
  // Implementation: The fetchContacts() function is automatically called every 5 minutes 
  //                 to refresh all contact information.
  // In conjunction with the click-to-update mechanism (updateContactChatInfo), 
  // this ensures that users can see the latest contact information in a timely manner.
  // Note: The current setting is off. To enable it, set ENABLE_PERIODIC_REFRESH to true.
  const ENABLE_PERIODIC_REFRESH = false;

  let refreshInterval = null;

  function startPeriodicRefresh() {
    // Check feature flag
    if (!ENABLE_PERIODIC_REFRESH) {
      chatLogger.info('Periodic contacts refresh is disabled by feature flag');
      return;
    }

    if (refreshInterval) {
      clearInterval(refreshInterval);
    }

    refreshInterval = setInterval(() => {
      chatLogger.debug('Starting periodic contacts refresh');
      fetchContacts();
    }, 5 * 60 * 1000); // 5 minutes

    chatLogger.info('Started periodic contacts refresh', { interval: '5 minutes' });
  }

  function stopPeriodicRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval);
      refreshInterval = null;
      chatLogger.info('Stopped periodic contacts refresh');
    }
  }

  return {
    chats,
    selectedChatId,
    isLoaded,
    contactLimits,
    currentUserId,
    initializeWithUser,
    loadUserData,
    clearUserContext,
    fetchContacts,
    selectChat,
    updateContactChatInfo,
    addMessage,
    updateMessageStatus,
    moveMessageToBottom,
    saveToStorage,
    clearChats,
    clearUserChats,
    clearAllChatMessages,
    clearContactChat,
    startPeriodicRefresh,
    stopPeriodicRefresh,
  };
}); 