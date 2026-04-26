# 邀请分享运营配置收敛与 Operation 领域清理方案

## 目标

- 移除邀请分享链路中的 `operation_assets`、`operation_slot_configs`、`invite_share_templates` 三表依赖。
- 邀请分享链路改为“固定路径 + system_configs 运营配置”实现，并拆分口令与分享卡片接口职责。
- `system_configs` 增加配置域能力，区分 `system`、`security`、`operation`。
- `system_configs.config_value/default_value` 升级为 `JSONB`。
- `system_configs` 采用 `value_type + config_shape` 描述值类型与值形态。
- 口令文案与分享卡片标题支持多文案随机选择。

## 已确认决策

- 分享页路径固定为 `/pages/boot/boot?inviteCode={{code}}`。
- 邀请分享接口拆分为：
  - `GET /api/v1/invitations/share-command`
  - `GET /api/v1/invitations/share-card`
- 删除 `operation_publish_logs`、`operation_assets`、`operation_slot_configs`。
- 分享文案迁移到 `system_configs` 运营配置，使用 `string[]` 存储。
- 分享卡片图使用固定资源 URL，不保留独立运营素材表。
- 管理后台保留 `SystemConfigView` 全量入口。
- 管理后台新增按 `config_scope` 的系统/运营分域设置页。
- `default_value` 在 `config_shape=ARRAY` 时为标量参考值，可为空字符串。
- 迁移链路收敛为单迁移：`20260426_00_refactor_operation_material_schema.py`。

## 现状

- 邀请分享接口通过 `system_configs` 读取运营配置。
- `system_configs` 模型字段为 `value_type`、`config_shape`、`config_scope`。
- 管理后台按配置域动态展示配置项。

## 实施范围

本次实施覆盖：

- 数据库迁移（单迁移 `20260426_00`）。
- 后端模型、枚举、CRUD、服务、API schema、Admin 视图。
- 邀请分享链路（文案、路径、图片来源）收敛。
- 文档同步（API/spec/plans）。

本次实施不覆盖：

- 新增运营活动编排系统。
- 非邀请分享链路的业务规则调整。

## 数据模型与迁移方案

### 1) 迁移文件策略

- `backend/alembic/versions/20260426_00_refactor_operation_material_schema.py` 作为唯一迁移入口，包含：
  - `system_configs` 值列转为 `JSONB`
  - `config_scope` 新增与归类
  - 邀请分享数据迁移
  - 冗余表删除
  - `config_type -> value_type`
  - `config_shape` 增加与数据回填

### 2) `system_configs` 结构定义

- `value_type`：`1=STRING`、`2=NUMBER`、`3=BOOLEAN`、`4=JSON`、`5=ENUM`
- `config_shape`：`1=SINGLE`、`2=ARRAY`
- `config_scope`：`system`、`security`、`operation`
- `ARRAY` 场景约束：
  - `config_value` 必须为非空数组
  - `default_value` 必须为标量（字符串/数字/布尔/null），可为空字符串

### 3) 历史配置归类规则

- `operation`：
  - `operation_invite_share_command_texts`
  - `operation_invite_share_card_titles`
  - `default_nickname_prefix`
  - `group_name=contacts` 全部分组项
- `security`：
  - `leancloud_im_webhook_token`
  - `admin_auth_whitelist`
  - `sms_whitelist`
- 其余配置归类为 `system`

### 4) 三表数据迁移到配置中心

- 文案迁移：
  - 从 `invite_share_templates` 抽取 `status=1` 文案，写入 `operation_invite_share_command_texts`（`string[]`）
- 卡片标题迁移：
  - 从 `operation_slot_configs` 抽取 `invite_share_card` 标题，写入 `operation_invite_share_card_titles`（`string[]`）
- 分享图策略：
  - 固定为 `media_public_base_url + /share/invite-share-card.webp`
- 迁移过程中清理历史配置键：
  - `operation_invite_share_command_text`
  - `operation_invite_share_card_title`
  - `operation_invite_share_card_image_url`
  - `operation_invite_share_text`

### 5) 删除冗余表

- `operation_slot_configs`
- `operation_assets`
- `operation_publish_logs`
- `invite_share_templates`

## 后端链路改造

### 1) 邀请分享 API

- `GET /api/v1/invitations/share-command`
  - 读取 `operation_invite_share_command_texts`（`string[]`）随机选一条
  - 执行 `{{code}}`、`{{link}}` 替换
  - 返回 `code`、`text`、`link`
- `GET /api/v1/invitations/share-card`
  - 读取 `operation_invite_share_card_titles`（`string[]`）随机选一条
  - 返回 `title`、`path`、`image_url`
  - `path` 固定 `/pages/boot/boot?inviteCode={{code}}`
  - `image_url` 固定 `media_public_base_url + /share/invite-share-card.webp`

### 2) 类型与校验

- 引入 `ConfigValueType`、`ConfigShape`、`SystemConfigScope`。
- 配置保存按 `value_type/config_shape` 执行结构校验。
- 运营配置页按 `config_scope=operation` 动态展示，不使用配置键白名单。
- `avatar_allowed_formats` 采用 `config_shape=ARRAY`（string[]），`default_value` 为单项字符串（用于后台行级填充）。

### 3) Operation 领域清理

- 删除 operation 对应模型、枚举、CRUD、Admin 入口。

## Admin 改造

- 系统配置页：仅 `system + security`
- 运营配置页：仅 `operation`
- 两个页面均按 `group_name` 动态分组
- 数组配置提供表格化编辑（增删行、默认填充、复制当前）

## 文档同步

- 更新 `docs/api/invitations.md`
- 更新 `docs/spec/admin-panel/system-settings.md`
- 更新 `docs/spec/system-configs/*`

## 实施步骤

1. 重写 `20260426_00` 为唯一迁移。
2. 将 `20260426_01/02/03` 移动到 `deleted/`。
3. 对齐后端模型与服务到 `value_type/config_shape/config_scope`。
4. 对齐管理后台分域展示与数组编辑。
5. 执行迁移与后端校验。
6. 同步 API/spec/plans 文档。

## 验收标准

- 邀请分享链路仅依赖 `system_configs`。
- `operation_*` 与 `invite_share_templates` 表不存在。
- `system_configs` 字段为：`config_value`、`default_value`（JSONB）+ `value_type` + `config_shape` + `config_scope`。
- 邀请接口为 `share-command` 与 `share-card` 两个独立端点。
- 运营配置页按 `config_scope=operation` 动态展示。
- `ARRAY` 配置支持非空数组值，`default_value` 为标量参考值。
- 本地迁移与后端校验通过。
