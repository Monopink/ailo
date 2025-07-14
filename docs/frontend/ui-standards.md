# UI设计规范

## 设计风格

### 现代macOS/Notion风格

- **设计理念**: 简洁、现代、精致
- **视觉特点**: 大圆角、半透明模糊效果、内嵌阴影
- **交互体验**: 流畅动画、微妙反馈、直观操作

### 色彩系统

```css
/* 主色调 */
--primary-color: #42db5a;      /* 绿色主色 */
--accent-color: #fdd700;       /* 黄色强调色 */

/* 中性色 */
--text-primary: #1a1a1a;       /* 主要文字 */
--text-secondary: #666666;     /* 次要文字 */
--background: #ffffff;         /* 背景色 */
--surface: #f8f9fa;           /* 表面色 */
--border: #e0e0e0;            /* 边框色 */

/* 状态色 */
--success: #42db5a;           /* 成功状态 */
--error: #ff4444;             /* 错误状态 */
--warning: #fdd700;           /* 警告状态 */
```

### 圆角规范

```css
/* 圆角大小 */
--radius-small: 6px;          /* 小圆角：按钮、输入框 */
--radius-medium: 12px;        /* 中圆角：卡片、面板 */
--radius-large: 20px;         /* 大圆角：模态框、容器 */
--radius-full: 50%;           /* 完全圆形：头像、图标按钮 */
```

## 组件样式规范

### 按钮设计

```css
.button {
  border-radius: var(--radius-small);
  padding: 12px 24px;
  font-weight: 500;
  transition: all 0.2s ease;
  border: none;
  cursor: pointer;
}

.button-primary {
  background-color: var(--primary-color);
  color: white;
}

.button-primary:hover {
  background-color: #3bc952;
  transform: translateY(-1px);
}

/* 圆形发送按钮 */
.send-button {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  background-color: var(--primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 红色按钮保持悬停状态 */
.button-danger:hover {
  background-color: #cc3333;
}
```

### 输入框设计

```css
.input {
  border: 1px solid var(--border);
  border-radius: var(--radius-small);
  padding: 12px 16px;
  font-size: 14px;
  transition: border-color 0.2s ease;
  background-color: white;
}

.input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(66, 219, 90, 0.1);
}

/* 统一输入框尺寸 */
.input-standard {
  height: 44px;
  min-width: 200px;
}
```

### 模态框设计

```css
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: var(--radius-medium); /* 较小的边框圆角 */
  padding: 24px;
  max-width: 500px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
}
```

### 联系人项设计

```css
.contact-item {
  padding: 12px 16px;
  border-radius: var(--radius-small);
  transition: background-color 0.2s ease;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 12px;
}

.contact-item:hover {
  background-color: #f5f5f5;
}

.contact-item.selected {
  background-color: #e8f5e8; /* 背景选中指示器 */
}

/* 无边框设计 */
.contact-item {
  border: none;
}
```

## 特殊效果

### 内嵌阴影效果（品牌名称）

```css
.brand-name {
  font-size: 24px;
  font-weight: 600;
  color: #999;
  text-shadow: 
    1px 1px 2px rgba(255, 255, 255, 0.8),
    -1px -1px 2px rgba(0, 0, 0, 0.1);
  /* 内嵌/雕刻效果 */
}
```

### 半透明模糊效果

```css
.glass-panel {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}
```

### 悬停效果

```css
.hover-lift {
  transition: transform 0.2s ease;
}

.hover-lift:hover {
  transform: translateY(-2px);
}

/* 避免过度的悬停抬升动画 */
.subtle-hover:hover {
  background-color: rgba(0, 0, 0, 0.05);
}
```

## 布局规范

### 间距系统

```css
/* 间距变量 */
--spacing-xs: 4px;
--spacing-sm: 8px;
--spacing-md: 16px;
--spacing-lg: 24px;
--spacing-xl: 32px;
--spacing-xxl: 48px;
```

### 响应式断点

```css
/* 媒体查询断点 */
@media (max-width: 768px) {
  /* 移动端样式 */
}

@media (min-width: 769px) and (max-width: 1024px) {
  /* 平板端样式 */
}

@media (min-width: 1025px) {
  /* 桌面端样式 */
}
```

### 统一聊天界面

```css
.chat-app {
  display: flex;
  height: 100vh;
  /* 无间隙设计，聊天列表和聊天窗口作为统一界面 */
}

.chat-sidebar {
  width: 300px;
  /* 无圆角分隔 */
}

.chat-main {
  flex: 1;
  /* 与侧边栏无缝连接 */
}
```

## 图标规范

### 图标使用

```css
/* 统一图标尺寸 */
.icon-sm { font-size: 16px; }
.icon-md { font-size: 20px; }
.icon-lg { font-size: 24px; }

/* 性别图标 */
.gender-icon {
  width: 20px;
  height: 20px;
  display: inline-block;
}

/* 密码可见性切换 - 猴子表情 */
.password-toggle::after {
  content: "🙈";
  cursor: pointer;
}

.password-toggle.visible::after {
  content: "🐵";
}
```

### 箭头图标

```css
.arrow-icon {
  width: 0;
  height: 0;
  border-left: 6px solid white;
  border-top: 4px solid transparent;
  border-bottom: 4px solid transparent;
}
```

## 表单设计

### 登录界面

```css
.login-container {
  /* 无背景框架，元素集成到页面中 */
  background: transparent;
  padding: var(--spacing-xl);
}

.login-tabs {
  /* 非全宽度登录标签 */
  display: inline-flex;
  border-radius: var(--radius-small);
  background: var(--surface);
}

.login-form {
  /* 紧凑登录表单 */
  max-width: 400px;
  margin: 0 auto;
}
```

### 错误提示

```css
.error-container {
  min-height: 1.2em; /* 最小预留空间 */
  color: var(--error);
  font-size: 0.9em;
  margin-top: var(--spacing-xs);
  /* 无错误时保持和谐间距 */
}
```

### 字符限制配置

```javascript
// 通过配置文件管理字符限制
const CHARACTER_LIMITS = {
  nickname: 20,
  bio: 100,
  message: 1000
}
```

## 动画规范

### 过渡动画

```css
/* 标准过渡时间 */
.transition-fast { transition: all 0.15s ease; }
.transition-normal { transition: all 0.2s ease; }
.transition-slow { transition: all 0.3s ease; }

/* 缓动函数 */
.ease-out { transition-timing-function: ease-out; }
.ease-in-out { transition-timing-function: ease-in-out; }
```

### 禁用动画

```css
/* 避免过度动画 */
.no-hover-lift {
  transform: none !important;
}

/* 减少动画干扰 */
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

## 无障碍设计

### 焦点指示

```css
.focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}
```

### 语义化标记

```html
<!-- 使用适当的语义标签 -->
<main role="main">
  <section aria-label="聊天列表">
    <ul role="list">
      <li role="listitem">
        <button aria-label="选择联系人">
```

### 颜色对比

- 确保文字与背景对比度至少4.5:1
- 重要信息不仅依赖颜色传达
- 支持高对比度模式
