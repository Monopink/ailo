# 多端登录功能说明

## 概述

本系统支持用户在多个设备上同时登录，提供灵活的多端登录策略和冲突处理机制。基于LeanCloud即时通讯服务的多端登录支持，实现了完整的多设备消息同步功能。

## 功能特性

### 1. 多端登录策略

- **无限制多端登录** (`UNLIMITED`)
  - 允许用户在任意数量的设备上同时登录
  - 所有设备都能接收和发送消息
  - 适用于团队协作场景

- **限制多端登录** (`LIMITED_MULTI`) - **推荐**
  - 允许用户在不同类型的设备上登录（Web、Mobile、Pad、Desktop）
  - 同类型设备只能有一个在线
  - 平衡了便利性和安全性

- **单设备登录** (`SINGLE_DEVICE`)
  - 只允许用户在一个设备上登录
  - 新设备登录会强制旧设备下线
  - 适用于高安全性要求的场景

### 2. 冲突处理机制

- **强制下线旧设备** (`FORCE_LOGOUT`) - **默认**
  - 新设备登录时，强制让较早登录的设备下线
  - 用户会收到"账号在其他设备上登录"的通知

- **拒绝新设备登录** (`REJECT_NEW`)
  - 当检测到冲突时，拒绝新设备的登录请求
  - 保护当前在线设备不被打断

- **仅通知不处理** (`NOTIFY_ONLY`)
  - 检测到冲突时仅显示通知，不进行强制操作
  - 适用于调试和特殊场景

### 3. 设备类型识别

系统自动识别设备类型：
- **Web**: 浏览器环境
- **Mobile**: 手机设备
- **Pad**: 平板设备  
- **Desktop**: 桌面应用（Electron等）

### 4. 消息同步

- **实时消息同步**: 所有在线设备实时接收新消息
- **离线消息拉取**: 设备重新上线时自动拉取离线期间的消息
- **未读消息计数**: 跨设备同步未读消息数量
- **消息状态同步**: 已读状态在所有设备间同步

## 使用方法

### 1. 基础配置

```javascript
import { multiDeviceManager } from './services/messaging/multiDeviceManager'
import { LoginStrategy, ConflictAction } from './services/messaging/types'

// 设置登录策略
multiDeviceManager.setLoginStrategy(LoginStrategy.LIMITED_MULTI)

// 设置冲突处理方式
multiDeviceManager.setConflictAction(ConflictAction.FORCE_LOGOUT)
```

### 2. 监听多端事件

```javascript
// 监听登录冲突
multiDeviceManager.onConflict((conflictInfo) => {
  console.log('登录冲突:', conflictInfo)
  // 处理冲突逻辑
})

// 监听网络状态变化
window.addEventListener('messaging-network-status', (event) => {
  const { type, data } = event.detail
  console.log('网络状态:', type, data)
})

// 监听多端登录下线事件
window.addEventListener('multi-device-logout', (event) => {
  const { reason, conflictInfo } = event.detail
  console.log('多端下线:', reason, conflictInfo)
  // 处理下线逻辑，如跳转到登录页
})
```

### 3. 获取设备信息

```javascript
const deviceInfo = multiDeviceManager.getDeviceInfo()
console.log('设备信息:', deviceInfo)
// 输出包含：设备类型、会话ID、登录策略、冲突处理方式等
```

### 4. 配置管理

```javascript
import { multiDeviceConfig } from './services/messaging/multiDeviceConfig'

// 获取当前配置
const config = multiDeviceConfig.getConfig()

// 更新配置
multiDeviceConfig.updateConfig({
  loginStrategy: LoginStrategy.LIMITED_MULTI,
  notifications: {
    showConflictNotifications: true,
    showReconnectNotifications: false
  }
})

// 重置为默认配置
multiDeviceConfig.resetToDefaults()
```

## 开发调试

### 1. 开发模式状态显示

在开发模式下，页面右上角会显示多端登录状态组件，包含：
- 设备信息
- 登录策略
- 网络状态
- 最近事件
- 快速操作

### 2. 配置界面

可以使用 `MultiDeviceSettings` 组件提供图形化配置界面：

```vue
<template>
  <MultiDeviceSettings />
</template>

<script>
import MultiDeviceSettings from './components/MultiDeviceSettings.vue'
</script>
```

### 3. 调试日志

开启调试日志：

```javascript
multiDeviceConfig.setDebugEnabled(true)
```

### 4. 模拟测试

```javascript
// 模拟设备类型
multiDeviceConfig.updateConfig({
  development: {
    mockDeviceType: 'Mobile'
  }
})

// 模拟登录冲突
multiDeviceConfig.updateConfig({
  development: {
    simulateConflicts: true
  }
})
```

## 最佳实践

### 1. 推荐配置

```javascript
// 生产环境推荐配置
const productionConfig = {
  loginStrategy: LoginStrategy.LIMITED_MULTI,
  conflictAction: ConflictAction.FORCE_LOGOUT,
  autoReconnect: {
    enabled: true,
    maxAttempts: 3,
    baseDelay: 1000
  },
  notifications: {
    showConflictNotifications: true,
    showReconnectNotifications: false,
    showDeviceChangeNotifications: false
  }
}
```

### 2. 错误处理

```javascript
// 处理登录失败
try {
  await messageService.initialize(userId)
} catch (error) {
  if (error.message.includes('conflict')) {
    // 处理登录冲突
    console.log('登录冲突，请稍后重试')
  } else {
    // 处理其他错误
    console.error('登录失败:', error)
  }
}
```

### 3. 用户体验优化

- 在登录冲突时提供清晰的用户提示
- 支持用户手动重连
- 在网络不稳定时显示连接状态
- 提供离线消息同步进度提示

## 技术实现

### 1. 架构设计

```
MultiDeviceManager (多端管理器)
├── MultiDeviceConfig (配置管理)
├── LeanCloudProvider (消息提供商)
└── MessageService (消息服务)
```

### 2. 关键组件

- `multiDeviceManager`: 核心多端登录管理器
- `multiDeviceConfig`: 配置管理器
- `MultiDeviceStatus`: 状态显示组件
- `MultiDeviceSettings`: 配置界面组件

### 3. 事件系统

- `messaging-network-status`: 网络状态变化
- `multi-device-logout`: 多端登录下线
- `chat-message-received`: 消息接收
- `typing-message`: 输入状态

## 注意事项

1. **配置持久化**: 配置会自动保存到 localStorage
2. **开发模式**: 某些功能仅在开发模式下可用
3. **网络依赖**: 多端同步依赖网络连接质量
4. **消息加密**: 支持消息加密，确保多端传输安全
5. **向后兼容**: 不支持向后兼容，建议统一升级

## 故障排除

### 1. 登录冲突频繁

- 检查登录策略配置
- 确认设备类型识别正确
- 查看网络连接稳定性

### 2. 消息同步延迟

- 检查网络状态
- 确认自动重连配置
- 查看离线消息拉取日志

### 3. 配置丢失

- 检查 localStorage 权限
- 确认配置格式正确
- 使用配置导出/导入功能备份

## 更新日志

- **v1.0.0**: 初始版本，支持基础多端登录
- **v1.1.0**: 添加配置管理和状态显示
- **v1.2.0**: 完善事件系统和错误处理
