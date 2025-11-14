# 联系人请求流程详解

本文档详细说明联系人请求的完整流程，包括AI和用户请求的处理逻辑。

---

## 核心设计原则

### 1. 统一API设计

**原则**: 用户不应区分添加AI还是普通用户，使用同一个API

**实现**:

- 单一API: `POST /api/v1/contact-requests`
- 后端通过查询数据库判断目标类型（先查users表，再查ai_characters表）
- 统一返回格式: `{"message": "请求已发送，等待对方同意"}`
- 防重复请求: 相同请求在有效期内只能有一条

### 2. 联系人请求 vs 联系人

**重要区别**:

- **联系人请求** (`contact_request` 表): 申请记录，状态可能是待处理/已接受/已拒绝等
- **联系人** (`contact` 表): 实际的联系人关系，只有在请求被接受后才创建

**流程**:

1. 发送请求 → 创建 `contact_request` 记录
2. 接受请求 → 创建 `contact` 记录
3. 删除联系人 → 设置 `contact.is_deleted=1`（软删除）
4. 重新添加 → 恢复 `contact.is_deleted=0`

---

## AI联系人请求流程

### 阶段1: 发送请求

**用户操作**: 调用 `POST /api/v1/contact-requests`

```json
{
  "to_qiao_id": "qiao_xm001",  // AI的qiao_id
  "message": "你好",
  "alias": "小萌",
  "tags": ["朋友"]
}
```

**后端处理**:

1. **联系人模块验证** (`services/contact/request_service.py`):

   ```python
   # 1.1 检查是否已添加（包括已删除的）
   existing = await contact_crud.get_user_contact_including_deleted(...)

   if existing:
       if existing.is_deleted == 1:
           # 恢复联系人
           restored_contact = await contact_crud.restore_contact(
               contact=existing,
               alias=request.alias,
               tags={"tags": request.tags} if request.tags else None,
           )
           return {"message": "请求已发送，等待对方同意"}
       else:
           # 已添加
           raise HTTPException(detail="已添加该联系人")

   # 1.1.5 检查是否有pending状态的请求
   existing_request = await contact_request_crud.get_pending_request(
       db, from_qiao_id=user_qiao_id, to_qiao_id=request.to_qiao_id
   )
   if existing_request and existing_request.expires_at > datetime.now():
       # 有效期内已有pending请求，直接返回成功
       return {"message": "请求已发送，等待对方同意"}

   # 1.2 判断目标类型（查询数据库）
   target_user = await user_crud.get_by_qiao_id(db, qiao_id=request.to_qiao_id)
   if target_user:
       target_type = ContactType.USER
   else:
       result = await db.execute(select(AICharacter).where(AICharacter.qiao_id == request.to_qiao_id))
       character = result.scalar_one_or_none()
       if character:
           target_type = ContactType.AI
       else:
           raise HTTPException(status_code=404, detail="目标用户不存在")

   # 1.3 验证AI联系人上限
   if target_type == ContactType.AI:
       ai_count = await contact_crud.count_user_contacts_by_type(
           db, user_qiao_id=user_qiao_id, contact_type=ContactType.AI
       )
       if ai_count >= settings.MAX_AI_CONTACTS:
           raise HTTPException(detail="AI联系人数量已达上限")
   ```

2. **创建联系人请求记录**:

   ```python
   contact_request = await contact_request_crud.create(
       db,
       obj_in=ContactRequestCreate(
           from_qiao_id=user_qiao_id,
           to_qiao_id=request.to_qiao_id,
           message=request.message,
           status=ContactRequestStatus.PENDING,
           ...
       ),
   )
   ```

3. **转发给AI模块** (`services/ai/contact_handler.py`):

   ```python
   decision = await handle_ai_contact_request(
       db=db,
       request_id=contact_request.id,
       from_qiao_id=user_qiao_id,
       to_qiao_id=request.to_qiao_id,
       message=request.message,
   )
   ```

