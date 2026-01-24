# 联系人管理

联系人管理负责处理联系人关系的更新、删除和恢复操作。

API 接口定义详见：[api/contacts.md](../../api/contacts.md)

## 核心设计原则

### 软删除机制

联系人删除采用软删除（is_deleted=1），而不是物理删除：

**原因**：

- 保留历史记录，便于数据分析
- 支持恢复功能
- 保留 conv_id，避免消息历史丢失

**实现**：

- 删除时：设置 is_deleted=1, deleted_at=NOW()
- 查询时：过滤 is_deleted=0
- 恢复时：设置 is_deleted=0, deleted_at=NULL

### 联系人恢复

用户删除联系人后再次添加，会恢复原有关系：

**保留内容**：

- conv_id（对话 ID）- 保持消息历史连续性
- contact_qiao_id - 联系人标识
- contact_type - 联系人类型

**不保留内容**：

- remark（备注信息）- 清空，用户可重新填写

**更新内容**：

- alias（备注名）- 使用新值
- tags（标签）- 使用新值
- is_deleted - 设置为 0
- deleted_at - 清空

## 联系人信息更新

### 更新逻辑

接口：`PUT /api/v1/contacts/{conv_id}`（详见 [api/contacts.md](../../api/contacts.md#更新联系人信息)）

**处理流程**：

1. **验证权限**：
   - 通过 conv_id 查询 contact 记录
   - 验证 user_qiao_id 是否为当前用户
   - 验证 is_deleted=0

2. **部分更新**：
   - 只更新传入的字段
   - 未传入的字段保持不变
   - 支持传入 null 清空字段（除 alias 和 tags）

3. **更新时间戳**：
   - 自动更新 updated_at

4. **返回完整信息**：
   - 返回更新后的联系人详情
   - 包含 profile 信息

## 联系人屏蔽

### 屏蔽功能

屏蔽联系人后：

- 不会收到对方的消息
- 不会删除联系人关系
- 不会删除聊天记录
- 可以随时取消屏蔽

### 屏蔽逻辑

接口：`POST /api/v1/contacts/{conv_id}/block`（详见 [api/contacts.md](../../api/contacts.md#屏蔽联系人)）

**处理流程**：

1. **验证权限**（同更新逻辑）

2. **更新状态**：
   - 设置 is_blocked=1
   - 更新 updated_at

3. **消息处理**：
   - 后续消息会被过滤
   - 不会存入 message_history
   - 不会推送给用户

### 取消屏蔽

接口：`POST /api/v1/contacts/{conv_id}/unblock`（详见 [api/contacts.md](../../api/contacts.md#取消屏蔽联系人)）

**处理流程**：

- 设置 is_blocked=0
- 恢复正常消息接收

## 联系人删除

### 删除逻辑

接口：`DELETE /api/v1/contacts/{conv_id}`（详见 [api/contacts.md](../../api/contacts.md#删除联系人)）

**处理流程**：

1. **验证权限**（同更新逻辑）

2. **软删除**：
   - 设置 is_deleted=1
   - 设置 deleted_at=NOW()
   - 更新 updated_at

3. **不删除内容**：
   - 不删除 contact 记录
   - 不删除消息历史（客户端本地管理）
   - 不删除 AI instance（如果是 AI 联系人）

### AI 联系人删除

**特殊处理**：

- AI instance 不会被删除
- instance.status 保持不变
- 如果其他用户也添加了同一个 AI，不受影响

**原因**：

- AI instance 可能被多个用户共享（通过 qiao_id）
- 删除联系人只是解除关系，不影响 AI 本身

## 联系人恢复

### 恢复场景

用户删除联系人后，再次添加同一个 qiao_id：

**触发时机**：

- 调用 `POST /api/v1/contact-requests` 时
- 检测到已存在 is_deleted=1 的联系人记录

**处理流程**：

1. **查询已删除的联系人**：
   - 条件：user_qiao_id=当前用户 AND contact_qiao_id=目标 qiao_id AND is_deleted=1

2. **恢复联系人关系**：
   - 设置 is_deleted=0
   - 清空 deleted_at
   - 更新 alias（使用新值）
   - 更新 tags（使用新值）
   - 清空 remark（不保留旧值）
   - 保留 conv_id（保持消息历史连续性）
   - 更新 updated_at

3. **返回统一响应**：
   - `{"message": "请求已发送"}`
   - 与新建联系人请求的响应一致

### 恢复 vs 新建

**恢复**（is_deleted=1 存在）：

- 保留 conv_id
- 更新 alias 和 tags
- 清空 remark
- 立即生效，无需等待接受

**新建**（不存在或已过期）：

- 生成新的 conv_id
- 创建新的 contact_request
- 需要等待接受（如果是用户联系人）

## 联系人列表查询

接口：`GET /api/v1/contacts`（详见 [api/contacts.md](../../api/contacts.md#获取联系人列表)）

**查询逻辑**：

- 过滤条件：user_qiao_id=当前用户 AND is_deleted=0
- 排序规则：is_pinned DESC, updated_at DESC
- 分页：cursor-based pagination

## 数据一致性

### Profile 信息

联系人的 profile 信息来自 profiles 表：

**AI 联系人**：

- owner_type = 2（AI Persona）
- owner_id = persona.id
- 多个用户共享同一个 profile

**用户联系人**：

- owner_type = 1（User）
- owner_id = user.id
- 每个用户有自己的 profile

**查询逻辑**：

- 通过 contact_qiao_id 查询 profiles 视图
- 视图自动关联 owner_type 和 owner_id

详见：[data-dict/profile.md](../../data-dict/profile.md)

### 消息历史

删除联系人不影响消息历史：

**客户端本地存储**：

- 消息存储在客户端本地数据库
- 删除联系人不删除本地消息
- 用户可以手动清空聊天记录

**服务端存储**：

- message_history 表保留除 TYPING 外的消息
- 通过 conv_id 关联
- 恢复联系人后，conv_id 不变，消息历史连续

详见：[spec/message/README.md](../message/README.md)

## 异常处理

### 联系人不存在或无权操作

**处理原则**：

- 返回 HTTP 400 Bad Request
- 错误信息："操作异常"
- 不暴露是否存在该联系人（保护隐私）

### 重复操作

**幂等性**：

- 重复屏蔽已屏蔽的联系人 → 返回成功
- 重复删除已删除的联系人 → 返回成功
- 不返回错误，保证幂等性

## 数据表

详见：[data-dict/contact.md](../../data-dict/contact.md)
