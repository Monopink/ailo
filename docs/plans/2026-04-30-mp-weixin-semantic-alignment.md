# 小程序语义替换与前后端对照

生效日期：2026-04-30

## 目标

- 小程序代码层不出现审核模式相关语义词。
- 后端配置项 `review_mode_*` 统一归属 `config_scope=system`。
- 建立一份前后端语义对照，保证字段含义一致。

## 小程序语义替换方案

### 小程序内部统一命名

- `review_scope` -> `account_segment`
- `review_mode_active` -> `access_gate_open`
- `review_mode_ends_at` -> `access_gate_ends_at`
- `review_mode_local_decision` -> `startup_local_policy`
- `review_mode_server_decision` -> `startup_server_policy`

### 小程序内部统一枚举值

- `NON_REVIEW` -> `STANDARD_MEMBER`
- `MP_WEIXIN_REVIEW` -> `LIMITED_MEMBER`
- `public_preview` -> `DEMO_PUBLIC`
- `network_fallback_preview` -> `DEMO_OFFLINE_WINDOW`
- `member_standard` -> `MEMBER_FULL`
- `member_restricted` -> `MEMBER_LIMITED`

### 小程序内部统一函数命名

- `resolveReviewScope()` -> `resolveAccountSegment()`
- `normalizeReviewScope()` -> `normalizeAccountSegment()`
- `isPublicPreviewMode()` -> `isDemoMode()`

## 前后端语义对照

| 后端契约字段/值 | 小程序内部字段/值 | 含义 |
|---|---|---|
| `review_scope=0` | `account_segment=STANDARD_MEMBER` | 登录用户标准能力 |
| `review_scope=1` | `account_segment=LIMITED_MEMBER` | 登录用户受限能力 |
| `review_mode_active=true` | `access_gate_open=true` | 服务器允许未登录体验入口 |
| `review_mode_active=false` | `access_gate_open=false` | 服务器关闭未登录体验入口 |
| `review_mode_ends_at` | `access_gate_ends_at` | 入口截止时间 |
| `review_mode_local_decision` | `startup_local_policy` | 启动链路本地判定结果 |
| `review_mode_server_decision` | `startup_server_policy` | 启动链路服务端判定结果 |
| `public_preview` | `DEMO_PUBLIC` | 未登录体验模式 |
| `network_fallback_preview` | `DEMO_OFFLINE_WINDOW` | 断网且 36 小时窗口内体验模式 |
| `member_standard` | `MEMBER_FULL` | 登录标准模式 |
| `member_restricted` | `MEMBER_LIMITED` | 登录受限模式 |

## 配置归属统一

- `review_mode_mp_weixin_enabled` 归属 `config_scope=system`
- `review_mode_mp_weixin_ends_at` 归属 `config_scope=system`
- `review_mode_mp_weixin_auto_disable_enabled` 归属 `config_scope=system`

## 实施结果记录

- 已新增本对照文档，作为本次语义收敛执行基准。
