# 未来功能预留记录

本文档记录代码中为未来功能预留的接口、参数和设计，防止这些预留内容成为悬空代码或被误删除。

---

## 1. AI 联系人请求验证消息决策

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

- ✅ 参数已定义并传递
- ✅ 数据已存储到 `contact_requests.message` 字段
- ❌ 函数内部未使用该参数

**设计意图**:

- AI 可以根据用户发送的验证消息内容决定是首次聊天消息内容

**相关文档**:

- [联系人请求流程](contact-request-flow.md#L51)
- [API 设计文档](../prototype/api-spec.md#L1045)

**记录时间**: 2025-11-28

## 时间格式不统一问题

文档示例中的时间戳为毫秒整数，返回体实际是 ISO8601 datetime，因为 Schema 直接暴露 datetime（backend/app/schemas/contact.py:128-141）。