4. **AI模块验证**:

   ```python
   # 验证AI资料模板是否可用
   template = await ai_template_crud.get_by_qiao_id(db, qiao_id=to_qiao_id)
   if not template or not template.is_active:
       raise ValueError("AI template not available")
   
   # 验证信息模板是否可用
   profile_template = await profile_template_crud.get_by_qiao_id(...)
   if not profile_template or not profile_template.is_active:
       raise ValueError("Profile template not available")
   
   # 返回决策
   return AIContactDecision(accepted=True, reason="")
   ```

5. **AI接受后创建联系人**:

   ```python
   if decision.accepted:
       # 创建AI角色
       ai_character = await create_character_from_template(
           db=db,
           template_qiao_id=request.to_qiao_id,
           user_qiao_id=user_qiao_id,
       )
       
       # 创建联系人记录
       contact = await contact_crud.create_with_user(
           db,
           obj_in=ContactCreate(
               contact_type=ContactType.AI,
               contact_qiao_id=ai_character.qiao_id,
               alias=request.alias,
               tags={"tags": request.tags} if request.tags else None,
               ...
           ),
           user_qiao_id=user_qiao_id,
           user_id=user_id,
           conv_id=conv_id,
       )
       
       # 更新请求状态
       contact_request.status = ContactRequestStatus.ACCEPTED
       
       # 发送CHAT_INFO消息
       from enums.templates import CHAT_INFO_TEMPLATES
       content = CHAT_INFO_TEMPLATES[ChatInfoType.CONTACT_ADDED]
       await send_chat_info(
           db=db,
           to_qiao_id=user_qiao_id,
           conv_id=conv_id,
           content=content,
       )
   ```

6. **返回统一响应**:

   ```python
   return {"message": "请求已发送"}
   ```

**用户收到**: `{"message": "请求已发送"}`

**后续**: 用户刷新联系人列表，看到新添加的AI联系人

---

## 用户联系人请求流程

### 阶段1: 发送请求

**用户操作**: 调用 `POST /api/v1/contact-requests`

```json
{
  "to_qiao_id": "qiao_user001",  // 用户的qiao_id
  "message": "你好，我想加你为好友",
  "alias": "小明",
  "tags": ["同事"]
}
```

**后端处理**:

1. **联系人模块验证** (同AI流程):
   - 检查是否已添加
   - 判断目标类型 → `ContactType.USER`

2. **创建联系人请求记录** (同AI流程)

3. **验证目标用户存在**:

   ```python
   target_user = await user_crud.get_by_qiao_id(db, qiao_id=request.to_qiao_id)
   if not target_user:
       raise HTTPException(detail="用户不存在")
   ```

4. **发送NOTIFICATION消息** (`services/message/notification.py`):

   ```python
   await send_contact_request_notification(
       db=db,
       to_qiao_id=request.to_qiao_id,
       from_qiao_id=user_qiao_id,
       request_id=contact_request.id,
       message=request.message,
   )
   ```

5. **通知消息内容**:

   ```json
   {
     "message_type": 9,  // NOTIFICATION
     "conv_id": "",  // 通知消息不需要conv_id
     "content": {
       "notification_type": 1,  // CONTACT_REQUEST
       "action": {
         "type": "navigate",
         "target": "contact_requests"
       },
       "data": {
         "request_id": 123,
         "from_qiao_id": "qiao_user002",
         "from_nickname": "小红",
         "from_avatar": "assets://2345",
         "message": "你好，我想加你为好友"
       }
     }
   }
   ```

6. **存储通知记录** (`notification_push_history` 表):

   ```python
   notification = await notification_crud.create_notification(
       db=db,
       to_qiao_id=request.to_qiao_id,
       notification_type=NotificationType.CONTACT_REQUEST,
       action_data={
           "action": {...},
           "data": {...},
       },
   )
   ```

7. **返回统一响应**:

   ```python
   return {"message": "请求已发送"}
   ```

**用户收到**: `{"message": "请求已发送"}`

**目标用户收到**: NOTIFICATION消息推送

---

### 阶段2: 接受请求

**目标用户操作**: 调用 `POST /api/v1/contact-requests/{id}/accept`

```json
{
  "alias": "小红",
  "tags": ["朋友"]
}
```

**后端处理**:

