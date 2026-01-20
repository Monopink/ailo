# LeanCloud Webhook 404 修复方案

## 背景与现象
- 现象: POST `/api/v1/webhook/leancloud/{token}` 返回 404，消息未进入处理流程。
- 现有路由: `backend/app/api/v1/webhook.py` 中注册路径为 `/api/v1/leancloud/webhook/{webhook_token}`。
- 文档定义: `docs/spec/message/leancloud.md` 与 `docs/api/leancloud-message.md` 均为 `/api/v1/leancloud/webhook/{webhook_token}`。
- 结论: 后台生成的 Webhook URL 路径顺序错误，导致 LeanCloud 回调命中 404。

## 目标
- 纠正 Webhook URL 的唯一生成逻辑，保证路径与后端路由/文档一致。
- 不新增任何向后兼容路径。
- 降低未来路径拼接错误风险，确保“单一事实来源”。

## 方案（选定）
### 1) 建立唯一 URL 生成点
- 新增纯函数（无副作用）用于生成 Webhook URL，例如:
  - `backend/app/services/message/providers/leancloud/url_builder.py`
  - `build_leancloud_webhook_url(api_base_url: str, token: str) -> str`
  - 固定拼接路径: `/api/v1/leancloud/webhook/{token}`
- 该函数只处理字符串拼接，不读取配置，不依赖数据库。

### 2) 替换所有手工拼接
- 修改以下文件中 webhook URL 的构造逻辑为调用新函数:
  - `backend/app/admin/views/system_settings_view.py`
  - `backend/app/admin/views/dashboard_view.py`
- 删除原先硬编码路径拼接，避免再次出现顺序错误。

### 3) 验证路径与控制台配置一致
- 在管理后台复制 Webhook URL 后，更新 LeanCloud 控制台回调地址。
- 确认回调日志不再出现 404。

## 影响范围
- 仅管理后台显示与复制的 Webhook URL 生成逻辑。
- 不改动对外 API 路由、不新增兼容路径。

## 风险与对策
- 风险: 已在 LeanCloud 控制台配置了错误 URL。
- 对策: 修复后立即更新控制台配置并验证。

## 验证计划
- 观察后端日志：LeanCloud 回调不再 404。
- 若可行，发一条消息触发回调，确认进入处理链（`webhook_messages_received`）。

## 状态
- Pending user approval for implementation.
