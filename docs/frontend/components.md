# 前端组件设计

## 核心组件架构

### 主要组件

- **App.vue**: 应用根组件，管理全局模态框
- **HomeView.vue**: 主页面，包含桌面和移动端布局
- **ChatList.vue**: 聊天列表组件
- **ChatWindow.vue**: 聊天窗口组件
- **LoginView.vue**: 登录注册页面

### 组件层次结构

```
App.vue
├── HomeView.vue (桌面端)
│   ├── ChatList.vue
│   └── ChatWindow.vue
├── HomeView.vue (移动端)
│   ├── ChatList.vue (列表视图)
│   └── ChatWindow.vue (聊天视图)
└── LoginView.vue
    ├── LoginForm.vue
    └── RegisterForm.vue
```

## 组件设计规范

### 聊天列表组件 (ChatList.vue)

```vue
<template>
  <div class="chat-list">
    <!-- 用户信息头部 -->
    <div class="user-header">
      <UserAvatar :nickname="userNickname" />
      <div class="user-info">
        <span class="nickname">{{ userNickname }}</span>
      </div>
    </div>
    
    <!-- 联系人列表 -->
    <div class="contacts-section">
      <ContactItem 
        v-for="contact in contacts"
        :key="contact.id"
        :contact="contact"
        :selected="selectedChatId === contact.id"
        @click="selectChat(contact.id)"
      />
    </div>
  </div>
</template>
```

**设计要点**:

- 无底部边框，使用圆角背景样式
- 背景选中指示器，无彩色条
- 支持删除按钮（仅清除聊天历史）
- 桌面端删除按钮与昵称内联显示

### 聊天窗口组件 (ChatWindow.vue)

```vue
<template>
  <div class="chat-window">
    <!-- 聊天头部 -->
    <div class="chat-header">
      <ContactInfo :contact="selectedContact" />
    </div>
    
    <!-- 消息列表 -->
    <div class="messages-container">
      <MessageItem
        v-for="message in messages"
        :key="message.id"
        :message="message"
        :is-own="message.from === currentUserId"
      />
    </div>
    
    <!-- 输入区域 -->
    <div class="input-area">
      <MessageInput @send="sendMessage" />
    </div>
  </div>
</template>
```

**设计要点**:

- 空聊天界面显示品牌名称（内嵌阴影效果）
- 时间戳显示频率较低
- 绿色主色调消息气泡 (#42db5a)
- 圆形发送按钮带箭头图标

### 联系人项组件 (ContactItem.vue)

```vue
<template>
  <div 
    class="contact-item"
    :class="{ selected: selected }"
    @click="$emit('click')"
  >
    <UserAvatar :nickname="contact.nickname" />
    <div class="contact-info">
      <div class="contact-name">{{ contact.nickname }}</div>
      <div class="last-message">{{ contact.lastMessage }}</div>
    </div>
    <div class="contact-actions">
      <button 
        v-if="showDeleteButton"
        class="delete-btn"
        @click.stop="$emit('delete')"
      >
        删除
      </button>
    </div>
  </div>
</template>
```

**设计要点**:

- 无边框，微妙圆角和悬停效果
- 选中状态仅使用背景色指示
- 删除按钮仅清除聊天历史，不移除联系人
- 移除表情符号显示

## 模态框组件

### 个人资料设置 (ProfileSetupModal.vue)

```vue
<template>
  <div class="modal-overlay">
    <div class="modal-content">
      <h2>完善个人资料</h2>
      <form @submit.prevent="handleSubmit">
        <div class="form-group">
          <label>昵称</label>
          <input 
            v-model="form.nickname"
            :maxlength="nicknameLimit"
            placeholder="请输入昵称"
          />
        </div>
        <div class="form-group">
          <label>性别</label>
          <GenderSelector v-model="form.gender" />
        </div>
      </form>
    </div>
  </div>
</template>
```

### 设置模态框 (SettingsModal.vue)

```vue
<template>
  <div class="modal-overlay">
    <div class="modal-content">
      <h2>设置</h2>
      <div class="settings-section">
        <div class="setting-item">
          <span>通知提醒</span>
          <span class="setting-value">已开启</span>
        </div>
      </div>
    </div>
  </div>
</template>
```

**设计要点**:

- 较小的边框圆角
- 单行通知提醒，无切换按钮
- 统一模态框样式

## 表单组件

### 性别选择器 (GenderSelector.vue)

```vue
<template>
  <div class="gender-selector">
    <button
      v-for="option in genderOptions"
      :key="option.value"
      :class="{ active: modelValue === option.value }"
      @click="$emit('update:modelValue', option.value)"
    >
      <i :class="option.icon"></i>
    </button>
  </div>
</template>
```

**设计要点**:

- 使用图标而非文字
- 支持国际化
- 圆角按钮设计

### 消息输入框 (MessageInput.vue)

```vue
<template>
  <div class="message-input">
    <textarea
      v-model="message"
      :maxlength="messageLimit"
      placeholder="输入消息..."
      @keydown.enter.exact.prevent="sendMessage"
    ></textarea>
    <button 
      class="send-button"
      :disabled="!message.trim()"
      @click="sendMessage"
    >
      <i class="arrow-icon"></i>
    </button>
  </div>
</template>
```

**设计要点**:

- 可配置字符限制
- 圆形发送按钮
- 箭头图标
- Enter键发送

## 工具组件

### 用户头像 (UserAvatar.vue)

```vue
<template>
  <div 
    class="user-avatar"
    :class="sizeClass"
  >
    <img v-if="avatarUrl" :src="avatarUrl" :alt="nickname" />
    <span v-else class="avatar-text">
      {{ avatarText }}
    </span>
  </div>
</template>

<script>
export default {
  props: {
    nickname: String,
    avatarUrl: String,
    size: {
      type: String,
      default: 'medium' // small, medium, large
    }
  },
  computed: {
    avatarText() {
      return this.nickname ? this.nickname.charAt(0).toUpperCase() : '?'
    }
  }
}
</script>
```

**设计要点**:

- 优先显示昵称首字符
- 多种尺寸支持
- 圆形设计
- 无头像时显示首字符

### 错误容器 (ErrorContainer.vue)

```vue
<template>
  <div 
    v-if="error"
    class="error-container"
  >
    {{ error }}
  </div>
</template>

<style scoped>
.error-container {
  /* 最小预留空间，保持元素间距和谐 */
  min-height: 1.2em;
  color: #ff4444;
  font-size: 0.9em;
}
</style>
```

**设计要点**:

- 无错误时最小预留空间
- 保持元素间距和谐
- 统一错误样式

## 响应式设计

### 桌面端布局

```css
.home-container {
  display: flex;
  height: 100vh;
}

.chat-app {
  display: flex;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
}

.chat-sidebar {
  width: 300px;
  border-right: 1px solid #e0e0e0;
}

.chat-main {
  flex: 1;
}
```

### 移动端布局

```css
.mobile-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.mobile-chat-list {
  flex: 1;
  overflow-y: auto;
}

.mobile-chat-window {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: white;
  z-index: 100;
}
```

### 断点管理

```javascript
// 响应式断点
const breakpoints = {
  mobile: 768,
  tablet: 1024,
  desktop: 1200
}

// 检测设备类型
const isMobile = computed(() => {
  return window.innerWidth < breakpoints.mobile
})
```
