# Contact Request Retry & Pending Inventory

## 背景

当同一个 `ai_type` 没有可用模板时，当前实现会直接抛错或静默失败，导致：
- 用户端收到模糊错误或无法得知进展。
- 管理员无法准确获知缺模板的 `qiao_id` / 类型。
- 重复提交会生成多条 `contact_requests` 记录，幂等性被破坏。

本任务的目标是让请求“挂起等待库存”，并提供可观测、可重试的操作流程。

## 交付目标

1. **数据结构完善**：`contact_requests` 应记录失败类型、详情、重试次数与最近重试时间。
2. **服务逻辑**：当模板不足时将请求保留为 `PENDING`，写入失败信息；补模板后可重试。
3. **前后端体验**：
   - 用户端始终只看到 “请求已发送”，重复操作转为重试。
   - 管理后台与联系人视图能看到挂起列表并触发重试按钮。
4. **观测性**：为挂起和重试行为打日志/指标，便于监控。

## 数据模型调整

`contact_requests` 新增字段（SQL 已到位）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `failure_code` | VARCHAR(50) | 失败原因枚举：`NO_TEMPLATE_AVAILABLE`、`MANUAL_PROVISION_REQUIRED` 等 |
| `failure_detail` | JSONB | 结构化信息，至少包含 `ai_type_id`、`qiao_id`、`request_id` |
| `retry_count` | INTEGER | 系统维护的重试次数 |
| `last_retry_at` | TIMESTAMPTZ | 最近一次尝试时间 |

> 注意：挂起请求依旧保持 `status=PENDING`；只有明确拒绝才转入 `IGNORED`。

## 工作流

```
模板不足 → contact_requests 写入 failure_* → 状态仍为 PENDING
    ↓（管理员补模板）
Admin 点击“重试”或用户再次发起同一请求
    ↓
系统复用原 request:
    - retry_count += 1
    - last_retry_at = NOW()
    - failure_code/failure_detail 清空
    - 重新执行 handle_ai_contact_request 直至成功
成功 → ACCEPTED & 创建联系人
再次失败 → failure_* 写入新的原因，继续等待
```

## 需要实现/修改的模块

1. **服务层**
   - `services/ai/contact_handler.py`
     - 当 `select_template` 返回 `None` 时，不抛异常；改为写 failure 信息并返回 `WAIT_TEMPLATE` 决策。
     - 新增 `mark_pending_failure` / `clear_pending_failure` 辅助函数。
   - `services/contact/request_service.py`
     - `create_contact_request` 中如果发现已有 `(from,to)` PENDING 记录，直接触发重试逻辑。
     - 重试前更新 `retry_count`、`last_retry_at`。
   - `services/contact/request_worker.py`
     - 避免 Worker 不断拾取同一条无库存的请求；对于 `failure_code` 不为空的记录跳过或延后。

2. **CRUD 层**
   - `crud/contact_request.py`
     - 新增更新 `failure_*` 的接口。
     - 提供按 `status=1 AND failure_code IS NOT NULL` 查询的分页方法（后台列表使用）。

3. **API / Admin**
   - 新建 `POST /api/v1/contact-requests/{id}/retry`（Admin 权限）
     - 校验请求仍为 `PENDING`。
     - 重置 failure 字段并立即触发处理逻辑。
   - 后台列表接口（Starlette Admin 或自定义 API）增加过滤字段。
   - 在联系人视图中追加“重试”按钮，调用 retry 接口。

4. **日志 & 监控**
   - `LOG.info("contact_request_pending", ...)`：记录挂起的模板类型。
   - `LOG.info("contact_request_retry", ...)`：记录谁触发了重试、结果如何。
   - 暂不引入新指标，但建议预留 Prometheus 计数器。

## 前端/后台需求

1. **Admin Dashboard**
  - 列表列：`request_id`、`from_qiao_id`、`to_qiao_id`、`ai_type_id`、`failure_code`、`retry_count`、`updated_at`。
   - 操作：`补模板`（跳转模板页面）、`重试`。
2. **Contacts 视图**
   - 在“我的联系人申请”中，当状态显示“等待库存”时展示 `重试` 按钮（调用同一 API）。
3. **Square/用户端**
   - 无额外文案；重复提交仍返回统一消息。

## 风险与注意事项

- 重试可能再次失败，必须把新的原因写回 `failure_detail`，防止管理员误以为已成功。
- 当管理员误填错误模板类型时，适当在 detail 中记录“模版类型不匹配”之类错误方便定位。
- 并发重试需要事务保障：使用 `(SELECT ... FOR UPDATE)` 锁住 `contact_requests` 行，防止同时重试。
- 监控：建议加入 PENDING 超时扫描，避免无限期挂起（可在后续任务实现）。

## 模板选择策略

### 选择规则

系统按以下策略选择模板：

1. **优先不可复用模板**：优先选择 `is_reusable=0` 的单次使用模板
2. **优先级降序排列**：按 `priority DESC` 排序（数字越大优先级越高）
3. **同优先级随机选择**：如果最高优先级有多个模板，随机选择一个
4. **回退到可复用模板**：如果没有不可复用模板，对 `is_reusable=1` 的模板应用相同规则

### 优先级字段

- **字段名称**：`ai_templates.priority`
- **数据类型**：INTEGER
- **默认值**：1
- **排序规则**：DESC（降序）
- **优先级含义**：数字越大，优先级越高

## 参考

- `docs/development/contact-request-flow.md`
- `backend/database/init/01_schema.sql`
- `docs/task/ai-persona-architecture.md`
