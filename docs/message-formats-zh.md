# 消息格式规范文档

## 概述

本文档定义了系统中三种消息格式及其关系：

1. **LeanCloud 传输格式** - LeanCloud IM 服务的原生格式
2. **系统消息格式** - 我们定义的统一消息格式
3. **加密消息格式** - 包含加密元数据的扩展格式

## 架构设计：统一系统对话

### 设计原则

所有用户与bot的对话都使用 **单一的统一系统对话**，通过消息内容中的 `entity_id` 来区分不同的bot。这种设计：

- 减少 LeanCloud 资源消耗
- 简化对话管理
- 消除对话映射表的需求

### 对话管理

- **用户对用户**：每对用户一个独立对话（保持不变）
- **用户对bot**：所有bot共享一个统一系统对话
- **conversation_id 获取**：前端通过 API `/api/v1/system/conversation-id` 获取
- **缓存机制**：前端内存缓存，错误时自动清除并重试

## 1. LeanCloud 传输格式

LeanCloud IM 服务使用的原生消息格式，不可修改：

```javascript
// LeanCloud 发送消息时的格式
{
  conversationId: "6864d79a9a6e605b27a4ebba",
  message: "JSON字符串内容",  // 这里放我们的系统消息格式
  fromClientId: "u1002",
  toClientIds: ["b9002"]
}

// LeanCloud webhook 接收格式
{
  data: {
    _lctext: "JSON字符串内容",  // 这里是我们的系统消息格式
    _lctype: -1
  },
  from: "u1002",
  conv: { objectId: "6864d79a9a6e605b27a4ebba" },
  // ... 其他 LeanCloud 字段
}
```

## 2. 系统消息格式（基础版本）

我们定义的统一消息格式，用于前后端通信：

```javascript
{
  type: 1,                    // 数字类型：1=聊天, 2=输入状态, 3=系统消息
  from: "u1002",             // 发送者实体ID
  to: "b9002",               // 接收者实体ID
  content: "Hello World",    // 消息内容
  timestamp: "2025-07-05T01:03:26.474Z",  // ISO时间戳
  service: 1                 // 服务类型：1=LeanCloud
}
```

### 消息类型定义

- `1` - 聊天消息
- `2` - 输入状态
- `3` - 系统消息

### 服务类型定义

- `1` - LeanCloud IM 服务

## 3. 加密消息格式（扩展版本）

包含加密元数据的扩展格式：

```javascript
{
  type: 1,                    // 消息类型
  from: "u1002",             // 发送者
  to: "b9002",               // 接收者
  content: "SGVsbG8gV29ybGQ=", // 加密后的内容（Base64）
  timestamp: "2025-07-05T01:03:26.474Z",
  service: 1,                // LeanCloud 服务
  encryption: 1,             // 加密算法：1=Base64, 2=AES-256-GCM
  enc_version: 1             // 加密版本号
}
```

### 加密算法定义

- `1` - Base64 编码（伪加密）
- `2` - AES-256-GCM（真正加密，未来实现）

### 加密版本定义

- `1` - 第一版加密实现

## 4. 消息流转关系

### 发送流程

> 前端创建消息 → 加密处理 → 包装为LeanCloud格式 → 发送
> 原始消息格式 → 加密消息格式 → LeanCloud传输格式

### 接收流程

> LeanCloud接收 → 解析系统格式 → 解密处理 → 业务处理
> LeanCloud格式 → 加密消息格式 → 原始消息格式

### 代码映射

#### 前端

- `types.js` - 定义消息类型和格式
- `messageService.js` - 处理消息加密和格式转换
- `leancloudProvider.js` - 处理LeanCloud格式转换

#### 后端

- `enums.py` - 定义消息类型枚举
- `leanmessage.py` - 处理LeanCloud格式和系统格式转换
- `encryption.py` - 处理消息加密解密

## 5. 向后兼容性

### 未加密消息

```javascript
{
  type: 1,
  from: "u1002", 
  to: "b9002",
  content: "Hello World",    // 明文内容
  timestamp: "2025-07-05T01:03:26.474Z",
  service: 1
  // 没有 encryption 和 enc_version 字段
}
```

### 检测规则

- 如果消息包含 `encryption` 字段，则为加密消息
- 如果消息不包含 `encryption` 字段，则为未加密消息（向后兼容）

## 6. 实现注意事项

1. **LeanCloud格式不可修改** - 只能在 `_lctext` 字段中放置我们的JSON字符串
2. **数字编码优先** - 加密算法、版本等使用数字而非字符串
3. **向后兼容** - 必须支持未加密的旧消息格式
4. **错误处理** - 加密/解密失败时的降级策略
5. **性能考虑** - Base64编码开销，未来AES加密开销

## 7. 测试用例

### 基础消息

```javascript
{type: 1, from: "u1001", to: "u1002", content: "test", timestamp: "2025-07-05T10:00:00.000Z", service: 1}
```

### 加密消息

```javascript
{type: 1, from: "u1001", to: "u1002", content: "dGVzdA==", timestamp: "2025-07-05T10:00:00.000Z", service: 1, encryption: 1, enc_version: 1}
```

### LeanCloud包装

```javascript
{
  data: {
    _lctext: '{"type":1,"from":"u1001","to":"u1002","content":"dGVzdA==","timestamp":"2025-07-05T10:00:00.000Z","service":1,"encryption":1,"enc_version":1}',
    _lctype: -1
  }
}
```
