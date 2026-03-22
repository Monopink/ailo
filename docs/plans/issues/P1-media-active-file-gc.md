# 存储：清理未引用的 active 媒体文件

## 目标

- 主动清理在宽限期后不再被任何实体引用的 active 媒体文件（扩展清理）。

## 现状

- 已实现 pending 文件清理：
  - `backend/app/services/media/cleanup.py` 会周期性删除 “长时间未确认的 pending 文件”，并将记录标记为 DELETED。
- 未实现 active 未引用文件清理。

## 待实现

- 定义“引用关系”覆盖范围（profiles、messages 等），并实现引用检查。
- 定义宽限期与批处理策略（避免误删与避免高峰扫描压力）。
- 实现后台定时任务：
  - 单次清理数量可控
  - 单次清理异常/数量异常可告警

## 相关文档与代码

- Media API：`../../api/media.md`
- 现有 pending 清理：`../../../backend/app/services/media/cleanup.py`
