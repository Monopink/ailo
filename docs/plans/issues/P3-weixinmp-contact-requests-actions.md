# 小程序：联系人申请处理动作（接受/忽略）与接口联调

## 当前实现

- 页面：`frontend/mp-weixin/pages/contact-requests/contact-requests.ts`
  - `handleApprove()`、`handleReject()` 仅展示 Toast，无 API 调用
  - `event.currentTarget.dataset.id` 当前仅用于占位，不参与业务逻辑
- 页面服务：`frontend/mp-weixin/services/pages/contact-requests-service.ts`
  - 当前仅加载传入数组，不包含网络请求或本地存储逻辑

## 现有后端接口

- API 文档：`docs/api/contact-requests.md`
  - 接受：`POST /api/v1/contact-requests/{id}/accept`
  - 忽略：`POST /api/v1/contact-requests/{id}/ignore`
- 后端实现：`backend/app/api/v1/contact_requests.py`
  - 接口路径与文档一致
  - `request_id` 路径参数类型：`int`

## 待确认

- `id` 格式：
  - 文档示例为字符串（如 `req_123`）
  - 后端实现为 `int`
  - 小程序页面数据当前定义为 `id: string`
- “拒绝”语义：
  - 小程序 `handleReject()` 当前表达为“拒绝”
  - 后端与文档为“忽略（ignore）”
- MVP 数据流：
  - `docs/api/contact-requests.md` 描述采用通知推送 + 客户端本地存储，不提供列表查询接口
  - 小程序当前页面尚未实现本地存储/推送接入
