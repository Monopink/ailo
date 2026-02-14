# Task: 测试聊天重构 + WebSocket Provider + 统一日志（确定方案）

## 背景与目标

当前测试页只能单次请求，无法模拟真实连续聊天，也绕过了消息 buffer、输入事件与消息发送链路，导致：
- 对话体验不真实（无连续上下文 / followup / typing 行为）
- 测试与生产逻辑割裂（双写日志、结构不一致）
- 可观测性差（无法统一追踪一条请求）

目标：
- 让测试页完全复用生产消息管线与对话逻辑（入站/出站/离线回补/ACK）
- 将 WebSocket 作为可替换的通用消息通道（transport only），而不是 admin-test 专用能力
- 日志结构统一，单次请求只写一条日志
- `llm_request_id` 使用 `ai_request_logs.id` 以支持单次请求定位与审计

---

## 变更记录（实施期）

- 2026-02-19：实例 profile 完整性与运行时降级补充（无向后兼容）
  - 创建链路必须强制保证实例可用 profile：实例创建后若 `owner_qiao_id=instance.qiao_id` 查不到 profile，自动补建最小 profile（`owner_type=3`）。
  - 对话处理链路对 profile 缺失执行降级：`self_profile` 置空并继续处理，不因 profile 缺失阻断消息处理。
  - 降级仅限 profile；`AIInstance`/`AIStyle`/`AIPersonality` 缺失仍视为硬错误并中断。

- 2026-02-14：时间格式约定收紧
  - API 返回的 ISO8601 时间字符串（`*_at`）**必须包含时区**（推荐统一 UTC：`Z` / `+00:00`），避免跨时区歧义。
  - 消息系统对外时间戳字段统一为 Unix 毫秒整数，并统一命名为 `client_sent_time_ms`（替换旧 `client_sent_at`）。
  - 不做向后兼容：接口与协议不再接受/返回旧字段名。
  - 注：数据库仍以 `message_history.client_sent_at`（timestamptz）存储客户端上送时间；对外 API 字段为 `client_sent_time_ms`（ms epoch int）。

- 2026-02-14：补充约定（命名/WS 鉴权/稳定性/安全）
  - 命名统一的强约束仅覆盖"定义层"（DB/接口/文档/SQL init）；实现层允许使用 `conv_id`（仅当无歧义且仅指代 `conversation_id`）。
  - WebSocket 鉴权统一使用首帧 `auth.access_token`（所有客户端）；不使用/不依赖握手 Header。
  - WebSocket 稳定性：单连接发送串行化 + 有限发送队列；发送失败/超时需清理连接；多 worker/多实例需引入 Hub（例如 Redis PubSub）保证广播可达。
  - 安全：`/api/v1/auth/login` 需要请求频率限制；禁止在日志中记录 access/refresh token 的任何片段。
  - 管理端调试接口仅用于 DEBUG 环境，生产默认关闭。

- 2026-02-16：认证链路一致性与审计安全补充（无向后兼容）
  - 所有登录签发接口统一强制 `device_id`（UUID）：`/auth/login`、`/auth/wechat/login`、`/auth/wechat/bind-phone`、`/auth/phone`。
  - `login_records` 禁止保存 token 明文/片段；会话追踪改为 `user_token_id`。
  - JWT `session_id` 语义收敛为稳定会话主键，要求与 `user_tokens.id` 一致（含 refresh 场景）。

---

## 实施进度（截至 2026-02-14）

说明：
- 本节记录“实现状态”，不等同于“已验收上线”。未实际跑通的部分会标注为“待验收”。
- 本任务不要求向后兼容；旧实现按规则移动到 `deleted/`。

### 已完成（实现已落地）

