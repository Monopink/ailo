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
    const chat = chats.value.find(c => c.id === chatId);
    if (chat) {
      if (!chat.messages) {
        chat.messages = [];
      }

      // Avoid duplicate messages
      const existingMessage = chat.messages.find(m => m.id === message.id);
      if (!existingMessage) {
        chat.messages.push({
          ...message,
          timestamp: message.timestamp || new Date()
        });

        // Save to localStorage
        localStorageService.addMessage(chatId, message);
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
    saveToStorage,
    clearChats,
  };
}); 