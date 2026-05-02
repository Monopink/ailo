# 小程序语义差异对照规范

## 目标

仅记录后端与小程序之间存在差异的语义映射；同名同义字段不在本文件重复列出。

## 差异分层原则

- 后端数据库与服务层保留直白语义：`review_scope`。
- API 契约与小程序业务层使用替代语义：`segment_type`。
- 事件名保持前后端同名同义，不在本文件建立事件名映射。

## 差异字段对照

| 场景 | 后端直白字段 | API 契约字段 | 小程序内部字段 |
| --- | --- | --- | --- |
| 账号分段判定结果 | `users.review_scope` | `segment_type`（`/client/preflight-probe`） | `runtime_segment_state.segment_type` |
| 审核员判定输入 | `system_configs.mp_weixin_review_*` | `build_id`、`build_time` | `BUILD_INFO.id`、`BUILD_INFO.builtAt` |
| 运行态观测分段快照 | `client_runtime_observations.scope_snapshot` | `segment_type` | `segment_type` |
| 运行态观测命中特征 | `client_runtime_observations.feature_hits` | `matched_features` | `matched_features` |
| 预览放行状态 | - | - | `runtime_segment_state` |
| 登录后能力分段 | `users.review_scope` | `account_segment` | `auth.user_info.account_segment` |

## 差异枚举对照

| 层级 | 取值 | 含义 |
| --- | --- | --- |
| 后端直白 | `review_scope=0` | `non_review` |
| 后端直白 | `review_scope=1` | `mp_weixin_review` |
| API/前端替代 | `segment_type=0` | `standard` |
| API/前端替代 | `segment_type=1` | `limited` |
| API/前端能力 | `account_segment=0` | `member_full` |
| API/前端能力 | `account_segment=1` | `member_limited` |
| 前端放行状态 | `runtime_segment_state.state_level=provisional` | 临时态 |
| 前端放行状态 | `runtime_segment_state.state_level=confirmed` | 确认态 |

## 约束

- 本文件只维护差异项。
- 同名同义字段在各自 API 文档中定义，不在本文件重复。
- 前端能力开关使用后端返回的 `account_segment`，不在客户端执行本地粘性升级。
- 审核员判定输入来自构建信息字段，不使用 UA 作为判定源。
