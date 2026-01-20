# 消息发送失败处理

本文档说明消息发送失败的处理策略和重试机制。

## 失败场景分类

### LeanCloud 层面失败

- 网络错误（网络超时、连接失败）→ 重试
- LeanCloud 服务异常（服务不可用、限流）→ 重试
- 消息格式错误（payload 格式不正确）→ 记录日志，不重试

### 业务层面失败（拒收）

- 用户被屏蔽（contacts.is_blocked = 1）→ 发送 CHAT_INFO，不重试
- AI 屏蔽用户（ai_instances.status = 3）→ 发送 CHAT_INFO，不重试
- 用户不是好友（contacts 表无记录）→ 发送 CHAT_INFO，不重试

详见 [special-types.md](special-types.md#block-功能和消息拒收)

## message_delivery_failures 表

完整表结构见 [data-dict/message.md](../../data-dict/message.md)

本文档关注的关键字段：

- msg_id_server - 原消息ID，关联 message_history.msg_id_server
- msg_id_provider - 第三方出站消息ID，失败定位使用
- content - 消息内容（用于重试）
- fail_reason_code - 失败原因代码
- fail_detail - 详细错误信息/堆栈（TEXT 类型）
- retry_count - 重试次数，默认 0
- max_retry_count - 最大重试次数，默认 3
- next_retry_at - 下次重试时间

## 失败记录写入

### 发送失败时

**逻辑步骤**：

1. 尝试调用 LeanCloud API 发送消息
2. 如果成功：
   - 写入 message_history
   - 记录 msg_id_provider_outbound
   - 标记 status = sent
3. 如果失败：
   - 写入 message_delivery_failures
   - 记录失败原因代码和详细信息
   - 设置 retry_count = 0
   - 计算 next_retry_at
   - 记录错误日志

### 失败原因代码

- NETWORK_ERROR (1001) - 网络错误
- LEANCLOUD_ERROR (1002) - LeanCloud 服务异常
- RATE_LIMITED (1003) - 速率限制
- INVALID_FORMAT (2001) - 消息格式错误
- INVALID_RECIPIENT (2002) - 接收者不存在
- BLOCKED (3001) - 被屏蔽
- NOT_FRIEND (3002) - 不是好友
- UNKNOWN (9999) - 未知错误

## 重试机制

### 指数退避策略

**重试间隔**：

- 第 1 次重试：1 分钟后
- 第 2 次重试：5 分钟后
- 第 3 次重试：15 分钟后

**计算逻辑**：

```
next_retry_at = current_time + intervals[retry_count]
```

### 重试流程

**定期扫描**（建议每分钟 1 次）：

1. 查询需要重试的消息：
   - retry_count < max_retry_count
   - next_retry_at <= 当前时间
2. 对每条失败消息：
   - 尝试重新发送
   - 如果成功：删除失败记录，记录成功日志
   - 如果失败：更新 retry_count，计算新的 next_retry_at
3. 如果达到最大重试次数：
   - 记录错误日志
   - 触发告警

### 定时任务

**执行频率**：每分钟 1 次

**任务内容**：扫描并重试失败的消息

## 不重试的场景

以下场景不进行重试，直接标记为最终失败：

- 消息格式错误（payload 格式不正确）→ 记录日志，告警
- 接收者不存在（to_qiao_id 无效）→ 记录日志，告警
- 被屏蔽（业务层拒收）→ 发送 CHAT_INFO
- 不是好友（业务层拒收）→ 发送 CHAT_INFO

**可重试错误代码**：

- NETWORK_ERROR
- LEANCLOUD_ERROR
- RATE_LIMITED

## 服务重启恢复

### 恢复策略

服务重启后，自动恢复未完成的重试。

**启动时检查**：

1. 查询所有待重试的消息（retry_count < max_retry_count）
2. 如果数量 > 0：
   - 记录日志：Found N messages pending retry
   - 立即执行一次重试任务

### 滞留消息清理

**定期清理**（建议每天凌晨 2 点）：

清理超过 7 天的失败记录：

- created_at < 当前时间 - 7 天
- retry_count >= max_retry_count

## 监控与告警

### 监控指标

- 失败率：发送失败 / 总发送（告警阈值：> 5%）
- 重试次数：平均重试次数（告警阈值：> 2）
- 滞留消息数：待重试消息数量（告警阈值：> 100）
- 最终失败数：重试耗尽的消息数（告警阈值：> 10/小时）

### 告警触发

**检查失败率**：

统计最近 1 小时的发送情况：

- 总发送数：message_history 表记录数
- 失败数：message_delivery_failures 表记录数
- 失败率 = 失败数 / 总发送数
- 如果失败率 > 5%：触发告警

### 日志记录

**发送失败**：

记录错误日志，包含：

- msg_id_server
- to_qiao_id
- error_code
- error_detail

**重试成功**：

记录信息日志，包含：

- msg_id_server
- retry_count

**重试失败**：

记录错误日志，包含：

- msg_id_server
- retry_count
- error_detail

**重试耗尽**：

记录错误日志，包含：

- msg_id_server
- max_retry_count

## 客户端失败处理

### 服务端拒收标记

服务端通过发送 CHAT_INFO 消息通知客户端消息被拒收。

**流程**：

1. 服务端检测到消息被拒收
2. 发送 CHAT_INFO 消息，包含 action：
   - type: "mark_message_failed"
   - target_msg_id: 原消息的 msg_id
3. 客户端收到 CHAT_INFO 后，根据 target_msg_id 标记对应消息为失败状态

详见 docs/spec/mini-program/prototype.md

## 错误处理最佳实践

### 1. 区分可重试和不可重试错误

- 可重试错误：网络错误、服务异常、速率限制
- 不可重试错误：格式错误、接收者不存在、业务拒收

### 2. 使用指数退避

重试间隔递增：1分钟 → 5分钟 → 15分钟

### 3. 设置最大重试次数

限制重试次数为 3 次，避免无限重试。

### 4. 记录详细错误信息

记录完整堆栈信息，便于排查问题。

### 5. 成功后删除失败记录

重试成功后立即删除 message_delivery_failures 记录，避免表无限增长。