1. **验证请求**:

   ```python
   contact_request = await contact_request_crud.get(db, id=request_id)
   if not contact_request:
       raise HTTPException(detail="请求不存在")
   
   if contact_request.to_qiao_id != current_user.qiao_id:
       raise HTTPException(detail="无权操作")
   
   if contact_request.status != ContactRequestStatus.PENDING:
       raise HTTPException(detail="请求已处理")
   ```

2. **创建联系人记录**:

   ```python
   contact = await contact_crud.create_with_user(
       db,
       obj_in=ContactCreate(
           contact_type=ContactType.USER,
           contact_qiao_id=contact_request.from_qiao_id,
           alias=request.alias,
           tags={"tags": request.tags} if request.tags else None,
           ...
       ),
       user_qiao_id=current_user.qiao_id,
       user_id=current_user.id,
       conv_id=conv_id,
   )
   ```

3. **更新请求状态**:

   ```python
   contact_request.status = ContactRequestStatus.ACCEPTED
   await db.commit()
   ```

4. **发送CHAT_INFO消息给申请人**:

   ```python
   from enums.templates import CHAT_INFO_TEMPLATES
   content = CHAT_INFO_TEMPLATES[ChatInfoType.CONTACT_ADDED]
   await send_chat_info(
       db=db,
       to_qiao_id=contact_request.from_qiao_id,
       conv_id=conv_id,
       content=content,
   )
   ```

5. **返回ContactResponse**:

   ```python
   return ContactResponse(
       conv_id=contact.conv_id,
       im_conv_id=im_conv_id,
       contact_qiao_id=contact.contact_qiao_id,
       contact_type=ContactType.USER,
       ...
   )
   ```

**目标用户收到**: ContactResponse（完整联系人信息）

**申请人收到**: CHAT_INFO消息（对方已将你添加为联系人）

---

## 联系人恢复逻辑

### 场景

用户A之前添加过用户B，后来删除了（`is_deleted=1`），现在想重新添加。

### 流程

1. **检查联系人关系**:

   ```python
   existing = await contact_crud.get_user_contact_including_deleted(
       db,
       user_qiao_id=user_qiao_id,
       contact_qiao_id=request.to_qiao_id,
   )
   ```

2. **判断是否已删除**:

   ```python
   if existing and existing.is_deleted == 1:
       # 恢复联系人
       restored_contact = await contact_crud.restore_contact(
           db,
           contact=existing,
           alias=request.alias,
           tags={"tags": request.tags} if request.tags else None,
       )
   ```

3. **恢复逻辑** (`crud/contact.py`):

   ```python
   async def restore_contact(
       self,
       db: AsyncSession,
       *,
       contact: Contact,
       alias: Optional[str] = None,
       tags: Optional[dict] = None,
   ) -> Contact:
       """Restore a soft-deleted contact with new settings."""
       contact.is_deleted = 0
       contact.deleted_at = None
       contact.alias = alias
       contact.tags = tags
       contact.remark = None  # Reset remark, not preserving old value
       # conv_id is preserved
       
       db.add(contact)
       await db.commit()
       await db.refresh(contact)
       
       return contact
   ```

4. **返回统一响应**:

   ```python
   return {"message": "请求已发送"}
   ```

### 重要说明

- ✅ **保留**: `conv_id`（对话ID）
- ❌ **不保留**: `remark`（备注信息）
- 🔄 **更新**: `alias`（备注名）、`tags`（标签）使用新值

---

## 消息类型说明

### CHAT_INFO (message_type=4)

**用途**: 聊天界面的信息提示

**特点**:

- 需要 `conv_id`
- 存储到 `message_history` 表
- 显示在聊天界面中

**示例**:

```json
{
  "message_type": 4,
  "conv_id": "conv_xyz789",
  "content": "已添加为联系人",
  "info_type": 1  // CONTACT_ADDED
}
```

### NOTIFICATION (message_type=9)

**用途**: 系统通知推送

**特点**:

- 不需要 `conv_id`（设为空字符串）
- 存储到 `notification_push_history` 表（不存入message_history）
- 不显示在聊天界面中
- 包含action和data，用于前端导航和显示

**示例**:

