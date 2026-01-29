# 未来功能预留记录

本文档记录代码中为未来功能预留的接口、参数和设计，防止这些预留内容成为悬空代码或被误删除。

---

## AI 联系人请求验证消息决策

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
- ❌ 函数内部未使用该参数

**相关文档**:

- [联系人请求流程](../spec/contact/request-flow.md)
- [API 设计文档](../api/contact-requests.md)

**Data Flow**: `message` → `contact_requests.message` (persisted but not yet consumed)

---

## AI 记忆写入超额归档

**Reserved**: write-time eviction/archiving when `memory_limits` exceeded.

**Current Behavior**:
- 仅检索时裁剪，写入不淘汰
- 超额记忆仍保留在表中

**Future Direction**:
- 写入时按策略归档/淘汰超额记忆
- 归档规则需与 `memory_limits` 保持一致
- 需要后台任务兜底清理

**相关文档**:
- [记忆系统规范](../spec/ai/memory-system.md)

---

## Extended Media File Types

**Reserved**: `file_type` enum values 2/3/4 in database schema

**Purpose**:
- **Type 2 (emoji)**: Custom emoji/sticker support
- **Type 3 (image)**: Chat image sharing
- **Type 4 (document)**: File attachments

**Architecture**: Unified `media_files` table + quota system + CDN delivery

---

## Storage Cleanup Strategies

**Reserved**: Active unreferenced file cleanup job

**Purpose**: Remove activated media files that are no longer referenced by any entity (profiles, messages, etc.) after a grace period.

**Rationale**: Prevent storage abuse patterns - token申请不确认, image hosting misuse, quota bypass attacks.

---

## File Security Enhancements

### Magic Bytes Verification

**Purpose**: Verify uploaded file's actual type matches declared MIME type using file signature detection.

**Threat Model**: Prevents executable masquerading (exe→jpg) and XSS vectors (html→img).

### Content Moderation

**Purpose**: Integrate third-party content moderation API (Tencent Cloud Tianyu) for NSFW/illegal content detection.

**Integration Point**: Right after `/api/v1/media/upload` stores the file (before returning URL).

---

## Private File Access

**Reserved**: `GET` method in `StorageBackend.get_presigned_url()`

**Purpose**: Generate time-limited download URLs for private files (documents, sensitive media).

**Use Cases**: Personal document sharing, temporary access grants, privacy-sensitive content.

---

## Emoji System Architecture

**Design Principles**:
- **No proprietary protocols**: Reject `assets://` scheme, use standard CDN URLs only
- **Placeholder system**: Messages store text markers `[emoji_key]`, clients render to images
- **Hybrid distribution**: Basic packs cached on client, extended packs cloud-delivered
- **Content flexibility**: Support seasonal/themed/AI-generated emoji packs

**Data Model**: New metadata structure (separate from `preset_assets` legacy approach)

**Client Flow**: Fetch pack manifest → cache CDN URLs → render placeholders

---

## 时间格式不统一问题

文档示例中的时间戳为毫秒整数，返回体实际是 ISO8601 datetime，因为 Schema 直接暴露 datetime（backend/app/schemas/contact.py:128-141）。

**Issue**: Timestamp representation inconsistency (docs show integers, actual responses use ISO8601 strings)

**Resolution Direction**: Define project-wide datetime serialization standard (integer ms vs ISO8601 strings)
