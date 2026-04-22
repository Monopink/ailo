# 邀请码识别与注册链路补充实施方案（2026-04-22）

## 1. 任务定位

本方案是 `79e926e` 邀请码与权益实施的补充修正，后续将 rebase 合并到同一提交语义。

本次实施按目标架构直接落地。

## 2. 固定决策

1. 注册/登录页仅在邀请码相关场景上传剪贴板文本到后端识别。
2. setup 链路中邀请码失败不允许阻塞资料提交流程。
3. 邀请链接统一采用 `https://<domain>/i/{token}` 并由后端跳转服务处理。
4. 邀请分享文案由 `invite_share_templates` 独立数据模型管理。
5. 邀请码识别日志使用明文落库并永久保留。
6. 邀请码识别规则采用“第一个独立 6 位字母数字串”，仅以数据库命中作为有效依据。
7. 邀请分享模板命名统一为 `invite_share_templates`，不使用 `command` 命名。
8. 邀请分享接口返回完整文案内容。
9. 邀请短链统一采用 `/i/{token}`。

## 3. 问题与目标

### 3.1 已确认问题

1. 剪贴板误识别会导致 setup 绑定失败并中断注册完成。
2. 邀请码识别规则分散在前端，存在多处分叉实现与 TS/JS 运行时不一致风险。
3. 后端缺少“原始文本识别 + 邀请码校验 + 事件记录”的统一入口。
4. 邀请口令模板存放在 `system_configs` JSON 字段，不利于独立管理。

### 3.2 目标态

1. 识别逻辑后端统一，前端只提交原始文本或链接邀请码。
2. setup 资料提交与邀请码绑定彻底解耦，邀请码永不阻断注册完成。
3. 邀请码识别、校验、open 记录与识别日志形成单链路闭环。
4. 邀请分享模板由独立表管理，`/invitations/share` 读取模板表。

## 4. 目标实现

### 4.1 后端接口

新增统一识别接口：

1. `POST /api/v1/public/invitations/intake`（未登录）
2. `POST /api/v1/invitations/intake`（已登录）

输入字段：

- `source`：`login | setup | link | invite_bind_page | invite_share_page`
- `trigger`：调用触发来源标记（如 `clipboard`、`link_param`、`manual_input`）
- `raw_text`：剪贴板原文（可空）
- `invite_code`：链接或手输邀请码（可空）

输出字段：

- `recognized_code`
- `valid`
- `bindable`（仅登录态接口返回）

行为约束：

1. 识别仅提取第一个独立 6 位字母数字串（统一大写后校验）。
2. 仅当数据库存在 active 邀请码时认定 `valid=true`。
3. 对于有效邀请码写入 `open` 事件；无效邀请码不写 `open`。
4. 每次 intake 都写入识别日志（明文）。

### 4.2 数据模型

新增表：

1. `invite_recognition_logs`
   - `actor_user_id`（可空）
   - `source`
   - `trigger`
   - `raw_text`
   - `first_candidate`
   - `recognized_code`
   - `invite_code_id`
   - `valid`
   - `bindable`
   - `created_at`
2. `invite_share_templates`
   - `template_text`（可包含 `{{code}}`、`{{link}}` 或纯文本）
   - `status`
   - `priority`
   - `locale`
   - `created_at`
   - `updated_at`

邀请码文案读取来源为 `invite_share_templates`。

### 4.3 前端流程

1. login/setup/invite-bind 改为调用 intake 接口获取可用邀请码。
2. 前端基于后端接口返回结果判定邀请码有效性与候选码。
3. setup 提交流程改为先提交资料，再尝试绑定邀请码；绑定失败只提示，不中断成功提交。
4. 清理邀请码链路 TS/JS 分叉，确保运行时代码与 TS 逻辑一致。

## 5. 迁移策略

数据库变更继续保持“单次干净落地”：

1. 直接合并到既有迁移 `backend/alembic/versions/20260412_00_add_invitations_and_entitlements.py`。
2. 不新增额外迁移，统一在既有迁移内完成定义。
3. 模型定义与迁移定义保持一致。

## 6. 文档同步范围

1. `docs/api/invitations.md`：补充 intake 接口，更新 share 来源与 setup 行为。
2. `docs/spec/client/base/profile-setup.md`：更新邀请码识别与非阻断提交行为。
3. 方案执行结果回填本计划文档“实施结果”。

## 7. 实施顺序

1. 后端模型/CRUD/schema/API 改造（含 intake 与分享模板表、`/invitations/share`）。
2. 小程序 login/setup/invite-bind 服务与页面改造。
3. 合并更新迁移文件（保持单迁移）。
4. 增加 `/i/{token}` 跳转入口与 Nginx 路由。
5. 同步更新 API 与 spec 文档。
6. 执行验证并修复问题。

## 8. 验收标准

1. 剪贴板 `gpedit.msc` 不会阻塞注册，且不会写入有效邀请码预填。
2. setup 中无效邀请码不会阻止资料提交成功。
3. intake 接口能返回识别结果并写入识别日志。
4. `/invitations/share` 从模板表返回文案，模板支持 `{{code}}`、`{{link}}` 或纯文本。
5. `/i/{token}` 可完成邀请码短链跳转。
6. 邀请码链路 TS/JS 同步检查通过。

## 9. 实施结果

1. 已新增后端 intake 接口：
   - `POST /api/v1/public/invitations/intake`
   - `POST /api/v1/invitations/intake`
2. 已新增识别服务与数据落库：
   - `invite_recognition_logs`（明文原文、候选、识别结果、有效性）
   - 有效识别时同步写入 `invite_events.open`
3. 已新增邀请码文案模板表：
   - `invite_share_templates`
   - `GET /api/v1/invitations/share` 读取模板表并返回完整文案内容
4. 已完成小程序链路改造：
   - login/setup/invite-bind 改为调用 intake
   - setup 改为“资料提交成功优先，邀请码失败不阻断”
5. 已将新增表与种子并入既有迁移 `20260412_00_add_invitations_and_entitlements.py`，保持单次干净落地。
6. 已新增邀请短链跳转入口：
   - `GET /i/{token}`（后端校验 token 后跳转到小程序 URL Link）
7. 已同步更新 `docs/api/invitations.md` 与 `docs/spec/client/base/profile-setup.md`。
8. 验证结果：
   - 后端：`ruff check`、`mypy` 通过
   - 前端：`npm run build`、`npm run verify:runtime-js-sync`、`npm run check` 通过
