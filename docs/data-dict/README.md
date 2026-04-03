# 数据库设计文档

## 真相源

- 真相源仅为 `backend/app/models/*.py` 与 `backend/alembic/versions/*.py`
- `docs/data-dict/*` 为自动生成产物，不是手工维护真相源
- `backend/database/init/sql/01_schema.sql` 与 `docs/data-dict/*` 必须由同一生成流程产出

## 产物格式（AI优先）

- `schema.tables.tsv`：表级索引
- `schema.columns.tsv`：字段级索引
- `schema.constraints.tsv`：约束与索引

## 规则

- 禁止手工修改自动生成产物中的结构字段定义
- 枚举取值以 `backend/app/enums/*` 为准
- 时间格式规范见 [时间格式规范](../spec/time-format.md)