```json
{
  "message_type": 9,
  "conv_id": "",
  "content": {
    "notification_type": 1,  // CONTACT_REQUEST
    "action": {
      "type": "navigate",
      "target": "contact_requests"
    },
    "data": {
      "request_id": 123,
      "from_qiao_id": "qiao_user002",
      "from_nickname": "小红",
      "from_avatar": "assets://2345",
      "message": "你好，我想加你为好友"
    }
  }
}
```

---

## 数据库表说明

### contact_request 表

**用途**: 存储联系人请求记录

**关键字段**:

- `id`: 请求ID
- `from_qiao_id`: 申请人qiao_id
- `to_qiao_id`: 目标qiao_id
- `message`: 申请消息
- `status`: 请求状态（1=待处理, 2=已接受, 3=已忽略, 8=处理中, 9=失败）
- `created_at`: 创建时间

### contact 表

**用途**: 存储联系人关系

**关键字段**:

- `id`: 联系人关系ID
- `user_qiao_id`: 用户qiao_id
- `contact_qiao_id`: 联系人qiao_id
- `conv_id`: 对话ID
- `alias`: 备注名
- `tags`: 标签（JSONB）
- `remark`: 备注信息
- `is_deleted`: 是否删除（0=否, 1=是）
- `deleted_at`: 删除时间

### notification_push_history 表

**用途**: 存储通知消息记录

**关键字段**:

- `id`: 通知ID
- `to_qiao_id`: 接收人qiao_id
- `notification_type`: 通知类型（1=联系人请求）
- `action_data`: 通知数据（JSONB）
- `status`: 发送状态（1=已发送, 2=失败）
- `created_at`: 创建时间

---

## 错误处理

### 验证失败

**原则**: 前端应做前置验证，后端验证失败时不返回详细错误信息

**示例**:

```python
# ❌ 错误示例
raise HTTPException(detail="AI联系人数量已达上限")

# ✅ 正确示例（如果前端已验证）
# 不返回任何内容，或返回通用错误
raise HTTPException(detail="操作异常")
```

### AI验证失败

**处理**: AI模块验证失败时，返回通用错误，不暴露内部细节

```python
try:
    decision = await handle_ai_contact_request(...)
except ValueError as e:
    logger.error("ai_validation_failed", error=str(e))
    raise HTTPException(detail="添加失败，请稍后再试")
```

### 通知发送失败

**处理**: 非关键操作，记录日志但不中断流程

```python
try:
    await send_contact_request_notification(...)
except Exception as e:
    logger.error("notification_send_failed", error=str(e))
    # 继续执行，不抛出异常
```

---

## 实施文件清单

### 已完成

1. ✅ `backend/app/crud/message/notification.py` - 通知CRUD
2. ✅ `backend/app/crud/message/__init__.py` - 导出通知CRUD
3. ✅ `backend/app/services/message/notification.py` - 通知发送服务
4. ✅ `backend/app/crud/contact.py` - 联系人恢复方法
5. ✅ `backend/app/services/contact/request_service.py` - 用户请求处理

### 待修改

1. ⏳ `backend/app/api/v1/contacts.py` - 修改响应模型为dict
2. ⏳ `backend/app/services/contact/request_service.py` - 修改AI请求返回类型
3. ⏳ `backend/app/services/contact/request_service.py` - 删除不需要的导入

### 待实施

1. ⏳ `GET /api/v1/contact-requests` - 获取请求列表
2. ⏳ `POST /api/v1/contact-requests/{id}/accept` - 接受请求
3. ⏳ `POST /api/v1/contact-requests/{id}/reject` - 拒绝请求

---

## 总结

### 核心要点

1. **统一API**: 一个API处理所有联系人请求
2. **统一返回**: 都返回 `{"message": "请求已发送"}`
3. **后端路由**: 自动判断目标类型并路由
4. **AI虚拟请求**: AI自动处理，立即创建联系人
5. **用户手动请求**: 发送通知，等待手动接受
6. **联系人恢复**: 自动恢复已删除的联系人关系

### 设计优势

- ✅ 用户体验统一，无需区分AI和用户
- ✅ 后端逻辑清晰，易于维护
- ✅ 扩展性好，易于添加新的联系人类型
- ✅ 符合SOLID原则，单一职责明确

