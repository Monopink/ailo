# LLM Provider 架构重构任务

## 问题分析

### 1. 核心问题

**Bug**: `_convert_messages_to_input` 函数存在类型转换缺陷
- **位置**: `backend/app/services/llm/providers/openai_sdk.py:398-416`
- **现象**: 当 `content` 为列表时，直接使用原始内容而不进行类型规范化
- **影响**: 历史消息中的 `type: "text"` 或 `type: "output_text"` 被直接传递给 Doubao Responses API，导致 400 错误
- **错误信息**: `'The parameter content.type specified in the request are not valid: unknown type: text.'`

**架构问题1**: Provider 抽象不清晰
- `openai_sdk.py` 名不副实，实际是 Doubao Responses API 的专用实现
- 硬编码了 Doubao 特有的 `input_text`/`output_text` 格式
- 缺少 provider 能力声明机制
- 未来添加新 provider 时会造成混乱和代码冲突

**架构问题2**: OpenAI SDK 通用功能未封装
- 多个 provider 都使用 OpenAI SDK，但客户端创建、错误处理等逻辑在每个 adapter 中重复
- 违反 DRY 原则，增加维护成本
- 新增 OpenAI 兼容 provider 时需要复制粘贴代码

### 2. 根本原因

从 `ai_conversation_items` 表查询的历史消息 `content` 字段是 JSONB 格式，可能包含：
- Chat Completions API 格式: `{"type": "text", "text": "..."}`
- Responses API 输出格式: `{"type": "output_text", "text": "..."}`
- Responses API 输入格式: `{"type": "input_text", "text": "..."}`

当前代码在第 404 行直接使用列表内容，没有统一转换为 Responses API 要求的 `input_text` 格式。

## 解决方案

### 架构设计原则

1. **KISS**: 不过度设计，当前只有 Doubao，但为未来扩展留好接口
2. **SOLID**: 每个 adapter 只负责一种 API 格式，职责单一
3. **DRY**: 消息格式转换逻辑独立复用
4. **向后兼容**: 所有现有调用保持不变，只重构内部实现

### 新架构结构

```
backend/app/services/llm/
├── providers/
│   ├── base.py                    # Provider 能力声明（新建）
│   ├── openai_base.py            # OpenAI SDK 封装层（新建，核心改进）
│   ├── doubao_responses.py        # Doubao Responses API（重命名自 openai_sdk.py，继承 openai_base）
│   ├── openai_chat.py            # OpenAI Chat Completions API（新建，继承 openai_base）
│   ├── mock.py                   # Mock provider（保持不变）
│   ├── factory.py                # Provider 路由（更新映射）
│   └── __init__.py               # 导出（更新）
├── converters/                   # 消息格式转换器（新建目录）
│   ├── __init__.py
│   ├── base.py                   # 转换器基类
│   └── responses_format.py       # Responses API 格式转换器
├── client.py                     # 统一客户端（保持不变）
├── config.py                     # 配置管理（保持不变）
├── types.py                      # 数据类型（保持不变）
└── ...
```

### 架构分层说明

```
┌─────────────────────────────────────────┐
│   Business Layer (conversation_flow)    │  业务逻辑层
└─────────────────┬───────────────────────┘
                  │ 调用统一接口
┌─────────────────▼───────────────────────┐
│   Client Layer (client.py)              │  客户端层
│   - 配置选择与 Failover                   │
│   - 参数规范化                            │
│   - 统一错误处理                          │
└─────────────────┬───────────────────────┘
                  │ 路由到具体 adapter
┌─────────────────▼───────────────────────┐
│   Adapter Layer (providers/)            │  适配器层
│                                          │
│   ┌──────────────────────────────────┐  │
│   │  openai_base.py                  │  │  ← OpenAI SDK 通用封装
│   │  - 客户端创建 (_build_client)     │  │
│   │  - 错误处理与重试                 │  │
│   │  - 超时配置                       │  │
│   │  - 模板方法模式                   │  │
│   └──────────┬───────────────────────┘  │
│              │ 继承                      │
│   ┌──────────▼──────────┐  ┌──────────┐ │
│   │ doubao_responses.py │  │ openai   │ │  ← 特定 API 实现
│   │ - Responses API     │  │ _chat.py │ │
│   │ - 参数构建           │  │ - Chat   │ │
│   │ - 响应解析           │  │   API    │ │
│   │ - 消息格式转换       │  │          │ │
│   └─────────────────────┘  └──────────┘ │
└─────────────────────────────────────────┘
```

