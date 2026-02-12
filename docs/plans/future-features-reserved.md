# 未来功能预留与待实施

本文档记录代码中为未来功能预留的接口、参数和设计，以及已设计但尚未实施的功能，防止这些预留内容成为悬空代码或被误删除。

---

## 第一部分：预留悬空内容待完善

此部分记录代码中已有预留但功能未完整实现的内容。

### 1. AI 联系人请求验证消息决策

**预留位置**: `backend/app/services/ai/contact_handler.py`

**函数签名**:

```python
async def handle_ai_contact_request(
    db: AsyncSession,
    *,
    request_id: int,
    from_qiao_id: str,
    to_qiao_id: str,
    message: str,  # ← 预留参数
) -> ContactRequestDecision:
```

**预留参数**: `message: str`

**当前状态**:
- 参数已定义并传递
- 数据已存储到 `contact_requests.message` 字段
- ❌ 函数内部未使用该参数（标记为 `noqa: ARG001`）

**数据流**: `message` → `contact_requests.message` (已持久化但未被消费)

**相关文档**:
- [联系人请求流程](../spec/contact/request-flow.md)
- [API 设计文档](../api/contact-requests.md)

---

### 2. 扩展媒体文件类型

**预留位置**: `backend/database/init/01_schema.sql` - `media_files` 表

**预留字段**: `file_type` (SMALLINT)

**预留类型值**:
- **Type 2 (emoji)**: 自定义表情/贴纸支持
- **Type 3 (image)**: 聊天图片分享
- **Type 4 (document)**: 文件附件

**架构设计**: 统一 `media_files` 表 + 配额系统 + CDN 分发

**当前状态**:
- ✅ 数据库字段已预留
- ❌ 业务逻辑未实现

---

## 第二部分：已设计或部分设计待实施功能

此部分记录已有设计文档或架构规划，但尚未开始代码实施的功能。

### 1. AI 记忆写入超额归档

**功能描述**: 当记忆数量超过 `memory_limits` 时，在写入时进行淘汰/归档

**当前行为**:
- 仅在检索时裁剪，写入时不淘汰
- 超额记忆仍保留在表中

**未来方向**:
- 写入时按策略归档/淘汰超额记忆
- 归档规则需与 `memory_limits` 保持一致
- 需要后台任务兜底清理

**相关文档**:
- [记忆系统规范](../spec/ai/memory-system.md)

---

### 2. 存储清理策略

**功能描述**: 主动清理未被引用的已激活媒体文件（扩展清理）

**目的**: 删除在宽限期后不再被任何实体（profiles、messages 等）引用的已激活媒体文件

**当前状态**:
- ❌ 未实现
- ✅ 当前仅实现 pending 文件每小时清理（`status=pending` 且超过 1 小时）

**业务场景**: 防止存储滥用模式
- 图床滥用
- 配额绕过攻击

**实施要点**:
- 后台定时任务扫描
- 宽限期设置（当前文档草案为 24 小时）
- 引用关系检查
- 记录每次清理数量，单次清理 > 100 时告警

**参考 SQL（来自存储设计文档原扩展清理段）**:
```sql
SELECT mf.id, mf.object_key
FROM media_files mf
LEFT JOIN profiles p ON p.avatar_media_id = mf.id
WHERE mf.status = 1  -- active
  AND mf.file_type = 1  -- avatar
  AND mf.confirmed_at < NOW() - INTERVAL '24 hours'
  AND p.id IS NULL  -- 未被任何 profile 引用
```

**调度方案（待选型）**:
- Celery Beat 定时任务
- Docker Compose + cron 容器
- APScheduler

---

### 3. 文件安全增强

#### 3.1 Magic Bytes 验证

**目的**: 验证上传文件的实际类型与声明的 MIME 类型是否匹配

**威胁模型**: 防止可执行文件伪装（exe→jpg）和 XSS 向量（html→img）

**实施方式**: 使用文件签名检测

#### 3.2 内容审核

**目的**: 集成第三方内容审核 API（腾讯云天御）进行 NSFW/违法内容检测

**集成点**: 在 `/api/v1/media/upload` 存储文件后、返回 URL 前

---

### 4. 私有文件访问

**预留位置**: `StorageBackend.get_presigned_url()` 的 `GET` 方法

**目的**: 为私有文件（文档、敏感媒体）生成限时下载 URL

**使用场景**:
- 个人文档分享
- 临时访问授权
- 隐私敏感内容

---

### 5. 表情系统架构

**设计原则**:
- **无专有协议**: 拒绝 `assets://` 方案，仅使用标准 CDN URL
- **占位符系统**: 消息存储文本标记 `[emoji_key]`，客户端渲染为图片
- **混合分发**: 基础包客户端缓存，扩展包云端分发
- **内容灵活性**: 支持季节性/主题性/AI 生成的表情包

**数据模型**: 新的元数据结构（独立于 `preset_assets` 旧方案）

**客户端流程**: 获取包清单 → 缓存 CDN URL → 渲染占位符
