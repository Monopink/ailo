# 创建上下文缓存 API

**最近更新时间：2025.07.02 10:30:42**
**首次发布时间：2025.04.10 20:43:38**

**POST** `https://ark.cn-beijing.volces.com/api/v3/context/create`

上下文缓存（Context API）是方舟提供的一个高效的缓存机制。它通过缓存上下文数据，减少重复加载或处理，提高响应速度和一致性。本文介绍上下文缓存 API 的输入输出参数，供您使用接口时查阅字段含义。

## 快速入口

### 鉴权说明

- [计费说明](https://www.volcengine.com/docs/82379/1099320#%E4%B8%8A%E4%B8%8B%E6%96%87%E7%BC%93%E5%AD%98%E8%AE%A1%E8%B4%B9)
- [API Key](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey?apikey=%7B%7D)
- [支持模型](https://www.volcengine.com/docs/82379/1330310#e6772192)
- [调用教程](https://www.volcengine.com/docs/82379/1396491)
- [开通模型](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&OpenTokenDrawer=false)

## 请求参数

### 请求体

#### model

- **类型**: string
- **必选**: 是
- **说明**: 通过 Endpoint ID 来调用模型，获得限流、计费类型（前付费/后付费）、运行状态查询、监控、安全等高级能力，可参考[获取 Endpoint ID](https://www.volcengine.com/docs/82379/1099522)。暂不支持通过 Model ID 来调用。

#### messages

- **类型**: object[]
- **必选**: 是
- **说明**: 对话组成的消息列表。您希望缓存的信息。

**注意**: 初始化的信息如系统人设，背景信息等，请使用系统消息（System message）放在消息列表最前。这部分信息在2种缓存模式下，均会一直存储在缓存中，直到缓存到期（触达最大生命周期）释放。

##### 系统消息 (object)

系统消息，开发人员提供的指令，模型应遵循这些指令。如模型扮演的角色或者目标等。

**属性**

- `messages.role` (string, 必选): 发送消息的角色，此处应为`system`。
- `messages.content` (string, 必选): 系统信息内容。

##### 用户消息 (object)

用户发送的消息，包含提示或附加上下文信息。

**属性**

- `messages.role` (string, 必选): 发送消息的角色，此处应为`user`。
- `messages.content` (string, 必选): 用户信息内容。
- `messages.name` (string): 发送此消息的角色的姓名。用于区别同一个角色但是不同主体发送的消息。

##### 模型消息 (object)

模型响应用户消息而回复的消息。

**说明**: `messages.content` 与 `messages.tool_calls` 字段二者至少填写其一。

**属性**

- `messages.role` (string, 必选): 发送消息的角色，此处应为`assistant`。
- `messages.content` (string): 模型回复的消息。
- `messages.tool_calls` (object[]): 模型回复的工具调用信息。

**属性**

- `messages.tool_calls.function` (object, 必选): 模型调用工具对应的函数信息。

**属性**

- `messages.tool_calls.function.name` (string, 必选): 模型需要调用的函数名称。
- `messages.tool_calls.function.arguments` (string, 必选): 模型生成的用于调用函数的参数，JSON 格式。

**说明**: 模型并不总是生成有效的 JSON，并且可能会虚构出一些您的函数参数规范中未定义的参数。在调用函数之前，请在您的代码中验证这些参数是否有效。

- `messages.tool_calls.id` (string, 必选): 调用的工具的 ID。
- `messages.tool_calls.type` (string, 必选): 工具类型，当前仅支持`function`。

#### mode

- **类型**: string
- **默认值**: session
- **说明**: 本次请求创建的上下文缓存的类型。[点此](https://www.volcengine.com/docs/82379/1398933)了解类型介绍。[点此](https://www.volcengine.com/docs/82379/1330310#e6772192)了解支持的模型。
  - **session**: Session 缓存。
  - **common_prefix**: 前缀缓存。

#### ttl

- **类型**: integer / null
- **默认值**: 86400
- **说明**: 过期时长，单位为秒，设置范围：[3600, 604800]，即1小时到7天。信息在创建后即开始计时，每次使用则重置为0。计时超过ttl，信息会被从缓存中删除。每次调用chat均根据ttl更新过期时间。

#### truncation_strategy

- **类型**: object / null
- **默认值**: null
- **说明**: 缓存的上下文长度的窗口长度策略配置，只在当 mode 字段设置为session，该字段可设置。支持 Session 缓存的模型能且只能支持 1 种 Session 缓存模式。如不配置该字段，方舟会根据您调用的模型自动适配合适的 Session 缓存模式。

##### last_history_tokens 模式 (object)

触发缓存上限不会重新计算。

**属性**

- `truncation_strategy.type` (string, 必选): 此处应为 `last_history_tokens`。
- `truncation_strategy.last_history_tokens` (integer, 默认值 4096): 取值范围： (0,32768)。缓存上下文窗口大小，即可缓存的上下文的最大 token 数。触发该上限将根据缓存上下文窗口大小对缓存内容进行清除。清除顺序按照信息被缓存时间长短排序，先清除缓存时间长的信息。

##### rolling_tokens 模式 (object)

触发缓存上限会进行重新计算。

**属性**

- `truncation_strategy.type` (string, 必选): 此处应为 `rolling_tokens`。
- `truncation_strategy.rolling_tokens` (boolean, 默认值 true): 在缓存中历史消息长度接近 max_window_tokens 字段值时，是否自动对历史上下文进行裁剪（按照 message 元素粒度裁剪，按照 message 元素取整，即删除的信息的长度在 rolling_window_tokens 范围内，不会截断任意信息）。
  - **false**: 在历史消息长度超过上下文长度时模型会停止输出（返回字段 finish_reason 为length)。
  - **true**: 在历史消息长度接近上下文长度时模型按照先进先出的顺序，自动删除定量（rolling_window_tokens 字段值 token 数）的内容，为新对话内容腾挪缓存空间；同时对缓存中的信息进行重新计算和读入，保障内容理解一致性。具体的计算逻辑，请参见[rolling_tokens 模式](https://www.volcengine.com/docs/82379/1396491#rolling-tokens-%E6%A8%A1%E5%BC%8F)。
- `truncation_strategy.max_window_tokens` (integer / null, 默认值 32768): 在缓存中可存储的历史消息长度最大值。取值满足下面条件：0 < rolling_tokens < max_window_tokens < context window（模型最大上下文）。
- `truncation_strategy.rolling_window_tokens` (integer / null, 默认值 4096): 当缓存触发了max_window_tokens 上限，则会裁剪滚动窗口长度。取值满足下面条件：0 < rolling_tokens < max_window_tokens < context window（模型最大上下文）。

## 响应参数

#### id

- **类型**: string
- **说明**: 本次请求创建的上下文缓存的ID，在后续创建带缓存的[上下文缓存对话 API](https://www.volcengine.com/docs/82379/1346560)需要使用。

#### model

- **类型**: string
- **说明**: 本次请求使用的推理接入点的 ID 。

#### mode

- **类型**: string
- **说明**: 本次请求创建的上下文缓存的类型。[点此](https://www.volcengine.com/docs/82379/1330310#e6772192)了解支持的模型。
  - **session**: Session 缓存。
  - **common_prefix**: 前缀缓存。

#### ttl

- **类型**: integer
- **说明**: 本次请求创建的上下文缓存过期时长，单位为秒。信息在创建后即开始计时，每次使用则重置为0。计时超过ttl，信息会被从缓存中删除。每次调用chat均根据ttl更新过期时间。过期时间可以设置的范围在1小时到7天，即[3600, 604800]。

#### truncation_strategy

- **类型**: object
- **说明**: 本次请求创建的 Session 缓存使用的截断策略信息。

##### last_history_tokens 模式 (object)

触发缓存上限，自动滚动缓存内容，无需重新计算。

**属性**

- `truncation_strategy.type` (string): 本次请求创建的 Session 缓存的截断策略，此处应为 `last_history_tokens`。
- `truncation_strategy.last_history_tokens` (integer): 本次请求创建的 Session 缓存可缓存的最大 token 数。

##### rolling_tokens 模式 (object)

触发缓存上限，进行重新计算。

**属性**

- `truncation_strategy.type` (string): 本次请求创建的 Session 缓存的截断策略，此处应为 `rolling_tokens`。
- `truncation_strategy.rolling_tokens` (boolean): 本次请求创建的 Session 缓存，当缓存的信息量达到最大缓存窗口时，是否自动处理。

#### usage

- **类型**: object
- **说明**: 本次请求的 token 用量。

**属性**

- `usage.prompt_tokens` (integer): 输入的 prompt token 数量。
- `usage.completion_tokens` (integer): 模型生成的 token 数量。
- `usage.total_tokens` (integer): 本次请求消耗的总 token 数量（输入 + 输出）。
- `usage.prompt_tokens_details` (object): 命中上下文缓存的 token 细节。
  - `usage.prompt_tokens_details.cached_tokens` (integer): 命中上下文缓存的 token 数。

## 示例

### 创建前缀缓存

#### Curl 示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/context/create \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "messages": [
    {
      "content": "你是李雷，你只会说\"我是李雷\"",
      "role": "system"
    }
  ],
  "mode": "common_prefix",
  "model": "ep-20250410*****-*****"
}'
```

#### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(
    api_key=os.getenv('ARK_API_KEY'),
)

# 创建前缀缓存
response = client.context.create(
    model="ep-20250410*****-*****",
    messages=[
        {
            "role": "system",
            "content": "你是李雷，你只会说\"我是李雷\""
        }
    ],
    mode="common_prefix"
)

print(f"缓存ID: {response.id}")
print(f"缓存模式: {response.mode}")
print(f"过期时间: {response.ttl}秒")
```

#### OpenAI Python SDK 示例

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 创建前缀缓存
response = client.post(
    "/context/create",
    body={
        "model": "ep-20250410*****-*****",
        "messages": [
            {
                "role": "system",
                "content": "你是李雷，你只会说\"我是李雷\""
            }
        ],
        "mode": "common_prefix"
    }
)

print(f"缓存ID: {response['id']}")
print(f"缓存模式: {response['mode']}")
```

### 创建 Session 缓存

#### Curl 示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/context/create \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "messages": [
    {
      "content": "你是一个专业的AI助手，擅长回答各种问题。",
      "role": "system"
    },
    {
      "content": "你好，我想了解一下人工智能的发展历史。",
      "role": "user"
    },
    {
      "content": "人工智能的发展历史可以追溯到20世纪40年代...",
      "role": "assistant"
    }
  ],
  "mode": "session",
  "ttl": 7200,
  "truncation_strategy": {
    "type": "rolling_tokens",
    "rolling_tokens": true,
    "max_window_tokens": 16384,
    "rolling_window_tokens": 2048
  },
  "model": "ep-20250410*****-*****"
}'
```

#### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(
    api_key=os.getenv('ARK_API_KEY'),
)

# 创建Session缓存
response = client.context.create(
    model="ep-20250410*****-*****",
    messages=[
        {
            "role": "system",
            "content": "你是一个专业的AI助手，擅长回答各种问题。"
        },
        {
            "role": "user",
            "content": "你好，我想了解一下人工智能的发展历史。"
        },
        {
            "role": "assistant",
            "content": "人工智能的发展历史可以追溯到20世纪40年代..."
        }
    ],
    mode="session",
    ttl=7200,
    truncation_strategy={
        "type": "rolling_tokens",
        "rolling_tokens": True,
        "max_window_tokens": 16384,
        "rolling_window_tokens": 2048
    }
)

print(f"缓存ID: {response.id}")
print(f"缓存模式: {response.mode}")
print(f"截断策略: {response.truncation_strategy.type}")
```

### 响应示例

#### 前缀缓存响应

```json
{
  "id": "ctx-20250410175333-lkjq2",
  "model": "ep-20250410*****-*****",
  "ttl": 86400,
  "usage": {
    "prompt_tokens": 18,
    "completion_tokens": 0,
    "total_tokens": 18,
    "prompt_tokens_details": {
      "cached_tokens": 0
    }
  },
  "mode": "common_prefix"
}
```

#### Session缓存响应

```json
{
  "id": "ctx-20250410180245-abc123",
  "model": "ep-20250410*****-*****",
  "mode": "session",
  "ttl": 7200,
  "truncation_strategy": {
    "type": "rolling_tokens",
    "rolling_tokens": true,
    "max_window_tokens": 16384,
    "rolling_window_tokens": 2048
  },
  "usage": {
    "prompt_tokens": 156,
    "completion_tokens": 0,
    "total_tokens": 156,
    "prompt_tokens_details": {
      "cached_tokens": 0
    }
  }
}
```

## 缓存模式对比

| 特性 | 前缀缓存 (common_prefix) | Session缓存 (session) |
|------|-------------------------|----------------------|
| **适用场景** | 固定的系统提示词或背景信息 | 多轮对话和动态上下文 |
| **缓存内容** | 静态前缀内容 | 完整对话历史 |
| **截断策略** | 不支持 | 支持多种截断策略 |
| **性能优化** | 减少重复计算固定内容 | 优化多轮对话响应速度 |
| **使用复杂度** | 简单 | 相对复杂 |
| **成本效益** | 高（对于固定内容） | 中等（对于多轮对话） |

## 最佳实践

1. **选择合适的缓存模式**：
   - 对于固定的系统提示词，使用前缀缓存
   - 对于多轮对话场景，使用Session缓存

2. **合理设置TTL**：
   - 短期对话：1-2小时
   - 长期会话：1-7天
   - 根据业务需求平衡成本和性能

3. **优化截断策略**：
   - rolling_tokens模式适合需要保持上下文连贯性的场景
   - last_history_tokens模式适合简单的历史记录管理

4. **监控缓存使用**：
   - 定期检查缓存命中率
   - 根据usage信息优化缓存策略

## 常见问题

### Q: 如何选择合适的缓存模式？

A:

- **前缀缓存**：适用于有固定系统提示词或背景信息的场景
- **Session缓存**：适用于需要维护多轮对话上下文的场景

### Q: 缓存的生命周期如何管理？

A: 缓存会在以下情况下被清除：

- 达到设置的TTL时间
- 手动删除缓存
- 系统资源不足时的自动清理

### Q: 如何优化缓存成本？

A:

- 合理设置TTL，避免过长的缓存时间
- 选择合适的截断策略
- 监控缓存使用情况，及时调整策略
