# Task: Chat Console 修复

## 任务日期

- 2026-02-19
- 2026-02-19（评审补充：按拍板结论重写为实施基准）

---

## 任务定位

- 当前任务
- 不做向后兼容分支
- 以联调效率、可观测性、排障效率为核心目标

---

## 拍板结论（已确认）

1. 本任务仅做 Chat Console 修复，`Square/添加好友` 拆分为独立任务
2. 增加本地消息持久化（IndexedDB），并配套容量/TTL/清理策略
3. `instance snapshot` 采用**单一聚合 debug API**，不走前端拼接多接口
4. `LLM Links` 改为自动批量查询 + 缓存，手工输入仅保留兜底
5. typing 语义收敛：聊天区仅展示对方 typing，自身 typing 仅进日志区
6. 文档同步改为**强制**：必须同步 `docs/spec/admin/chat-console.md` 与 `docs/api/*`

---

## 旧实现复用审查结论（已确认）

### 结论

- 旧 `ai_instance_chat_test` 页面相关运行时代码已清理，不存在可直接复用的旧 API。
- 但存在可复用的底层能力，应直接复用，避免重复实现。

### 可复用能力（必须复用）

- 实例运行上下文查询：`get_instance_context`
- 记忆 prompt 聚合：`build_memory_prompt`
- 管理端高级编辑页已有的实例 summary / memory 查询与组装逻辑

### 无价值遗留（实施期清理）

- 清理无引用的旧测试 TypedDict：`AIInstanceTestContext`、`AIInstanceTestResponse`
- 仅允许“删除符号/代码块”式清理；如涉及文件移除，必须按规则移动到 `deleted/`

---

## 背景与问题清单

1. 自己/对方资料展示不完整（bio、region 等）
2. 联系人详情展示不完整（remark、is_pinned、is_muted、is_blocked）
3. 消息可观测性不足（未直接展示 msg_id、llm_request_id 关联成本高）
4. 消息未持久化，刷新后时间线丢失
5. 缺少可直接展示的 instance 快照（memory/style/personality/relationship）
6. 对方 typing 与自身 typing 语义混杂
7. 界面信息密度和层级仍可优化（新增能力后需保持秩序和可读性）

---

## 目标

1. 完整展示自己与对方资料
2. 完整展示联系人详情信息
3. 建立消息级可观测性（msg_id / llm_request_id 自动关联）
4. 增加本地持久化并与 ACK 语义一致
5. 新增 instance 快照调试视图（admin + DEBUG）
6. typing 展示语义严格分离
7. 在能力扩展后保持界面结构清晰、秩序良好、美观可读

---

## 范围

### In Scope

- `backend/app/admin/templates/custom_views/chat_console.html`
- `backend/app/admin/static/js/chat-console.js`
- `backend/app/admin/static/css/chat-console.css`
- Chat Console 所需 admin debug API（仅 DEBUG）
- 强制文档同步：
  - `docs/spec/admin/chat-console.md`
  - `docs/api/*`（新增/变更的 admin debug 接口）

### Out of Scope

- Square / 添加好友测试入口（独立任务）
- 消息协议字段变更
- 小程序端改造

---

## 关键设计约束（实施必须遵守）

1. 不引入向后兼容分支
2. 不修改现有 WS/Offline/ACK 协议语义
3. debug 能力必须 `admin session + DEBUG` 双重门控
4. 调试接口及日志禁止暴露 token/敏感字段
5. 本地 ACK 必须建立在“消息已成功写入本地存储”之后

---

## 接口与数据基线

### A. LLM Links（已有接口，改为自动化使用）

- 接口：`POST /admin-api/debug/messages/llm-links`
- 用途：`msg_id_server[] -> llm_request_id`
- 前端策略：
  - 自动按当前会话消息批量查询（分批 + 去重 + debounce）
  - 查询结果本地缓存（会话级）
  - 手工输入查询保留为兜底
- 降级：若接口不可用（例如非 DEBUG 返回 404），自动关闭该模块并提示“当前环境不可用”

### B. Instance Snapshot（新增聚合 debug API）

