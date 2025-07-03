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
    console.log('🔧 [DEBUG] fetchBots called')
    const authStore = useAuthStore();
    console.log('🔧 [DEBUG] authStore.token:', !!authStore.token)
    if (!authStore.token) return;

    try {
      console.log('🔧 [DEBUG] Fetching bots...')
      const response = await getBots(authStore.token);
      console.log('🔧 [DEBUG] getBots response:', response)

      // Merge with existing chat data from localStorage
      const existingChats = chats.value;

      // Transform the bot data to fit the chat structure
      console.log('🔧 [DEBUG] Received bots data:', response.data)
      const newChats = response.data.map(bot => {
        console.log('🔧 [DEBUG] Processing bot:', bot)
        // Find existing chat data
        const existingChat = existingChats.find(c => c.id === bot.entity_id);

        return {
          id: bot.leancloud_conversation_id || bot.entity_id, // Use LeanMessage conversation ID if available
          entity_id: bot.entity_id, // Keep entity_id for reference
          name: bot.nickname, // Use nickname for display only
          avatar: bot.avatar_url || bot.entity_id.charAt(0).toUpperCase(),
          bio: bot.bio || `AI Chat Bot - ${bot.entity_id}`,
          gender: bot.gender,
          relationship_type: bot.relationship_type,
          relationship_level: bot.relationship_level,
          friend_score: bot.friend_score,
          romance_score: bot.romance_score,
          messages: existingChat?.messages || [], // Preserve existing messages
        };
      });

      chats.value = newChats;

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