**关键设计点**：
1. **openai_base.py** 封装所有使用 OpenAI SDK 的 provider 的通用功能
2. **doubao_responses.py** 和 **openai_chat.py** 继承 openai_base，只实现各自 API 的特定逻辑
3. **converters/** 独立处理消息格式转换，可被多个 adapter 复用

### 核心组件设计

#### 1. Provider 能力声明 (`base.py`)

```python
from dataclasses import dataclass

@dataclass
class ProviderCapabilities:
    """Provider capability declaration."""

    supports_streaming: bool = True
    supports_json_schema: bool = False
    supports_caching: bool = False
    supports_tools: bool = True
    message_format: str = "openai"  # "openai" | "responses" | "custom"
    supports_thinking_mode: bool = False
    supports_multimodal: bool = False
```

#### 2. OpenAI SDK 封装层 (`openai_base.py`) - **核心新增**

**设计目的**：
- 封装所有使用 OpenAI SDK 的 provider 的通用功能
- 避免代码重复（客户端创建、错误处理、重试逻辑）
- 使用模板方法模式，让子类只需实现特定 API 的差异部分

**实现要点**：

```python
"""
OpenAI SDK base adapter.

Provides common functionality for all providers using OpenAI SDK.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from openai import AsyncOpenAI

from models.llm import LLMConfig, LLMProvider
from services.llm.types import LLMRequestOptions, LLMProviderResult
from exceptions.llm import LLMConfigurationError
from utils.logging import get_logger

logger = get_logger(__name__)


class OpenAIBaseAdapter(ABC):
    """
    Base adapter for providers using OpenAI SDK.

    This class encapsulates common OpenAI SDK operations:
    - Client creation and configuration
    - Error handling and retry logic
    - Timeout management

    Subclasses must implement:
    - build_request_params(): Build provider-specific request parameters
    - parse_response(): Parse provider-specific response format
    - _send_non_streaming_request(): Call specific API endpoint (non-streaming)
    - _send_streaming_request(): Call specific API endpoint (streaming)
    """

    def create_client(
        self,
        provider: LLMProvider,
        timeout: Optional[int] = None,
    ) -> AsyncOpenAI:
        """
        Create OpenAI SDK client with unified configuration.

        Handles:
        - API key retrieval from environment
        - Base URL configuration
        - Timeout and retry settings
        """
        api_key = self._get_api_key(provider)
        if not api_key:
            raise LLMConfigurationError(
                f"API key not configured for provider: {provider.display_name}"
            )

        return AsyncOpenAI(
            base_url=provider.base_url,
            api_key=api_key,
            timeout=timeout or 60,
            max_retries=3,
        )

    async def send_request(
        self,
        config: LLMConfig,
        provider: LLMProvider,
        options: LLMRequestOptions,
        *,
        stream: bool = False,
        preemption_checker=None,
    ) -> LLMProviderResult:
        """
        Unified request sending with error handling.

        Template method pattern:
        1. Create client (common)
        2. Build params (provider-specific, implemented by subclass)
        3. Send request (common)
        4. Parse response (provider-specific, implemented by subclass)
        """
        try:
            # Step 1: Create client (common)
            client = self.create_client(
                provider,
                timeout=options.provider_overrides.get("timeout"),
            )

            # Step 2: Build params (provider-specific)
            params = await self.build_request_params(options)

            # Step 3: Send request (common)
            if stream:
                response = await self._send_streaming_request(
                    client, params, preemption_checker
                )
            else:
                response = await self._send_non_streaming_request(
                    client, params
                )

            # Step 4: Parse response (provider-specific)
            return await self.parse_response(response, params)

        except Exception as exc:
            logger.error(
                "openai_base_request_failed",
                provider=provider.name,
                error=str(exc),
                exc_info=True,
            )
            raise

    @abstractmethod
    async def build_request_params(
        self, options: LLMRequestOptions
    ) -> Dict[str, Any]:
        """
        Build provider-specific request parameters.

        Must be implemented by subclass.
        Returns a dict containing all parameters needed for the API call.
        """
        pass

    @abstractmethod
    async def parse_response(
        self, response: Any, params: Dict[str, Any]
    ) -> LLMProviderResult:
        """
        Parse provider-specific response.

        Must be implemented by subclass.
        Converts API response to unified LLMProviderResult format.
        """
        pass

    @abstractmethod
    async def _send_non_streaming_request(
        self, client: AsyncOpenAI, params: Dict[str, Any]
    ) -> Any:
        """
        Send non-streaming request to specific API endpoint.

        Must be implemented by subclass.
        Example: client.responses.create() or client.chat.completions.create()
        """
        pass

    @abstractmethod
    async def _send_streaming_request(
        self,
        client: AsyncOpenAI,
        params: Dict[str, Any],
        preemption_checker,
    ) -> Any:
        """
        Send streaming request to specific API endpoint.

        Must be implemented by subclass.
        Should handle preemption_checker for early stopping.
        """
        pass

    def _get_api_key(self, provider: LLMProvider) -> Optional[str]:
        """Get API key from environment variables."""
        import os

        if provider.api_key_env:
            api_key = os.getenv(provider.api_key_env)
            if api_key:
                return api_key

        default_env_name = f"{provider.name.upper()}_API_KEY"
        return os.getenv(default_env_name)
```

**关键点**：
1. **模板方法模式**：`send_request()` 定义了请求流程，子类只需实现特定步骤
2. **通用功能封装**：客户端创建、错误处理在基类中统一处理
3. **抽象方法**：强制子类实现 API 特定的参数构建和响应解析

#### 2. 消息格式转换器 (`converters/`)

**基类** (`converters/base.py`):
```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List

class MessageConverter(ABC):
    """Base class for message format converters."""

    @abstractmethod
    def convert_to_provider_format(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert standard messages to provider-specific format."""
        pass

    @abstractmethod
    def normalize_content_blocks(
        self,
        blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Normalize content blocks to provider format."""
        pass
```

**Responses API 转换器** (`converters/responses_format.py`):
```python
class ResponsesFormatConverter(MessageConverter):
    """Converter for Doubao Responses API format."""

    def convert_to_provider_format(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert messages to Responses API input format."""
        converted = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if isinstance(content, list):
                # Normalize list content blocks
                content_blocks = self.normalize_content_blocks(content)
            else:
                # Convert string to input_text block
                content_blocks = [
                    {"type": "input_text", "text": str(content)}
                ]

            converted.append({"role": role, "content": content_blocks})

        return converted

    def normalize_content_blocks(
        self,
        blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Normalize content blocks to Responses API format.

        Converts all text-like blocks to input_text format:
        - type: "text" -> "input_text"
        - type: "output_text" -> "input_text"
        - type: "input_text" -> "input_text" (unchanged)

        Preserves other block types (image_url, etc.) as-is.
        """
        normalized = []
        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get("type", "")

            # Convert text-like blocks to input_text
            if block_type in ("text", "output_text", "input_text"):
                normalized.append({
                    "type": "input_text",
                    "text": block.get("text", ""),
                })
            else:
                # Preserve other block types (image_url, etc.)
                normalized.append(block)

        return normalized
```

#### 4. Doubao Responses Adapter (`doubao_responses.py`)

**重命名自 `openai_sdk.py`，继承 `OpenAIBaseAdapter`**

**关键修改**：

```python
"""
Doubao Responses API adapter.

Inherits from OpenAIBaseAdapter and implements Responses API specifics.
"""

from services.llm.providers.openai_base import OpenAIBaseAdapter
from services.llm.converters.responses_format import ResponsesFormatConverter
from services.llm.providers.base import ProviderCapabilities

# Capability declaration
CAPABILITIES = ProviderCapabilities(
    supports_streaming=True,
    supports_json_schema=True,
    supports_caching=True,
    supports_tools=True,
    message_format="responses",
    supports_multimodal=True,
)

# Message format converter
converter = ResponsesFormatConverter()


class DoubaoResponsesAdapter(OpenAIBaseAdapter):
    """Adapter for Doubao Responses API."""

    async def build_request_params(
        self, options: LLMRequestOptions
    ) -> Dict[str, Any]:
        """Build Responses API parameters."""
        # Convert messages using converter (fixes the bug!)
        converted_messages = converter.convert_to_provider_format(options.messages)

        params = {
            "model": options.model,
            "input": converted_messages,
        }

        # Add caching
        if options.caching.previous_response_id:
            params["previous_response_id"] = options.caching.previous_response_id

        # Build extra_body for Responses API specific parameters
        extra_body = self._build_extra_body(options)

        return {
            "params": params,
            "extra_body": extra_body,
            "extra_headers": options.extra_headers,
            "extra_query": options.extra_query,
        }

    async def _send_non_streaming_request(
        self, client: AsyncOpenAI, params: Dict[str, Any]
    ) -> Any:
        """Send non-streaming Responses API request."""
        return await client.responses.create(
            **params["params"],
            extra_body=params["extra_body"],
            extra_headers=params["extra_headers"],
            extra_query=params["extra_query"],
        )

    async def _send_streaming_request(
        self,
        client: AsyncOpenAI,
        params: Dict[str, Any],
        preemption_checker,
    ) -> Any:
        """Send streaming Responses API request with preemption support."""
        # Implementation similar to current code
        # ... (streaming logic with preemption_checker)
        pass

    async def parse_response(
        self, response: Any, params: Dict[str, Any]
    ) -> LLMProviderResult:
        """Parse Responses API response."""
        content, tool_calls, reasoning = self._extract_responses_content(response)
        usage = self._extract_usage(response)

        return LLMProviderResult(
            content=content,
            model=response.model,
            usage=usage,
            finish_reason=self._extract_finish_reason(response),
            raw_response=response.to_dict(),
            request_params=params["params"],
            response_id=getattr(response, "id", None),
            cache_hit=self._is_cache_hit(usage),
            tool_calls=tool_calls,
            reasoning_content=reasoning,
        )

    def _build_extra_body(self, options: LLMRequestOptions) -> Dict[str, Any]:
        """Build extra_body for Responses API."""
        # Current implementation for temperature, max_tokens, tools, JSON schema, etc.
        pass


# Module-level function for factory compatibility
async def send_request(
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    *,
    stream: bool = False,
    preemption_checker=None,
) -> LLMProviderResult:
    """Entry point for factory to call."""
    adapter = DoubaoResponsesAdapter()
    return await adapter.send_request(
        config, provider, options, stream=stream, preemption_checker=preemption_checker
    )
```

**改进点**：
1. ✅ 继承 `OpenAIBaseAdapter`，复用客户端创建和错误处理
2. ✅ 使用 `ResponsesFormatConverter` 修复消息类型转换 bug
3. ✅ 只实现 Responses API 特定的逻辑（参数构建、响应解析）
4. ✅ 保持模块级 `send_request()` 函数供 factory 调用

#### 4. OpenAI Chat Adapter (`openai_chat.py`)

新建文件，为未来真正的 OpenAI 兼容 provider 准备：

```python
"""
OpenAI Chat Completions API adapter.

This adapter implements the standard OpenAI Chat Completions API format,
which is compatible with many providers (OpenAI, Azure OpenAI, etc.).
"""

from services.llm.providers.base import ProviderCapabilities

CAPABILITIES = ProviderCapabilities(
    supports_streaming=True,
    supports_json_schema=False,  # Standard OpenAI doesn't support JSON Schema
    supports_caching=False,
    supports_tools=True,
    message_format="openai",
    supports_multimodal=True,
)

async def send_request(...) -> LLMProviderResult:
    """
    Send request using OpenAI Chat Completions API.

    Note: This is a placeholder implementation for future use.
    Currently, all providers use Doubao Responses API.
    """
    raise NotImplementedError(
        "OpenAI Chat Completions adapter not yet implemented. "
        "Use Doubao Responses adapter for now."
    )
```

#### 5. Factory 更新 (`factory.py`)

```python
PROVIDER_ADAPTERS: Dict[str, str] = {
    "doubao": "doubao_responses",  # Updated: use specific adapter
    "qwen": "doubao_responses",    # Qwen also uses Responses API
    "deepseek": "doubao_responses", # DeepSeek also uses Responses API
    "mock": "mock",
}

async def send_request(...) -> LLMProviderResult:
    """Route the LLM request to the correct adapter."""
    adapter_name = PROVIDER_ADAPTERS.get(provider.name, "doubao_responses")

    logger.debug(
        "llm_adapter_selected",
        provider=provider.name,
        adapter=adapter_name,
    )

    if adapter_name == "mock":
        from . import mock as adapter
    elif adapter_name == "doubao_responses":
        from . import doubao_responses as adapter
    elif adapter_name == "openai_chat":
        from . import openai_chat as adapter
    else:
        raise ValueError(f"Unsupported adapter: {adapter_name}")

    return await adapter.send_request(...)
```

## 实施步骤

**重要提示**：按顺序执行，每个 Phase 完成后验证再继续下一个。

### Phase 1: 创建基础设施

#### 1.1 创建 `providers/base.py`
```bash
# 创建文件
touch backend/app/services/llm/providers/base.py
```

**内容**：
- 定义 `ProviderCapabilities` 数据类
- 添加文档说明各字段含义
- 参考上面"核心组件设计"章节的代码

#### 1.2 创建 OpenAI SDK 封装层 `providers/openai_base.py` ⭐ **核心新增**
```bash
# 创建文件
touch backend/app/services/llm/providers/openai_base.py
```

**内容**：
- 定义 `OpenAIBaseAdapter` 抽象基类
- 实现 `create_client()` 方法（客户端创建）
- 实现 `send_request()` 方法（模板方法模式）
- 定义抽象方法：`build_request_params()`, `parse_response()`, `_send_non_streaming_request()`, `_send_streaming_request()`
- 实现 `_get_api_key()` 辅助方法
- 参考上面"核心组件设计"章节的完整代码

**验证**：
```bash
# 检查语法
python -m py_compile backend/app/services/llm/providers/openai_base.py
```

#### 1.3 创建 `converters/` 目录
```bash
# 创建目录和文件
mkdir -p backend/app/services/llm/converters
touch backend/app/services/llm/converters/__init__.py
touch backend/app/services/llm/converters/base.py
touch backend/app/services/llm/converters/responses_format.py
```

**`converters/__init__.py`**:
```python
from .responses_format import ResponsesFormatConverter

__all__ = ["ResponsesFormatConverter"]
```

**`converters/base.py`**:
- 定义 `MessageConverter` 抽象基类
- 参考上面"核心组件设计"章节的代码

**`converters/responses_format.py`**:
- 实现 `ResponsesFormatConverter` 类
- 实现 `convert_to_provider_format()` 方法
- 实现 `normalize_content_blocks()` 方法（**修复 bug 的关键**）
- 参考上面"核心组件设计"章节的完整代码

**验证**：
```bash
# 检查语法
python -m py_compile backend/app/services/llm/converters/*.py
```

### Phase 2: 重构现有 Adapter

#### 2.1 重命名 `openai_sdk.py` 为 `doubao_responses.py`
```bash
cd backend/app/services/llm/providers
git mv openai_sdk.py doubao_responses.py
```

#### 2.2 修改 `doubao_responses.py` ⭐ **核心修改**

**步骤**：

1. **更新导入语句**：
```python
# 添加新导入
from services.llm.providers.openai_base import OpenAIBaseAdapter
from services.llm.converters.responses_format import ResponsesFormatConverter
from services.llm.providers.base import ProviderCapabilities
```

2. **添加能力声明**（文件顶部）：
```python
CAPABILITIES = ProviderCapabilities(
    supports_streaming=True,
    supports_json_schema=True,
    supports_caching=True,
    supports_tools=True,
    message_format="responses",
    supports_multimodal=True,
)

converter = ResponsesFormatConverter()
```

3. **创建 Adapter 类**：
```python
class DoubaoResponsesAdapter(OpenAIBaseAdapter):
    """Adapter for Doubao Responses API."""
    # 实现抽象方法...
```

4. **删除重复代码**：
   - 删除 `_build_client()` 函数（已在 openai_base 中）
   - 删除 `_get_api_key()` 函数（已在 openai_base 中）
   - 删除 `_convert_messages_to_input()` 函数（使用 converter 替代）

5. **重构 `send_request()` 函数**：
   - 改为模块级函数，创建 adapter 实例并调用
   - 参考上面"核心组件设计"章节的代码

6. **更新文档字符串**：
```python
"""
Doubao Responses API adapter.

This adapter implements Doubao's Responses API using OpenAI SDK.
Inherits from OpenAIBaseAdapter for common OpenAI SDK functionality.
"""
```

**验证**：
```bash
# 检查语法
python -m py_compile backend/app/services/llm/providers/doubao_responses.py

# 检查导入
python -c "from services.llm.providers import doubao_responses; print('OK')"
```

#### 2.3 更新 `factory.py`

**修改**：
```python
PROVIDER_ADAPTERS: Dict[str, str] = {
    "doubao": "doubao_responses",  # 更新：使用新名称
    "qwen": "doubao_responses",
    "deepseek": "doubao_responses",
    "mock": "mock",
}

async def send_request(...) -> LLMProviderResult:
    adapter_name = PROVIDER_ADAPTERS.get(provider.name, "doubao_responses")

    if adapter_name == "mock":
        from . import mock as adapter
    elif adapter_name == "doubao_responses":
        from . import doubao_responses as adapter  # 更新导入
    elif adapter_name == "openai_chat":
        from . import openai_chat as adapter
    else:
        raise ValueError(f"Unsupported adapter: {adapter_name}")

    return await adapter.send_request(...)
```

**验证**：
```bash
python -m py_compile backend/app/services/llm/providers/factory.py
```

### Phase 3: 创建占位 Adapter

#### 3.1 创建 `openai_chat.py`
```bash
touch backend/app/services/llm/providers/openai_chat.py
```

**内容**：
```python
"""
OpenAI Chat Completions API adapter.

Placeholder for future OpenAI-compatible providers.
Inherits from OpenAIBaseAdapter.
"""

from services.llm.providers.openai_base import OpenAIBaseAdapter
from services.llm.providers.base import ProviderCapabilities
from services.llm.types import LLMProviderResult
from models.llm import LLMConfig, LLMProvider

CAPABILITIES = ProviderCapabilities(
    supports_streaming=True,
    supports_json_schema=False,
    supports_caching=False,
    supports_tools=True,
    message_format="openai",
    supports_multimodal=True,
)


async def send_request(
    config: LLMConfig,
    provider: LLMProvider,
    options,
    *,
    stream: bool = False,
    preemption_checker=None,
) -> LLMProviderResult:
    """
    Placeholder for OpenAI Chat Completions API.

    Currently not implemented. All providers use Doubao Responses API.
    """
    raise NotImplementedError(
        "OpenAI Chat Completions adapter not yet implemented. "
        "Use Doubao Responses adapter for now."
    )
```

### Phase 4: 更新导入和测试

#### 4.1 全局搜索并更新导入引用
```bash
# 搜索所有导入 openai_sdk 的地方
grep -r "from.*openai_sdk" backend/app/
grep -r "import.*openai_sdk" backend/app/

# 手动更新为 doubao_responses
```

**预期**：应该没有其他文件直接导入 `openai_sdk`，因为都通过 factory 调用。

#### 4.2 更新 `providers/__init__.py`
```python
from . import doubao_responses, openai_chat, mock, factory

__all__ = ["doubao_responses", "openai_chat", "mock", "factory"]
```

#### 4.3 运行测试验证
```bash
# 1. 语法检查
python -m py_compile backend/app/services/llm/providers/*.py
python -m py_compile backend/app/services/llm/converters/*.py

# 2. 单元测试
cd backend
pytest tests/unit/services/test_llm_responses_payload.py -v

# 3. 导入测试
python -c "
from services.llm.providers import factory
from services.llm.providers import doubao_responses
from services.llm.converters import ResponsesFormatConverter
print('All imports OK')
"
```

### Phase 5: 验证和文档

#### 5.1 集成测试
```bash
# 启动后端服务
cd backend
docker-compose up -d

# 测试 LLM 配置（通过管理后台）
# 访问 http://localhost:8000/qiao-dash/
# 测试 LLM 配置功能

# 测试 AI 对话
# 访问 ai_character/chat-test/ 端点
```

#### 5.2 验证修复效果

**测试场景**：
1. ✅ 新对话（无历史消息）
2. ✅ 有历史消息的对话（包含不同 content type）
3. ✅ 流式请求
4. ✅ 非流式请求
5. ✅ 带 JSON Schema 的请求
6. ✅ 带工具调用的请求

**预期结果**：
- 不再出现 `unknown type: text` 错误
- 历史消息中的 `text`/`output_text` 正确转换为 `input_text`
- 所有功能正常工作

#### 5.3 代码审查检查清单

- [ ] `openai_base.py` 正确实现模板方法模式
- [ ] `doubao_responses.py` 正确继承 `OpenAIBaseAdapter`
- [ ] `ResponsesFormatConverter` 正确处理所有 content type
- [ ] 没有代码重复（客户端创建、错误处理等）
- [ ] 所有导入引用已更新
- [ ] 文档字符串清晰准确
- [ ] 类型提示完整

#### 5.4 更新项目文档
- 在 `CLAUDE.md` 中更新架构说明（如需要）
- 添加代码注释说明新架构

## 测试计划

### 单元测试

1. **转换器测试** (`test_converters.py`)
   ```python
   def test_normalize_text_type():
       """Test converting 'text' type to 'input_text'"""

   def test_normalize_output_text_type():
       """Test converting 'output_text' type to 'input_text'"""

   def test_preserve_input_text_type():
       """Test 'input_text' type remains unchanged"""

   def test_preserve_other_types():
       """Test image_url and other types are preserved"""
   ```

2. **Adapter 测试** (`test_doubao_responses.py`)
   ```python
   def test_message_conversion_with_mixed_types():
       """Test messages with mixed content types"""

   def test_streaming_with_preemption():
       """Test streaming can be preempted"""
   ```

### 集成测试

1. **对话流程测试**
   - 创建包含历史消息的对话
   - 验证新消息能正确处理
   - 确认 LLM 响应正常

2. **管理后台测试**
   - 测试 LLM 配置测试功能
   - 验证不同 provider 的切换

## 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 文件重命名导致导入错误 | 高 | 中 | 全局搜索所有导入，使用 IDE 重构功能 |
| 消息格式转换遗漏边界情况 | 中 | 中 | 充分的单元测试覆盖 |
| 现有测试失败 | 中 | 低 | 逐步验证，及时修复 |
| 性能影响 | 低 | 低 | 转换器是轻量级操作，影响可忽略 |

## 预期收益

1. **Bug 修复**: 解决历史消息类型转换错误
2. **架构清晰**: Provider 职责明确，命名准确
3. **易于扩展**: 新增 provider 只需实现 adapter 和可选的 converter
4. **可维护性**: 代码结构清晰，逻辑分离
5. **可测试性**: 转换逻辑独立，易于单元测试

## 完成标准

- [ ] 所有新文件创建完成
- [ ] `openai_sdk.py` 成功重命名为 `doubao_responses.py`
- [ ] 消息格式转换器实现并测试通过
- [ ] Factory 映射更新完成
- [ ] 所有导入引用更新完成
- [ ] 单元测试通过
- [ ] 集成测试通过（`ai_character/chat-test/` 正常工作）
- [ ] 代码审查通过
- [ ] 文档更新完成

## 参考资料

- [ai-message-processing.md](./ai-message-processing.md): AI 消息处理技术文档
- [Doubao Responses API 文档](../../references/doubao-docs/): Doubao API 参考
- [SOLID 原则](https://en.wikipedia.org/wiki/SOLID): 软件设计原则
