# Starlette Admin 开发规范

## 文档定位

本文件只定义 Admin 模块特有规则。
通用后端规则见：`backend/AGENTS.md`。

## 核心规则

1. 禁止在 Admin 层编写业务逻辑（仅负责展示、输入、CRUD 编排）
2. 业务行为必须下沉到 `app/services/`，Admin 仅调用 service
3. `fields` 必须全部使用 `Field` 对象，禁止混入字符串
4. `type: ignore` 仅允许用于框架边界，且必须写明原因

## 代码示例

```python
# Good: all fields are Field objects.
fields = [
    IntegerField("id", label="ID"),
    DateTimeField("created_at", label="Created At"),
]
```

```python
# Good: delegate business logic to service layer.
class AIInstanceView(ModelView):
    async def after_create(self, request, obj):
        await instance_service.create_with_initialization(request.state.db, obj)
```

## 类型处理约束

- JSONValue/union 类型先做类型缩窄，再访问属性
- 覆盖父类签名时若必须 `type: ignore[override]`，注释说明框架限制
- `FormValidationError` 使用明确的 `dict[str | int, Any]` 错误映射

## 验证要求

- 修改 `app/admin/` 后必须执行 `/validate`
- 手动验收入口：`http://localhost:8000/qiao-dash/`
