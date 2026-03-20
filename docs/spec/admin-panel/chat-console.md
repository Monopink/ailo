# 管理端对话控制台（Chat Console）

管理端 Chat Console 是内部联调用的 Web 客户端，用于端到端验证消息系统链路（HTTP + WebSocket）。

---

## 信息架构原则

- 采用卡片化信息架构，按“聊天主路径优先”组织信息
- 主工作区固定为四列（从左到右）：
  1. `Session & Account` / `Logs`
  2. `Active Account` / `Chats`
  3. 聊天主卡片
  4. `Peer Profile` / `Instance Snapshot`
- 第二行调试区固定为 `LLM Diagnostics : Tools = 2 : 1`
- `LLM Diagnostics` 顶部采用两行布局：第一行展示当前定位状态（msg_id_server / llm_request_id / 状态），第二行放置手动 `llm_request_id` 查询入口
- 调试能力与聊天能力分层展示：高频聊天信息在首屏，低频操作收敛到 `Tools`
- 同一字段在同一页面仅展示一次，避免跨卡片重复渲染

---

## 信息去重与展示基线

### 账号信息

- 必须展示：`avatar_url(图片)`、`nickname`、`username`、`identifier`、`device_id`
- 可选展示：`qiao_id`、`bio`、`region/gender`（如展示，必须避免与其他卡片重复）

### 对方/联系人信息

- 必须展示：`avatar_url(图片)`、`contact_qiao_id`、`contact_username`、`alias`、`remark`、`is_pinned/is_muted/is_blocked`
- 可选展示：`conversation_id`、`profile.bio/region/gender`
- 去重规则：`conversation_id`、`qiao_id`、`username` 不得在多个区块重复渲染

数据来源：

- 列表：`GET /api/v1/contacts?limit=100`
- 详情：`GET /api/v1/contacts/{conversation_id}`
- `contact_username` 统一来源于 snapshot.contact_username（服务端通过 persona.username 计算）；手动实例（persona_id=NULL）允许为空

---

## 消息可观测性基线

每条消息气泡必须展示：

- `msg_id_server`（双向都展示）
- `msg_id_client`（仅发送气泡展示）
- `llm_request_id`（仅接收气泡展示，类型为 `string`）
- `sent_time_ms`（双向都展示）
- `client_sent_time_ms`（仅发送气泡展示）

LLM 解析与诊断：

- 自动关联接口：`POST /admin-api/debug/messages/llm-links`（按 `msg_id_server[]` 批量映射 `llm_request_id`）
- 自动解析数据源：最新入站消息的 `llm_request_id`（优先使用消息自带值；缺失时使用 llm-links 映射结果）
- 入站消息缺失 `llm_request_id`（含映射结果为空）：界面显示缺失状态
- 手工查询输入：`llm_request_id`
- 手工查询接口：`POST /admin-api/debug/messages/llm-request-detail`
- 手工查询展示：展示该 `llm_request_id` 的请求与响应详情
- `Request Payload` / `Raw Response` 面板展示完整内容

---

## Instance Snapshot（调试聚合接口）

Chat Console 使用单一聚合调试接口：

- `POST /admin-api/debug/instances/snapshot`

用途：

- 以会话为入口，展示实例关键上下文，避免前端拼接多个后端接口

展示字段最小集合：

- instance：`instance_id`、`instance_qiao_id`、`user_qiao_id`、`conversation_id`
- identity：`contact_username`（来自 persona.username；手动实例为 `null`）
- profile：`nickname/avatar_url/bio/region/gender`
- style：`id/display_name`
- personality：`id/display_name`
- relationship：`display_name/prompt_fragment`（若存在）
- memory：memory 摘要条目

刷新策略：

- 会话切换后自动刷新
- 当前会话收到新消息后自动刷新（需 debounce，避免频繁请求）
- 保留手工 `Refresh` 按钮作为补充

约束：

- 仅管理端 debug 展示
- 必须 `admin session` 鉴权

---

## 本地持久化与 ACK 语义

消息本地持久化采用 IndexedDB，分区键：

- `account_id + conversation_id`

保留策略：

- 每会话消息上限（默认 400 条，超限淘汰最旧）
- TTL（默认 7 天）
- 支持手工清空当前账号本地消息

账号会话保险库约束：

- 安全上下文下，账号会话（含 token）使用加密 `localStorage`
- `localhost` / 私网 IP 的非安全上下文下，账号会话（含 token）使用明文 `localStorage`
- 其他非安全上下文下，账号会话只保存在当前页面内存，不做本地持久化
- `device_id` 继续按客户端规范稳定复用

启动顺序：

1. 读取本地消息并渲染
2. 执行离线补齐
3. 自动 ACK 推进

ACK 语义约束：

- 仅当消息成功写入本地存储后，才允许纳入自动 ACK 候选
- 离线补齐结束前，需等待本地写入队列 drain 后再 flush ACK
- IndexedDB 不可用时进入 `DEGRADED`，关闭自动 ACK
- `Manual HTTP ACK` 保留，但必须放入与 `LLM Diagnostics` 并列的独立 `Tools` 卡片

---

## Typing 语义

- typing 提示显示在聊天标题区（非输入框下方）
- 聊天区只展示**对方** typing
- 自己 typing 仅写入日志，不进入聊天提示
- 收到对方 `typing_start` 后最多展示 30 秒；收到对方 TEXT 或 `typing_end` 立即隐藏
- 本端发送消息时立即隐藏 typing 提示
- 判定必须同时满足：
  - 当前会话一致（`conversation_id`）
  - `from_qiao_id/to_qiao_id` 与当前“自己/对方”身份严格匹配
- typing 发送规则（含 1 秒 buffer）统一遵循 `docs/spec/message/typing.md`

---

## 状态机与降级

- `UNAUTH`：未登录
- `AUTHING`：登录中
- `BOOTSTRAPPING`：登录后自动启动序列
- `READY`：WS 已认证，可发送
- `RECONNECTING`：断线自动重连中
- `DEGRADED`：局部能力失败但聊天主路径可继续

降级要求：

- Debug 接口不可用（如鉴权失败/网络异常）时：标记 unavailable，不阻断聊天
- 本地存储不可用时：禁用自动 ACK，并给出明确状态提示
- 状态展示去重：`Stage` 与状态文案语义相同（如 `READY` / `Ready.`）时仅保留 `Stage`

---

## 响应式策略

- 桌面端：保持四列主工作区 + 第二行调试区（2:1）
- 中屏：首行优先保留 `Chats`（左）+ 聊天主卡（右），其余卡片下移
- 小屏：允许仅保留聊天主栏（资料/debug 的独立页面改造不作为本任务目标）