- 新增接口：`POST /admin-api/debug/instances/snapshot`（命名可在实施时微调，但必须保持聚合语义）
- 建议入参：`conversation_id`（首选）或 `instance_qiao_id`（二选一，必须明确校验）
- 返回摘要字段（最小可用集合）：
  - instance 基础信息：`instance_id`、`instance_qiao_id`
  - profile：`nickname/avatar_url/bio/region/gender`
  - style：`id/display_name`
  - personality：`id/display_name`
  - relationship：`id/display_name/prompt_fragment`
  - memory 摘要：`memory_prompt` + 最近核心 memory 条目摘要（数量受限）
- 约束：仅调试展示，严格脱敏，不返回无关内部字段

---

## 前端实施基线

1. 自己资料：登录后除 token 逻辑外，额外拉取并展示完整 profile
2. 对方资料：会话切换后补拉 contact detail，展示 remark + flags + profile 细项
3. 消息气泡元信息（按方向裁剪）：
   - 发送气泡展示：`msg_id_server`、`msg_id_client`、`sent_at_ms/client_sent_time_ms`
   - 接收气泡展示：`msg_id_server`、`llm_request_id`、`sent_at_ms`
4. LLM links 自动关联：会话级自动拉取并写入消息元信息区域
5. 手工兜底排障：支持 `msg_id_server -> llm_request_id -> 请求/响应详情(解析)` 的一键链路
6. typing 语义：
   - 对方 typing 显示在聊天标题区（不显示在输入框下方）
   - 自身 typing 不进聊天区，仅记录日志
   - 必须基于 `from_qiao_id/to_qiao_id` 与当前会话严格判定

---

## 本地持久化实施基线（IndexedDB）

1. 分区键：`account_id + conversation_id`
2. 启动顺序：先读本地 -> 再离线补齐 -> 再触发自动 ACK
3. 保留策略（默认）：
   - 会话最大消息条数上限（超限淘汰最旧）
   - TTL（超期清理）
   - 支持手工“一键清空本地消息”
4. 账号隔离：切换账号严格隔离，不得串会话
5. 降级策略：IndexedDB 不可用时进入 `DEGRADED`，关闭自动 ACK 并给出提示

---

## UI/交互优化基线

1. 调整为三栏主布局 + 右栏双子列：
   - 左栏合并“自己资料 + 会话列表”
   - 聊天主区保持中栏
   - 右栏固定两列并排（资料/快照 与 debug/log）
2. 登录改为弹窗（Modal），Switch Account 增加「Add Account」按钮唤起弹窗
3. 调试信息与聊天信息分层显示，避免干扰主聊天阅读
4. 消息元信息可读且不喧宾夺主（弱视觉层级）
5. 响应式下保持主路径优先，不因 Debug 模块阻断聊天

---

## 验收标准

1. 自己/对方资料、联系人详情完整可见（含 bio/region/remark/flags）
2. 每条消息可直接查看 `msg_id_server`，并可自动关联 `llm_request_id`
3. 刷新后可恢复最近会话时间线；切账号不串数据
4. 对方 typing 展示在标题区；自身 typing 仅进入日志区
5. instance snapshot 可稳定展示 style/personality/relationship/memory 摘要
6. IndexedDB 与 ACK 语义一致：未落盘不 ACK，落盘后 ACK
7. 不引入向后兼容分支，不破坏既有 WS/Offline/ACK 语义
8. 文档已同步更新（spec + api）

---

## 验证清单（实施完成后必须执行）

1. 登录 -> 自动启动序列 -> READY
2. 会话切换 -> 资料区与联系人详情正确刷新
3. 连续发消息 + 实时收取 + 自动 llm links 关联
4. 刷新页面 -> 本地时间线恢复 -> 离线补齐无重复
5. 断线重连 -> 自动补齐 -> ACK 正常推进
6. typing：自己输入不污染聊天区；对方 typing 可见且可自动消失
7. DEBUG 关闭场景：debug API 不可用时前端可降级、不崩溃

---

## 实施前置

- 本文档为已拍板的实施基准文档
- 后续代码实施严格以本文档为准
