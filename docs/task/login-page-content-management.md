# 登录页内容管理系统

## 任务目标

将登录页展示内容(示例联系人、功能列表)从前端硬编码迁移到后端数据库管理。

**架构原则**:
- UI 内容与系统配置分离,使用独立表 `app_ui_contents`
- 不复用 `system_configs` 或 `square_type_entries`
- 预留多语言、版本管理、定时发布扩展能力

**重要说明**:
- **无向后兼容**: 所有登录页数据必须来源 `app_ui_contents`/API，禁止前端保留任何本地兜底数据
- **无前端兜底**: 后端不可达时登录页无法使用,显示错误提示即可

## 附加要求
- MVP 阶段 **不需要任何向后兼容**，如果发现文档或代码仍保留兼容逻辑/兜底，请先报告我再决定处理方式。
- **禁止为已经移除或修改的功能/设计撰写补充文档或注释**，所有说明必须对应当前实际存在的流程，不要为不存在的状态制造“历史”说明。

### 本任务额外限定
- 本任务涉及的登录页内容必须完全来源后端/数据库，**不能为现有流程预留任何向后兼容或兜底实现**；如发现兼容逻辑请立即汇报。
- 所有文档和注释必须反映当前实现，**不要为已删除或修改的功能补写说明**，也不要保留过时状态的解释性文字。

---

## 一、数据库设计

### 表结构

```sql
CREATE TABLE app_ui_contents (
    id SERIAL PRIMARY KEY,

    -- 内容定位
    page_key VARCHAR(64) NOT NULL,        -- 页面标识: login, home, square
    section_key VARCHAR(64) NOT NULL,     -- 区块标识: sample_contacts, features
    item_order INTEGER NOT NULL DEFAULT 0,

    -- 内容数据
    content_data JSONB NOT NULL,          -- 灵活的 JSON 字段

    -- 多语言与状态
    locale VARCHAR(10) NOT NULL DEFAULT 'zh_CN',
    status INTEGER NOT NULL DEFAULT 1,    -- 1=active, 2=inactive, 3=draft

    -- 定时发布 (可选)
    start_time TIMESTAMP WITH TIME ZONE NULL,
    end_time TIMESTAMP WITH TIME ZONE NULL,

    -- 版本控制 (可选)
    version INTEGER NOT NULL DEFAULT 1,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,

    -- 审计字段
    created_by INTEGER REFERENCES admin_users(id) ON DELETE SET NULL,
    updated_by INTEGER REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_app_ui_contents_page_section_locale_current
        UNIQUE(page_key, section_key, locale, item_order, is_current)
);

CREATE INDEX idx_app_ui_contents_page_section ON app_ui_contents(page_key, section_key);
CREATE INDEX idx_app_ui_contents_status_time ON app_ui_contents(status, start_time, end_time);
CREATE INDEX idx_app_ui_contents_locale ON app_ui_contents(locale);
```

### 初始数据

**重要**: `avatar_file_id` 使用字符串 `file_id` (如 `"file_20251219_abc123"`),通过 `/api/v1/media/upload` 上传头像后获得。

```sql
-- 示例联系人
INSERT INTO app_ui_contents (page_key, section_key, item_order, content_data, locale, status) VALUES
('login', 'sample_contacts', 1, jsonb_build_object(
    'qiao_id', 'sample_showcase_1',
    'nickname', '小敲',
    'avatar_file_id', '<替换为实际的file_id>',
    'bio', '温暖的AI伙伴,喜欢倾听你的故事'
), 'zh_CN', 1);

-- 功能列表
INSERT INTO app_ui_contents (page_key, section_key, item_order, content_data, locale, status) VALUES
('login', 'features', 1, jsonb_build_object(
    'id', 'chat',
    'title', '智能对话',
    'description', '保持真人聊天的语气与节奏,随时陪伴'
), 'zh_CN', 1);
```

---

## 二、后端实现

### 2.1 Model

