# 消息系统

消息系统负责处理客户端与服务端之间的所有消息通信，包括用户消息、AI响应、输入状态、系统通知等。

## 完整消息流

```mermaid
flowchart TB
    A[客户端发送消息] --> B{消息 Provider}
    B -->|LeanCloud| C[Webhook接收<br/>leancloud.md]
    B -->|WebSocket| D[WS接收<br/>websocket.md]
    C --> E[消息验证和解密<br/>encryption.md]
    D --> E
    E --> F{消息类型}

    F -->|TEXT| G[安全检测]
    F -->|TYPING| H[special-types.md]
    F -->|CHAT_INFO| H
    F -->|NOTIFICATION| H

    G --> I[频率限制]
    I --> J[消息缓冲<br/>buffer.md]
    J --> K{计时器到期?}

    K -->|否| L[等待更多消息]
    L --> J

    K -->|是| M[锁定窗口<br/>LOCKED]
    M --> N[构建上下文<br/>context.md]
    N --> O[LLM调用]
    O --> P[响应处理]
    P --> Q[写入message_history<br/>schema.md]
    Q --> R[写入message_dispatch_outbox<br/>schema.md]
    R --> S[Worker 读取 outbox 并选择 endpoints]
    S --> T[Provider 发送]
    T --> U[写入message_deliveries<br/>schema.md]
    U --> V[客户端接收]
    V --> W[HTTP ACK 推进游标<br/>delivery-reliability.md]
```
