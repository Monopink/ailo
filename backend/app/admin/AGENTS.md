# Starlette Admin 管理后台开发规范

## 模块说明

本模块是基于 Starlette Admin 的管理后台，**仅用于运维和数据管理**，不是核心业务逻辑。

**重要原则：**
- ❌ **禁止在 admin 模块中编写业务逻辑**
- ✅ Admin 仅做数据展示和基础 CRUD
- ✅ 复杂业务逻辑必须在 `services/` 中实现，admin 只调用

---

## Starlette Admin 框架限制

### 类型检查豁免

由于 Starlette Admin 的 API 设计与 Python 类型系统存在冲突，本模块的以下类型错误是**已知且可接受的框架限制**：

**已知问题类型：**
1. `[misc]` - "Cannot override instance variable with class variable"
   - **原因**: Starlette Admin 要求用类变量覆盖基类的实例变量
   - **处理**: 在 pyproject.toml 中忽略此模块的 misc 错误

2. `[union-attr]` - JSONValue 类型的联合类型属性访问
   - **原因**: Admin 字段配置使用 JSON 格式，类型为 `JSONValue`
   - **处理**: 在 pyproject.toml 中忽略此模块的 union-attr 错误

3. `[arg-type]` - Starlette Admin API 参数类型不匹配
   - **原因**: 框架类型注解不完善或使用 `Any`
   - **处理**: 在 pyproject.toml 中忽略此模块的 arg-type 错误

4. `[list-item]` - fields 列表中混入字符串类型
   - **原因**: 历史遗留代码，某些 view 的 fields 列表中直接使用字符串而非 Field 对象
   - **处理**: 在 pyproject.toml 中暂时忽略，逐步重构时修复
   - **注意**: 新代码必须使用 Field 对象（见下文"正确的代码模式"）

**mypy 配置：**
```toml
# pyproject.toml
[[tool.mypy.overrides]]
module = [
    "app.admin.views.*",
    "app.admin.fields.*",
]
disable_error_code = ["misc", "union-attr", "arg-type", "list-item"]
```

---

## 正确的代码模式

### ✅ 正确：使用 Field 对象定义字段

```python
from starlette_admin.fields import (
    DateTimeField,
    IntegerField,
    StringField,
)

class UserStatsView(ModelView):
    fields = [
        IntegerField("id", label="ID"),
        StringField("name", label="Name"),
        DateTimeField("created_at", label="Created At"),  # ← 使用 Field 对象
    ]
```

### ❌ 错误：在 fields 列表中混入字符串

```python
# ❌ 错误示例
class UserStatsView(ModelView):
    fields = [
        IntegerField("id"),
        "created_at",  # ← 错误！不能直接使用字符串
    ]
```

**为什么错误：**
- Starlette Admin 的 `fields` 类型是 `Sequence[BaseField]`
- 字符串不是 `BaseField` 的子类
- 运行时会导致 AttributeError

**如何修复：**
```python
# ✅ 正确修复
from starlette_admin.fields import DateTimeField

fields = [
    IntegerField("id"),
    DateTimeField("created_at", label="Created At"),
]
```

---

### ✅ 正确：覆盖方法而不是属性

虽然 Starlette Admin 文档推荐直接覆盖 `fields` 类变量，但为了更好的类型安全，**推荐覆盖方法**：

```python
from typing import Sequence
from starlette.requests import Request
from starlette_admin.fields import BaseField, IntegerField, StringField

class UserView(ModelView):
    def get_fields_list(
        self, request: Request, action: RequestAction = RequestAction.LIST
    ) -> Sequence[BaseField]:
        """Define fields dynamically (better type safety)."""
        return [
            IntegerField("id", label="ID"),
            StringField("name", label="Name"),
        ]
```

**优点：**
- ✅ 避免 mypy `[misc]` 错误
- ✅ 可以根据 request 和 action 动态返回不同字段
- ✅ 更符合 Python 面向对象设计

---

## JSONValue 类型处理

Admin 表单数据和配置常使用 JSON 格式，类型为 `JSONValue`（联合类型）。

### ✅ 正确：使用类型缩窄

```python
from app.type_defs import JSONDict, JSONValue

def _process_config(config: JSONValue) -> dict[str, int]:
    """Process configuration JSON."""
    # ✅ 类型缩窄
    if not isinstance(config, dict):
        raise ValueError("Config must be a dict")

    # 现在 config 被缩窄为 dict[str, JSONValue]
    result = {}
    for key, value in config.items():
        if isinstance(value, int):
            result[key] = value
    return result
```

### ❌ 错误：直接访问联合类型的属性

```python
def _process_config(config: JSONValue) -> dict[str, int]:
    # ❌ 错误：JSONValue 可能是 str/int/list/None，没有 .items()
    for key, value in config.items():  # ← mypy [union-attr]
        ...
```

**如果无法避免，添加 type ignore：**
```python
def _process_legacy_data(data: JSONValue) -> JSONDict:
    """Process legacy data format (framework limitation)."""
    # Framework requires JSONValue but always passes dict at runtime
    return data.get("config", {})  # type: ignore[union-attr]
```

