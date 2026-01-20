## 小程序消息接收错误：msg_id 字段缺失

**日期**: 2026-01-22

**问题描述**:
小程序在接收消息时报错，提示 `msg_id` 字段验证失败：
```
[ERROR] [MessageService] Handle message error {
  "error": "[{
    \"code\": \"invalid_type\",
    \"expected\": \"string\",
    \"received\": \"undefined\",
    \"path\": [\"msg_id\"],
    \"message\": \"Required\"
  }]"
}
```

**根本原因**:
1. 前端严格校验 `msg_id`（`frontend/wx-minipg/utils/message/adapter-types.ts:7`），但 `BusinessMessage` 实例字段未被 LeanCloud SDK 自动映射。
2. 实际消息数据存在于 `_lcattrs`（`raw_attributes` 中含 `msg_id/from_qiao_id/to_qiao_id/conv_id/...`），但前端解析使用了 `message.msg_id` 等实例字段，导致 `undefined`。
3. 部分发送路径未强制校验 `msg_id`（尤其是通知类消息），存在发送不规范的风险。

**影响范围**:
- 小程序无法正常接收和处理消息
- 可能影响所有类型的消息（文本、系统消息、通知等）

**解决方案**:

#### 方案 A：前端按 `_lcattrs` 正确解析（最终方案）
将 `processBusinessMessage` 解析源从实例字段改为 `_lcattrs`，以 `_lcattrs` 为权威数据源：
- 从 `getAttributes()/attributes` 读取 `msg_id/from_qiao_id/to_qiao_id/conv_id/...`
- 若 `_lcattrs.msg_id` 仍缺失则记录错误并终止处理（不做回退/兜底）

#### 方案 B：后端强制 `msg_id` 校验并补齐通知类消息
- 出站消息强制 `msg_id` 非空，否则拒发
- 通知类消息生成并传入 `msg_id`
- LeanCloud 适配器构造前强校验 `msg_id`

#### 方案 C：日志定位（完成后已移除临时日志）
通过临时日志确认 `raw_attributes` 中已有 `msg_id`，问题来自前端解析路径而非后端缺失。

**相关文件**:
- 前端：
  - `frontend/wx-minipg/utils/message/leancloud.ts` (LeanCloud 适配器)
  - `frontend/wx-minipg/utils/message/adapter-types.ts` (消息类型定义)
  - `frontend/wx-minipg/utils/message/service.ts` (消息服务)
- 后端：
  - `backend/app/services/message/providers/leancloud/adapter.py` (消息构建)
  - `backend/app/services/message/outbound/sender.py` (消息发送)

**状态**: 已修复

**负责人**: Codex

**修复日期**: 2026-01-23

---
