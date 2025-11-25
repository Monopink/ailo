# 联系人请求流程详解

本文档详细说明联系人请求的完整流程，包括AI和用户请求的处理逻辑。

---

## 核心设计原则

### Square 曝光与联系人处理

- `square_type_entries` 决定哪些 AI 类型对用户可见，包含分类、曝光策略、状态等字段
- 模板类型与模板库存只控制“用户拿到 qiao_id 后能否创建联系人”，不会影响 Square 曝光
- 所有文案对外只出现 `qiao_id`，后台根据 `ai_personas` 管理 persona 与 `profiles` 展示信息

### 1. 统一API设计

**原则**: 用户不应区分添加AI还是普通用户，使用同一个API

**实现**:

- 单一API: `POST /api/v1/contact-requests`
- 后端通过查询数据库判断目标类型（先查users表，再查ai_instances表）
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

1. **联系人模块验证**：

   - 检查是否已添加该联系人（包括已删除的）
   - 如果已删除，则恢复联系人关系并返回成功
   - 如果已添加且未删除，返回错误提示
   - 检查是否有pending状态的有效请求，如有则直接返回成功
   - 判断目标类型（先查users表，再查ai_personas表）
   - 如果是AI类型，验证AI联系人数量是否达到上限

2. **创建联系人请求记录**：

   - 创建 contact_request 记录，状态为 PENDING
   - 记录申请人和目标的 qiao_id、申请消息等信息

3. **转发给AI模块**：

   - 调用 AI 联系人处理服务
   - 传递请求ID、申请人qiao_id、目标qiao_id和申请消息

4. **AI模块验证**：

   - 通过 qiao_id 查找 ai_personas（注意：查询的是 persona，不是 instance）
   - 检查 persona 是否存在且状态为可用（status=1）
   - 检查 persona 是否可复用，如果不可复用且已被使用（status=3），则拒绝
   - 查找该 type 下的可用模板
   - 如果没有可用模板，标记请求为挂起状态（failure_code="NO_TEMPLATE_AVAILABLE"），返回决策为等待模板
   - 如果有可用模板，返回决策为接受

5. **AI接受后创建联系人**：

   - 从 persona + template 创建 AI instance
   - Instance 继承 persona.qiao_id（不生成新的 qiao_id）
   - Instance 不创建新 profile（共享 persona 的 profile，owner_type=2）
   - 设置 creation_metadata.source = "persona"
   - 创建联系人记录，使用 persona.qiao_id
   - 如果模板不可复用，标记模板为已使用（status=3）
   - 如果 persona 不可复用，标记为已使用（status=3）

6. **返回统一响应**：

   - 返回 {"message": "请求已发送"}

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

1. **联系人模块验证**（同AI流程）：
   - 检查是否已添加
   - 判断目标类型 → ContactType.USER

2. **创建联系人请求记录**（同AI流程）

3. **验证目标用户存在**：

   - 通过 qiao_id 查询 users 表
   - 如果用户不存在，返回错误

4. **发送NOTIFICATION消息**：

   - 调用通知发送服务
   - 发送联系人请求通知给目标用户

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

6. **存储通知记录**：

   - 创建 notification_push_history 记录
   - 记录通知类型、接收人、通知数据等信息

7. **返回统一响应**：

   - 返回 {"message": "请求已发送"}

**用户收到**: `{"message": "请求已发送"}`

**目标用户收到**: NOTIFICATION消息推送

---

## 模板不足与重试流程

当某个 `ai_type` 暂时没有可用模板时，请求不会被拒绝或失败，而是保持在 `PENDING` 状态并记录失败原因：

1. **记录失败元数据**
   - `contact_requests.failure_code`：例如 `NO_TEMPLATE_AVAILABLE`, `MANUAL_PROVISION_REQUIRED`。
   - `contact_requests.failure_detail`：JSON，建议至少包含 `ai_type_id`、`qiao_id`、`request_id` 等信息，方便后台定位问题。
   - `retry_count`：每次自动或手动重试都会递增，用于运营监控。
   - `last_retry_at`：最近一次重试尝试的时间。

2. **Admin 视图**
   - 后台和 Starlette Admin 需要提供“待补库存”列表，筛选 `(status=1 AND failure_code IS NOT NULL)` 的记录。
   - 管理员补充模板后，可直接在该视图触发“重试”；前端 contacts 视图也需要同样的按钮。
3. **重试逻辑**
   - 重试会清空 `failure_code`/`failure_detail`，更新 `last_retry_at`、`retry_count`，然后重新执行模板选择流程。
   - 成功 → `status=ACCEPTED`，`failure_*` 字段保持 NULL。
   - 再次失败 → 重新写入 `failure_code`/`failure_detail`，以便管理员继续处理。
4. **用户端幂等**
   - 用户重复提交相同 `(from_qiao_id, to_qiao_id)` 的请求时，系统不会新建 `contact_requests`，而是触发同一条记录的重试。
   - 客户端始终只收到统一文案 `{"message": "请求已发送"}`，无需了解挂起细节。
   - 若上一条请求已经过期或进入终态，新的请求会生成新的记录并重新走审批流程。

所有挂起数据都通过 `contact_requests` 维护，不需要额外的工作队列或表。后续实现必须确保代码层面校验与数据库约束一致，避免重复创建记录。

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

1. **验证请求**：

   - 获取 contact_request 记录
   - 验证请求是否存在
   - 验证当前用户是否有权操作（to_qiao_id 必须是当前用户）
   - 验证请求状态是否为 PENDING

