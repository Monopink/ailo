# Starlette Admin 开发规范

## 核心原则

1. **❌ 禁止在 admin 中编写业务逻辑** - 仅做数据展示和 CRUD，复杂逻辑在 `services/` 实现
2. **✅ 使用 Field 对象** - `fields` 列表必须用 `IntegerField`/`StringField` 等，不能用字符串
3. **✅ 类型检查豁免** - 框架限制导致的 `[misc]`, `[union-attr]`, `[arg-type]`, `[list-item]` 错误已在 pyproject.toml 忽略

---

## 代码模式

### Fields 定义

```python
# ✅ 正确：使用 Field 对象
fields = [
    IntegerField("id", label="ID"),
    DateTimeField("created_at", label="Created At"),
]

# ❌ 错误：不能用字符串
fields = [IntegerField("id"), "created_at"]  # 运行时 AttributeError
```

### 动态字段（可选，更好的类型安全）

```python
def get_fields_list(self, request: Request, action: RequestAction) -> Sequence[BaseField]:
    return [IntegerField("id"), StringField("name")]
```

---

## 类型处理要点

### JSONValue 类型
```python
# ✅ 使用类型缩窄
if not isinstance(config, dict):
    raise ValueError("Config must be a dict")

# ❌ 无法避免时添加 ignore
return data.get("config", {})  # type: ignore[union-attr]
```

### FormValidationError
```python
errors: dict[str | int, Any] = {"name": "Name is required"}
raise FormValidationError(errors)
```

### 方法覆盖
```python
# 基类使用 Any 时需要 ignore
async def render(self, request: Request, templates: Any) -> Response:  # type: ignore[override]
    ...
```

---

## 业务逻辑分离

```python
# ❌ 错误：在 admin 中写业务逻辑
class AIInstanceView(ModelView):
    async def after_create(self, request, obj):
        relationship_score = calculate_relationship_score(obj)  # ❌
        update_memory_context(obj, relationship_score)  # ❌

# ✅ 正确：调用 service
class AIInstanceView(ModelView):
    async def after_create(self, request, obj):
        await instance_service.create_with_initialization(request.state.db, obj)
```

---

## 测试

手动测试 UI 功能即可，访问 http://localhost:8000/qiao-dash/ 验证 CRUD 正常。
