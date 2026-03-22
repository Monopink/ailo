# 系统配置读取收敛与优化（2026-03-21）

## 目标

在后端统一系统配置读取逻辑，满足以下约束：

- 环境变量仅由 `Settings(get_settings)` 读取
- `system_configs` 仅由 `SystemConfigService` 读取
- 禁止环境变量覆盖 `system_configs`（单一真相）
- `system_configs.default_value` 仅用于展示，不参与运行时兜底
- 核心/启动必需配置缺失：阻止启动
- 非核心配置缺失：允许明确降级（调用方显式声明 required=false）
- 禁止向后兼容、禁止补丁式默认值掩盖错误、禁止冗余读取与冗余缓存

## 已确认的讨论结论（记录）

- `media_public_base_url` 属于核心配置，缺失需阻止启动
- `LeanCloud signature ttl` 无配置需求，保持代码常量（不引入 `system_configs`）
- `ws_presence_lease_ttl_seconds` 无配置需求，保持代码常量（从 `system_configs` 删除）
- `registration_lease_ttl_days` 无配置需求，保持代码常量（从 `system_configs` 删除）
- `sms_code_length_digits` 无配置需求，保持代码常量（从 `system_configs` 删除）
- 字数限制与消息发送失败链路复杂，作为预留内容记录在单独方案文档中，不在本次任务实施
- AI 上下文配置作为预留内容记录在单独方案文档中，不在本次任务实施
- SMS 验证码相关配置接线属于独立实施，记录在单独方案文档中
- 消息传输 WebSocket 始终可用（管理端联调能力），不引入 `CHAT_CONSOLE_PROVIDER`
- 业务对外 outbound provider 由代码内部逻辑选择（当前固定为 LeanCloud）；WebSocket 不属于该选择逻辑治理范围

关联文档：

- SMS 验证码配置接线：`docs/plans/2026-03-21_sms-code-config-wiring.md`
- 字数限制与消息失败预留：`docs/plans/2026-03-21_text-length-limit_and_message-failure.md`
- AI 上下文配置预留：`docs/plans/2026-03-21_ai-context-config-reservation.md`

## 现状问题点（与目标不一致项）

### 1) 读取入口分裂（多套读取 API 并存）

- 环境变量与 `.env`：`backend/app/core/config.py`（`Settings`, `get_settings`）
- DB 缓存读取：`backend/app/services/system_config.py`（`SystemConfigService` + 模块级 cache）
- DB 直连读取：`backend/app/crud/system/config.py`（`system_configs.get_config_value`，每次按 key SELECT）
- 叠加读取层：`backend/app/services/config.py`（`ConfigService`：env-first + DB + 自身 cache）

后果：

- 同一配置 key 在不同调用方表现不一致（缓存策略、缺失处理、类型转换、默认兜底）

### 2) 双重缓存与缓存一致性缺口

- `ConfigService` 维护一层 per-key cache：`backend/app/services/config.py`
- `SystemConfigService` 维护一层全表 cache：`backend/app/services/system_config.py`
- 写入入口对 `SystemConfigService.reload_cache` 执行不一致：
  - admin 页面更新路径包含 reload：`backend/app/admin/views/system_settings_view.py`
  - 部分 admin API 更新路径不包含 reload：`backend/app/api/admin/system_management.py`

后果：

- 同一配置在不同读取路径可出现新旧值不一致

### 3) 类型转换不一致（NUMBER）

- `SystemConfigService`：NUMBER 转换为 `int`
- `system_configs.get_config_value`：NUMBER 转换为 `float`

后果：

- 业务层在不同读取 API 下得到不同类型，导致边界行为不一致

### 4) 补丁式默认兜底掩盖错误

- middleware 读取 app.state 时存在默认值兜底：`backend/app/middleware/rate_limit.py`
- 业务读取存在 `default_value=...` 兜底（运行时来源不唯一）

后果：

- 配置缺失、启动加载失败、缓存未初始化被掩盖

### 5) 悬空/未接线项（影响“单一真相”）

- 代码读取但 required data 不存在（未接线读取）：
  - `leancloud_im_app_id`（读取位置：`backend/app/api/v1/leancloud.py`）

## 实施范围（本次任务）

### A) 读取入口收敛

将后端读取入口收敛为：

