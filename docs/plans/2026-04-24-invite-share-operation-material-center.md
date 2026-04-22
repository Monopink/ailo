# 邀请分享页运营素材中心改造方案（invite-share）

## 目标

- 将小程序 `invite-share` 页面分享卡片从前端硬编码图片改为后端配置驱动。
- 在后端建立“素材中心 + 槽位配置”两层模型，支持运营发布与回滚。
- 复用现有 `media_files` 作为文件事实源，不改其核心职责。
- 一期不实现 A/B 分流，只支持单生效版本。

## 已确认决策

- API 形态：扩展 `GET /api/v1/invitations/share`。
- 图片访问：返回公网 CDN URL（非签名 URL）。
- 实验能力：一期不做 A/B。
- 数据建模：新增 `operation_assets`、`operation_slot_configs`，不以 `media_files` 直接承载运营配置。

## 现状

- 前端 `pages/invite-share/invite-share.ts` 在 `onShareAppMessage` 中硬编码 `imageUrl='/assets/share/invite-share-card.png'`。
- 后端 `GET /api/v1/invitations/share` 当前返回 `code/text/link`，不返回分享卡片结构化配置。
- 后端已存在 `invite_share_templates` 用于分享文案模板，但未覆盖分享图与分享标题/路径策略。
- 后端已存在 `media_files`，其职责为上传文件元数据与状态管理，不包含投放位、排期、版本发布语义。

## 问题点

- 硬编码分享图导致每次改图必须发版，无法运营实时调整。
- 现有邀请文案模板与分享卡片素材分离，缺少统一“分享载荷”来源。
- 若将投放语义直接塞入 `media_files`，会耦合上传域与运营域，后续维护成本高。

## 方案范围

一期仅覆盖：

- 槽位 `invite_share_card`（小程序邀请分享卡片）。
- 扩展邀请分享接口返回分享卡片配置。
- 小程序 invite-share 页面改为消费后端返回的分享卡片配置。

不在一期范围：

- A/B 分桶实验。
- 通用多端素材分发协议。
- 其他页面（如 `login_bg`）接入改造。

## 数据模型

### 1) operation_assets

用途：运营素材业务表，描述可投放素材。

建议字段：

- `id` bigint PK
- `asset_code` varchar(64) unique，素材业务编码
- `media_file_id` bigint nullable，FK -> `media_files.id`
- `asset_type` smallint，1=image（一期）
- `cdn_url` varchar(1024) not null，公网可访问 URL
- `mime_type` varchar(100) nullable
- `width` int nullable
- `height` int nullable
- `status` smallint not null，1=active 2=inactive
- `version` int not null default 1
- `created_by` bigint nullable
- `updated_by` bigint nullable
- `created_at` timestamptz
- `updated_at` timestamptz

约束：

- `asset_type IN (1)`（一期）
- `status IN (1,2)`
- `cdn_url` 必须为 `https://`

### 2) operation_slot_configs

用途：投放位配置表，定义某槽位在某端的生效素材与分享参数。

建议字段：

- `id` bigint PK
- `slot_code` varchar(64) not null（一期固定使用 `invite_share_card`）
- `channel` varchar(32) not null（一期固定 `mini_program`）
- `title` varchar(128) not null
- `path_template` varchar(512) not null（示例：`/pages/setup/setup?inviteCode={{code}}`）
- `asset_id` bigint not null，FK -> `operation_assets.id`
- `priority` int not null default 100
- `start_at` timestamptz nullable
- `end_at` timestamptz nullable
- `status` smallint not null，1=active 2=inactive
- `version` int not null default 1
- `created_by` bigint nullable
- `updated_by` bigint nullable
- `created_at` timestamptz
- `updated_at` timestamptz

约束：

- `status IN (1,2)`
- `slot_code='invite_share_card'`（一期可用 check 约束限定）
- `channel='mini_program'`（一期可用 check 约束限定）
- `start_at <= end_at`（当 `end_at` 非空）

生效选择规则：

- 过滤条件：`slot_code`、`channel`、`status=active`、时间窗口命中。
- 排序规则：`priority ASC, id DESC`，取第一条作为当前生效配置。