```python
# backend/app/models/app_content.py
from sqlalchemy import Boolean, Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.models.base import AutoIncrementModel

class AppUIContent(AutoIncrementModel):
    __tablename__ = "app_ui_contents"

    page_key: Mapped[str] = mapped_column(String(64), nullable=False)
    section_key: Mapped[str] = mapped_column(String(64), nullable=False)
    item_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="zh_CN")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    start_time: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

### 2.2 CRUD

```python
# backend/app/crud/app_content.py
from datetime import datetime, UTC
from sqlalchemy import select, and_
from app.crud.base import CRUDBase
from app.models.app_content import AppUIContent

class CRUDAppUIContent(CRUDBase[AppUIContent]):
    async def get_active_contents(
        self,
        db,
        page_key: str,
        section_key: str | None = None,
        locale: str = "zh_CN"
    ) -> list[AppUIContent]:
        """
        获取生效的内容,自动过滤状态和定时发布条件

        筛选条件:
        - status = 1 (active)
        - is_current = True (当前版本)
        - locale 匹配
        - start_time <= now (或为 NULL)
        - end_time > now (或为 NULL)

        排序: section_key ASC, item_order ASC
        """
        now = datetime.now(UTC)

        conditions = [
            AppUIContent.page_key == page_key,
            AppUIContent.locale == locale,
            AppUIContent.status == 1,
            AppUIContent.is_current == True,
            (AppUIContent.start_time == None) | (AppUIContent.start_time <= now),
            (AppUIContent.end_time == None) | (AppUIContent.end_time > now)
        ]

        if section_key:
            conditions.append(AppUIContent.section_key == section_key)

        query = (
            select(AppUIContent)
            .where(and_(*conditions))
            .order_by(AppUIContent.section_key, AppUIContent.item_order)
        )

        result = await db.execute(query)
        return list(result.scalars().all())

app_ui_content = CRUDAppUIContent(AppUIContent)
```

### 2.3 Service (关键实现)

**前置准备**: 在头像服务中添加公共函数 `get_default_avatar_url(db)`（开放给多处调用）

```python
# backend/app/services/app_content/service.py
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.app_content import app_ui_content
from app.enums import FileStatus
from app.models.message.media import MediaFile
from app.schemas.app_content import PageSections, SampleContactItem, FeatureItem
from app.services.media.url import build_public_url
from app.services.profile.avatar import get_default_avatar_url  # 公共函数,文件顶部导入
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def get_page_content(db: AsyncSession, page_key: str, locale: str = "zh_CN") -> PageSections:
    """
    获取页面内容,按 section 分组

    关键逻辑:
    1. 批量查询 avatar 的 file_id -> URL 映射
    2. 使用 avatars/default.webp 作为 fallback（优先读取 `system_configs.media_public_base_url`，空值时回退 `MEDIA_PUBLIC_BASE_URL`）
    3. 替换 avatar_file_id -> avatar_url
    4. 构造强类型 Pydantic 对象 (自动验证数据)

    默认头像兜底机制:
    - 若 avatar_file_id 在 media_files 中不存在或状态非 ACTIVE
    - 调用 get_default_avatar_url(db) 返回系统默认头像 CDN URL
    - 该函数优先读取 `system_configs.media_public_base_url`（回退 `MEDIA_PUBLIC_BASE_URL` 环境变量）拼接 avatars/default.webp；缺失时直接报错，避免返回无效 URL
    """
    contents = await app_ui_content.get_active_contents(db, page_key=page_key, locale=locale)

    if not contents:
        logger.warning("no_page_content_found", page_key=page_key, locale=locale)
        return PageSections()

    # 收集所有 avatar_file_id
    avatar_file_ids = {
        c.content_data["avatar_file_id"]
        for c in contents
        if "avatar_file_id" in c.content_data
    }

    # 批量查询 MediaFile (使用 file_id 而非 id)
    avatar_url_map: dict[str, str] = {}
    if avatar_file_ids:
        result = await db.execute(
            select(MediaFile).where(
                MediaFile.file_id.in_(avatar_file_ids),
                MediaFile.status == int(FileStatus.ACTIVE)
            )
        )
        avatar_url_map = {mf.file_id: build_public_url(mf) for mf in result.scalars()}

    # 获取默认头像 URL (fallback,永不为空)
    default_avatar_url = await get_default_avatar_url(db)

    # 转换数据并构造 Pydantic 对象
    result_map = defaultdict(list)
    for content in contents:
        data = content.content_data.copy()
        if "avatar_file_id" in data:
            file_id = data.pop("avatar_file_id")
            data["avatar_url"] = avatar_url_map.get(file_id, default_avatar_url)
        result_map[content.section_key].append(data)

    logger.info(
        "page_content_retrieved",
        page_key=page_key,
        locale=locale,
        section_count=len(result_map)
    )

    # 构造强类型响应 (Pydantic 自动验证数据)
    return PageSections(
        sample_contacts=[SampleContactItem(**item) for item in result_map.get("sample_contacts", [])],
        features=[FeatureItem(**item) for item in result_map.get("features", [])]
    )
