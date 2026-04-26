# 邀请策略卡片与设置页拆分实施方案

生效日期：2026-04-27

## 目标

- 清除“新用户跨来源总封顶”完整链路，仅保留按奖励渠道/规则控制上限。
- 将邀请奖励规则收敛到 Operation Settings 的业务卡片入口，邀请分享文案保留在通用配置列表维护。
- 拆分 `backend/app/admin/templates/custom_views/system_settings.html`，按页面职责拆分模板与脚本，提取共用模块。
- 以一次性交付完成架构整理，清理冗余逻辑并保持结构清晰。

## 已确认决策

- 删除并停用配置键：
  - `growth_new_user_reward_window_days`
  - `growth_new_user_reward_cap_total`
- 邀请奖励规则在 Operation Settings 使用业务卡片入口，邀请分享文案在通用配置列表维护。
- `growth_reward_rules`、`growth_reward_applies` 继续作为执行与审计数据源。
- 管理后台不提供数据表直改作为主操作路径，主操作路径为业务卡片。
- `contacts_initial_ai_contact_limit` 保留在 `system_configs`，不迁移到独立策略表。
- Operation Settings 保留“卡片 + 通用配置列表”双入口。

## 范围

### 包含

- 奖励服务、配置读取、配置种子、管理后台展示、管理后台 API、相关文档同步。
- `system_settings` 页面模板与前端脚本拆分。
- 邀请业务卡片（奖励参数）落地。

### 不包含

- 活动归因与兑换码奖励模型重设计。
- 权益账本模型重设计。

## 现状问题

1. `reward_service` 存在跨来源总封顶逻辑，行为与“渠道独立封顶”目标冲突。
2. `system_settings.html` 同时承载 System/Operation 两页，模板体量与脚本体量过大，页面职责耦合。
3. 邀请相关操作入口分散在 Reward Rules 表视图与 Operation Settings 配置列表，运营路径不聚合。

## 实施方案

### 1. 奖励链路清理（移除总封顶）

- 修改文件：
  - `backend/app/services/growth/reward_service.py`
- 变更内容：
  - 移除 `growth_new_user_reward_window_days`、`growth_new_user_reward_cap_total` 的读取逻辑。
  - 删除 `_cap_delta_for_new_user_reward_window` 与相关常量、查询与聚合逻辑。
  - `apply_growth_rewards` 仅按规则自身参数执行发放（`delta_granted`、`max_rewards_per_actor`）。

### 2. 配置数据清理

- 新增 Alembic 迁移（2026-04-27）：
  - 从 `system_configs` 删除：
    - `growth_new_user_reward_window_days`
    - `growth_new_user_reward_cap_total`
- 同步清理映射与展示：
  - `backend/app/admin/i18n.py` 删除上述两个键的名称和描述映射。
- 同步清理文档中的配置项定义（若出现）。

### 3. 邀请业务卡片（Operation Settings 单入口）

- 新增管理后台 API（挂载到 `backend/app/api/admin/system_management.py`）：
  - `GET /admin-api/system/invitation-policy`
  - `PUT /admin-api/system/invitation-policy`
- 卡片字段定义：
  - `invitee_reward_contact_delta`（邀请码绑定成功给被邀请人）
  - `inviter_reward_contact_delta`（被邀请人完成首轮 setup 后给邀请人）
  - `inviter_max_rewards_per_actor`（邀请人奖励次数上限）
- 邀请分享文案配置项：
  - `operation_invite_share_command_texts`
  - `operation_invite_share_card_titles`
  - 仅在通用配置列表编辑，不纳入卡片编辑字段。
- 规则定位方式（固定槽位）：
  - `(trigger_event=1, target_role=2, scope_type=1, scope_id=0, entitlement_type=ai_contact_limit)`
  - `(trigger_event=2, target_role=3, scope_type=1, scope_id=0, entitlement_type=ai_contact_limit)`
- 更新方式：
  - 单事务、行级锁、参数校验、操作日志写入。

### 4. 管理页面拆分与模块化

- 模板拆分（参考 `advanced-edit` 的页面/共用模块结构）：
  - 新建 `backend/app/admin/templates/custom_views/system_settings/`
  - 新建页面模板：
    - `system_page.html`（System Settings）
    - `operation_page.html`（Operation Settings）
  - 新建共用片段：
    - `partials/alerts.html`
    - `partials/config_groups_form.html`
- 脚本拆分：
  - 新建 `backend/app/admin/static/js/system-settings/common/`
    - `page-core.js`
    - `invitation-policy-card.js`
  - 新建 `backend/app/admin/static/js/system-settings/pages/`
    - `system-settings.js`
    - `operation-settings.js`
- `backend/app/admin/views/system_settings_view.py` 调整：
  - 按页面选择模板文件，分别渲染对应模板文件。
  - 向模板输出页面级配置对象，脚本通过模块初始化。

### 5. 入口治理与权限

- Operation Settings 页面：
  - 邀请相关操作走“邀请业务卡片”入口。
  - 邀请相关配置保留卡片与通用配置列表双入口。
- Reward Rules 视图：
  - 设置为只读审计视图（禁用创建/编辑/删除）。

## 实施步骤

1. 新建并应用迁移：删除两个总封顶配置键。
2. 清理 `reward_service.py` 总封顶逻辑与常量。
3. 新增 Invitation Policy 管理 API（读/改）。
4. 拆分 `system_settings` 模板与前端脚本模块。
5. 接入 Operation Settings 邀请业务卡片，联调 API。
6. 调整管理入口：保留邀请卡片与通用配置列表双入口，Reward Rules 改只读。
7. 同步更新 `docs/spec/admin-panel/system-settings.md` 与涉及邀请奖励策略的 API/spec 文档。
8. 执行验证（格式、静态检查、后端测试、手工回归）。

## 验收标准

- 代码中不存在对 `growth_new_user_reward_window_days`、`growth_new_user_reward_cap_total` 的读取与业务判断。
- 数据库 `system_configs` 中不存在上述两个配置键。
- Operation Settings 存在“邀请业务卡片”，且同时保留通用配置列表编辑入口。
- `system_settings` 页面拆分为独立模板与独立页面脚本，共用逻辑在 common 模块维护。
- Reward Rules 页面仅用于查看审计数据，无法直接改写规则。
- 邀请奖励发放行为仅由奖励规则控制，渠道上限由规则参数体现。
