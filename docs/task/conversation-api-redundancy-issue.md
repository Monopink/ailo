# Conversation API 职责澄清与整改计划

> 更新时间：2025-11-20  
> 结论：**保留并精简 `/api/v1/conversation/current`（重命名为 `/api/v1/system/lc-im-conversation`），使其成为系统 IM 通道注册表；contact 接口继续返回派生字段。**

---

## 1. 背景与症状

- 小程序登录后调用 `GET /api/v1/conversation/current`，后端在 `backend/app/api/v1/conversation.py:35` 访问 `state["version"]` 触发 `KeyError`。  
  日志：`logs/backend.log` 中的 `conversation_state_failed`。
- 代码梳理发现：
  - `get_conversation_registry_state()`（`backend/app/services/message/providers/leancloud/service.py`）只返回 `{"im_conv_id": ...}`，未提供 `version/updated_at`。
  - `frontend/wx-minipg/utils/message/conversation-store.js` 期望从 `/conversation/current` 获得 `{im_conv_id, version, updated_at}` 并缓存。
- 文档与实现脱节：原型 `docs/prototype/api-design.md` 8.1 节标注“IM 配置暂不实现”，但实际已经通过 `/conversation/current` 对外提供，只是未命名清楚。

## 2. 现状梳理

| 组件 | 角色 | 说明 |
| --- | --- | --- |
| `/api/v1/contacts/*` | 业务接口 | 负责联系人 CRUD、profile 等业务数据。返回的 `im_conv_id` 是从系统配置派生出来的字段，方便聊天页面初始化。 |
| `/api/v1/conversation/current` | 系统接口 | 目前实现了“LeanCloud 系统会话注册表”，被 `ConversationStore` 用于 App 启动、消息发送失败后的重连等全局场景。 |
| `ConversationStore` | 前端全局状态 | 在 App 初始化时拉取系统会话 ID，缓存/广播给 `MessageService`、聊天页面等。 |
| `MessageService._sendViaAdapter` | 消息发送 | 每次发送前调用 `conversationStore.getImConvId()`；遇到 LeanCloud `CONVERSATION_NOT_FOUND` 时触发 `conversationStore.refresh()`。 |

### 为什么两个接口都会返回 `im_conv_id`？

LeanCloud MVP 架构采用“单一系统 conversation”，因此所有联系人共享同一个 `im_conv_id`。**但这并不代表两个接口功能相同：**

- Contact 接口关注“某个 conv_id 的业务信息”，只是顺带把系统通道 ID 填入响应，方便 UI 兜底。
- `/conversation/current` 则面向“系统级操作”——App 启动、消息重连、健康检查等无需联系人上下文的场景。

若仅依赖 contact 接口：

- 消息服务在 LeanCloud 报错时，没有 conv_id 的语境去请求联系人接口；

- App 冷启动也会不必要地读取联系人 + Profile；

- 后台刷新系统通道后，缺少统一信号通知客户端刷新。

因此，更合理的做法是**保留系统接口，但明确它与 contact 的职责边界**。

## 3. 结论

1. `/conversation/current` 保留，并正式定义为 **System IM Conversation Registry**：
   - 建议重命名：`/api/v1/system/lc-im-conversation`（lc = LeanCloud；如未来扩展其它 provider，可加 query 参数或路径前缀）。
   - 响应体简化为 `{"im_conv_id": "..."}`。`version/updated_at` 暂不返回，必要时可扩展。
   - 后端以 `system_configs.leancloud_im_service_conversation_id` 为唯一来源。

2. Contact 接口的 `im_conv_id` 标注为“派生字段”：在 API 文档与代码注释中说明其来源，避免误以为它是唯一真相源。

3. `ConversationStore` 是唯一的系统会话入口：App 及消息服务通过 Store 获取 `im_conv_id`；聊天页面不直接请求系统接口，只订阅 Store。

4. 若系统接口请求失败，可以在 Store 中 fallback 到联系人接口（或缓存），但默认数据源必须是系统接口。

## 4. 具体整改计划

### 4.1 后端

1. **接口更名与精简**
   - 路由：`/api/v1/system/lc-im-conversation`（保留旧路由做临时兼容，返回相同结构并打弃用日志）。
   - 响应体：
     ```json
     {
       "im_conv_id": "system_conversation_id"
     }
     ```
   - 日志与监控重点记录 `im_conv_id`，不再引用 `version`。

