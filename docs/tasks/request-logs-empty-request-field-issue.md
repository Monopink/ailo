# Request Logs 表 request 字段为空问题分析

## 问题描述

在测试 AI 聊天功能时，发现 `request_logs` 表中的 `request` 字段为空或内容不完整，无法查看完整的请求参数。

## 问题根源分析

### 1. 数据流追踪

通过代码追踪，发现数据流如下：

```
LLM Provider (doubao_responses.py)
  ↓
  _build_responses_call_params() → 返回基本参数 (model, input)
  _build_request_kwargs() → 返回额外参数 (temperature, tools, etc. 在 extra_body 中)
  ↓
parse_response() → 只返回 call_params 作为 request_params
  ↓
LLM Client (client.py:357) → 使用 provider_result.request_params
  ↓
Transaction Service (transactions.py:215) → 保存到数据库
```

### 2. 核心问题

在 `backend/app/services/llm/providers/doubao_responses.py` 文件中：

**问题位置 1**: `parse_response` 方法 (第 61-82 行)

```python
async def parse_response(
    self,
    response: JSONDict,
    params: dict[str, JSONDict],
    options: LLMRequestOptions,
) -> LLMProviderResult:
    content, tool_calls, reasoning_content = _extract_responses_text(response)
    usage = _usage_to_dict(getattr(response, "usage", None))
    call_params = params.get("call_params")  # 只获取了 call_params

    return LLMProviderResult(
        content=content,
        model=getattr(response, "model", None),
        usage=usage,
        finish_reason=_extract_finish_reason(response),
        raw_response=response.to_dict() if hasattr(response, "to_dict") else None,
        request_params=call_params if isinstance(call_params, dict) else None,  # ❌ 问题在这里
        response_id=getattr(response, "id", None),
        cache_hit=_is_cache_hit(usage),
        tool_calls=tool_calls,
        reasoning_content=reasoning_content,
    )
```

**问题说明**:
- `call_params` 只包含基本参数：`model` 和 `input`
- 重要的请求参数（`temperature`, `max_tokens`, `tools`, `tool_choice` 等）都在 `request_kwargs["extra_body"]` 中
- 当前代码只返回了 `call_params`，导致丢失了大部分请求参数

**问题位置 2**: `_build_responses_call_params` 方法 (第 221-252 行)

```python
def _build_responses_call_params(options: LLMRequestOptions) -> JSONDict:
    """
    Build the set of direct parameters accepted by Responses API.
    """
    params: JSONDict = {
        "model": options.model,
        "input": cast(JSONValue, _converter.convert_to_provider_format(options.messages)),
    }
    # ... 只包含基本参数
    return params
```

**问题位置 3**: `_build_request_kwargs` 方法 (第 254-315 行)

```python
def _build_request_kwargs(options: LLMRequestOptions) -> JSONDict:
    """
    Build kwargs (extra headers/body/query) for Responses API invocation.
    """
    extra_body: JSONDict = dict(options.extra_body or {})

    if options.temperature is not None:
        extra_body["temperature"] = options.temperature
    if options.top_p is not None:
        extra_body["top_p"] = options.top_p
    if options.max_tokens is not None:
        extra_body["max_output_tokens"] = options.max_tokens
    if options.stop_sequences:
        extra_body["stop"] = cast(JSONValue, options.stop_sequences)

    if options.tools:
        extra_body["tools"] = cast(JSONValue, options.tools)
        if options.tool_choice:
            extra_body["tool_choice"] = options.tool_choice
        if options.max_tool_calls:
            extra_body["max_tool_calls"] = options.max_tool_calls

    # ... 更多参数在 extra_body 中

    return {
        "extra_headers": merged_headers or None,
        "extra_query": merged_query or None,
        "extra_body": extra_body or None,  # ⚠️ 这些参数没有被包含在 request_params 中
        "timeout": options.provider_overrides.get("timeout"),
    }
```

### 3. 对比 Mock Provider（正常工作）

在 `backend/app/services/llm/providers/mock.py` 中：

```python
def _build_payload(
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    provider_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a payload snapshot to simplify debugging."""

    payload: dict[str, Any] = {
        "model": options.model or config.model_name or provider.default_model or "mock-model-v1",
        "messages": options.messages,
        "input": provider_messages,
        "temperature": ...,
        "max_tokens": ...,
        "thinking_mode": ...,
        "tools": options.tools,
        "tool_choice": options.tool_choice,
        # ... 完整的参数列表
    }
    return payload

# 然后在返回时：
return LLMProviderResult(
    content=content,
    model=...,
    usage=usage,
    finish_reason="stop",
    raw_response=raw_response,
    request_params=payload,  # ✅ 返回完整的参数
    response_id=response_identifier,
)
```

**关键区别**：Mock Provider 在构建 payload 时就包含了所有参数，并直接返回。

## 解决方案

### 方案 1: 修改 `parse_response` 方法（推荐）

在 `DoubaoResponsesAdapter.parse_response` 方法中，将 `call_params` 和 `extra_body` 合并后返回：