---

## 状态详细说明

### 状态枚举值

```python
class ContactRequestStatus(IntEnum):
    PENDING = 1      # 待处理
    ACCEPTED = 2     # 已接受
    IGNORED = 3      # 已忽略
    PROCESSING = 8   # 处理中
    FAILED = 9       # 失败
```

### 状态转换流程

```
PENDING (1)
    ↓ (worker锁定并标记)
PROCESSING (8)
    ↓
    ├─→ ACCEPTED (2)  ✅ AI接受，创建联系人成功
    ├─→ IGNORED (3)   ✅ 业务拒绝（模板不可用、AI不接受等）
    └─→ FAILED (9)    ❌ 系统错误（数据库错误、代码bug等）
```

### 状态说明

#### PENDING (1) - 待处理
**定义**: 请求已创建，等待处理

**触发场景**:
- 用户发送联系人请求后的初始状态
- AI请求：等待后台worker处理
- 用户请求：等待目标用户手动接受/拒绝

**特点**:
- 有过期时间(`expires_at`)
- Worker只处理未过期的PENDING请求
- 过期的PENDING请求不会被处理，但保留在数据库中

---

#### PROCESSING (8) - 处理中
**定义**: Worker正在处理该请求

**触发场景**:
- Worker锁定PENDING请求后立即标记为PROCESSING
- 防止其他worker重复处理

**特点**:
- 只有AI请求会进入此状态
- 用户请求不经过此状态
- 标记后立即commit，释放数据库锁

---

#### ACCEPTED (2) - 已接受
**定义**: 请求被接受，联系人关系已创建

**触发场景**:
- AI接受请求，成功创建AI角色和联系人记录
- 用户手动接受请求，成功创建联系人记录

**特点**:
- 终态，不会再变更
- 对应的`contact`记录已创建

---

#### IGNORED (3) - 已忽略
**定义**: 业务逻辑判断后的正常拒绝

**触发场景**:
- ✅ AI模板不存在
- ✅ AI模板状态为inactive（不可用）
- ✅ 用户已达AI联系人上限
- ✅ AI决定不接受该请求（业务逻辑）
- ✅ 用户主动拒绝请求

**特点**:
- 终态，不会再变更
- 这是正常的业务流程，不需要告警
- 记录info级别日志

**代码示例**:
```python
# AI模块验证失败
if not template or template.status != 1:
    raise ValueError("AI template not available")

# 捕获并标记为IGNORED
except ValueError as e:
    contact_request.status = ContactRequestStatus.IGNORED
    logger.info("ai_contact_request_ignored", reason=str(e))
```

---

#### FAILED (9) - 失败
**定义**: 系统错误导致处理失败

**触发场景**:
- ❌ 数据库连接失败
- ❌ 网络超时
- ❌ 代码bug导致的未捕获异常
- ❌ 第三方服务调用失败
- ❌ 数据完整性错误

**特点**:
- 终态，不会再变更
- 需要监控和告警
- 记录error级别日志（带exc_info=True）
- 理论上可以重试（修复后）

**代码示例**:
```python
# 系统错误
except Exception as e:
    contact_request.status = ContactRequestStatus.FAILED
    logger.error("ai_contact_request_failed", error=str(e), exc_info=True)
```

---

## 异步处理机制

### Worker轮询架构

**文件**: `backend/app/services/contact/request_worker.py`

**工作流程**:

1. **轮询查询** (每2秒):
   ```python
   SELECT * FROM contact_requests
   WHERE status = 1  -- PENDING
     AND to_type = 2  -- AI
     AND expires_at > NOW()  -- 未过期
   FOR UPDATE SKIP LOCKED
   LIMIT 10
   ```

2. **立即标记PROCESSING**:
   ```python
   for req in batch:
       req.status = ContactRequestStatus.PROCESSING
   await db.commit()  # 释放锁
   ```

3. **独立处理每个请求**:
   ```python
   for req in batch:
       async with SessionLocal() as process_db:
           await _process_one(process_db, req)
   ```

4. **更新最终状态**:
   - 成功 → ACCEPTED
   - 业务拒绝 → IGNORED
   - 系统错误 → FAILED

