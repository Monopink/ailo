# 小程序运行态分流与观测重构方案

生效日期：2026-05-01

## 目标

- 启动分流与账号标记采用长期有效策略，不使用审核期与截止时间。
- 小程序启动链路在在线/离线场景下按运行态特征稳定分流。
- 登录链路按运行态特征持续判定并升级账号分段，能力控制保持一致。
- 客户端观测上报从“连通性诊断”重构为“运行态环境与行为观测”。
- 文档、配置、接口、前端语义完成全链路清理，运行规则单一且可恢复。

## 范围

- 后端：运行态分流判定、登录判定、账号分段升级、客户端接口、观测数据模型。
- 小程序：启动判定、离线兜底、页面路由、Preview 访问守卫、埋点语义。
- 数据：新建运行态观测表，邀请识别日志增加判定快照关联字段。
- 文档：`docs/api/*`、`docs/spec/*`、本方案文档。

## 强制决策

### 1. 判定策略

- 一级命中词：`Tencent Security Team`。
- 二级组合特征：`XWEB`、`WindowsWechat/WMPF`、`MiniProgramEnv/Windows`。
- 判定流程：先执行一级命中词；未命中时执行二级组合。
- 前后端判定依据不完全一致是设计决策：
  - 后端保留一级命中词 + 二级组合，作为 `review_scope` 判定真值来源。
  - 前端仅使用二级组合特征，避免在客户端代码中出现一级命中词。
- 后端判定真值使用 `review_scope`（`0=non_review`、`1=mp_weixin_review`）。
- API 与前端替代字段使用 `segment_type`（`0=standard`、`1=limited`）。
- 小程序内命中特征键名与二级特征一致：`xweb`、`windows_wechat_runtime`、`mini_program_windows`。

### 2. 启动路由策略

- 小程序先在本地执行 UA 判定，得到 `segment_type_local`（`0=standard`、`1=limited`）。
- 小程序维护统一运行态状态 `runtime_segment_state`：`segment_type`、`state_source`、`state_level`、`issued_at_ms`、`expires_at_ms`。
- 在线：
  - 以本地判定为主进行分流：`segment_type_local=1` -> `square-demo`；`segment_type_local=0` -> `login`。
  - 当本地 UA 判定失败时，调用后端专用判定接口，使用接口返回 `segment_type` 分流。
- 离线：
  - 当本地 UA 判定失败时，按“构建时间 + 36 小时”执行兜底：未超时进入 `preview`，超时进入 `login`。
  - 当服务端判定不可用时，不允许停留在启动页；按“最近可用状态优先，否则 `login`”路由。
  - `runtime_segment_state` 维持离线前的最近状态。
- 网络恢复：
  - 若当前页面在 `preview-*`，统一 `reLaunch` 到 `boot`，重新执行启动判定。

### 3. 账号分段策略

- 注册与登录均执行运行态判定。
- 判定为 `review_scope=1` 的账号写入 `users.review_scope=1`。
- `review_scope` 仅允许 `0 -> 1` 单向升级，不回退。
- 前端能力判断（如邀请入口）仅使用后端返回的 `account_segment`，不在客户端执行本地粘性升级。

### 4. Preview 访问守卫

- `preview-*` 页面统一接入访问守卫。
- `runtime_segment_state.state_level=confirmed` 且 `segment_type=1` 时放通全部 `preview-*` 页面。
- 账号分段 `account_segment=1` 时同样放通全部 `preview-*` 页面。
- 其他情况误入时统一跳转 `boot`，并写入 `source=preview_guard`。

### 5. 观测数据重构

- 废弃 `client_connectivity_events` 方案。
- 新建 `client_runtime_observations` 承载环境与行为观测。
- 审核员操作期间持续采集。
- `client_runtime_observations` 通过 `event_payload` 采集剪贴板内容与操作行为，用于交叉分析。
- `invite_intake_logs` 仅增加判定快照关联字段，不承载主判定。
- 事件命名保持原样：`preflight_probe_result`、`runtime_session_tick` 不做语义改名。
- `runtime_session_tick` 每 30 秒采集一次；离线时写入本地队列，网络恢复后按原始 `occurred_at_ms` 补发。

## 数据模型

