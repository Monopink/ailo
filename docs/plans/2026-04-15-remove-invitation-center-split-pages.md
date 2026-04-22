# 去除邀请中心并拆分邀请码流程（实施计划）

## 背景

当前系统将“填写邀请码”和“邀请分享”放在同一个“邀请中心”页面，导致页面语义与事件口径混杂。现要求移除“邀请中心”概念，将其拆分为两个独立页面与操作流，并同步后端 source 语义、事件定义、接口文档与数据库 schema 产物。

## 目标

- 不再使用“邀请中心 / invite_center”概念。
- 前端拆分为两个独立页面：
  - 邀请码填写页（仅 resolve/bind）
  - 邀请分享页（仅我的邀请码、复制口令、微信分享）
- 后端 source 改为白名单，不接受 `invite_center`。
- 邀请事件维持 `open` 语义（event_type=1），口径定义为“邀请码识别事件”。
- 文档、迁移、`01_schema.sql`、`docs/data-dict/*` 与实现一致。

## 范围

### 包含

- 前端页面与路由拆分、Profile 入口调整、相关 service 调整。
- 后端邀请 schema / API source 校验与事件映射调整。
- 邀请相关 API/spec 文档同步。
- 邀请事件语义变更所需模型注释、Alembic 迁移与 schema/data-dict 产物同步。

### 不包含

- 邀请码核心绑定规则变更。
- entitlement 计算策略变更。

## 实施步骤

1. 创建并锁定本计划文档。
2. 后端调整：
   - `InvitationEventType`：固定 `open`，不引入 `page_view`。
   - source 白名单：`setup`、`link`、`invite_bind_page`、`invite_share_page`。
   - API 映射与参数说明同步。
3. 前端调整：
   - 新增 `invite-bind`、`invite-share` 页面与对应 service。
   - Profile 将“邀请中心”入口替换为两个独立入口。
   - `app.json` 去除 `invitation-center` 路由并注册新页面。
   - 原 `invitation-center` 页面与 service 移入 `deleted/` 归档目录。
4. 文档同步：
   - 更新 `docs/api/invitations.md`。
   - 更新 `docs/spec/client/base/profile-setup.md`。
5. 数据库与产物：
   - 更新模型事件注释。
   - 新增 Alembic 迁移以同步数据库 comment 语义。
   - 生成 `backend/database/init/sql/01_schema.sql` 与 `docs/data-dict/*`。
6. 验证：
   - 后端与前端校验通过。
   - 全库检索无 `invite_center` 残留（`deleted/` 归档除外）。

## 验收标准

- UI 中不存在“邀请中心”入口和页面。
- Profile 存在“填写邀请码”“邀请好友”两个独立入口并可正常跳转。
- 后端不接受 `invite_center` source，`open` 事件可正常入库。
- API/spec 文档与实现一致。
- 迁移、schema.sql、data-dict 反映新事件语义。
- 关键流程可用：setup 绑定、填写页绑定、分享页复制与分享事件。

## 影响文件（计划）

- `frontend/mp-weixin/app.json`
- `frontend/mp-weixin/pages/profile/profile.wxml`
- `frontend/mp-weixin/pages/profile/profile.ts`
- `frontend/mp-weixin/pages/invitation-center/*`（迁移到 `deleted/`）
- `frontend/mp-weixin/pages/invite-bind/*`（新增）
- `frontend/mp-weixin/pages/invite-share/*`（新增）
- `frontend/mp-weixin/services/pages/invitation-center-service.ts`（迁移到 `deleted/`）
- `frontend/mp-weixin/services/pages/invite-bind-service.ts`（新增）
- `frontend/mp-weixin/services/pages/invite-share-service.ts`（新增）
- `frontend/mp-weixin/services/pages/setup-service.ts`
- `frontend/mp-weixin/utils/schemas.ts`
- `backend/app/enums/invitation.py`
- `backend/app/schemas/invitation.py`
- `backend/app/api/v1/invitations.py`
- `backend/app/models/invitation.py`
- `backend/alembic/versions/*`（新增迁移）
- `backend/database/init/sql/01_schema.sql`
- `docs/data-dict/*`
- `docs/api/invitations.md`
- `docs/spec/client/base/profile-setup.md`
