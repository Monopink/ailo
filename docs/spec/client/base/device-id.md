# Device ID

用于标识同一设备/安装实例的稳定 ID，跨会话复用，不与账号绑定。

## 生成时机

- 首次启动时生成并持久化
- 若本地不存在则生成（可在登录前生成）

## 生成方式

- UUID v4 随机生成

## 持久化

- 小程序本地存储（`wx.setStorageSync`）
- 建议 Key：`device_id`

## 生命周期

- 跟随本地存储生命周期
- 卸载或清理缓存后会丢失，视为新设备

## 多账号规则

- 同一设备多账号共享同一 `device_id`
- 服务端使用 `(user_id, device_id)` 作为游标唯一约束

## 接口约束（强制）

`device_id` 必须在以下登录接口中上送，且必须是 UUID：

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/wechat/login`
- `POST /api/v1/auth/wechat/bind-phone`
- `POST /api/v1/auth/phone`

客户端禁止走“无 device_id 登录”路径。
