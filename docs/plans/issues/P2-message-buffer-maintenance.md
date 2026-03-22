# Buffer 维护策略（未来）

## 异常滞留窗口清理

定期清理长时间 LOCKED 的窗口（超限置 CANCELLED 或回到 OPEN），避免卡死。

## 处理轨迹审计

如需，可增加 locked_at/canceled_at 等审计列。
