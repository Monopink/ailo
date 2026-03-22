# AI 联系人请求：验证消息决策

## 目标

- 在 AI 联系人请求的接受/拒绝决策中，纳入申请消息（`contact_requests.message`）的校验与判定逻辑。

## 现状（预留点）

- 预留实现位置：`backend/app/services/ai/contact_handler.py`
- 函数签名包含 `message: str`，但函数内部未使用该参数（`# noqa: ARG001`）。
- 数据已持久化：`message` 写入 `contact_requests.message`。

数据流：

`message` → `contact_requests.message`（已存储）→ `handle_ai_contact_request(..., message=...)`（已传递但未消费）

## 待实现

- 为联系人请求增加“申请消息校验”：
  - 允许/拒绝的规则边界需要明确（长度、空白、敏感词/攻击语等）。
  - 决策结果需要能回传稳定的 reason（用于客户端提示与监控）。
- 将校验逻辑接入 `handle_ai_contact_request`，并与 `ContactRequestDecision.reason` 对齐。

## 相关文档与代码

- 联系人请求流程：`../../spec/contact/request-flow.md`
- Contact Requests API：`../../api/contact-requests.md`
- 预留实现位置：`../../../backend/app/services/ai/contact_handler.py`