```

### 2.4 API

```python
# backend/app/api/v1/app_content.py
from fastapi import APIRouter, Depends, Query
from app.schemas.app_content import PageContentResponse

router = APIRouter()

@router.get("/pages/{page_key}", response_model=PageContentResponse)
async def get_page_content_api(
    page_key: str,
    locale: str = Query("zh_CN"),
    db = Depends(get_db)
):
    """获取页面内容 (公开接口,无需认证)"""
    sections = await get_page_content(db, page_key=page_key, locale=locale)
    return PageContentResponse(page_key=page_key, locale=locale, sections=sections)
```

### 2.5 Schema

```python
# backend/app/schemas/app_content.py
from pydantic import BaseModel, Field

class SampleContactItem(BaseModel):
    """登录页示例联系人."""

    qiao_id: str = Field(..., min_length=1, max_length=64, description="示例账号ID")
    nickname: str = Field(..., min_length=2, max_length=20, description="昵称")
    avatar_url: str = Field(..., pattern=r"^https://", description="头像 CDN URL")
    bio: str = Field(..., min_length=1, max_length=50, description="个性签名")

class FeatureItem(BaseModel):
    """登录页功能介绍."""

    id: str = Field(..., min_length=1, max_length=32, description="功能唯一标识")
    title: str = Field(..., min_length=2, max_length=10, description="功能名称")
    description: str = Field(..., min_length=5, max_length=50, description="功能描述")

class PageSections(BaseModel):
    """页面内容分区."""

    sample_contacts: list[SampleContactItem] = Field(default_factory=list, description="示例联系人列表")
    features: list[FeatureItem] = Field(default_factory=list, description="功能列表")

class PageContentResponse(BaseModel):
    """页面内容响应."""

    page_key: str = Field(..., description="页面标识")
    locale: str = Field(..., description="语言代码")
    sections: PageSections = Field(..., description="页面分区内容")
```

**优势**:
- 自动数据验证: Pydantic 在序列化时检查字段类型、长度、格式
- Swagger 文档完整: 自动生成详细的 API 文档,前端可直接查看
- IDE 智能提示: 类型安全,开发时自动补全字段
- 拦截脏数据: 运营误操作插入错误数据时,后端响应 500 而非返回给前端

---

## 三、前端实现

### 3.1 API 封装

```typescript
// frontend/wx-minipg/utils/app-content.ts
import { get } from './api';

export async function fetchLoginPageContent() {
  const content = await get('/app/pages/login', { locale: 'zh_CN' }, { auth: false });
  return {
    sample_contacts: content.sections.sample_contacts || [],
    features: content.sections.features || []
  };
}
```

**设计原则**:
- 工具函数不捕获异常,让错误自然向上抛出
- 调用方根据具体场景实施降级策略 (参考 3.2 登录页示例)
- 后端不可达时登录页无法使用,不伪造数据

### 3.2 登录页改造

```typescript
// frontend/wx-minipg/pages/login/login.ts
import { fetchLoginPageContent } from '../../utils/app-content';
import { getLogger } from '../../utils/logger';

