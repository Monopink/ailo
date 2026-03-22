# 消息：History API（按会话回看 / 补历史）

## 目标

- 提供基于 `conversation_id` 的消息回看/补历史能力（按时间窗与分页查询）。

## 现状

- `docs/api/messages-offline.md` 只覆盖断联期间的增量补齐（Offline）。
- `docs/api/messages-offline.md` 已移除对 History 的描述。

## 预期能力范围

- 查询维度：`conversation_id` + 时间窗 / 分页（游标）
- 返回内容：聊天时间线消息
- 时间窗：基础可配置；允许按订阅/付费扩展更长窗口
