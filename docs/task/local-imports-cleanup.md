# 局部导入清理任务

## 文档状态

- **创建日期**: 2025-01-27
- **状态**: 待实施
- **优先级**: 高
- **关联文档**: [循环导入重构方案](circular-import-refactoring.md)

## 问题描述

虽然已完成循环导入重构，但系统中仍存在**18处局部导入**（函数内部的 import 语句），违反 PEP 8 规范。

### 当前进展

- `backend/app/services/ai/` 目录下的 18 处局部导入已全部清理，所有导入统一集中至文件顶部并按“标准库 → 第三方 → 项目”排序。
- 后台视图目录中以下文件已完成导入梳理：`ai_instance_views.py`、`ai_template_views.py`、`ai_style_test_view.py`、`dashboard_view.py`、`system_settings_view.py`、`system_views.py`、`llm_views.py`、`user_views.py`、`base.py`。`ai_advanced_edit_views.py` 也同步移除了 UTF-8 BOM，确保后续工具可以解析。
- 调试脚本 `tmp_local_imports.py` 仍位于仓库根目录（权限限制暂未删除），后续统一清理。

### 待办事项

1. **继续清理后台视图**：`backend/app/admin/views` 下仍有 50+ 处局部导入（见 `rg -n "^\s{4,}(from|import)" backend/app/admin/views --stats`），需要逐个文件迁移到顶部并校验顺序。
2. **扩展到 API/CRUD/Service 层**：`backend/app/api/**`、`backend/app/crud/**`、`backend/app/services/message/**` 等目录依旧存在大量函数内部导入，需要按目录分批治理。
3. **检测自动化**：建议保留或编写扫描脚本 / Make 任务，将局部导入检测纳入日常检查或 CI，以避免回归。
4. **临时文件清理**：具备权限后删除 `tmp_local_imports.py` 等调试脚本，保持仓库干净。

## 解决方案

### 原则

1. **所有 import 必须在文件顶部**（除 TYPE_CHECKING 块）
2. **标准库 → 第三方库 → 本地模块** 的导入顺序
3. **发现循环依赖立即停止，重构架构而非使用局部导入**

### 实施步骤

#### 步骤1: 清理重复导入

**文件**: `backend/app/services/ai/conversation_prompt.py`

**操作**: 删除函数内的重复导入语句

```python
# 删除以下行:
Line 117: import re
Line 606: from zoneinfo import ZoneInfo
Line 728: import re
Line 812: import re

# 保留顶部的导入:
Line 8: import re
Line 10: from zoneinfo import ZoneInfo
```

#### 步骤2: 移动模型导入到顶部

**文件**: `backend/app/services/ai/orchestrators/conversation_flow.py`

```python
# 在文件顶部添加:
from models.contact import Contact
from models.ai.instance import AIInstance
from services.message.security.validation import message_validation_service
from core.database import SessionLocal

# 删除 Line 122-125 和 Line 380 的局部导入
```

**文件**: `backend/app/services/ai/relationship_scoring.py`

```python
# 在文件顶部添加:
from models.ai import AIInstance
from models.ai.instance_dimension import AIInstanceDimension
from models.ai.style import AIStyleDimension, AIDimension
from sqlalchemy.orm import selectinload

# 删除 Line 111, 147-149 的局部导入
```

**文件**: `backend/app/services/ai/queries/relationship_queries.py`

```python
# 在文件顶部添加:
from models.ai import AIInstance

# 删除 Line 107 的局部导入
```

**文件**: `backend/app/services/ai/queries/transactions.py`

```python
# 在文件顶部添加:
from models.ai import AIConversationItem
from sqlalchemy import and_

# 删除 Line 281-282 的局部导入
```

**文件**: `backend/app/services/ai/queries/updates.py`

```python
# 在文件顶部添加:
from models.ai import AIDimension

# 删除 Line 132 的局部导入
```

#### 步骤3: 处理业务逻辑导入

**验证循环依赖**:

```bash
cd backend
# 测试每个导入是否会造成循环依赖
python -c "from app.services.ai.conversation_prompt import build_system_prompt"
python -c "from app.services.ai.relationship_scoring import get_relationship_scores"
```

**如果没有循环依赖**，移到顶部：

**文件**: `backend/app/services/ai/conversation_prompt.py`

```python
# 在文件顶部添加:
from .relationship_scoring import get_relationship_scores
from .queries import get_user_profile, get_conversation_contexts

# 删除 Line 263, 375, 509, 727 的局部导入
```

**文件**: `backend/app/services/ai/relationship_scoring.py`

```python
# 在文件顶部添加:
from crud.ai.instance_dimension import get_by_instance
from .utils.position_mapping import map_score_to_position
from .utils.score_mapping import map_to_permille

# 删除 Line 631, 643-644 的局部导入
```

**文件**: `backend/app/services/ai/instance_creation.py`

```python
# 在文件顶部添加:
from services.ai.relationship_scoring import initialize_relationship_scores

# 删除 Line 101 的局部导入
```

**如果发现循环依赖**，停止实施并报告，需要架构重构。

#### 步骤4: 验证修改

```bash
cd backend

# 1. 语法检查
python -m py_compile app/services/ai/conversation_prompt.py
python -m py_compile app/services/ai/orchestrators/conversation_flow.py
python -m py_compile app/services/ai/relationship_scoring.py
python -m py_compile app/services/ai/queries/*.py
python -m py_compile app/services/ai/instance_creation.py

# 2. 循环导入检查
python -c "import app.services.ai.conversation_prompt"
python -c "import app.services.ai.orchestrators.conversation_flow"
python -c "import app.services.ai.relationship_scoring"
python -c "import app.services.ai.queries"
python -c "import app.services.ai.instance_creation"

# 3. 搜索残留的局部导入
grep -rn "^    from " app/services/ai/ --include="*.py"
grep -rn "^    import " app/services/ai/ --include="*.py"

# 4. 容器测试
cd ../deployment
docker-compose restart backend
docker-compose logs -f backend | grep -i error
```

## 验证标准

### 必须满足

- [ ] 所有18处局部导入已清理
- [ ] 所有 import 语句在文件顶部（除 TYPE_CHECKING）
- [ ] 无循环导入错误
- [ ] 所有文件可独立导入
- [ ] 容器启动无错误
- [ ] 搜索 `grep -rn "^    from \|^    import " backend/app/services/ai/` 返回空结果

### 代码质量

- [ ] 导入按标准库、第三方库、本地模块分组
- [ ] 每组内按字母顺序排列
- [ ] 无未使用的导入

## 常见问题

### Q: 为什么不能使用局部导入？

A: 
1. 违反 PEP 8 规范
2. 隐藏依赖关系，难以维护
3. 每次函数调用都重新导入，性能损失
4. 掩盖循环依赖问题

### Q: 如果移到顶部后出现循环依赖怎么办？

A: 
1. **立即停止**，不要使用局部导入作为临时方案
2. 报告问题，分析依赖关系
3. 重构架构，通常需要：
   - 提取共享代码到独立模块
   - 使用依赖注入
   - 引入中间层（如 orchestrators）

### Q: TYPE_CHECKING 块中的导入是否需要清理？

A: 不需要。TYPE_CHECKING 块中的导入是类型检查专用，不会在运行时执行，这是正确的做法：

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from some.module import SomeType  # 这是正确的
```

## 参考资料

- [PEP 8 - Imports](https://peps.python.org/pep-0008/#imports)
- [循环导入重构方案](circular-import-refactoring.md)
