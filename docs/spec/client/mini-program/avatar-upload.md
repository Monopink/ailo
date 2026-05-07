# 头像上传规范

## 1. 约束条件

- **后端代理上传**：微信小程序无法直传 COS（`Content-Length` 限制 + Query 签名裁剪），必须通过 `/api/v1/media/upload` 代理
- **文件规格**：512x512 WebP，默认质量 85%，当文件超过 1MB 时自动降质重导出后上传
- **配额限制**：每日 5 次、总量 10MB（后端返回 429）
- **认证依赖**：需要 Bearer Token，支持 401 自动刷新
- **后端兜底**：前端不维护默认头像，由后端返回兜底 URL
- **来源分流**：微信头像在当前页面导出为 512x512 WebP，相册/拍照进入裁剪页后再上传

## 2. 模块职责

| 模块 | 职责 |
| --- | --- |
| `utils/avatar-uploader.ts` | 统一上传流程编排，返回 `{ fileId, url }` |
| `utils/avatar-image.ts` | 方图导出与 512x512 WebP 输出 |
| `utils/media.ts` | 封装 `/api/v1/media/upload`，支持 401 自动刷新 |
| `utils/profile.ts` | 封装 `/api/v1/user/profile`，提供 `updateUserAvatar(fileId)` |
| `utils/avatar.ts` | URL 解析，不做前端兜底 |
| `pages/avatar-cropper` | 输出 512x512 WebP，通过 EventChannel 通信 |

## 3. 数据流

```
用户点击头像
  → 基础库 >= 2.21.2: wx.chooseAvatar → 当前页面导出 512x512 WebP
  → 基础库 < 2.21.2: wx.chooseMedia → avatar-cropper 导出 512x512 WebP
  → wx.getFileInfo
  → POST /api/v1/media/upload → { file_id, url }
  → (可选) PUT /api/v1/user/profile
  → 刷新界面
```

**相关 API 文档**：
- [POST /api/v1/media/upload](../../../api/media.md)
- [PUT /api/v1/user/profile](../../../api/user.md)
- [头像昵称填写](profile-avatar-nickname.md)

## 5. 并发控制

- 页面维护 `uploadingAvatar` 布尔标记
- 上传中禁用再次点击
- `finally` 中重置状态，避免残留 loading

## 6. 故障排查

### 路径格式差异(正常现象)
- **DevTools**: 返回 `http://tmp/...` 或 `http(s)://tmp/...`
- **真机**: 返回 `wxfile://tmp_...`
- **重要**: 这两种格式都是**合法的本地临时文件协议**,微信 API (如 `wx.uploadFile`) **原生支持**,无需转换。
- **文件大小获取差异**:
  - DevTools: `FileSystemManager.getFileInfo()` 不支持 `http://tmp/...` 路径,前端传递 `file_size=0`,后端自动检测
  - 真机: `FileSystemManager.getFileInfo()` 支持 `wxfile://` 路径,前端正常获取并传递精确值
- 参考: [微信官方文档 - 本地文件路径](https://developers.weixin.qq.com/miniprogram/dev/framework/ability/file-system.html)

### 监控指标
- 日志中包含 `environment` 字段 (如 `devtools:3.10.0`, `ios:17.1`) 及 `selectionDurationMs`/`uploadDurationMs`,用于区分问题发生的设备与阶段。
- 日志中出现 `[avatar] using DevTools temp file path` 表示正常使用 DevTools 路径,非错误。
- 日志中出现 `[avatar] DevTools path - skipping file size check` 表示正常跳过 DevTools 文件大小检查,非错误。
- 后端日志中出现 `file_size_auto_detected` 表示接收到 `file_size=0` 并自动检测了实际大小。