- 命名统一：全链路 `conv_id` → `conversation_id`（DB/接口/文档/SQL init；代码仅修到无歧义与不报错）。
- WebSocket provider：新增 `GET /ws/messages`，支持 `auth/ping/send_message/typing`，并按 (user_id, device_id) 建 Presence endpoint（租约 TTL 配置化）。
- WS 幂等与 ACK：`send_message` 基于 `UNIQUE (conversation_id, msg_id_client)` 去重；WS 帧级 ACK 在消息落库 commit 后返回稳定 `msg_id_server`。
- WS 多端同步：落库后按 endpoint provider 路由到该用户所有活跃 endpoints；WebSocket endpoint 推送 `event:message`；typing 入站广播 `event:typing`。
- assistant 出站 WS 推送：AI 出站消息落库 commit 后，best-effort 广播 `event:message` 给 WS endpoints（用于“即时收取”）。
- 离线/ACK：复用 `GET /api/v1/messages/offline` 与 `POST /api/v1/messages/ack`（device_id 游标单调推进；新设备初始 cursor 不回补历史淹没）。
- 投递状态收敛：投递记录落在 `message_deliveries`，并满足 `UNIQUE (msg_id_server, endpoint_id)`；`message_history` 只存消息事实。
- 重试字段：本期不实现重试调度，deliveries 表不保留重试相关字段；重试设计保留在文档并标注“未实施”。
- 管理端对话控制台（Chat Console）：
  - 新增 admin 页面（入口由 admin session gate；业务鉴权走 JWT），路径 `/chat-console`。
  - 控制台支持：账号密码登录获取 JWT → 拉 contacts 取 `conversation_id` → WS 收发（含 typing）→ 离线拉取 → HTTP ACK → 调试接口拉 llm links。
- 账号密码登录：新增 `POST /api/v1/auth/login`（username/phone/email + password）供控制台获取 JWT。
  - `device_type` 必须为 int，Chat Console 作为 Web 客户端固定传 `3`（`DeviceType.WEB`）。
- 日志定位：新增 `POST /admin-api/debug/messages/llm-links`（msg_id_server[] → llm_request_id[]）。
- 清理旧链路：旧 admin 测试页与旧离线游标/失败表相关实现已按清单移动至 `deleted/` 并移除引用。

### 待验收（实现已落地，但需要你实际跑通确认）

- “控制台自由连发 + 即时收取”的端到端体验（依赖完整运行环境与可用配置/依赖）。
- “单次 LLM 请求仅写一条 ai_request_logs”在真实对话流程中的验证（需要跑通一次完整消息流并观察日志表）。

### 已知限制/环境说明

- 当前环境缺少部分运行依赖时无法进行 `import app.main` 级别的运行验证；已做全量语法编译校验（不落盘 bytecode）。

---

## 现状问题清单

1) 重复日志写入
- 同一次请求产生两条日志：test + production
- 根因：测试执行器创建 test log，同时调用 process_conversation 触发 save_ai_request_log

2) 日志结构不统一
- test 日志：response 顶层为 success/buffer_id/response/...
- production 日志：response 顶层为 schema 输出 + __llm_response

3) 测试链路绕过生产消息系统
- 测试页直接调用 conversation 逻辑，未通过消息事件/缓冲/发送链路

4) 缺乏真实对话体验
- 测试页只能 一问一答，不能自由连发与即时收取

---

## 核心设计原则

- 消息传输层可替换：业务逻辑仍在后端服务层
- 一次 LLM 请求仅写一条日志
- 测试与生产使用同一消息管线
- 测试链路与生产保持一致：不保留 `persist` 开关；前置检查与自动补齐关系仅针对虚拟测试用户（user_type=virtual）。
- 无向后兼容包袱：直接收敛到统一结构
- WebSocket / LeanCloud 都是 Provider（transport only）；Provider 必须携带业务管线所需的最小定位信息（例如 conversation_id），以接入统一消息管线
- 命名统一：全链路统一使用 `conversation_id`（替换旧的 `conv_id`，不做向后兼容）

### 命名统一决策（不向后兼容）

为彻底消除 `conv_id` / `conversation_id` 混用导致的实现错误，本任务实施中将同步修改：

