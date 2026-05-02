# 客户端基础接口

## 获取客户端健康状态

### 基本信息

- 路径：`GET /api/v1/client/health`
- 认证：无需认证

### 成功响应（200）

```json
{
  "status": "ok",
  "server_time_ms": 1760000000000
}
```

### 字段说明

- `status` (string): 固定为 `ok`
- `server_time_ms` (integer): 服务端 UTC 时间戳（毫秒）

### 错误响应

- `403`: 网关访问控制拒绝
- `500`: 系统错误