### 过期请求处理

**策略**: 查询时过滤，不主动标记

**原因**:
- ✅ 符合YAGNI原则，MVP不需要额外的定时任务
- ✅ 节省系统资源，不处理无效请求
- ✅ 简单直接，通过`expires_at > NOW()`过滤

**查询示例**:
```sql
-- Worker只处理未过期的请求
SELECT * FROM contact_requests
WHERE status = 1 
  AND expires_at > NOW()  -- 过滤过期
```

**过期请求状态**:
- 保持PENDING状态
- 不会被worker处理
- 可以通过查询识别: `status = 1 AND expires_at < NOW()`

### 事务管理

**关键设计**: PROCESSING状态 + 独立session

**问题**: 如果在事务中锁定并处理，会导致长事务

**解决方案**:
1. 在事务中锁定请求
2. 立即标记为PROCESSING并commit（释放锁）
3. 每个请求使用独立session处理
4. 处理失败不影响其他请求

**优势**:
- ✅ 避免长事务
- ✅ 防止重复处理（PROCESSING状态保护）
- ✅ 支持水平扩展（多worker）
- ✅ 失败隔离

---

## 监控建议

### 监控FAILED状态（需要告警）

```sql
-- 查看最近的FAILED请求
SELECT id, from_qiao_id, to_qiao_id, created_at, updated_at
FROM contact_requests 
WHERE status = 9 
ORDER BY updated_at DESC 
LIMIT 20;

-- 统计FAILED数量（如果过多需要告警）
SELECT COUNT(*) as failed_count
FROM contact_requests 
WHERE status = 9 
AND updated_at > NOW() - INTERVAL '1 hour';
```

**告警阈值建议**: 1小时内FAILED > 10

### 监控IGNORED状态（仅统计）

```sql
-- 统计IGNORED数量
SELECT COUNT(*) as ignored_count
FROM contact_requests 
WHERE status = 3 
AND created_at > NOW() - INTERVAL '1 day';
```

### 监控过期请求

```sql
-- 查看过期但未处理的请求数量
SELECT COUNT(*) as expired_pending_count
FROM contact_requests 
WHERE status = 1 
AND expires_at < NOW();
```

### 监控PROCESSING状态（异常检测）

```sql
-- 查看长时间处于PROCESSING的请求（可能是worker崩溃）
SELECT id, from_qiao_id, to_qiao_id, updated_at
FROM contact_requests 
WHERE status = 8 
AND updated_at < NOW() - INTERVAL '5 minutes'
ORDER BY updated_at;
```

**说明**: 正常情况下PROCESSING状态应该很快转换为其他状态，如果长时间停留可能是worker崩溃。

---

## 数据库索引优化

### 已添加的索引

```sql
-- Worker查询优化索引（部分索引）
CREATE INDEX idx_contact_requests_worker_query 
ON contact_requests(status, to_type, expires_at) 
WHERE status IN (1, 8);  -- 只索引PENDING和PROCESSING

-- 过期时间索引
CREATE INDEX idx_contact_requests_expires_at 
ON contact_requests(expires_at);
```

### 索引说明

1. **组合索引**: 支持worker的复合查询条件
2. **部分索引**: 只索引PENDING和PROCESSING状态，减少索引大小
3. **包含expires_at**: 支持过期时间过滤

---

## 重要变更说明

### 相比原设计的变更

1. **删除EXPIRED(4)状态**:
   - 原因: MVP不需要主动标记过期
   - 替代方案: 查询时通过`expires_at`过滤

2. **删除REJECTED(5)状态**:
   - 原因: MVP暂不需要区分拒绝和忽略
   - 替代方案: 统一使用IGNORED(3)

3. **添加PROCESSING(8)状态**:
   - 原因: 防止worker重复处理
   - 值为8: 与AI相关状态保持距离

4. **添加FAILED(9)状态**:
   - 原因: 区分业务拒绝和系统错误
   - 用途: 监控和告警

### 向后兼容性

- 数据库中status=4,5的旧记录不会被处理
- 新代码不会创建status=4,5的记录
- 建议清理: 可以将旧的4,5状态批量更新为3(IGNORED)
