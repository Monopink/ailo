# 联系人申请监控（未来）

## 关键指标

- PENDING 请求数量（按类型统计）
- PROCESSING 请求平均处理时间
- FAILED 请求数量（需要告警）
- 过期请求数量

## 告警规则

- 1 小时内 FAILED > 10（系统错误）
- PROCESSING 状态超过 5 分钟（Worker 可能崩溃）
- 过期 PENDING 请求 > 100（需要清理）
