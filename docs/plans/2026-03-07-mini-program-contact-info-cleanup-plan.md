# 小程序 contact-info 页面整理计划

## 已确认决策

- 一个联系人对应一个业务会话。
- 移除 `/contacts/{conversation_id}/conversation`（前后端与文档同步移除）。
- 保留 `lc-im` 独立命名空间。
- 小程序页面层禁止直接依赖 `lc-im` 语义。
- `contact-info` 页面移除消息免打扰相关展示与悬空逻辑。
- 置顶功能保留设计，不在本次实现中展示或保留假逻辑。
- 首页继续承担联系人列表与会话列表双重产品功能。
- `tags` 纳入本次实现范围。
- `contact-info` 刷新策略：`onLoad` 必定远程刷新；`onShow` 仅在 dirty 标记命中、TTL 过期或前后台切换且 TTL 过期时触发远程刷新；手动刷新方式为退出重进页面。

## 目标范围

- 实装 `pages/contact-info/contact-info` 的备注、描述、标签展示、编辑与持久化。
- 移除 `pages/contact-info/contact-info` 的置顶聊天、消息免打扰、发送消息按钮及对应悬空逻辑。
- 修复清空聊天记录后聊天页与首页缩略残留的问题。
- 清理与废弃接口、废弃字段、悬空交互相关的前后端冗余实现。

## 接口与数据源调整

- `contact-info` 页面联系人详情读取统一使用 `GET /api/v1/contacts/{conversation_id}`。
- 备注、描述、标签保存统一使用 `PUT /api/v1/contacts/{conversation_id}`。
- `chat` 页面不再依赖 `/contacts/{conversation_id}/conversation`。
- 消息接入配置继续使用 `GET /api/v1/lc-im/config`。
- 移除 `/contacts/{conversation_id}/conversation` 对应的前端调用、后端路由实现与文档引用。

## 前端改动清单

### 1. 联系人详情页

- 调整 `frontend/wx-minipg/pages/contact-info/contact-info.ts` 页面数据结构，移除 `isPinned`、`isMuted` 及相关事件处理。
- 调整 `frontend/wx-minipg/pages/contact-info/contact-info.wxml`，移除置顶聊天、消息免打扰、发送消息按钮。
- 增加备注、描述、标签展示区块，展示字段来源为联系人详情接口返回的 `alias`、`remark`、`tags`。
- 将“备注和标签”入口改为实际编辑流程，表单字段包含 `alias`、`remark`、`tags`。
- 新增条件远程刷新触发规则，避免 `onShow` 无条件请求。

### 2. 联系人详情页 Service

- 调整 `frontend/wx-minipg/services/pages/contact-info-service.ts`，改为读取联系人详情接口。
- 增加联系人详情更新方法，负责调用 `PUT /contacts/{conversation_id}` 并同步本地缓存。
- 保留页面级状态模型，不再承接置顶和免打扰的本地假状态。

### 3. 联系人与会话本地缓存

- 调整 `frontend/wx-minipg/utils/schemas.ts`，为联系人本地缓存补充 `remark` 字段。
- 调整联系人缓存同步逻辑，保证 `alias`、`tags`、`remark`、`profile` 同步写入本地缓存。
- 清理对废弃 `/conversation` 接口的依赖代码。

### 4. 清空聊天记录一致性修复

- 将“清空聊天记录”收敛为单一清理入口，统一清理消息存储、会话视图状态、未读计数、未读标记、已读状态。
- `contact-info` 清空聊天记录成功后，主动刷新当前页数据并通知相关页面重新加载本地会话状态。
- `chat` 页面在 `onShow` 或等价页面激活时强制刷新当前会话消息，不复用已失效的内存消息状态。
- `index` 页面在 `onShow` 时重新从本地缓存构建列表，确保聊天缩略与未读状态即时一致。

### 5. 相关悬空逻辑清理

- 清理 `contact-info` 页面置顶、免打扰的展示、事件、日志与状态字段。
- 检查 `chat-detail` 页面同类悬空逻辑，按同一规则处理。
- 检查首页、聊天页、联系人缓存层是否仍存在 `is_muted` 驱动的展示逻辑。

## 文档同步

- 更新 `docs/spec/client/base/contacts-and-chat.md`，移除与本次实现不一致的置顶聊天、消息免打扰、发送消息描述。
- 更新 `docs/api/contacts.md`，移除 `/contacts/{conversation_id}/conversation` 文档。
- 更新 `docs/api/contacts.md` 中联系人详情与更新接口字段说明，确保 `remark`、`alias`、`tags` 为联系人详情唯一数据源。
- 更新 `docs/spec/client/mini-program/service-layer.md` 中与页面职责相关的描述（如需）。
- 更新后端接口实现与后端接口文档，移除 `/contacts/{conversation_id}/conversation` 路由及相关 schema/service 引用。

## 验证清单

- 进入联系人详情页可看到备注、描述、标签当前值。
- 修改备注、描述、标签后返回联系人详情页与首页，展示结果一致。
- 联系人详情页不再出现置顶聊天、消息免打扰、发送消息按钮。
- 从联系人详情页清空聊天记录后，返回聊天页不再残留旧消息。
- 从联系人详情页清空聊天记录后，返回首页不再残留旧消息摘要。
- 反复进入退出联系人详情页、聊天页、首页，消息清空状态保持一致。
- `/contacts/{conversation_id}/conversation` 在后端路由与文档中均不存在。
- 运行小程序校验命令并通过。

## 实施顺序

1. 调整文档与接口职责定义。
2. 调整联系人详情页与 Service 数据源。
3. 调整联系人本地缓存 schema 与同步逻辑。
4. 修复清空聊天记录一致性。
5. 清理悬空逻辑并完成验证。