- 数据库：`contacts.conv_id` → `contacts.conversation_id`（并同步所有索引/约束/引用注释）
- 接口（HTTP/WS）：统一使用 `conversation_id`
- 文档：统一使用 `conversation_id`
- SQL init 脚本：统一使用 `conversation_id`

#### 命名统一适用范围（重要）

本任务对"定义层"作强约束：数据库字段/约束、对外 HTTP/WS 接口字段、以及文档规范中，一律使用 `conversation_id`，禁止出现 `conv_id`。

对"实现层"的变量命名不作一刀切要求：在函数内部/局部变量中允许使用 `conv_id`，前提是语义明确且仅指代 `conversation_id`，不允许引入歧义或出现两者混用导致的误用风险。

---

## 最终架构

### 1) Provider/通道选择：以 Device -> Endpoint 为核心
- 系统需要面向未来“从 LeanCloud 切换到自研或其他第三方”的演进能力。
- 同一 user 可多设备登录；出站对“活跃 endpoints”广播。
- 同一 `device_id` 同时只绑定一个 provider（切换 provider 时，cursor 继续沿用 `msg_id_server`）。
- Provider 由 Router 根据 endpoints 决定。
- WebSocket 客户端仅提供 `device_id`；服务端登记 Presence endpoint 时按 (user_id, device_id) upsert `message_endpoints` 并得到 `endpoint_id`，后续内部路由/投递目标以 `endpoint_id` 为准（避免多账号复用同一 device_id 时串线）。

### 2) Endpoint 活跃判定：两类 lease + 配置化
- Presence lease（短）：用于 WebSocket 在线活跃（连接/心跳续租）。
- Registration lease（长）：用于第三方通道 installation/register 绑定。
- lease TTL 为配置项（默认值见下文“默认配置”）。

### 3) Router 合并发送
- 本任务不实现“合并发送”的额外抽象，按 endpoint 逐个投递并记录 `message_deliveries`。

### 4) ACK/幂等/投递状态
- ACK 表示“物理上已收到”（不承载已读）。
- HTTP 统一 ACK。
- 幂等判断需要：客户端幂等键 + 服务端状态集合；并通过 DB 约束保证（见下文 UNIQUE）。
- 投递状态 **全移出** `message_history`，不在 message_history 上承载投递状态。
- ACK 聚合为 ANY：客户端按 `device_id` ACK；服务端确认游标推进。
- 同意 UNIQUE：`UNIQUE (msg_id_server, endpoint_id)`。
- WS `send_message` 成功的帧级 `ack.payload` 必须返回 `msg_id_server`（可选 `sent_at_ms`），用于客户端 UI 对齐与后续 HTTP ACK 推游标；幂等重发同一 `(conversation_id, msg_id_client)` 必须返回同一个 `msg_id_server`。
- WS 帧级 `ack` 必须发生在“幂等记录已落库”之后（至少已能稳定返回同一 `msg_id_server`），避免断线重连/重发时出现 msg_id_server 漂移。
- 入站去重必须落 DB UNIQUE：统一使用 `UNIQUE (conversation_id, msg_id_client)`；要求入站 TEXT 的 `msg_id_client` 必填，typing 不落库。
- ID 口径：`msg_id_server` 是服务端为时间线消息生成的唯一标识（inbound/outbound 均有值）；`msg_id_client` 仅用于入站幂等与客户端本地对齐。

### 5) 显式记录 provider
- 出站投递记录中显式写入 provider（便于审计、排障、后续迁移与共存）。
- 入站 provider 信息保留在 `message_history`（无需拆两张表）。

### 6) Admin 测试 Web 客户端的 device_id
- 客户端必须传 `device_id`。
- 管理端测试（Web 客户端）用浏览器 `localStorage` 持久化 `device_id`（UUID v4）。
- 管理端测试逻辑中自动复用上次的 `device_id`；没有则生成并持久化。

### 7) 鉴权：JWT（真实链路测试）
- 测试逻辑尽量复用主逻辑。
- 决定实现一套简易 Web 客户端（内部测试），具备登录 + 消息收发 + 离线拉取 + ACK。
- JWT 来源：账号密码登录。
- Admin session 仅用于“能打开页面”的入口 gate；WebSocket 端点为通用消息通道能力，不绑定 admin session。