const logger = getLogger('Login');

Page({
  data: {
    sampleContacts: [],
    featureList: [],
    contentVisible: false,
    wechatLoading: false,
    loginCode: '',
  },

  async onLoad() {
    void this.loadLoginPageContent();
    // 其余登录初始化逻辑（authService、wx.login、登录按钮等）保持不变
  },

  async loadLoginPageContent() {
    try {
      const sections = await fetchLoginPageContent();
      const sampleContacts = sections.sample_contacts || [];
      const featureList = sections.features || [];
      this.setData({
        sampleContacts,
        featureList,
        contentVisible: sampleContacts.length > 0 || featureList.length > 0,
      });
    } catch (error) {
      logger.error('Failed to fetch login content', { error });
      this.setData({
        sampleContacts: [],
        featureList: [],
        contentVisible: false,
      });
    }
  },
});
```

**改造要点**:
- `login.ts` 通过接口返回的数据渲染示例联系人与功能列表，代码库中不得存在 `SAMPLE_CONTACTS`、`FEATURE_LIST` 等硬编码常量
- 登录页直接消费接口返回的 `avatar_url`，无需调用 `getAvatarUrl()`
- 不保留任何向后兼容代码

**降级策略**:
- 获取失败时设置 `contentVisible: false`
- WXML 使用 `wx:if="{{contentVisible}}"` 隐藏预览区块
- 登录核心功能不受影响(解耦设计)
- 记录错误日志便于排查（不向用户展示额外提示）

### 3.3 WXML 调整

```xml
<!-- 头像字段使用 avatar_url -->
<t-avatar size="medium" image="{{contact.avatar_url}}" />
```

---

## 四、头像上传流程

1. **准备图片**: 5 张头像,200x200px WebP,< 50KB
2. **上传到对象存储**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/media/upload" \
     -H "Authorization: Bearer <TOKEN>" \
     -F "file=@login_sample_1.webp" \
     -F "file_type=1"
   ```
3. **记录 file_id**: 响应中的 `"file_id": "file_20251219_abc123"`
4. **更新 SQL**: 替换 `avatar_file_id` 占位符为实际 `file_id`

---

## 五、部署检查

**数据库**:
- [ ] 表结构已创建 (`app_ui_contents`)
- [ ] 索引已创建
- [ ] 初始数据已插入 (头像 `file_id` 已替换)

**后端**:
- [ ] Model 注册到 `models/__init__.py`
- [ ] API 路由注册到 `api/v1/__init__.py`
- [ ] 接口测试通过: `GET /api/v1/app/pages/login`

**前端**:
- [ ] 新增 `app-content.ts` 工具文件
- [ ] `login.ts` 仅引用 API 数据源
- [ ] `login.wxml` 绑定 `avatar_url`
- [ ] 微信开发者工具测试通过

---

## 六、已知问题

1. **新增 section 需扩展 Schema**
   - 目前登录页 sections 已通过 `SampleContactItem` / `FeatureItem` / `PageSections` 定义
   - 若未来增加新的区块,必须同步更新 Schema 与 API 文档,否则 Pydantic 会直接拒绝未知字段

2. **前端 avatar.ts 工具函数**
   - 登录页完全使用接口返回的 `avatar_url`，默认头像兜底由后端基于 `system_configs.media_public_base_url` 拼接 avatars/default.webp
   - 其他仍引用 `getAvatarUrl` 的页面如需占位，应调用接口或提供在线占位资源（如 `https://via.placeholder.com/200x200.png?text=Avatar`），不要依赖本地 `/assets/avatars/` 目录
   - 若需自定义默认头像，统一在后端 avatar 服务里扩展逻辑，前端始终使用接口返回的 `avatar_url`
