import { defineStore } from 'pinia';
import { ref } from 'vue'
import localStorageService from '../services/localStorage';
import { getBots } from '../services/api';
import { useAuthStore } from './auth';

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

  // Save chats to localStorage
  function saveToStorage() {
    localStorageService.saveChats(chats.value);
  }

  // Add message to chat and save to localStorage
  function addMessage(chatId, message) {
    console.log('📝 [ChatStore] Adding message to chat:', chatId, message)

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

      console.log('📝 [ChatStore] Existing message check:', existingMessage ? 'DUPLICATE FOUND' : 'NEW MESSAGE')
      console.log('📝 [ChatStore] Message details:', {
        id: message.id,
        localId: message.localId,
        text: message.text,
        sender: message.sender,
        isReceived: !message.localId
      })

      if (!existingMessage) {
        const newMessage = {
          ...message,
          timestamp: message.timestamp || new Date()
        };

        chat.messages.push(newMessage);
        console.log('📝 [ChatStore] Message added to chat.messages, total count:', chat.messages.length)

        // Save to localStorage
        localStorageService.addMessage(chatId, message);
        console.log('📝 [ChatStore] Message saved to localStorage')
      } else {
        console.log('📝 [ChatStore] Message skipped - duplicate detected')
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

  async function fetchBots() {
    const authStore = useAuthStore();
    if (!authStore.token) return;

    try {
      const response = await getBots(authStore.token);

      // Merge with existing chat data from localStorage
      const existingChats = chats.value;

      // Transform the bot data to fit the chat structure
      const botChats = response.data.map(bot => {
        // Find existing chat data by entity_id or conversation_id
        const existingChat = existingChats.find(c =>
          c.entity_id === bot.entity_id ||
          c.id === (bot.leancloud_conversation_id || bot.entity_id)
        );

        return {
          id: bot.leancloud_conversation_id || bot.entity_id, // Use LeanMessage conversation ID if available
          entity_id: bot.entity_id, // Keep entity_id for reference
          name: bot.nickname, // Use nickname for display only
          avatar: bot.avatar_url || bot.entity_id.charAt(0).toUpperCase(),
          bio: bot.bio,
          contact_type: bot.contact_type, // 1=user, 2=bot
          gender: bot.gender,
          relationship_type: bot.relationship_type,
          relationship_level: bot.relationship_level,
          friend_score: bot.friend_score,
          romance_score: bot.romance_score,
          leancloud_conversation_id: bot.leancloud_conversation_id, // Store separately for clarity
          messages: existingChat?.messages || [], // Preserve existing messages
        };
      });

      // Keep existing user chats (contact_type !== 2) and merge with new bot chats
      const userChats = existingChats.filter(chat => chat.contact_type !== 2);

      // Remove duplicates by creating a Map with unique IDs
      const allChats = [...userChats, ...botChats];
      const uniqueChatsMap = new Map();

      allChats.forEach(chat => {
        // Use entity_id as the primary key for deduplication
        const key = chat.entity_id || chat.id;
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

    } catch (error) {
      console.error("Failed to fetch bots:", error);
      // Handle error, maybe show a toast
    }
  }

  function selectChat(chatId) {
    selectedChatId.value = chatId;
  }

  // Clear all chat data
  function clearChats() {
    chats.value = [];
    selectedChatId.value = null;
    localStorageService.clearAllData();
  }

  return {
    chats,
    selectedChatId,
    isLoaded,
    fetchBots,
    selectChat,
    addMessage,
    updateMessageStatus,
    moveMessageToBottom,
    saveToStorage,
    clearChats,
  };
}); 