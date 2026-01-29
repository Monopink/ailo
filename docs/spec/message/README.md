# 消息系统

消息系统负责处理客户端与服务端之间的所有消息通信，包括用户消息、AI响应、输入状态、系统通知等。

## 文档索引

- [schema.md](schema.md) - 消息数据结构、ID规则、Event定义
- [buffer.md](buffer.md) - AI消息缓冲、双计时器、唤醒机制
- [context.md](context.md) - 上下文管理、消息查询、裁剪策略
- [leancloud.md](leancloud.md) - LeanCloud集成、Webhook处理
- [delivery-reliability.md](delivery-reliability.md) - 离线消息与未来消息同步
- [encryption.md](encryption.md) - 消息加密、Base64/AES方案
- [special-types.md](special-types.md) - TYPING/CHAT_INFO/NOTIFICATION处理
- [failure-handling.md](failure-handling.md) - 失败处理、重试机制

## 快速查找

按场景索引：

- **用户发送消息** → [leancloud.md](leancloud.md) Webhook → [buffer.md](buffer.md) 缓冲
- **AI生成回复** → [context.md](context.md) 构建上下文 → [buffer.md](buffer.md) 触发处理
- **消息发送失败** → [failure-handling.md](failure-handling.md)
- **输入状态显示** → [special-types.md](special-types.md) TYPING
- **系统通知** → [special-types.md](special-types.md) NOTIFICATION
- **消息加密** → [encryption.md](encryption.md)
- **消息ID规则** → [schema.md](schema.md)

## 完整消息流

```mermaid
flowchart TB
    A[客户端发送消息] --> B[LeanCloud系统对话]
    B --> C[Webhook接收<br/>leancloud.md]
    C --> D[消息验证和解密<br/>encryption.md]
    D --> E{消息类型}

    E -->|TEXT| F[安全检测]
    E -->|TYPING| G[special-types.md]
    E -->|CHAT_INFO| G
    E -->|NOTIFICATION| G

    F --> H[频率限制]
    H --> I[消息缓冲<br/>buffer.md]
    I --> J{计时器到期?}

    J -->|否| K[等待更多消息]
    K --> I

    J -->|是| L[锁定窗口<br/>LOCKED]
    L --> M[构建上下文<br/>context.md]
    M --> N[LLM调用]
    N --> O[响应处理]
    O --> P[消息发送]

    P --> Q{发送成功?}
    Q -->|是| R[写入message_history<br/>schema.md]
    Q -->|否| S[写入message_delivery_failures<br/>failure-handling.md]

    R --> T[LeanCloud发送]
    T --> U[客户端接收]

    S --> V[重试机制]
    V --> P
```