### 8) WebSocket 稳定性与扩容约束
- 连接保活：客户端按 `ws_ping_interval_seconds` 发送 ping；服务端按 ping 续租 presence lease；超时未续租需断开连接并视为离线。
- 发送串行化：单连接的发送必须串行执行（避免并发 send）；服务端应为每条连接提供有限发送队列用于 backpressure。
- 失败即清理：发送失败或发送超时应主动断开连接并清理 endpoint 绑定，避免僵尸连接占用资源与拖累广播。
- 扩容约束：WebSocket 连接态为进程内状态；当部署为多 worker/多实例时，广播必须通过统一的 Hub（例如 Redis PubSub）跨进程转发，否则不保证消息可达。

### 9) 日志统一
- `llm_request_id == ai_request_logs.id`。
- 日志写入只有一个入口：`conversation_flow` 负责创建并落库 `ai_request_logs`，避免 test + production 双写。
- `ai_request_logs.response` 存储完整 raw 响应（JSONB）。
- 任何“请求调试日志”必须受 `DEBUG` 开关保护；生产默认关闭；严禁记录 access/refresh token 及其任何片段（包括 URL query 中的敏感字段）。

---

## 管理端调试：消息定位请求日志

为避免把调试字段混入通用消息通道，管理端测试页通过 **admin session** 调用专用调试接口完成关联：

- 安全约束：该调试接口仅用于 DEBUG 环境（生产默认关闭）。

- 输入：`msg_id_server[]`
- 输出：每条消息对应的 `llm_request_id`（等于 `ai_request_logs.id`）

实现：通过 `message_history.llm_request_id` 直接关联（assistant 出站消息写入时即写入）。

---

## 账号密码登录 + JWT（为测试 Web 客户端提供真实链路）

### 登录标识
- 支持 username / phone / email 三种输入自动识别：
  - 包含 `@` → email
  - 纯数字 → phone
  - 其他 → username
- email/username 字段可为 NULL。

### username 规则
- 5~20 位
- 只能包含字母、数字、`_`、`-`
- 只能字母开头
- 禁止连续分隔符：不允许出现 `__`、`--`、`_-`、`-_`
- 支持大小写；唯一性按小写（case-insensitive unique），但保留原始大小写存储
- 禁止保留字注册：保留字配置在 `system_configs.username_reserved_words`（JSON 数组，全小写，可随时补充）

### 账号管理（当前阶段）
- 用户创建/密码重置仅通过管理后台执行（登录接口只负责校验与签发 JWT）。
- 安全约束：
  - `/api/v1/auth/login` 必须做请求频率限制（建议按 client_ip + identifier 的窗口限流 + 冷却）。
  - 禁止在日志中记录 access_token/refresh_token（包括任何前缀/片段）。
  - 登录失败提示应避免泄露账号是否存在（统一失败文案）。

---

## 数据模型

> 不考虑向后兼容。

### 1) message_devices（设备维度，承载离线 cursor）
- 主键：`id`（Snowflake）
- 字段：
  - `user_id`
  - `user_qiao_id`
  - `device_id`
  - `last_acked_msg_id`（msg_id_server）
  - `last_acked_msg_sent_at`（服务端 sent_at，取 `last_acked_msg_id` 对应消息的 sent_at）
  - `last_pull_at`
  - `last_seen_at`
  - `created_at`
  - `updated_at`

约束：`(user_id, device_id)` 唯一（同一设备可多账号复用）。

初始 cursor：新 (user_id, device_id) 首次登记时，不回补历史离线消息，cursor 从“当前时间点”开始。
实现约束：首次创建 `message_devices` 时写入 `last_acked_msg_sent_at = server_now` 且 `last_acked_msg_id = NULL`，offline 从该时间点之后的增量开始。

