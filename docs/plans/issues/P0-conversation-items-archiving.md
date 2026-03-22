# 会话记录归档（未来）

## 归档策略

定期将超过 14 天的记录迁移到 ai_conversation_items_archive。

## 归档后处理

- 归档后立即从主表删除对应记录。
- 执行 VACUUM ANALYZE ai_conversation_items 保持索引健康。
