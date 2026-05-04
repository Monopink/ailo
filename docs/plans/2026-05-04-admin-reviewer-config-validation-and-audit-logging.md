# Operation Settings: reviewer config validation + audit logging transaction fix

## 问题点

1. `docs/api/auth.md` 将 `POST /api/v1/auth/wechat/login` 纳入“审核员判定统一约束”，但该接口实现为“两段式登录 stage1”，不会触发审核员判定，不会写入 `users.review_scope`，也不会返回 `segment_type`。
2. `mp_weixin_release_build_ids` 在运营后台保存时缺少语义校验，可能出现“保存成功但实际无效项被静默过滤”的情况。
3. Admin 系统设置页（Operation Settings / System Settings）保存配置时，会先提交配置变更，再逐条写入操作日志；而 `create_operation_log` 内部固定提交事务，导致同一请求内多次 commit、事务割裂与日志不一致风险。
4. 审核版规则（build-cycle）要求除 `mp_weixin_review_deadline_at` 外还需至少配置 `mp_weixin_review_build_ids` 或 `mp_weixin_review_build_time_from/to` 才可能命中；仅配置 deadline 不会触发 build-cycle 命中，运营侧容易误解。

## 需求点

1. 修正 `docs/api/auth.md` 的对外契约，使其与当前实现一致：`POST /api/v1/auth/wechat/login` 不参与审核员判定写入。
2. 为 `mp_weixin_release_build_ids` 增加语义校验，并确保后台保存时会触发该校验。
3. 修复系统设置页保存链路的事务与审计日志写入方式，避免同一请求多次 commit 和事务割裂。
4. 在文档/运营层面明确提示：仅设置 `mp_weixin_review_deadline_at` 不会触发 build-cycle 命中，需要至少配置一类 matcher。

## 实施方案

### 1) 文档契约修正（对齐实现）

- 修改 `docs/api/auth.md` 的“审核员判定统一约束”描述：
  - 仅保留 `POST /api/v1/auth/phone` 与 `POST /api/v1/auth/wechat/bind-phone` 作为“新用户创建时 review_scope 初始化”的写入入口。
  - `POST /api/v1/auth/wechat/login` 保持“两段式 stage1”语义，不参与审核员判定写入，不产生 `segment_type` 输出。
- `docs/api/auth.md` 的 “微信登录（两段式）/检查绑定状态”章节保持 `build_id/build_time` 字段定义不变（仍作为统一客户端上送的构建信息字段），但不描述其会触发审核员判定写入。

### 2) `mp_weixin_release_build_ids` 语义校验与后台接线

- 在 `backend/app/services/system_settings_validation.py` 中增加 `mp_weixin_release_build_ids` 语义校验：
  - 必须为字符串数组。
  - 每项必须为非空字符串（去空白后不得为空）。
  - 去重由判定服务内部处理即可；语义校验侧只负责阻止明显无效输入。
- 在 `backend/app/admin/views/system_settings_view.py` 的 `review_validation_keys` 中加入 `mp_weixin_release_build_ids`，保证后台保存时会触发该语义校验。

### 3) System Settings 保存链路：日志与事务改造（方案 A）

- 修改 `backend/app/utils/admin_logs.py`：
  - 为 `create_operation_log` / `create_login_log` 增加可选参数 `commit: bool = True`。
  - 当 `commit=False` 时，仅 `db.add(log_entry)` 并 `await db.flush()`，不执行 `commit()`。
- 修改 `backend/app/admin/views/system_settings_view.py`：
  - 在同一事务中完成：配置更新 + 语义校验 + 写入操作日志 + 单次 `commit()`。
  - `create_operation_log(..., commit=False)` 用于累积日志，最终由视图统一 `commit()`。
- 其它调用点保持默认行为不变（不修改调用方），以保证改动范围可控。

### 4) 文档/运营提示：deadline-only 不生效

- 在 `docs/spec/review-mode.md` 的“审核版规则（build-cycle）”段落增加明确提示：
  - `mp_weixin_review_deadline_at` 仅用于判断审核期窗口；
  - 必须至少配置 `mp_weixin_review_build_ids` 或 `mp_weixin_review_build_time_from/to`，build-cycle 才可能命中。

## 验收标准

1. `docs/api/auth.md` 明确 `POST /api/v1/auth/wechat/login` 不参与审核员判定写入，且整体表述与 `backend/app/api/v1/auth.py` 的实现一致。
2. 运营后台保存 `mp_weixin_release_build_ids`：
   - 输入非数组、包含空字符串、包含非字符串项时，保存被拦截并返回字段级错误。
3. 系统设置保存：
   - 单次保存请求在成功路径下只发生一次最终提交；
   - 当日志写入失败时，不应出现“配置已提交但日志部分缺失”的事务割裂（以同一事务统一提交为准）。
4. `docs/spec/review-mode.md` 明确写出 deadline-only 不会触发 build-cycle 命中，避免运营误用。