### 2) message_endpoints（可投递端点，承载 provider 绑定 + lease）
- 同一 (user_id, device_id) 仅一条 endpoint 记录，因此同一 user 的同一 device 同时只绑定一个 provider。
- `(provider, user_id, target_key)` 唯一（同一 provider 下允许不同 user 复用相同 target_key）。
- 字段：
  - `endpoint_id`（Snowflake，主键）
  - `user_id`
  - `user_qiao_id`
  - `device_id`
  - `provider`（enum）
  - `target_key`（provider 的可投递标识；WebSocket 为 device_id；LeanCloud 为 client_id/qiao_id）
  - `client_kind`（记录端类型：web/miniprogram/ios/android；不参与 lease 分裂）
  - `lease_expires_at`
  - `last_seen_at`
  - `created_at`
  - `updated_at`

一个 user 的出站消息会广播到该 user 的所有“活跃 endpoints”。

### 3) message_deliveries（投递记录）
- 字段：
  - `delivery_id`
  - `msg_id_server`
  - `endpoint_id`
  - `provider`（显式写入，便于审计）
  - `target_key`
  - `provider_msg_id`（第三方回执 ID；WebSocket 可为空；LeanCloud 发送成功后回填）
  - `status`（最小集合：1=pending, 2=dispatched, 3=failed）
  - `dispatched_at`（provider 投递成功时间；不等于客户端 HTTP ACK）
  - 语义约定：
    - `dispatched` 表示服务端已成功调用 provider 投递（WebSocket 场景为服务端成功写入连接）；不代表客户端已收到/已 HTTP ACK。
    - `pending` 仅用于需要异步回执/回调才能确认投递结果的 provider。
  - `failed_reason_code`
  - `failed_detail`
  - `created_at`
  - `updated_at`
- 约束：`UNIQUE (msg_id_server, endpoint_id)`

ACK 聚合（ANY）：
- 客户端按 device_id ACK 某条 `msg_id_server`。
- 服务端推进 `message_devices.last_acked_msg_*`（单调递增）；ACK 仅代表客户端已持久化确认，不回写 `message_deliveries.status`。

### 4) message_history（仅承载消息事实，不承载投递状态）
- message_history 只记录消息事实（谁在什么时间发送了什么），不记录“投递给哪些端、是否成功”等状态。
- 入站相关字段：
  - `inbound_provider`（enum，小整数存储）
  - `inbound_device_id`（WebSocket 入站时写入；LeanCloud 入站通常为空）
  - `msg_id_provider_inbound`（LeanCloud 入站必填；WebSocket 入站为空）

- 出站相关字段：
  - `llm_request_id`（可空；assistant 出站消息写入，对应 `ai_request_logs.id`，用于 `msg_id_server -> llm_request_id` 映射与审计）

### 5) ai_request_logs（统一日志写入点）
- `llm_request_id == ai_request_logs.id`
- 日志唯一写入点：`conversation_flow`

---

## 接口

### WebSocket（通用消息通道）

- 端点：`GET /ws/messages`
- 鉴权：JWT（所有客户端统一通过 WebSocket 首帧 `auth.access_token` 上送裸 JWT；不使用/不依赖握手 Header）
- 客户端标识：device_id；服务端内部路由/投递：endpoint_id（Presence 绑定 endpoint）
- 协议与消息类型：见 `docs/api/websocket-messages.md` 与 `docs/spec/message/websocket.md`
- **入站业务定位键**：统一使用 `conversation_id`（等于 `contacts.conversation_id`）；WebSocket 仅负责传输，业务层按 `conversation_id` 查找 contact/instance 并进入统一消息管线
- 多端在线同步：消息落库后，服务端应按 endpoint provider 路由到该用户所有活跃 endpoints（包含“用户自己发送消息”的回显）；其中 WebSocket endpoint 接收 `event: message`；广播范围仅限当前 user 的 endpoints；WS 推送允许重复，客户端按 `msg_id_server` 去重。

### 离线消息与 ACK（HTTP）

