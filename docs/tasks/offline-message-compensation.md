## 离线消息设计

**日期**: 2026-01-24

**问题描述**:
小程序断联后存在消息丢失，需要离线消息能力，同时保持消息传输层解耦并为未来消息同步预留空间。

**关键结论**:
1. 离线消息仅补齐发给用户的消息，不进行双向补齐。
2. 不设置时间窗口限制，依赖服务端游标与 ACK 机制避免重复与历史同步。
3. 新客户端不做补齐，首次请求创建游标并从当前时间开始。
4. 客户端生成稳定 UUID 作为 device_id，并在拉取与 ACK 中上送。

**接口与数据设计**:
- 新增离线消息接口与 ACK 接口（docs/api/messages-offline.md）。
- 新增离线消息游标表 message_offline_cursor（docs/data-dict/message-offline-cursor.md）。
- 新增规范文档（docs/spec/message/delivery-reliability.md）。

**待实现内容**:
- 后端接口实现（离线拉取与 ACK）。
- 前端接入 device_id与 ACK 上报。

**实施原则**
- 不要向后兼容
- 不要为不存在的内容保留文档或注释

**状态**: 设计完成，待实现
