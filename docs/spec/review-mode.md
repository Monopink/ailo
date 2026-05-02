## 审核员分段判定

- 判定输入字段：`build_id`、`build_time`。
- 判定配置字段：
  - `system_configs.mp_weixin_review_deadline_at`
  - `system_configs.mp_weixin_review_build_ids`
  - `system_configs.mp_weixin_review_build_time_from`
  - `system_configs.mp_weixin_review_build_time_to`
- 审核周期条件：`mp_weixin_review_deadline_at` 非空且未过期（UTC）；为空或过期视为不在审核期。
- 构建匹配条件：
  - `mp_weixin_review_build_ids` 非空时，`build_id` 必须命中列表。
  - `mp_weixin_review_build_time_from/to` 非空时，`build_time` 必须落入闭区间。
  - 仅存在一类条件时，只匹配该类。
  - 两类条件都存在时，必须同时命中。
- 最终审核员结果：`in_review_period AND build_match`。
- 无鉴权请求：`/api/v1/client/preflight-probe` 使用该规则返回 `segment_type`。
- 登录与使用链路：`/api/v1/auth/phone`（已存在账号登录）、`/api/v1/auth/wechat/login`、`/api/v1/auth/wechat/bind-phone`（复用已存在账号）、`/api/v1/client/preflight-probe` 使用同一规则判定审核分段，但不写入 `users.review_scope`。
- 账号标记规则：仅在小程序注册创建账号时，命中审核分段才将 `users.review_scope` 初始化为 `1`；创建后不在登录或使用链路自动升级，不自动回退。
- 请求缺失构建信息时，按非审核员处理，不阻断登录注册流程。