### `client_runtime_observations`

- 主键与基础：`id`、`created_at`、`occurred_at_ms`、`client_type`、`device_id`、`session_id`。
- 环境快照：`user_agent`、`platform`、`os_version`、`app_version`、`network_type`、`build_id`、`build_time`。
- 判定快照：`scope_snapshot`、`feature_hits`（JSON 数组）、`ua_fetch_status`。
- 行为快照：`event_name`、`page_path`、`entry_source`、`event_payload`（JSON）。
- 关联字段：`request_id`、`user_id`（可空，仅服务端按鉴权态写入）。

### `invite_intake_logs` 增量字段

- `reviewer_flag_snapshot`（tinyint）
- `runtime_observation_id`（bigint，可空）
- `client_user_agent`（varchar）

## 安全与治理约束

- `runtime-observations` 接口允许匿名调用。
- `runtime-observations` 请求体不接收 `user_id`。
- 匿名请求写入 `user_id=null`；携带有效鉴权时由服务端解析并写入 `user_id`。
- 仅接收 `client_type=mp_weixin` 且 `event_name` 命中白名单的事件。
- `event_payload.clipboard_raw_text` 单条最大 2048 字符，超长截断后入库。
- 2 秒去重窗口：`device_id + event_name + page_path + entry_source + event_payload_digest`。
- `runtime_session_tick` 使用独立去重策略（30 秒时间桶），避免会话内周期采样被日级去重压缩。
- 分层限频：`ip + device_id + session_id` 同时执行秒级与日级配额。
- 入库前执行文本清洗（控制字符过滤、UTF-8 规范化）。
- 运行态观测数据按短周期保留并定时清理。

## 接口调整

- 保留：`GET /api/v1/client/health`（仅返回基础健康信息与服务端时间）。
- 新增：`POST /api/v1/client/preflight-probe`（前端 UA 失败时服务端判定）。
- 新增：`POST /api/v1/client/runtime-observations`（运行态观测上报）。
- 移除：`POST /api/v1/client/connectivity-events`。

## 清理清单

- 后端配置：移除 `review_mode_mp_weixin_enabled`、`review_mode_mp_weixin_ends_at`、`review_mode_mp_weixin_auto_disable_enabled`。
- 后端逻辑：移除审核期判断、自动关闭逻辑、旧连通性去重语义。
- 前端语义：移除 `access_gate_open`、`access_gate_ends_at`、`startup_local_policy`、`startup_server_policy` 旧映射。
- 页面守卫：所有 `preview-*` 页面接入统一守卫。
- 文档：移除审核期与旧连通性语义描述。
- 状态冗余：移除 `client-access-mode` 存储与调用链路。

## 已确认的分叉设计

- 游客链路分叉属于有意架构：
  - 在线受限分段（未登录）进入 `square-demo`。
  - 离线受限分段（未登录）进入 `preview-*`。
- 该分叉用于区分在线可交互浏览与离线演示浏览，不属于并行竞品实现。

## 实施任务

1. 数据库迁移：新建 `client_runtime_observations`，扩展 `invite_intake_logs`，下线旧连通性表写入。
2. 后端接口：实现 `preflight-probe` 与 `runtime-observations`，重写 `health` 输出字段。
3. 后端登录链路：注册与登录统一执行判定并单向升级 `review_scope`。
4. 小程序启动链路：接入 UA 判定、本地分流、服务端兜底与离线 36 小时兜底。
5. 小程序页面守卫：统一 `preview-*` 访问守卫与误入回跳。
6. 邀请识别链路：写入判定快照关联字段，不改变 intake 主流程。
7. 文档与后台：同步接口、规范与管理后台配置展示。

## 验收标准

- 系统不包含 `review_mode_*` 配置与审核期相关运行逻辑。
- 在线/离线启动分流符合规则矩阵；UA 失败路径符合兜底策略。
- 登录后账号分段按单向升级生效，能力控制与分段一致。
- 普通用户无法访问 `preview-*` 页面，误入均回跳 `boot`。
- 运行态观测可持续写入，邀请识别日志具备判定快照关联。
- 文档中不保留旧审核期与旧连通性语义。

## 实施状态

- 状态：实施中
- 最后更新：2026-05-01
