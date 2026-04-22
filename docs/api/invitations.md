# 邀请码、活动归因与兑换码接口

## 接口列表

- [获取我的邀请码](#获取我的邀请码) - `GET /api/v1/invitations/code`
- [获取邀请码绑定状态](#获取邀请码绑定状态) - `GET /api/v1/invitations/binding-status`
- [获取邀请统计](#获取邀请统计) - `GET /api/v1/invitations/stats`
- [获取邀请分享文案](#获取邀请分享文案) - `GET /api/v1/invitations/share`
- [邀请短链跳转](#邀请短链跳转) - `GET /i/{token}`
- [匿名邀请码识别](#匿名邀请码识别) - `POST /api/v1/public/invitations/intake`
- [登录态邀请码识别](#登录态邀请码识别) - `POST /api/v1/invitations/intake`
- [解析邀请码](#解析邀请码) - `POST /api/v1/invitations/resolve`
- [绑定邀请码](#绑定邀请码) - `POST /api/v1/invitations/bind`
- [上报邀请事件](#上报邀请事件) - `POST /api/v1/invitations/events`
- [上报活动归因](#上报活动归因) - `POST /api/v1/growth/attributions/track`
- [兑换兑换码](#兑换兑换码) - `POST /api/v1/redeem-codes/claim`

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

## 获取邀请统计

### 基本信息

- **路径**: `GET /api/v1/invitations/stats`
- **认证**: Bearer Token（必需）

### 成功响应 (200)

```json
{
  "success_invite_count": 12,
  "max_invite_count": 3,
  "reward_contact_limit_per_invite": 1,
  "max_reward_contact_limit_total": 3,
  "rewarded_contact_limit_total": 2
}
```

**字段说明**:

- `success_invite_count` (integer) - 当前用户已邀请成功人数（即成功绑定到该用户邀请码的人数）
- `max_invite_count` (integer | null) - 当前用户最多可邀请人数（`null` 表示不限制）
- `reward_contact_limit_per_invite` (integer) - 每次邀请成功可获得的联系人上限增量
- `max_reward_contact_limit_total` (integer | null) - 可获得联系人上限总增量（`max_invite_count * reward_contact_limit_per_invite`，`null` 表示不限制）
- `rewarded_contact_limit_total` (integer) - 当前用户已获得的联系人上限总增量

---

## 获取邀请分享文案

### 基本信息

- **路径**: `GET /api/v1/invitations/share`
- **认证**: Bearer Token（必需）

### 成功响应 (200)

```json
{
  "code": "K8P2Q7",
  "text": "敲敲好友都在用，K8P2Q7 https://example.com/i/K8P2Q7",
  "link": "https://example.com/i/K8P2Q7",
  "share_card": {
    "title": "来敲敲AI，对话敲多新奇有趣",
    "path": "/pages/setup/setup?inviteCode=K8P2Q7",
    "image_url": "https://cortex.qiaoqiaoai.cn/share/invite-share-card.png",
    "slot_code": "invite_share_card",
    "channel": "mini_program",
    "version": 1
  }
}
```

**字段说明**:

- `code` (string) - 当前用户的邀请码
- `text` (string) - 后端模板渲染后的邀请文案（模板可包含 `{{code}}`、`{{link}}` 或纯文本）
- `link` (string) - 邀请短链（`/i/{token}`）
- `share_card` (object) - 邀请分享卡片配置
- `share_card.title` (string) - 分享标题
- `share_card.path` (string) - 小程序分享路径
- `share_card.image_url` (string) - 分享图片公网 URL（HTTPS）
- `share_card.slot_code` (string) - 运营槽位标识（当前为 `invite_share_card`）
- `share_card.channel` (string) - 渠道标识（当前为 `mini_program`）
- `share_card.version` (integer) - 槽位配置版本号（>=1）

---

## 邀请短链跳转

### 基本信息

- **路径**: `GET /i/{token}`
- **认证**: 无

### 成功行为

- 校验 `token` 对应有效邀请码后，后端生成微信 URL Link 并返回 302 重定向。

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
  "invite_code": null
}
```

**字段说明**:

- `source` (string, 必填) - 来源标记：`login`、`setup`、`link`、`invite_bind_page`、`invite_share_page`
- `trigger` (string, 必填) - 触发来源标记（如：`clipboard`、`link_param`、`manual_input`）
- `raw_text` (string, 可选) - 原始文本（如剪贴板）
- `invite_code` (string, 可选) - 直传邀请码（如链接参数）

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
- 仅当 `trigger=clipboard` 时写入 `invite_recognition_logs`（用于剪贴板解析统计）。
- 识别日志对 `(actor_user_id, source, trigger, raw_text)` 在 2 秒窗口内做去重，避免重复噪声。
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
  "invite_code": null
}
```

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

- 仅当 `trigger=clipboard` 时写入识别日志。
- 仅当邀请码有效时记入 `open` 事件。
- 识别日志对 `(actor_user_id, source, trigger, raw_text)` 在 2 秒窗口内做去重，避免重复噪声。
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
- 邀请奖励由统一奖励规则执行器按配置发放：
  - invitee 奖励触发：绑定成功；
  - inviter 奖励触发：invitee 完成 setup；若 invitee 已完成 setup，则绑定成功后立即触发。
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