- env：`backend/app/core/config.py:get_settings`
- system_configs：`backend/app/services/system_config.py:SystemConfigService`（以及 `get_config_int/get_config_str/get_config` 便捷函数）

处理项：

- 迁移所有业务调用方：禁止使用 `system_configs.get_config_value`
- 处理 `ConfigService` 的存在性：停止在业务侧使用其读取能力，并移除 env-first 行为
- 业务对外 outbound provider 不通过环境变量配置，改由代码内部逻辑选择（当前固定为 LeanCloud）

### B) 缓存一致性规则统一

统一规则：

- 所有写入 `system_configs` 的入口必须触发 `SystemConfigService.reload_cache`
- 禁止在 CRUD 层引入 service 依赖（保持分层约束）

### C) 启动必需配置 fail-fast

调整启动行为：

- `media_public_base_url` 缺失：阻止启动
- 启动阶段加载的其它核心配置缺失：阻止启动

### D) 禁止默认兜底（核心链路）

移除或禁止以下形式：

- middleware 对核心配置的 `getattr(..., default)` 兜底
- system_configs 读取缺失时的隐式默认值兜底

### E) 悬空/未接线项处置（本次任务内的范围）

- `leancloud_im_app_id`：修正为唯一来源（环境变量 `LEANCLOUD_IM_APP_ID`），并确保调用方一致

### F) 取消 ws_presence_lease_ttl_seconds 配置项

- WebSocket presence lease TTL 固定为代码常量（90 秒）
- 从 required data 与已部署数据库中删除 `ws_presence_lease_ttl_seconds`（需要数据迁移）

### G) 取消 registration_lease_ttl_days 配置项

- Registration lease TTL 固定为代码常量（365 天）
- 从 required data 与已部署数据库中删除 `registration_lease_ttl_days`（需要数据迁移）

### H) 取消 sms_code_length_digits 配置项

- SMS code length 固定为代码常量（6 位）
- 从 required data 与已部署数据库中删除 `sms_code_length_digits`（需要数据迁移）

## 任务清单（用于审查与实施）

1) 调整读取入口
   - 搜索并替换所有 `system_configs.get_config_value` 调用为 `SystemConfigService`/便捷函数
   - 停止业务侧使用 `ConfigService.get_config`（避免 env-first 与二级缓存）
   - 移除 `DEFAULT_MESSAGE_PROVIDER` 环境变量读取，改为代码内部固定 outbound provider 选择逻辑
2) 启动阶段 fail-fast
   - `media_public_base_url` 缺失直接抛出，阻止启动
   - 核心配置缺失不允许降级为默认值
3) 写入后缓存一致性
   - 定位所有更新 system_configs 的入口并统一执行 `SystemConfigService.reload_cache`
4) 悬空/未接线项处理
   - `leancloud_im_app_id` 修正
5) 删除 `ws_presence_lease_ttl_seconds`
   - 代码改为常量（90 秒）
   - init SQL 删除该 key
   - Alembic 迁移删除已部署库中的该 key
6) 删除 `registration_lease_ttl_days`
   - 代码改为常量（365 天）
   - init SQL 删除该 key
   - Alembic 迁移删除已部署库中的该 key
7) 删除 `sms_code_length_digits`
   - 代码改为常量（6 位）
   - init SQL 删除该 key
   - Alembic 迁移删除已部署库中的该 key
5) 自检
   - 静态检查：查找禁用入口与默认兜底是否仍存在

## 验收标准（可检索）

- `backend/app` 内不存在业务读取 `system_configs.get_config_value`（允许 admin UI/CRUD 展示用途另行限定）
- `backend/app` 内不存在业务读取 `ConfigService.get_config`（避免 env-first）
- `backend/app` 内不存在读取 `ws_presence_lease_ttl_seconds`（改为代码常量）
- `backend/app` 内不存在读取 `registration_lease_ttl_days`（改为代码常量）
- `backend/app` 内不存在读取 `sms_code_length_digits`（改为代码常量）
- 核心配置缺失时应用启动失败（包含 `media_public_base_url`）
- 更新 system_configs 后，服务层读取一致（`SystemConfigService` 缓存与读取一致）
- 禁止默认兜底：核心链路无 `getattr(..., default)` 形式的静默回退
- 悬空项清单减少：`leancloud_im_app_id` 不再作为 DB 读取 key 存在

## 状态

- 方案文档已更新并包含部分实施结果
