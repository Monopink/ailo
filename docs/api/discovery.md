# 发现页面接口

## 接口列表

- [获取广场随机联系人](#获取广场随机联系人) - `GET /api/v1/discovery/square`
- [获取陌生人详情](#获取陌生人详情) - `GET /api/v1/discovery/profile/{qiao_id}`

---

## 获取广场随机联系人

### 基本信息

- **路径**: `GET /api/v1/discovery/square`
- **认证**: Bearer Token（必需）
- **速率限制**: 由配置控制，默认60秒

### 请求参数

**查询参数**:

- `category` (integer, 可选) - 分类筛选
  - 可选值: 1=交友, 2=恋爱, 3=倾诉, 4=闺蜜, 5=同好
  - 默认为1（交友）
- `force_refresh` (boolean, 可选) - 强制刷新，跳过频率限制（仅测试用）

### 成功响应 (200)

```json
{
  "items": [
    {
      "qiao_id": "qiao_xm001",
      "category": "1",
      "nickname": "小萌",
      "gender": 2,
      "avatar_url": "assets://8923",
      "bio": "喜欢音乐和电影",
      "tags": ["音乐", "电影"],
      "region": "上海"
    }
  ],
  "refresh_available_at": "2024-01-01T12:01:00Z"
}
```

**字段说明**:

- `items` (array) - 推荐的联系人列表
  - `qiao_id` (string) - 联系人的qiao_id
  - `category` (string) - 分类
  - `nickname` (string) - 昵称
  - `gender` (integer) - 性别，枚举值见：`backend/app/enums/common.py` - `Gender`
  - `avatar_url` (string) - 头像URL
  - `bio` (string) - 个人简介
  - `tags` (array) - 标签列表
  - `region` (string) - 地区

- `refresh_available_at` (string) - 下次可刷新的时间（ISO 8601格式）

### 错误响应

**429 Too Many Requests**:

- `"刷新过于频繁，请稍后再试"` - 超过速率限制

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

### 业务说明

**配置项**（system_configs表）:

- `square_recommend_count` (NUMBER) - 每次推荐的联系人数量，默认10
- `square_refresh_interval` (NUMBER) - 刷新间隔（秒），默认60

**推荐逻辑**:

- 每次返回随机的联系人列表
- 推荐数量由配置控制
- 刷新频率由配置控制
- `force_refresh=true` 可跳过频率限制（仅测试用）
- 仅返回**已绑定 Profile 的活跃 Persona**

### 相关接口

- [获取陌生人详情](#获取陌生人详情)
- [发送联系人申请](contact-requests.md#发送联系人申请)

---

## 获取陌生人详情

### 基本信息

- **路径**: `GET /api/v1/discovery/profile/{qiao_id}`
- **认证**: 无需认证
- **说明**: 公开访问，用于分享和外链

### 路径参数

- `qiao_id` (string, 必填) - 陌生人的qiao_id

### 成功响应 (200)

```json
{
  "qiao_id": "qiao_abc123",
  "nickname": "小乔",
  "gender": 2,
  "avatar_url": "assets://1234",
  "bio": "喜欢和大家聊天",
  "region": "北京",
  "category": "1"
}
```

**字段说明**:

- `qiao_id` (string) - 联系人的qiao_id
- `nickname` (string) - 昵称
- `gender` (integer) - 性别，枚举值见：`backend/app/enums/common.py` - `Gender`
- `avatar_url` (string) - 头像URL
- `bio` (string) - 个人简介
- `region` (string) - 地区
- `category` (string) - 分类

### 错误响应

**400 Bad Request**:

- `"操作异常"` - 用户不存在

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

### 业务说明

- 公开访问，无需认证
- 返回 profiles 视图数据
- 只返回 active 状态的资料
- 不返回是否已添加联系人的状态
- 用于发现页面点击联系人后查看详情
- 支持分享和外链直达

### 相关接口

- [发送联系人申请](contact-requests.md#发送联系人申请)