---

## FormValidationError 参数类型

### ✅ 正确：使用 dict[str | int, Any]

```python
from starlette_admin.exceptions import FormValidationError

async def validate(self, request: Request, data: dict[str, Any]) -> None:
    """Validate form data."""
    if not data.get("name"):
        # ✅ 使用正确的类型
        errors: dict[str | int, Any] = {"name": "Name is required"}
        raise FormValidationError(errors)
```

### 如果已有 dict[str, str]，两种处理方式：

**方式1：修改类型（推荐）**
```python
errors: dict[str | int, Any] = {"name": "Name is required"}
raise FormValidationError(errors)
```

**方式2：类型转换**
```python
errors: dict[str, str] = {"name": "Name is required"}
raise FormValidationError(dict(errors))  # 显式转换
```

---

## 方法覆盖签名

Starlette Admin 的 ModelView 基类有时使用 `Any` 类型参数，子类覆盖时需要匹配或添加 ignore。

### 常见需要 ignore 的方法

```python
from typing import Any
from starlette.requests import Request
from starlette_admin.views import BaseModelView

class CustomView(BaseModelView):
    # Starlette Admin 基类签名使用 Any
    async def render(  # type: ignore[override]
        self, request: Request, templates: Any
    ) -> Response:
        """Custom render logic."""
        ...

    def serialize_field_value(  # type: ignore[override]
        self, value: Any, action: RequestAction
    ) -> Any:
        """Custom serialization."""
        ...
```

**注释规范：**
- 添加 `# type: ignore[override]` 或 `# type: ignore[explicit-any]`
- 在上一行用注释说明原因："Starlette Admin base class signature uses Any"

---

## 禁止的模式

### ❌ 在 Admin 中编写业务逻辑

```python
# ❌ 错误示例
class AIInstanceView(ModelView):
    async def after_create(self, request, obj):
        # ❌ 不要在 admin 中写复杂业务逻辑
        relationship_score = calculate_relationship_score(obj)
        update_memory_context(obj, relationship_score)
        trigger_background_job(obj.id)
```

**正确做法：**
```python
# ✅ 在 service 中实现业务逻辑
# app/services/ai/instance_service.py
async def create_ai_instance_with_initialization(
    db: AsyncSession, data: AIInstanceCreate
) -> AIInstance:
    """Create AI instance with full initialization logic."""
    instance = await crud_ai_instance.create(db, data)
    await relationship_service.initialize_scores(db, instance.id)
    await memory_service.setup_context(db, instance.id)
    await background_tasks.trigger_initialization(instance.id)
    return instance

# ✅ Admin 中只调用 service
class AIInstanceView(ModelView):
    async def after_create(self, request, obj):
        db = request.state.db
        # 调用 service，不写业务逻辑
        await instance_service.create_ai_instance_with_initialization(db, obj)
```

---

## 测试要求

Admin 模块的测试重点：
1. ✅ **UI 可用性测试** - 字段能正确显示、编辑、保存
2. ✅ **权限测试** - CRUD 权限控制正确
3. ❌ **不需要单元测试** - Admin 是配置性代码，不是业务逻辑

**测试方式：**
- 启动开发服务器
- 访问 http://localhost:8000/qiao-dash/
- 手动验证 CRUD 功能正常

---

## 常见问题

### Q: 为什么 admin 模块不需要严格的类型检查？

A:
1. Admin 是**运维工具**，不是核心业务
2. Starlette Admin 框架本身类型注解不完善
3. 类型错误不会影响 API 和业务逻辑
4. ROI 太低，不值得花大量时间修复框架问题

### Q: 什么情况下可以在 admin 中添加 type: ignore？

A:
1. Starlette Admin API 强制要求 `Any` 类型
2. 框架基类方法签名使用 `Any`
3. JSON 配置处理中的 `JSONValue` 类型缩窄不可行
4. **必须添加注释说明原因**

### Q: Admin 代码会不会影响 AI 学习？

A:
1. ✅ 不会 - AI 会优先读取**当前目录**的 AGENTS.md
2. ✅ 本文档明确标注了哪些是"框架限制"，哪些是"错误模式"
3. ✅ AI 在核心业务模块会遵守更严格的规范（`backend/AGENTS.md`）

---

## 修改 Admin 代码前必读

1. ✅ 确认修改是否涉及业务逻辑
   - 如果是，**必须在 `services/` 中实现**，admin 只调用

2. ✅ 确认是否需要添加 type: ignore
   - 检查是否是已知的框架限制（见上文）
   - 添加清晰的注释说明原因

3. ✅ 使用 Field 对象，不要使用字符串
   - `fields` 列表中所有元素都必须是 `BaseField` 子类

4. ✅ 手动测试 UI 功能
   - 访问管理后台验证 CRUD 功能正常

5. ❌ 不要尝试"修复"框架的类型问题
   - 保持与 Starlette Admin 文档推荐的写法一致
   - 添加 type: ignore 即可
