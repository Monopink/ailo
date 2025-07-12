import { defineStore } from 'pinia';
import { ref } from 'vue'
import localStorageService from '../services/localStorage';
import { getContacts, getContactChatInfo, getContactLimits } from '../services/api';
import { useAuthStore } from './auth';
import { ContactType } from '../services/messaging/types';
import { chatLogger } from '../utils/logger.js';
import { handleError } from '../utils/errorHandler.js';
import { CACHE_CONFIG, CONTACT_CONFIG } from '../config/constants.js';

// Load initial data from localStorage
const loadInitialData = () => {
  const data = localStorageService.loadChats();
  return data ? { chats: data.chats, selectedChatId: null } : { chats: [], selectedChatId: null };
};

export const useChatStore = defineStore('chat', () => {
  // Load initial data from localStorage
  const initialData = loadInitialData();
  const chats = ref(initialData.chats);
  const selectedChatId = ref(initialData.selectedChatId);
  const isLoaded = ref(false);

  // Contact limits information
  const contactLimits = ref({
    contact_limit: CONTACT_CONFIG.DEFAULT_LIMIT,
    current_count: 0,
    can_add_more: true
  });

  // Save chats to localStorage
  function saveToStorage() {
    localStorageService.saveChats(chats.value);
  }

  // Add message to chat and save to localStorage
  function addMessage(chatId, message) {
    chatLogger.debug('Adding message to chat', { chatId, messageId: message.id || message.localId });

    const chat = chats.value.find(c => c.id === chatId);
    if (chat) {
      if (!chat.messages) {
        chat.messages = [];
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

        chat.messages.push(newMessage);
        chatLogger.debug('Message added to chat', {
          chatId,
          totalMessages: chat.messages.length
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

    try {
      chatLogger.debug('Fetching contacts and limits');

      // Fetch both contacts and contact limits
      const [contactsResponse, limitsResponse] = await Promise.all([
        getContacts(),
        getContactLimits()
      ]);

      // Update contact limits
      contactLimits.value = limitsResponse.data;
      chatLogger.debug('Contact limits updated', contactLimits.value);

      const response = contactsResponse;

      // Merge with existing chat data from localStorage
      const existingChats = chats.value;

      // Transform contact data to fit the chat structure
      const contactChats = response.data.map(contact => {
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

      // Keep existing chats and merge with fetched contacts
      const existingUserChats = existingChats.filter(chat => chat.contact_type !== ContactType.TYPE2);

      // Remove duplicates by creating a Map with unique IDs
      const allChats = [...existingUserChats, ...contactChats];
      const uniqueChatsMap = new Map();

      allChats.forEach(chat => {
        // Use id as the primary key for deduplication
        const key = chat.id;
        if (!uniqueChatsMap.has(key)) {
          uniqueChatsMap.set(key, chat);
        }
      });

      chats.value = Array.from(uniqueChatsMap.values());

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

    // Update specific contact's chat info when selected
    await updateContactChatInfo(chatId);
  }

  // Cache mechanism to prevent repeated requests in a short period of time
  const chatInfoCache = new Map(); // Storage format: {contactId: {timestamp: number, promise: Promise}}

  async function updateContactChatInfo(contactId) {
    const authStore = useAuthStore();
    if (!authStore.token) {
      chatLogger.warn('No auth token available for chat info update');
      return;
    }

    // Check the cache to prevent repeated requests in a short period of time
    const now = Date.now();
    const cached = chatInfoCache.get(contactId);

    if (cached && (now - cached.timestamp) < CACHE_CONFIG.CHAT_INFO_DURATION) {
      const remainingTime = Math.round((CACHE_CONFIG.CHAT_INFO_DURATION - (now - cached.timestamp)) / 1000);
      chatLogger.debug('Using cached chat info', { contactId, remainingTime });
      return cached.promise;
    }

    // Creating a new Promise request
    const requestPromise = (async () => {
      try {
        const response = await getContactChatInfo(contactId);
        const chatInfo = response.data;

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
        // When the request fails, remove it from the cache to allow retries
        chatInfoCache.delete(contactId);

        // Handle error with user notification
        handleError(error, {
          operation: 'load_chat',
          context: 'updateContactChatInfo',
          showToast: false, // Don't show toast for background updates
        });

        throw error;
      }
    })();

    // Cache the request's Promise and timestamp
    chatInfoCache.set(contactId, {
      timestamp: now,
      promise: requestPromise
    });

    return requestPromise;
  }

  // Clear all chat data
  function clearChats() {
    chats.value = [];
    selectedChatId.value = null;
    localStorageService.clearAllData();

    // Clear the chat-info request cache
    chatInfoCache.clear();
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
    fetchContacts,
    selectChat,
    updateContactChatInfo,
    addMessage,
    updateMessageStatus,
    moveMessageToBottom,
    saveToStorage,
    clearChats,
    startPeriodicRefresh,
    stopPeriodicRefresh,
  };
}); 