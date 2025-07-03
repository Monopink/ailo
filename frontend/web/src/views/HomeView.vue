<template>
  <div class="home-container grid-bg">
    <div class="chat-container glass-panel">
      <!-- Mobile chat list toggle button -->
      <button class="mobile-toggle btn hide-on-desktop" @click="toggleChatList">
        查看列表
      </button>



      <!-- Chat sidebar - hidden by default on mobile, toggled with the button -->
      <div :class="{
        'chat-sidebar': true,
        'glass-panel': true,
        'mobile-sidebar-visible': showMobileChatList
      }">
        <ChatList />
      </div>

      <!-- Main chat area -->
      <div class="chat-main glass-panel">
        <ChatWindow />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import ChatList from '../components/ChatList.vue';
import ChatWindow from '../components/ChatWindow.vue';

// State for mobile sidebar toggle
const showMobileChatList = ref(false);

// Function to toggle the chat list on mobile
const toggleChatList = () => {
  showMobileChatList.value = !showMobileChatList.value;
};
</script>

<style scoped>
.home-container {
  width: 100%;
  height: 100%;
  padding: 20px;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
}

.chat-container {
  display: flex;
  position: relative;
  height: var(--chat-container-height);
  width: var(--chat-container-width);
  max-width: var(--chat-container-max-width);
  background-color: var(--color-bg-overlay);
  overflow: hidden;
  border-radius: var(--border-radius);
}

.nav-links {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 100;
  display: flex;
  gap: 10px;
}

.nav-link {
  padding: 5px 10px;
  background-color: var(--color-primary);
  color: white;
  text-decoration: none;
  border-radius: 4px;
  font-size: 0.8rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.chat-sidebar {
  flex: 0 0 280px;
  /* Fixed width on desktop */
  margin: 10px;
  border-radius: var(--border-radius);
  background-color: var(--color-bg-secondary);
  overflow: hidden;
}

.chat-main {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  margin: 10px;
  margin-left: 0;
  border-radius: var(--border-radius);
  overflow: hidden;
}

.mobile-toggle {
  display: none;
  /* Hidden by default on desktop */
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  z-index: 1000;
}

/* Responsive adjustments */
@media (max-width: 767px) {
  .home-container {
    padding: 0;
    height: 100vh;
  }

  .chat-container {
    height: 100vh;
    width: 100%;
    max-width: 100%;
    border-radius: 0;
  }

  .chat-sidebar {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 10;
    margin: 0;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
  }

  .mobile-sidebar-visible {
    transform: translateX(0);
  }

  .mobile-toggle {
    display: flex;
    /* Show toggle on mobile */
  }

  .chat-main {
    width: 100%;
    margin: 0;
  }
}
</style>