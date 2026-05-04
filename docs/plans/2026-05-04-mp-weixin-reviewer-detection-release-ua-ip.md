# 小程序审核员判定扩展（正式版 UA + 审核 IP）

## 问题点

- 现有审核员判定仅覆盖“审核周期 + 审核构建信息”，无法对正式上线版本中的模拟器访问进行审核员识别。
- 现有规则缺少独立的审核 IP 命中能力，无法在无构建信息或构建信息不命中时直接按来源 IP 判定审核员。

## 需求点

- 新增正式上线版本 `build_id` 配置项。
- 新增审核 IP 黑名单配置项。
- 审核员判定采用三路独立规则，三者任一命中即判定为审核员：
  - 审核版规则命中（现有 build-cycle 规则）。
  - 正式版 + 模拟器 UA 命中。
  - 审核 IP 黑名单命中。
- UA 模拟器规则采用硬编码关键词匹配：将 UA 归一化为小写后，判断是否包含 `wechatdevtools`。
- IP 黑名单采用精确 IP 匹配（不支持 CIDR 段）。

## 实施方案

## 1. 配置项与数据初始化

- 新增 `system_configs` 配置键：
  - `mp_weixin_release_build_ids`
    - 类型：字符串数组
    - 作用：定义“正式版 + 模拟器 UA”规则中的正式版构建集合。
  - `mp_weixin_review_ip_blacklist`
    - 类型：字符串数组
    - 作用：定义审核 IP 黑名单。
- 更新 Alembic 迁移与 `backend/database/bootstrap/base.sql`，保证新环境与已有环境均具备配置项。
- 新配置项归属 `review` 分组，scope 与现有审核判定配置保持一致。

## 2. 审核员判定服务扩展

- 在审核员判定服务中扩展统一判定输入：
  - `build_id`
  - `build_time`
  - `user_agent`
  - `client_ip`
- 保留现有审核版 build-cycle 判定逻辑不变。
- 新增正式版模拟器判定逻辑：
  - `build_id` 命中 `mp_weixin_release_build_ids`
  - `user_agent`（小写）包含 `wechatdevtools`
  - 两条件同时成立即命中该路规则。
- 新增审核 IP 判定逻辑：
  - `client_ip` 命中 `mp_weixin_review_ip_blacklist` 即命中该路规则。
- 最终判定规则：
  - `is_reviewer = matched_review_cycle OR matched_release_simulator OR matched_review_ip`

## 3. 接口接线范围

- 注册判定链路：
  - `POST /api/v1/auth/phone`
  - `POST /api/v1/auth/wechat/bind-phone`
  - 创建新用户时使用扩展后的统一判定，决定 `users.review_scope` 初始化值。
- 运行时预探测链路：
  - `POST /api/v1/client/preflight-probe`
  - 使用同一判定规则返回 `segment_type`，不写入 `users.review_scope`。
- `POST /api/v1/auth/wechat/login` 保持现有行为：仅登录检查与已绑定账号登录，不触发新用户 `review_scope` 初始化。

## 4. 后台配置保存与校验

- 管理后台系统设置页纳入新增配置项展示与保存。
- 扩展运营配置语义校验：
  - `mp_weixin_review_ip_blacklist` 每项必须是合法 IP 字符串（IPv4/IPv6）。
  - `mp_weixin_release_build_ids` 复用字符串数组基础校验（非空、去空白、去重）。

## 5. 文档同步

- 更新 `docs/spec/review-mode.md`：补充三路独立判定规则与关键词匹配定义。
- 更新 `docs/spec/client/mini-program/semantic-alignment.md`：更新审核员判定输入来源定义，纳入 UA/IP 输入。
- 更新 `docs/api/client-review-runtime.md`：明确 `preflight-probe` 判定输入包含构建信息、UA、IP。
- 更新 `docs/api/auth.md`：明确注册链路判定规则与输入约束。

## 验收标准

- 当审核版 build-cycle 命中时，判定为审核员。
- 当 `build_id` 命中 `mp_weixin_release_build_ids` 且 UA 包含 `wechatdevtools` 时，判定为审核员。
- 当 `client_ip` 命中 `mp_weixin_review_ip_blacklist` 时，判定为审核员。
- 上述三路任一路命中，`preflight-probe` 返回 `segment_type=1`。
- 新用户注册链路在三路任一路命中时，`users.review_scope` 初始化为 `1`；否则为 `0`。
- 管理后台可成功保存新增配置项，非法 IP 配置会被拦截并返回字段级错误。