### 3) operation_publish_logs（可选但建议一期落地）

用途：发布/回滚审计。

建议字段：

- `id` bigint PK
- `slot_code` varchar(64) not null
- `action` varchar(16) not null（publish/rollback）
- `from_version` int nullable
- `to_version` int not null
- `operator_id` bigint nullable
- `reason` varchar(500) nullable
- `created_at` timestamptz

## API 变更

### 扩展接口

- 路径：`GET /api/v1/invitations/share`
- 认证：Bearer Token（保持不变）

### 响应新增字段

响应字段：

- `share_card` (object)
  - `title` (string)
  - `path` (string)
  - `image_url` (string, https)
  - `slot_code` (string，固定 `invite_share_card`)
  - `version` (integer)

示例：

```json
{
  "code": "K8P2Q7",
  "text": "敲敲好友都在用，K8P2Q7 https://example.com/i/K8P2Q7",
  "link": "https://example.com/i/K8P2Q7",
  "share_card": {
    "title": "来敲敲AI，对话敲多新奇有趣",
    "path": "/pages/setup/setup?inviteCode=K8P2Q7",
    "image_url": "https://cdn.example.com/ops/invite/card-v1.png",
    "slot_code": "invite_share_card",
    "version": 1
  }
}
```

### 服务端处理

- `path_template` 使用邀请码渲染 `{{code}}`。
- 若未命中生效槽位配置，接口返回错误（不提供后端临时兜底配置）。

## 小程序改造

### invite-share 页面

- `onShareAppMessage` 改为读取接口返回 `share_card`。
- `title/path/imageUrl` 分别使用 `share_card.title/share_card.path/share_card.image_url`。
- 页面初始化阶段缓存 `share_card` 到页面 data。

### 事件埋点

- 保留现有 `share_wechat` 事件上报。
- `payload` 增加 `slot_code` 与 `slot_version`。

## 管理后台改造

- 新增 `operation_assets` 管理视图：创建/编辑素材元信息与状态。
- 新增 `operation_slot_configs` 管理视图：配置槽位、标题、path 模板、素材关联、时间窗、优先级。
- 新增发布动作：写入 `operation_publish_logs`。

## 迁移与实施步骤

1. 新增 Alembic 迁移：创建 `operation_assets`、`operation_slot_configs`、`operation_publish_logs`。
2. 新增 SQLAlchemy Model 与 CRUD。
3. 新增运营槽位解析服务（邀请域内调用）。
4. 扩展邀请分享 schema 与 `GET /api/v1/invitations/share` 响应。
5. 改造小程序 `invite-share-service.ts`、`invite-share.ts` 消费 `share_card`。
6. 新增后台管理视图并初始化一条 `invite_share_card` 生效配置。
7. 更新 `docs/api/invitations.md`（接口契约）。
8. 更新 `docs/spec/client/base/profile-setup.md` 中邀请分享能力描述（与实现一致）。

## 验收标准

- `invite-share` 页面分享卡片图片由接口返回配置驱动。
- 修改后台 `invite_share_card` 配置后，无需小程序发版即可生效。
- `GET /api/v1/invitations/share` 稳定返回 `share_card`。
- 分享链路中 `path` 正确携带当前用户邀请码。
- 埋点可区分分享槽位与版本。

## 影响文件（实施阶段）

- `backend/alembic/versions/*.py`
- `backend/app/models/*`
- `backend/app/crud/*`
- `backend/app/schemas/invitation.py`
- `backend/app/api/v1/invitations.py`
- `backend/app/admin/views/*`
- `frontend/mp-weixin/services/pages/invite-share-service.ts`
- `frontend/mp-weixin/pages/invite-share/invite-share.ts`
- `docs/api/invitations.md`
- `docs/spec/client/base/profile-setup.md`

## 实施结果

- 当前状态：已实施完成并与主干代码对齐。
- `GET /api/v1/invitations/share` 已稳定返回 `share_card`，小程序 `invite-share` 已改为动态消费后端分享卡片配置。
- 后台已具备运营素材与槽位配置能力（`operation_assets`、`operation_slot_configs`），支持邀请分享卡片配置发布。
