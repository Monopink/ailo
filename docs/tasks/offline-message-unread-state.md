**日期**: 2026-01-28

**问题描述**:
离线消息已接入，但客户端未读状态未建模，导致离线消息进入本地后不会触发未读红点与未读计数。现有“标为未读”功能只作用于 UI 层，缺少统一的状态来源。

**目标**:
建立客户端侧的未读状态管理模型，统一覆盖实时与离线消息，并与现有“标为未读”行为对齐。

**设计结论**:
1. 未读/已读仅在客户端管理，与后端 delivery/ACK 无关。
2. 实时与离线消息走同一未读更新路径。
3. 进入会话页即清零未读（MVP 期，符合主流 IM 行为）。
4. TYPING/NOTIFICATION/CHAT_INFO 不计入未读。
5. “标为未读”通过设置 unreadCount >= 1 来显式标记红点。

**方案计划**:
- 新增本地会话未读存储（per-conv unread count）。
- 新增会话读位点存储（last_read_sent_time / last_read_msg_id）。
- MessageService 在接收实时/离线消息后统一触发未读更新。
- 进入聊天页时清零该会话未读，并更新读位点。
- 联系人列表读取 unreadCount 展示红点与数字。

**涉及文件**:
- `frontend/wx-minipg/utils/message/service.ts`
- `frontend/wx-minipg/utils/message/message-state-store.ts`
- `frontend/wx-minipg/utils/storage.ts`
- `frontend/wx-minipg/pages/index/index.ts`
- `frontend/wx-minipg/pages/chat/chat.ts`
- `docs/spec/message/delivery-reliability.md`
- `docs/spec/mini-program/prototype.md`

**状态**: 计划中

---