- 离线拉取：`GET /api/v1/messages/offline`
- ACK：`POST /api/v1/messages/ack`（统一入口，实时与离线共用）
- ACK 请求体：`{ device_id, last_ack_msg_id }`（不传 `last_ack_sent_at`；服务端以 DB 中该消息 `sent_at` 为准推进 `message_devices.last_acked_msg_*`）
- Offline 仅用于断线重连后的增量补齐，游标维度为 `(user_id, device_id)`，返回“该 device 尚未 ACK 的时间线增量（双向：user↔assistant）”；在线状态禁止依赖 offline 频繁轮询。
- Offline 消息集合仅包含聊天时间线消息（TEXT + CHAT_INFO）；NOTIFICATION 不属于聊天时间线，不在该接口返回范围内。
- 服务端必须校验离线消息所属 `conversation_id` 对当前用户可见（例如联系人关系/会话参与方校验），避免越权或串会话。
- `sent_at_ms` 为服务端认定的事件时间（用于排序与游标推进）；`client_sent_time_ms` 仅为客户端上送时间（用于展示/调试）。
- History（回看/多设备补历史）不在本任务实施范围；未来按 conversation + 时间窗/分页，并可结合付费扩展可回看范围。

### Admin Chat Console（内部联调）

- 说明文档：`docs/spec/admin/chat-console.md`
- 目标：验证“登录 → 获取/确保 contact（拿到 conversation_id）→ WS 实时收发（含 typing）→ 离线拉取 → HTTP ACK → 日志关联”的端到端链路

---

## 验收标准（实施阶段必须满足）

1) [待验收] 管理端对话控制台支持“自由连发 + 即时收取”（非单轮问答模式）
2) [已实现] 控制台链路复用生产消息管线（入站/出站/离线回补/ACK），不绕过系统
3) [待验收] 单次 LLM 请求只写一条 `ai_request_logs`（无 test+production 双写）
4) [已实现] `llm_request_id = ai_request_logs.id`，可定位单次请求日志
5) [已实现] WebSocket provider 不依赖 admin session（admin session 只 gate 页面入口），JWT 鉴权可独立复用到未来生产客户端
6) [部分实现] 投递状态不在 `message_history` 承载；目前 WebSocket 路径已通过 `message_deliveries` 管理并满足 `UNIQUE (msg_id_server, endpoint_id)`，非 WebSocket 出站链路待补齐一致落库
7) [已实现] ACK（device_id + msg_id_server）幂等、游标单调推进，新 (user_id, device_id) 初始 cursor 不会拉取历史淹没

---

## 默认配置（system_configs）

- `ws_presence_lease_ttl_seconds`: 90
- `ws_ping_interval_seconds`: 25
- `registration_lease_ttl_days`: 365

---

## 实施清理清单（旧测试链路）

本任务实施时，将以下旧测试链路相关模块移动到 `deleted/`，并移除旧消息投递/离线游标相关的遗留实现（不再保留双实现）：

- 后端管理端测试页
  - `backend/app/admin/views/ai_instance_chat_test_view.py`
  - `backend/app/admin/templates/custom_views/ai_instance_chat_test.html`
- 后端 admin testing 服务
  - `backend/app/services/admin/testing/instance_chat/`

- 旧消息投递/离线游标遗留实现（不再使用，收敛为 `message_deliveries` / `message_devices`）
  - DB：不再保留旧表。若现有数据库中仍存在旧表，直接通过 SQL 脚本重置数据库解决（本任务不额外提供 drop/migrate）。
  - 后端模型/CRUD（仅服务旧表的实现整体移动到 `deleted/`）：
    - `backend/app/models/message/offline_cursor.py`
    - `backend/app/crud/message/offline_cursor.py`
  - 后端代码（与其他功能共用的文件，仅移除旧表相关的类/引用，不移动整个文件）：
    - `backend/app/models/message/message.py`（移除 `MessageDeliveryFailure`）
    - `backend/app/admin/views/message_media_views.py`（移除/替换对旧表模型的引用）