```python
async def parse_response(
    self,
    response: JSONDict,
    params: dict[str, JSONDict],
    options: LLMRequestOptions,
) -> LLMProviderResult:
    content, tool_calls, reasoning_content = _extract_responses_text(response)
    usage = _usage_to_dict(getattr(response, "usage", None))
    call_params = params.get("call_params")
    request_kwargs = params.get("request_kwargs")

    # ✅ 合并 call_params 和 extra_body 以获取完整的请求参数
    merged_request_params: JSONDict | None = None
    if isinstance(call_params, dict):
        merged_request_params = dict(call_params)
        if isinstance(request_kwargs, dict):
            extra_body = request_kwargs.get("extra_body")
            if isinstance(extra_body, dict):
                merged_request_params.update(extra_body)

    return LLMProviderResult(
        content=content,
        model=getattr(response, "model", None),
        usage=usage,
        finish_reason=_extract_finish_reason(response),
        raw_response=response.to_dict() if hasattr(response, "to_dict") else None,
        request_params=merged_request_params,  # ✅ 返回合并后的完整参数
        response_id=getattr(response, "id", None),
        cache_hit=_is_cache_hit(usage),
        tool_calls=tool_calls,
        reasoning_content=reasoning_content,
    )
```

**优点**：
- 最小改动
- 不影响现有的 API 调用逻辑
- 保持了 call_params 和 request_kwargs 的分离（用于实际 API 调用）
- 只影响返回给上层的 request_params

**缺点**：
- 需要在非流式请求的 parse_response 中修改
- 需要同步修改流式请求中的相关代码（第 143、149、179 行）

### 方案 2: 修改 `_build_responses_call_params` 方法

将所有参数都放入 `call_params` 中：

```python
def _build_responses_call_params(options: LLMRequestOptions) -> JSONDict:
    """
    Build the complete set of parameters for logging and debugging.
    """
    params: JSONDict = {
        "model": options.model,
        "input": cast(JSONValue, _converter.convert_to_provider_format(options.messages)),
    }

    # 添加其他参数
    if options.temperature is not None:
        params["temperature"] = options.temperature
    if options.max_tokens is not None:
        params["max_tokens"] = options.max_tokens
    if options.tools:
        params["tools"] = cast(JSONValue, options.tools)
    # ... 更多参数

    return params
```

**优点**：
- 更直观，所有参数都在一个地方
- 不需要修改 parse_response

**缺点**：
- 可能与 Responses API 的实际调用方式不一致
- 需要维护两份参数列表（一份用于实际调用，一份用于日志）
- 可能导致混淆

### 方案 3: 创建单独的方法构建完整请求参数

```python
def _build_complete_request_params(
    call_params: JSONDict,
    request_kwargs: JSONDict
) -> JSONDict:
    """Merge call_params and extra_body for complete request logging."""
    merged = dict(call_params)
    extra_body = request_kwargs.get("extra_body")
    if isinstance(extra_body, dict):
        merged.update(extra_body)
    return merged
```

然后在需要的地方调用这个方法。

**优点**：
- 代码更清晰，职责分离
- 易于测试

**缺点**：
- 需要在多个地方调用（parse_response 和流式请求处理）

## 推荐实施步骤

1. **采用方案 1**：修改 `parse_response` 方法
2. **同步修改流式请求**：在 `_send_streaming_request` 方法中的三个返回位置（第 143、149、179 行）也应用相同的合并逻辑
3. **添加单元测试**：确保 request_params 包含完整参数
4. **验证**：
   - 运行 AI 聊天测试
   - 检查 request_logs 表中的 request 字段
   - 确认包含 temperature, tools, max_tokens 等参数

## 影响范围

### 修改的文件

- `backend/app/services/llm/providers/doubao_responses.py`
  - `DoubaoResponsesAdapter.parse_response` 方法（第 61-82 行）
  - `DoubaoResponsesAdapter._send_streaming_request` 方法（第 108-190 行）

### 影响的功能

- AI 聊天功能的请求日志记录
- AI 测试执行器的请求日志记录
- 所有使用 Doubao Responses API 的场景

### 不影响的部分

- 实际的 LLM API 调用逻辑（因为修改只影响返回的 request_params，不影响实际调用）
- Mock Provider（已经正常工作）
- 其他不使用 Doubao Responses API 的提供商

## 测试计划

1. **单元测试**：
   - 测试 parse_response 返回的 request_params 包含所有必要字段
   - 测试流式和非流式请求都正确记录参数

2. **集成测试**：
   - 在 AI Instance Chat Test 中测试
   - 检查 request_logs 表中的数据

3. **验证检查点**：
   - [ ] request_logs.request 字段不为空
   - [ ] 包含 model 和 input
   - [ ] 包含 temperature（如果设置）
   - [ ] 包含 tools（如果使用）
   - [ ] 包含 max_tokens（如果设置）
   - [ ] 包含其他 extra_body 中的参数

## 附加说明

### 为什么之前没发现这个问题？

1. **Mock Provider 正常工作**：在本地测试环境中，使用的是 Mock Provider，它正确实现了完整的 request_params
2. **功能未受影响**：这个问题只影响日志记录，不影响实际的 LLM 调用功能
3. **可能只在生产环境使用 Doubao**：开发环境可能主要使用 Mock Provider

### 长期优化建议

1. **统一 Provider 接口**：确保所有 Provider 都以相同的方式构建 request_params
2. **添加集成测试**：测试每个 Provider 的 request_params 是否完整
3. **文档化要求**：在 Provider 接口文档中明确说明 request_params 应该包含哪些字段
