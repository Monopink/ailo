# 管理后台：Profile 头像 Advanced Edit（复用现有上传链路）

## 目标

- 在管理后台提供 Profile 头像高级编辑能力，支持上传、裁切、转码、缩放后直接绑定到 profile。
- 头像变更完成后，同步写入 `user_profile_logs` 审计记录。
- 全链路优先复用现有媒体上传能力与校验规则，禁止新增并行上传逻辑分支。

## 现状

- Admin `ProfileView` 仅支持从 `media_files` 选择已有记录，不能直接上传新头像。
- 现有上传链路已完整存在：`/api/v1/media/upload` + `app/services/media/uploader.py`。
- 现有上传服务以用户鉴权路径为中心，`admin-api` 尚无 profile 头像上传绑定入口。
- `user_profile_logs` 表存在，但头像改动未形成稳定写入路径。

## 问题点

- 若在 Admin 新增独立上传实现，会导致校验规则、去重策略、存储写入逻辑分叉。
- 头像上传与 profile 绑定、审计日志写入若分多事务执行，存在部分成功导致数据不一致风险。
- 裁切与转码若放在前端本地完成，质量与输出规范无法统一。

## 实施约束

- 必须复用或抽象复用现有上传服务，不允许复制上传核心逻辑。
- Admin 层不承载业务逻辑，业务行为下沉 `app/services/*`。
- 头像处理产物统一：`WebP + 512x512 + quality=80`。
- 裁切比例固定 `1:1`。
- 不保留原图，仅保留处理后头像对象。
- 覆盖策略为即时生效（无草稿态）。
- 审计日志字段统一记录 `field_name=avatar_media_id`。

## 待实现

1. Admin 入口与页面

- 为 `Profile` 增加行级 `advanced_edit` 入口，跳转头像高级编辑页。
- 页面支持：当前头像预览、上传文件、1:1 裁切框、提交保存、清空头像。

2. Admin API

- 新增 `admin-api` 头像上传绑定接口（session 鉴权）：
  - 接收图片文件与裁切参数。
  - 调用复用后的媒体上传服务完成处理与落库。
  - 在同一事务中更新 `profiles.avatar_key/avatar_media_id`。

3. 服务层复用改造

- 对现有 `app/services/media/uploader.py` 做可复用扩展：
  - 支持 admin 场景调用。
  - 保持与现有上传规则一致（quota/rate-limit/mime/size/dedup/storage）。
- 新增 profile 头像应用服务（供 admin-api 调用）：
  - 统一处理头像绑定与清空。
  - 对外返回稳定结果，不暴露内部实现细节。

4. 审计日志写入

- 头像变更时写入 `user_profile_logs`：
  - `owner_id / owner_qiao_id / owner_type` 来自目标 profile。
  - `modified_by_type = ADMIN`。
  - `field_name = avatar_media_id`。
  - `old_value/new_value` 记录旧/新 media_id（字符串化，清空时 `new_value=NULL`）。
  - `change_reason` 使用固定值：`admin_avatar_upload` / `admin_avatar_clear`。

5. 文档同步

- API 文档：补充 admin 头像高级编辑接口契约。
- Spec 文档：补充 admin 头像编辑行为与交互规则。
- 若涉及 schema 变更再触发 data-dict 生成；本任务默认不改 schema。

## 验收标准

- 管理后台可直接上传头像并绑定 profile，页面实时看到新头像。
- 上传处理结果恒定为 `WebP 512x512`。
- 仅存在一套媒体上传核心逻辑，不存在复制分叉实现。
- 头像每次变更均新增一条 `user_profile_logs`，字段和值符合约束。
- 清空头像后回退默认头像，且日志记录完整。

## 相关文档与代码

- Profile Admin View：`../../../backend/app/admin/views/user_views.py`
- Media Upload API：`../../api/media.md`
- User Profile API：`../../api/user.md`
- Storage Spec：`../../spec/storage.md`
- Media Upload Service：`../../../backend/app/services/media/uploader.py`
- Profile Model / Log Model：`../../../backend/app/models/profile.py`