2. **创建联系人记录**：

   - 创建 contact 记录，类型为 USER
   - 使用申请人的 qiao_id 作为 contact_qiao_id
   - 设置备注名、标签等信息
   - 关联对话 ID

3. **更新请求状态**：

   - 将 contact_request.status 更新为 ACCEPTED
   - 提交数据库事务

4. **发送CHAT_INFO消息给申请人**：

   - 使用 CHAT_INFO_TEMPLATES 中的 CONTACT_ADDED 模板
   - 发送消息到申请人的对话

5. **返回ContactResponse**：

   - 返回完整的联系人信息
   - 包含 conv_id、im_conv_id、contact_qiao_id、contact_type 等字段

**目标用户收到**: ContactResponse（完整联系人信息）

**申请人收到**: CHAT_INFO消息（对方已将你添加为联系人）

---

## 联系人恢复逻辑

### 场景

用户A之前添加过用户B，后来删除了（`is_deleted=1`），现在想重新添加。

### 流程

1. **检查联系人关系**：

   - 查询包括已删除的联系人记录
   - 使用 user_qiao_id 和 contact_qiao_id 进行查询

2. **判断是否已删除**：

   - 如果 existing.is_deleted == 1，则恢复联系人
   - 调用 restore_contact 方法恢复联系人关系

3. **恢复逻辑**：

   - 设置 is_deleted = 0
   - 清空 deleted_at
   - 更新 alias（备注名）为新值
   - 更新 tags（标签）为新值
   - 重置 remark（备注信息）为 NULL
   - 保留 conv_id（对话ID）
   - 提交到数据库并刷新记录

4. **返回统一响应**：

   - 返回 {"message": "请求已发送"}

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
- `failure_code`: 模板不足等业务失败原因（挂起才会填写）
- `failure_detail`: JSON，描述缺失的模板类型、qiao_id、重试次数等
- `retry_count`: 手动/自动重试计数
- `last_retry_at`: 最近一次重试时间
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

**处理方式**: 返回通用错误信息，不暴露内部细节

### AI验证失败

**处理**: AI模块验证失败时，返回通用错误，不暴露内部细节

**记录**: 记录错误日志，包含详细错误信息用于调试

### 通知发送失败

**处理**: 非关键操作，记录日志但不中断流程

**记录**: 记录错误日志，但继续执行后续流程

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

- AI接受请求，成功创建 AI instance 和联系人记录
- 用户手动接受请求，成功创建联系人记录

**特点**:

- 终态，不会再变更
- 对应的`contact`记录已创建

---

#### IGNORED (3) - 已忽略

**定义**: 业务逻辑判断后的正常拒绝

**触发场景**:

- ✅ 用户已达AI联系人上限
- ✅ AI决定不接受该请求（业务逻辑）
- ✅ 用户主动拒绝请求
- ✅ 管理端明确拒绝（例如人工审核不通过）

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

1. **轮询查询**（每2秒）：

   - 查询 status=PENDING 且 to_type=AI 且未过期的请求
   - 使用 FOR UPDATE SKIP LOCKED 防止并发冲突
   - 每次最多处理 10 条记录

2. **立即标记PROCESSING**：

   - 遍历批次中的每个请求
   - 将 status 更新为 PROCESSING
   - 立即提交事务，释放数据库锁

3. **独立处理每个请求**：

   - 为每个请求创建独立的数据库 session
   - 调用处理函数处理单个请求

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

**查询示例**：

- Worker 只处理未过期的请求
- 使用 expires_at > NOW() 过滤过期请求

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

> 只有 `status=PENDING` 且 `expires_at` 大于当前时间的记录可以被上述逻辑复用。`ACCEPTED`、`IGNORED`、`FAILED`、`PROCESSING` 以及已过期的记录都视为终态，新的请求会重新写入 `contact_requests`。

---

## 模板选择策略

### 选择规则

当用户添加 AI 联系人时，系统按以下策略选择模板：

1. **优先不可复用模板**：优先选择 `is_reusable=0` 的单次使用模板
2. **优先级降序排列**：按 `priority DESC` 排序（数字越大优先级越高）
3. **同优先级随机选择**：如果最高优先级有多个模板，随机选择一个
4. **回退到可复用模板**：如果没有不可复用模板，对 `is_reusable=1` 的模板应用相同规则

### 实现逻辑

**选择策略**：

1. 优先查询不可复用模板（is_reusable=0）
   - 按 priority DESC 排序（数字越大优先级越高）
   - 同优先级使用随机排序
   - 限制返回 1 条记录
   - 使用 FOR UPDATE SKIP LOCKED 防止并发冲突

2. 如果没有不可复用模板，回退到可复用模板（is_reusable=1）
   - 应用相同的排序和选择规则

3. 返回选中的模板或 NULL

### 优先级字段说明

- **字段名称**：`ai_templates.priority`
- **数据类型**：INTEGER
- **默认值**：1
- **排序规则**：DESC（降序）
- **优先级含义**：数字越大，优先级越高

**示例**：

| 模板 | priority | is_reusable | 选择顺序 |
|------|----------|-------------|----------|
| 模板A | 10 | 0 | 1（最高优先级，不可复用） |
| 模板B | 10 | 0 | 1（同优先级，随机） |
| 模板C | 5 | 0 | 2 |
| 模板D | 10 | 1 | 3（可复用，最高优先级） |
| 模板E | 1 | 1 | 4 |

### 并发控制

- 使用 `FOR UPDATE SKIP LOCKED` 防止并发冲突
- 单次使用模板被选中后立即标记为 `status=3`（已使用）
- 事务内完成模板选择、实例创建、联系人创建的原子操作
