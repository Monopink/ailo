# Contact Request Retry & Pending Inventory

## 背景

当某个 AI 类型暂时没有可用模板时，之前的流程要么抛错要么默默失败，用户看不到进展，后台也无法得知缺少的模板。这个任务旨在让这类请求保持 `PENDING` 状态，记录明确失败原因，并提供在管理后台补模板后“一键重试”的闭环。

## 目标

1. **保留失败元数据**：`contact_requests` 需维护 `failure_code/detail`、`retry_count`、`last_retry_at`。SQL 已更新，模型与 CRUD 必须同步。
2. **服务逻辑**：模板不足时调用 `mark_pending_failure` 写入失败信息；管理员或重复请求触发 `clear_pending_failure` 后复用同一条记录，再次执行 `_process_ai_contact_request`。
3. **后台能力**：
   - 新增 `POST /api/v1/admin/contact-requests/{request_id}/retry`（依赖 `verify_admin_session`），只允许 Starlette Admin 登录用户调用。
   - 自定义视图 `custom_views/contact_request_pending.html` 提供“概览 → 列表 → 详情”流程化操作：可跳转模板管理、直接触发重试，并展示最近日志。
4. **观测性**：统一使用结构化日志记录 `contact_request_pending`、`contact_request_retry` 等事件（携带 `request_id`、`ai_type_id`、`admin_user`、`retry_count`）。

## 工作流回顾

```
模板不足 → mark_pending_failure → 仍为 PENDING
    ↓（管理员补模板）
Admin 在后台点击“重试”或用户重复发起 → clear_pending_failure → retry_count += 1
    ↓
重新执行 handle_ai_contact_request → 成功则 ACCEPTED & 创建联系人
    ↓
失败则写入新的 failure_*，继续等待
```

## 实施要点

### 服务/CRUD
- `contact_handler.py`：选择模板失败时不再抛错，改为触发 `WAIT_TEMPLATE` 决策并填充 `failure_*`。
- `request_service.py`：
  - `_check_and_update_pending_request` 发现已有挂起记录时，复用同一条并进入重试逻辑。
  - 新建的 `retry_pending_contact_request` 需记录重试次数、时间并调用核心处理函数。
- `request_worker.py`：跳过 `failure_code IS NOT NULL` 的记录，避免无穷 picking。
- `crud/contact_request.py`：补充 `failure_*` 更新接口以及 `status=1 AND failure_code IS NOT NULL` 的分页查询，供后台视图 / API 使用。

### 管理后台
- Admin API：`POST /api/v1/admin/contact-requests/{id}/retry`，使用 Starlette Admin Session 认证。
- Pending 面板：
  - 列字段：`request_id`、`from_qiao_id`、`to_qiao_id`、`ai_type_id`、`failure_code`、`retry_count`、`last_retry_at`、`updated_at`。
  - 操作：`补模板`（跳转模板管理）、`重试`（调用上面 API）。
  - 详情侧栏：展示 `failure_detail`、最近日志、流程提示。

## 风险
- 重试可能继续失败，务必覆盖新的失败原因，避免管理员误判。
- 重试/补模板操作需在事务中 `SELECT ... FOR UPDATE` 锁定，防止并发重复执行。
- 长时间挂起需后续任务补充超时扫描或告警。

## 参考
- `docs/spec/contact/request-flow.md`
- `backend/app/services/contact/request_service.py`
- `backend/app/admin/views/user_views.py`