2. **服务函数调整**
   - `get_conversation_registry_state` 返回 `dict[str, str]`，只包含 `im_conv_id`。
   - 若未来需要版本、元数据，可追加字段，但需在文档中同步说明。

3. **文档更新**
   - `docs/prototype/api-design.md` 8.1 节补充接口定义。
   - `docs/development/contact-request-flow.md` 等引用 contact schema 的文档注明 `im_conv_id` 为派生字段。

### 4.2 前端

1. **ConversationStore**
   - 注释说明：这是“系统会话注册表”的唯一入口。
   - `refresh()` 首选 `/system/lc-im-conversation`，若失败再 fallback。
   - 缓存结构可简化为 `{im_conv_id}`，但保留扩展空间（兼容后续字段）。

2. **聊天页面**
   - 初始化时仍需 contact 接口（获取昵称、头像等），但 `im_conv_id` 以 Store 为准；contact 字段用作 UI 兜底。
   - `refreshConversationChannel()`：先刷新 Store，再更新 UI；不再主动覆盖 Store 返回值。

3. **消息服务**
   - 已经只通过 Store 获取 `im_conv_id`，只需补充注释，明确依赖关系。

### 4.3 兼容策略

| 阶段 | 处理方式 |
| --- | --- |
| 短期 | 修复后端 KeyError（只返回 `im_conv_id`，日志改写）。 |
| 中期 | 上线新路由 `/system/lc-im-conversation`，旧路由返回 301/弃用提示。前端更新 Store 使用新路由。 |
| 长期 | 若切换到多 conversation/provider 架构，可在系统接口返回 `{provider, im_conv_id, metadata}`，前端 Store 按 provider 分桶。 |

## 5. 任务清单

### 后端
1. `backend/app/api/v1/conversation.py`
   - 统一入口改名；响应体只包含 `im_conv_id`。
   - 日志字段改为 `im_conv_id`。
2. `backend/app/services/message/providers/leancloud/service.py`
   - `get_conversation_registry_state()` 仅返回 `im_conv_id`。
3. `docs/prototype/api-design.md`
   - 更新 8.1 章节，添加示例响应、使用场景、错误码。
4. `docs/development/*` & schema
   - Contact schema 注释 `im_conv_id` 来源。
5. （可选）在管理后台/system config 文档中补充“lc-im conversation”配置项说明。

### 前端（wx-minipg）
1. `utils/message/conversation-store.js`
   - 注释/日志更新，明确数据源。
   - 若接口失败，fallback 到联系人或缓存。
2. `pages/chat/chat.js`
   - 读取 `im_conv_id` 时优先使用 Store，contact 字段只做兜底。
3. `utils/message/service.js`
   - 注释 `conversationStore` 依赖，确保重连逻辑只刷新 Store。
4. 文档 `docs/task/temp`（如还存在）同步更新结论，避免再次建议删除接口。

## 6. 风险与测试

| 风险 | 缓解 |
| --- | --- |
| 接口改名导致旧版本小程序请求失败 | 保留旧路由一段时间并返回兼容数据；在响应头增加 `Deprecation` 提示。 |
| Store fallback 逻辑未覆盖无联系人场景 | 增加空联系人测试：新用户登录 → 直接拉 `/system/lc-im-conversation`，确认可工作。 |
| 文档未同步导致团队误解 | 在 PR 中引用此文档；发布后通知全体在 Slack/钉钉确认。 |

### 回归建议
1. App 冷启动：观察日志 `conversation_state_retrieved`，确认只记录 `im_conv_id`。
2. 手动触发 LeanCloud 会话刷新（更新 system_configs）：确认前端在下次刷新时拿到新 ID。
3. 消息发送时故意破坏 conversation：验证 `CONVERSATION_NOT_FOUND` → Store refresh → 重发逻辑仍工作。

## 7. 结语

此次问题的根因不是“接口冗余”，而是“字段缺失 + 职责描述不清”。通过将 `/conversation/current` 正式纳入系统配置层，并在文档、代码中标注 contact 字段的派生关系，可以同时满足 KISS / SOLID，也让后续扩展（多 provider、多会话）更易落地。请以本方案为准实施修复与重构。*** End Patch***}):
