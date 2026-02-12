# 联系人系统

联系人系统负责管理用户之间的联系关系，包括 Square 曝光、联系人请求、AI 实例创建和联系人管理。

## 完整流程图

```mermaid
flowchart TB
    A[用户浏览 Square] --> B[square.md<br/>曝光策略]
    B --> C[点击 AI 卡片]
    C --> D[查看详情]
    D --> E[点击添加]

    E --> F[request-flow.md<br/>统一 API]
    F --> G{目标类型}

    G -->|AI| H[创建 contact_request<br/>status=PENDING]
    G -->|用户| I[创建 contact_request<br/>发送 NOTIFICATION]

    H --> J[Worker 轮询]
    J --> K[标记 PROCESSING]
    K --> L[ai-creation.md<br/>AI 验证]

    L --> M{模板可用?}
    M -->|是| N[创建 AI instance]
    M -->|否| O[挂起<br/>failure_code]

    N --> P[创建 contact]
    P --> Q[status=ACCEPTED]

    O --> R[管理员补充模板]
    R --> S[手动重试]
    S --> L

    I --> T[用户手动接受]
    T --> U[创建 contact]
    U --> V[status=ACCEPTED]

    Q --> W[management.md<br/>联系人管理]
    V --> W

    W --> X[更新/删除/恢复]
```
