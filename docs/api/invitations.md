# 邀请码、活动归因与兑换码接口

## 接口列表

- [获取我的邀请码](#获取我的邀请码) - `GET /api/v1/invitations/code`
- [获取邀请码绑定状态](#获取邀请码绑定状态) - `GET /api/v1/invitations/binding-status`
- [获取邀请规则](#获取邀请规则) - `GET /api/v1/invitations/policy`
- [获取邀请统计](#获取邀请统计) - `GET /api/v1/invitations/stats`
- [获取邀请口令文案](#获取邀请口令文案) - `GET /api/v1/invitations/share-command`
- [获取邀请分享卡片](#获取邀请分享卡片) - `GET /api/v1/invitations/share-card`
- [邀请短链跳转](#邀请短链跳转) - `GET /i/{token}`
- [匿名邀请码识别](#匿名邀请码识别) - `POST /api/v1/public/invitations/intake`
- [登录态邀请码识别](#登录态邀请码识别) - `POST /api/v1/invitations/intake`
- [解析邀请码](#解析邀请码) - `POST /api/v1/invitations/resolve`
- [绑定邀请码](#绑定邀请码) - `POST /api/v1/invitations/bind`
- [上报邀请事件](#上报邀请事件) - `POST /api/v1/invitations/events`
- [上报活动归因](#上报活动归因) - `POST /api/v1/growth/attributions/track`
- [兑换兑换码](#兑换兑换码) - `POST /api/v1/redeem-codes/claim`

## 访问能力约束

- 所有登录态邀请接口都会进行账号能力校验。
- 当当前账号 `review_scope` 不允许邀请能力时，接口返回：
  - `403 Forbidden`
  - `detail`: `当前账号暂不可用该功能`

---

## 获取我的邀请码

### 基本信息

- **路径**: `GET /api/v1/invitations/code`
- **认证**: Bearer Token（必需）

### 成功响应 (200)

```json
{
  "code": "K8P2Q7"
}
```

**字段说明**:

- `code` (string) - 当前用户的邀请码（6 位，英文/数字，服务端大写化，全局唯一码池）

---

## 获取邀请码绑定状态

### 基本信息

- **路径**: `GET /api/v1/invitations/binding-status`
- **认证**: Bearer Token（必需）

### 成功响应 (200)

```json
{
  "is_bound": true
}
```

**字段说明**:

- `is_bound` (boolean) - 当前用户是否已绑定过邀请码

---

## 获取邀请规则

### 基本信息

- **路径**: `GET /api/v1/invitations/policy`
- **认证**: Bearer Token（必需）

### 成功响应 (200)

```json
{
  "invitee_reward_contact_delta": 1,
  "inviter_reward_contact_delta": 1,
  "inviter_max_rewards_per_actor": 3
}
```

**字段说明**:

- `invitee_reward_contact_delta` (integer) - 被邀请人绑定成功后的联系人上限奖励增量
- `inviter_reward_contact_delta` (integer) - 邀请人绑定成功后的联系人上限奖励增量
- `inviter_max_rewards_per_actor` (integer | null) - 邀请人奖励次数上限（`null` 表示不限制）

---

## 获取邀请统计

### 基本信息

- **路径**: `GET /api/v1/invitations/stats`
- **认证**: Bearer Token（必需）

### 成功响应 (200)

```json
{
  "inviter_success_bind_count": 12,
  "inviter_reward_contact_limit_actual_total": 2,
  "inviter_reward_contact_limit_preview_total": 3
}
```

**字段说明**:

- `inviter_success_bind_count` (integer) - 当前用户已邀请成功人数（即成功绑定到该用户邀请码的人数）
- `inviter_reward_contact_limit_actual_total` (integer) - inviter 已实际发放总增量（基于 `growth_reward_applies` 与 `user_entitlement_ledger` 对齐后的真值）
- `inviter_reward_contact_limit_preview_total` (integer) - 按“当前规则参数 × 邀请成功人数（受规则上限约束）”计算的预估总增量

---

## 获取邀请口令文案

### 基本信息

- **路径**: `GET /api/v1/invitations/share-command`
- **认证**: Bearer Token（必需）

### 成功响应 (200)

```json
{
  "code": "K8P2Q7",
  "text": "敲敲好友都在用，K8P2Q7 https://example.com/i/K8P2Q7",
  "link": "https://example.com/i/K8P2Q7"
}
```

**字段说明**:

- `code` (string) - 当前用户的邀请码
- `text` (string) - 后端模板渲染后的邀请口令文案（模板支持 `{{code}}`、`{{link}}` 占位符）
- `link` (string) - 邀请短链（`/i/{token}`）

---

## 获取邀请分享卡片

### 基本信息

- **路径**: `GET /api/v1/invitations/share-card`
- **认证**: Bearer Token（必需）

### 成功响应 (200)

```json
{
  "code": "K8P2Q7",
  "title": "来敲敲AI，对话敲多新奇有趣",
  "path": "/pages/boot/boot?inviteCode=K8P2Q7",
  "image_url": "https://cortex.qiaoqiaoai.cn/share/invite-share-card.webp"
}
```

**字段说明**:

- `code` (string) - 当前用户的邀请码
- `title` (string) - 分享卡片标题（从运营配置文案数组中随机选择）
- `path` (string) - 小程序分享路径（固定为 `/pages/boot/boot?inviteCode={code}`）
- `image_url` (string) - 分享图片公网 URL（`media_public_base_url + /share/invite-share-card.webp`）

---

## 邀请短链跳转

### 基本信息

- **路径**: `GET /i/{token}`
- **认证**: 无

### 成功行为

- 校验 `token` 对应有效邀请码后，后端生成微信 URL Link 并返回 302 重定向。
- URL Link 小程序路径固定为 `/pages/boot/boot`，并携带 `inviteCode={token}` 查询参数。

### 失败响应

- `404`：token 无效或邀请码不存在
- `503`：微信跳转服务暂不可用

---

## 匿名邀请码识别

### 基本信息

- **路径**: `POST /api/v1/public/invitations/intake`
- **认证**: 无（匿名可用）

### 请求体

```json
{
  "source": "login",
  "trigger": "clipboard",
  "raw_text": "敲敲好友都在用，k8p2q7",
  "invite_code": null,
  "device_id": "mp_dv_1234567890",
  "segment_type": 1,
  "runtime_observation_id": 1987654321000,
  "client_user_agent": "Mozilla/5.0 ..."
}
```

**字段说明**:

- `source` (string, 必填) - 来源标记：`login`、`setup`、`link`、`invite_bind_page`、`invite_share_page`
- `trigger` (string, 必填) - 触发来源标记（如：`clipboard`、`link_param`、`manual_input`）
- `raw_text` (string, 可选) - 原始文本（如剪贴板）
- `invite_code` (string, 可选) - 直传邀请码（如链接参数）
- `device_id` (string, 可选) - 客户端设备 ID 快照（建议上传）
- `segment_type` (integer, 可选) - 客户端分段快照（`0=standard`、`1=limited`）
- `runtime_observation_id` (integer, 可选) - 关联运行态观测事件 ID
- `client_user_agent` (string, 可选) - 客户端 UA 快照（最大 2048 字符）

### 成功响应 (200)

```json
{
  "recognized_code": "K8P2Q7",
  "valid": true
}
```

**字段说明**:

- `recognized_code` (string | null) - 识别出的有效邀请码；未命中时为 `null`
- `valid` (boolean) - 是否识别到 active 邀请码

### 业务规则

- 服务端仅提取并验证“第一个独立 6 位字母数字串”。
- 仅当邀请码有效时记入 `open` 事件。
- 任意 `trigger` 都会写入 `invite_intake_logs`。
- 识别日志与 `open` 事件对“同一主体 + 同一来源 + 同一触发 + 同一输入内容”在 10 分钟窗口内做去重，避免短时间重复上传。
- 匿名 intake 去重优先使用 `device_id`；当 `device_id` 缺失时回退 `runtime_observation_id`，再回退 `client_user_agent`。
- `invite_intake_logs` 扩展关联字段：`reviewer_flag_snapshot`、`runtime_observation_id`、`client_user_agent`、`client_device_id`。
- intake 主流程（识别、有效性判断）与日志/事件写入解耦：若日志或事件写入异常，不影响 intake 返回。

---

## 登录态邀请码识别

### 基本信息

- **路径**: `POST /api/v1/invitations/intake`
- **认证**: Bearer Token（必需）

### 请求体

```json
{
  "source": "setup",
  "trigger": "clipboard",
  "raw_text": "敲敲好友都在用，k8p2q7",
  "invite_code": null,
  "device_id": "mp_dv_1234567890",
  "segment_type": 1,
  "runtime_observation_id": 1987654321000,
  "client_user_agent": "Mozilla/5.0 ..."
}
```

**字段说明**:

- `source` (string, 必填) - 来源标记：`login`、`setup`、`link`、`invite_bind_page`、`invite_share_page`
- `trigger` (string, 必填) - 触发来源标记（如：`clipboard`、`link_param`、`manual_input`）
- `raw_text` (string, 可选) - 原始文本（如剪贴板）
- `invite_code` (string, 可选) - 直传邀请码（如链接参数）
- `device_id` (string, 可选) - 客户端设备 ID 快照（建议上传）
- `segment_type` (integer, 可选) - 客户端分段快照（`0=standard`、`1=limited`）
- `runtime_observation_id` (integer, 可选) - 关联运行态观测事件 ID
- `client_user_agent` (string, 可选) - 客户端 UA 快照（最大 2048 字符）

### 成功响应 (200)

```json
{
  "recognized_code": "K8P2Q7",
  "valid": true,
  "bindable": true
}
```

**字段说明**:

- `recognized_code` (string | null) - 识别出的有效邀请码；未命中时为 `null`
- `valid` (boolean) - 是否识别到 active 邀请码
- `bindable` (boolean) - 当前登录用户是否可绑定该邀请码

### 业务规则

- 仅当邀请码有效时记入 `open` 事件。
- 任意 `trigger` 都会写入识别日志。
- 识别日志与 `open` 事件对“同一主体 + 同一来源 + 同一触发 + 同一输入内容”在 10 分钟窗口内做去重，避免短时间重复上传。
- 匿名 intake 去重优先使用 `device_id`；当 `device_id` 缺失时回退 `runtime_observation_id`，再回退 `client_user_agent`。
- `invite_intake_logs` 扩展关联字段：`reviewer_flag_snapshot`、`runtime_observation_id`、`client_user_agent`、`client_device_id`。
- 后台“解析成功”主口径统一使用 `open` 事件计数。
- intake 主流程（识别、有效性判断、bindable 判断）与日志/事件写入解耦：若日志或事件写入异常，不影响 intake 返回。

---

## 解析邀请码

### 基本信息

- **路径**: `POST /api/v1/invitations/resolve`
- **认证**: Bearer Token（必需）
- **速率限制**: 可能返回 `429`

### 请求体

```json
{
  "code": "K8P2Q7",
  "source": "setup"
}
```

**字段说明**:

- `code` (string) - 待解析的邀请码
- `source` (string, 必填) - 事件来源标记：`login`、`setup`、`link`、`invite_bind_page`、`invite_share_page`

### 成功响应 (200)

**当可解析**:

```json
{
  "valid": true,
  "code_type": "user",
  "bindable": true
}
```

**当不可解析/不可用**:

```json
{
  "valid": false,
  "code_type": null,
  "bindable": false
}
```

**字段说明**:

- `valid` (boolean) - 是否存在且可识别（仅 active 邀请码返回 true）
- `code_type` (`"user" | null`) - 邀请码类型（仅支持用户邀请码）
- `bindable` (boolean) - 当前用户是否可绑定该码（互斥规则与场景约束）

### 业务规则

- 当解析到有效邀请码时，服务端会写入 `resolve_valid` 事件用于行为统计。

---

## 绑定邀请码

### 基本信息

- **路径**: `POST /api/v1/invitations/bind`
- **认证**: Bearer Token（必需）
- **速率限制**: 可能返回 `429`

### 业务规则（服务端强制）

- 每个用户最多绑定一次邀请码。
- 仅支持用户邀请码。
- 用户不可绑定自己邀请码。
- 用户不可绑定“自己邀请过的人”的邀请码。
- 邀请奖励由统一奖励规则执行器按配置发放
- 邀请人数上限由 inviter 当前生效规则控制；当达到上限时，后续新用户无法再绑定该 inviter 的邀请码。
- 奖励发放记录写入权益账本并可追溯。
- `bind_success` 仅记录绑定结果，不重复记录“打开”行为；若当前用户此前缺失该邀请码的 `open` 事件，服务端会在绑定时自动补齐一条 `open`（`trigger=bind_backfill`）。

### 请求体

```json
{
  "code": "K8P2Q7",
  "source": "setup"
}
```

**字段说明**:

- `code` (string) - 待绑定的邀请码
- `source` (string, 必填) - 事件来源标记：`login`、`setup`、`link`、`invite_bind_page`、`invite_share_page`

### 成功响应 (200)

```json
{
  "code_type": "user",
  "reward_contact_limit": 1
}
```

**字段说明**:

- `code_type` (`"user"`) - 实际绑定的码类型
- `reward_contact_limit` (integer) - 对 invitee 发放的联系人上限增量（>=0）

### 错误响应

**400 Bad Request**:

- `"邀请码无效"` - 码不存在/不可用/不满足场景约束
- `"已绑定邀请码"` - 当前用户已绑定过邀请码
- `"邀请人数已达上限"` - 邀请人可邀请人数已达到上限

**429 Too Many Requests**:

- `"操作过于频繁，请稍后再试"`

**500 Internal Server Error**:

- `"系统错误"`

---

## 上报邀请事件

### 基本信息

- **路径**: `POST /api/v1/invitations/events`
- **认证**: Bearer Token（必需）

### 请求体

```json
{
  "event_type": "copy_command",
  "code": "K8P2Q7",
  "source": "invite_share_page",
  "payload": {
    "length": 12
  }
}
```

**字段说明**:

- `event_type` (string) - 事件类型：`resolve_valid`、`bind_success`、`copy_command`、`share_wechat`
- `code` (string, 可选) - 邀请码快照
- `source` (string, 必填) - 事件来源标记：`login`、`setup`、`link`、`invite_bind_page`、`invite_share_page`
- `payload` (object, 可选) - 附加业务信息

### 成功响应 (200)

```json
{
  "accepted": true
}
```

---

## 上报活动归因

### 基本信息

- **路径**: `POST /api/v1/growth/attributions/track`
- **认证**: Bearer Token（必需）

### 请求体

```json
{
  "campaign_code": "SPRING2026",
  "source": "link",
  "payload": {
    "scene": "setup_entry"
  }
}
```

**字段说明**:

- `campaign_code` (string, 必填) - 活动编码（非邀请码）
- `source` (string, 必填) - 归因来源标记
- `payload` (object, 可选) - 附加上下文

### 业务规则

- 采用首次归因模型（first-touch）。
- 每用户最多有效归因一次。
- 归因成功后按奖励规则执行器触发归因奖励（可与邀请/兑换叠加）。

### 成功响应 (200)

```json
{
  "accepted": true,
  "attributed": true
}
```

---

## 兑换兑换码

### 基本信息

- **路径**: `POST /api/v1/redeem-codes/claim`
- **认证**: Bearer Token（必需）

### 请求体

```json
{
  "code": "WELCOME-8M2X"
}
```

### 业务规则

- 支持一次性码与批次通用码。
- 批次级预算、兑换码状态、生效时间窗由服务端强校验。
- 用户对同一码仅可领取一次。
- 兑换成功后按奖励规则执行器发放奖励。

### 成功响应 (200)

```json
{
  "claimed": true,
  "reward_contact_limit": 1
}
```
