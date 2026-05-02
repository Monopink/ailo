# 小程序审核员识别改造（Build 周期匹配）实施方案

生效日期：2026-05-02

## 问题与发现

- 运行态审核员识别使用 UA 特征匹配，识别依据与实际审核员特征不一致。
- 前后端均存在 UA 驱动的审核员判定与审核分段升级逻辑，导致判定链路不一致且可维护性差。
- 小程序上线审核需要在审核周期内对审核构建执行稳定分流，同时保持既有审核账号能力约束行为不变。

## 目标

- 审核员识别从 UA 判定切换为审核周期 + 构建信息匹配判定。
- 完全移除前后端 UA 审核员判定与 UA 驱动分段升级逻辑。
- 保持审核账号后续行为不变：审核账号继续映射 `account_segment=1`，继续受现有能力约束。
- 配置时间值以 UTC 存储；管理端时间输入使用本地时间显示与修改。

## 非目标

- 不调整 Nginx 对腾讯安全测试流量的 UA 拦截策略。
- 不变更 `users.review_scope` 与 `account_segment` 的数据模型定义。
- 不重构邀请、广场、账号能力约束的业务规则。

## 强制决策

### 1. 审核员识别规则

- 审核员判定仅基于审核周期与构建匹配，不使用 UA。
- 审核周期条件：`mp_weixin_review_deadline_at` 非空且 `now_utc <= deadline_at`。
- 构建匹配条件：
  - `mp_weixin_review_build_ids` 存在时，要求客户端 `build_id` 命中列表。
  - `mp_weixin_review_build_time_from/to` 存在时，要求客户端 `build_time` 落入闭区间。
  - 仅存在一类条件时，只匹配该类。
  - 两类条件都存在时，必须交叉匹配同时命中。
- 最终判定：`is_reviewer = in_review_period AND build_match`。

### 2. 配置清空语义

- `mp_weixin_review_build_ids` 允许清空。
- `mp_weixin_review_build_time_from`、`mp_weixin_review_build_time_to` 允许清空。
- 当 `deadline_at` 为空或已过期时，视为不在审核期。

### 3. 截止时间约束

- `mp_weixin_review_deadline_at` 禁止设置为早于当前已存值的时间。
- `mp_weixin_review_deadline_at` 到期后自动失效，无需额外开关字段。

### 4. 登录注册链路行为

- 审核员识别后续行为保持不变：注册/登录命中审核员时，账号标记为审核分段。
- `review_scope` 保持只升不降（`0 -> 1`，不自动回退）。
- 登录/注册请求缺失构建信息时，按非审核员处理，不阻断登录注册流程。

### 5. 时间与展示规则

- 后端统一以 UTC ISO8601 存储时间配置。
- 管理端表单使用本地时间编辑，并在提交时转换为 UTC。
- 管理端当前值展示使用本地时间格式渲染。

## 实施内容

### A. 系统配置与迁移

- 新增配置键：
  - `mp_weixin_review_deadline_at`（TIME, SINGLE, 可空）
  - `mp_weixin_review_build_ids`（STRING, ARRAY, 可空）
  - `mp_weixin_review_build_time_from`（TIME, SINGLE, 可空）
  - `mp_weixin_review_build_time_to`（TIME, SINGLE, 可空）
- 移除配置键：
  - `mp_weixin_review_mode`
- 初始化数据、`base.sql` 与环境引导脚本同步更新。

### B. 后端审核员判定链路

- 新增构建周期判定服务，统一输出审核员判定结果。
- `POST /api/v1/client/preflight-probe` 改为调用构建周期判定，不再使用 UA 分类器。
- `POST /api/v1/auth/wechat/login`、`POST /api/v1/auth/wechat/bind-phone`、`POST /api/v1/auth/verify-phone` 请求体新增构建信息字段，使用同一判定服务驱动 `review_scope` 升级。
- 删除 `review_scope_classifier` 及其调用点。

### C. 前端小程序

- 删除 `runtime-segment` 本地 UA 分类逻辑与签名 token 常量。
- 在线场景仅依赖 `/client/preflight-probe` 返回的 `segment_type`。
- 离线场景保留 36 小时 fallback 跳转逻辑。
- 登录注册相关请求补充构建信息上送字段。

### D. 系统设置校验

- `backend/app/services/system_settings_validation.py` 增加审核配置语义校验：
  - `deadline_at` 不允许回退。
  - `build_time_from <= build_time_to`（当二者同时存在）。
  - 审核配置组合满足判定规则要求。
- 在设置保存链路接入该校验并返回字段级错误。

### E. 文档同步

- 更新 `docs/api/client-review-runtime.md`：审核员判定来源改为构建周期匹配。
- 更新 `docs/api/auth.md`：登录注册请求新增构建字段与判定行为。
- 更新 `docs/spec/client/mini-program/semantic-alignment.md`：移除 UA 判定语义描述。

## 验收标准

- 前后端不存在 UA 审核员判定与 UA 分段升级逻辑。
- 审核期内，构建信息命中时未登录启动返回 `segment_type=1`；不命中返回 `segment_type=0`。
- 审核期外（`deadline_at` 为空或过期）统一返回非审核判定。
- 登录/注册命中审核条件时账号 `review_scope` 升级为 `1`，且不会自动降级。
- 设置页以本地时间编辑审核时间配置，保存后后端以 UTC 存储。
- 设置 `deadline_at` 为早于当前值时保存失败并返回字段级错误。

## 实施状态

- 状态：待实施
- 最后更新：2026-05-02
