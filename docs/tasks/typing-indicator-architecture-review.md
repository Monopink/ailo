# 输入状态架构复核与改造方案

## 目的

从顶层重新收敛小程序输入状态指示的架构，避免补丁式修复，保持最小正确架构与实现复杂度。

## 发现的问题

1. **输入状态分发路径不唯一**
   - 目前存在“事件总线 → MessageStateStore → 页面”和“MessageService → App → Page”的双通道分发。
   - 实际页面未使用 App 直达通道，造成冗余与潜在分叉。

2. **输入状态顺序判断依赖对端 sent_time**
   - MessageStateStore 使用 typing 的 sent_time 与 lastMessageSentTime 比较。
   - sent_time 来自对端客户端，受时钟偏差影响，可能误判为过时事件。

3. **存在未使用的输入状态实现**
   - `frontend/wx-minipg/utils/message/typing.ts` 未被引用，与现有 `utils/typing-manager.ts` 重复。

4. **发送消息与 typing_end 语义易混淆**
   - 文档要求：typing_end 只在“输入结束”时发送，发送消息仅需本地隐藏输入状态。
   - 需要在实现与文档中明确语义边界，避免后续误改。

## 修改方案（正确架构，最小改动）

1. **统一输入状态分发通道**
   - 仅保留“适配器 → 事件总线 → MessageStateStore → 页面渲染”的通道。
   - 移除 App 级 `onTypingReceived` 分发路径及相关调用点，避免双入口。

2. **使用消息层统一接收时间**
   - 在消息层生成 `received_time`（可直接使用 `Date.now()`）。
   - MessageStateStore 使用 `received_time` 进行顺序判断，不依赖对端 sent_time。
   - 该字段为内部统一时间基准，不暴露供应商字段，避免耦合。

3. **移除未使用 typing 实现**
   - 将 `frontend/wx-minipg/utils/message/typing.ts` 移动到 `deleted/` 目录。
   - 保留 `frontend/wx-minipg/utils/typing-manager.ts` 作为唯一输入状态发送入口。

4. **文档处理**
   - 本次为内部架构收敛，用户行为不变，规格文档无需调整。

## 不做的事项

1. **不移除 App 层 message 分发**
   - `pages/index/index.ts` 仍依赖 `onMessageReceived` 更新会话列表。
   - 直接移除会导致会话列表行为退化，且不属于输入状态问题域。

2. **不扩展 MessageStateStore 为多会话**
   - 当前输入状态仅在单会话聊天页展示。
   - 多会话 store 会引入额外复杂度，属于过度设计。

## 影响范围

- `frontend/wx-minipg/utils/message/service.ts`
- `frontend/wx-minipg/utils/message/message-state-store.ts`
- `frontend/wx-minipg/app.ts`
- `frontend/wx-minipg/utils/message/typing.ts`（移动到 `deleted/`）
- `docs/spec/message/special-types.md`
- `docs/spec/mini-program/prototype.md`

## 风险与验证

- 风险：移除 App 直达通道后，若有页面隐式依赖会丢失输入状态。
  - 验证：检查是否存在 `onTypingReceived` 页面实现。
- 风险：接收时间替换后可能影响输入状态显示时序。
  - 验证：本地/真机测试输入状态显示、输入结束隐藏、收到消息隐藏。
