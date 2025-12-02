# 上下文缓存(Context API)

**最近更新时间：2025.09.01 19:44:04**
**首次发布时间：2024.12.18 10:36:46**

本文介绍如何使用Context API 实现 Session 缓存以及前缀缓存能力。

> - 使用 Responses API 调用缓存，参见[缓存机制](/docs/82379/1585128#30f5992e)。
> - 了解 Session 缓存与前缀缓存，参见[缓存类型](/docs/82379/1398933#a8910b9a)。

## 前提条件

使用前请确保您已完成下列操作。

- [获取 API Key](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey)。
  - 使用 Access Key 鉴权请参考[Access Key 签名鉴权](/docs/82379/1298459#21bff83b)。
- [开通模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&OpenTokenDrawer=false)。
- 在[模型列表](/docs/82379/1330310)获取所需 Model ID 。
  - 通过 Endpoint ID 调用模型服务请参考[获取 Endpoint ID（创建自定义推理接入点）](/docs/82379/1099522)。
- 开通模型的缓存服务：在[开通管理页](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&OpenTokenDrawer=false)，模型列表的**推理（缓存）定价**列开通。

[图片: 此处原本有一张开通缓存服务的截图]

## 支持的模型

请参见文档[上下文缓存](/docs/82379/1330310#e6772192)。

## Session 缓存教程

> 快速跳转至[前缀缓存教程](#前缀缓存教程)

Session 缓存（Session Cache，会话级别的缓存），是针对模型服务的优化。它将 Session 中的上下文（Context）进行缓存（Caching），非常适合超长轮数对话场景，可以减少计算和存储重复内容的开销。您开通 Session 缓存后，在多轮对话场景下对于缓存中的内容使用会给予您一定的折扣，降低您使用模型推理服务的成本。

> 因为使用缓存来存储您的上下文信息，您开通并使用了该功能后，会产生相应的存储费用。

### 快速开始

#### 1.创建 Session 缓存

使用 Session 缓存前，您需要调用[创建上下文缓存 API](https://www.volcengine.com/docs/82379/1528789)创建缓存，并写入初始信息。后续只要在[上下文缓存对话 API](https://www.volcengine.com/docs/82379/1529329)中引入此缓存，即可让方舟为您管理历史对话以及享受使用缓存带来的费用降低。

##### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/context/create' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model":"<YOUR_ENDPOINT_ID>",
  "messages":[
    {"role":"system","content":"你是李雷，你只会说\"我是李雷\""}
  ],
  "ttl":3600,
  "mode": "session"
}'
```

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY
api_key = os.getenv('ARK_API_KEY')
client = Ark(api_key=api_key)

# 创建Session缓存
response = client.context.create(
    model="<YOUR_ENDPOINT_ID>",
    messages=[
        {"role": "system", "content": "你是李雷，你只会说\"我是李雷\""}
    ],
    ttl=3600,
    mode="session"
)

print("缓存创建成功:")
print(f"缓存ID: {response.id}")
print(f"模型: {response.model}")
print(f"TTL: {response.ttl}")
print(f"模式: {response.mode}")
print(f"使用情况: {response.usage}")
```

##### OpenAI Python SDK 示例

```python
import os
import requests

# 使用requests直接调用API（OpenAI SDK不直接支持Context API）
def create_session_cache():
    url = "https://ark.cn-beijing.volces.com/api/v3/context/create"
    headers = {
        "Authorization": f"Bearer {os.getenv('ARK_API_KEY')}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "<YOUR_ENDPOINT_ID>",
        "messages": [
            {"role": "system", "content": "你是李雷，你只会说\"我是李雷\""}
        ],
        "ttl": 3600,
        "mode": "session"
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()

# 创建Session缓存
cache_response = create_session_cache()
print("缓存创建成功:")
print(f"缓存ID: {cache_response['id']}")
print(f"模型: {cache_response['model']}")
print(f"TTL: {cache_response['ttl']}")
print(f"模式: {cache_response['mode']}")
```

**参数说明：**

- `$ARK_API_KEY` 替换为您的 API Key，或者配置 API Key 至环境变量。
- `<YOUR_ENDPOINT_ID>` 替换为您的推理接入点 ID。
- `"ttl":3600` 代表 Session 缓存 TTL，当前为 3600 秒。
- `"mode": "session"` 代表使用的 Session 缓存模式。

**模型回复预览：**

```json
{
  "id": "<YOUR_CONTEXT_ID>",
  "model": "<YOUR_ENDPOINT_ID>",
  "ttl": "3600",
  "mode": "session",
  "truncation_strategy": {
    "type": "last_history_token",
    "last_history_token": 4096
  },
  "usage": {
    "prompt_tokens": 18,
    "completion_tokens": 0,
    "total_tokens": 18,
    "prompt_tokens_details": {
      "cached_tokens": 0
    }
  }
}
```

返回的创建的 Session 缓存的基本信息，其中`<YOUR_CONTEXT_ID>`是创建的 Session 缓存的 ID，格式类似`ctx-****`，需要记录并在后面请求模型推理服务时使用。

#### 2.使用 Session 缓存进行对话

我们使用接口[上下文缓存对话 API](https://www.volcengine.com/docs/82379/1529329)，来进行使用 Session 缓存的对话。

##### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/context/chat/completions' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "context_id": "<YOUR_CONTEXT_ID>",
  "model": "<YOUR_ENDPOINT_ID>",
  "messages":[
    {
      "role":"user",
      "content": "你好"
    }
  ]
}'
```

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY
api_key = os.getenv('ARK_API_KEY')
client = Ark(api_key=api_key)

# 使用Session缓存进行对话
response = client.context.chat.completions.create(
    context_id="<YOUR_CONTEXT_ID>",
    model="<YOUR_ENDPOINT_ID>",
    messages=[
        {
            "role": "user",
            "content": "你好"
        }
    ]
)

print("对话响应:")
print(f"内容: {response.choices[0].message.content}")
print(f"使用情况: {response.usage}")
print(f"缓存Token数: {response.usage.prompt_tokens_details.cached_tokens}")
```

##### OpenAI Python SDK 示例

```python
import os
import requests

def chat_with_session_cache(context_id, message):
    url = "https://ark.cn-beijing.volces.com/api/v3/context/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('ARK_API_KEY')}",
        "Content-Type": "application/json"
    }
    data = {
        "context_id": context_id,
        "model": "<YOUR_ENDPOINT_ID>",
        "messages": [
            {
                "role": "user",
                "content": message
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()

# 使用Session缓存进行对话
chat_response = chat_with_session_cache("<YOUR_CONTEXT_ID>", "你好")
print("对话响应:")
print(f"内容: {chat_response['choices'][0]['message']['content']}")
print(f"使用情况: {chat_response['usage']}")
print(f"缓存Token数: {chat_response['usage']['prompt_tokens_details']['cached_tokens']}")
```

**参数说明：**

- `$ARK_API_KEY` 替换为您的 API Key，或者配置 API Key 至环境变量。
- `<YOUR_CONTEXT_ID>` 替换为之前创建的 Session 缓存 ID。
- `<YOUR_ENDPOINT_ID>` 替换为您的推理接入点 ID。

**模型回复预览：**

```json
{
  "id": "****",
  "object": "chat.completion",
  "created": 167765****,
  "model": "<YOUR_ENDPOINT_ID>",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "我是李雷"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 28,
    "completion_tokens": 4,
    "total_tokens": 32,
    "prompt_tokens_details": {
      "cached_tokens": 18
    }
  }
}
```

### 典型使用

#### 控制 Session 缓存上限

> 仅 last_history_token 模式支持。

您可以自行控制缓存上限。根据需要选择适合的缓存上限，可以缓存输入的 token 比例高，在合理存储成本前提下，降低输入成本。

##### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/context/create' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model":"<YOUR_ENDPOINT_ID>",
  "messages":[
    {"role":"system","content":"你是李雷，你只会说\"我是李雷\""}
  ],
  "ttl":3600,
  "mode": "session",
  "truncation_strategy":{
    "type": "last_history_tokens",
    "last_history_tokens": 4096
  }
}'
```

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY
api_key = os.getenv('ARK_API_KEY')
client = Ark(api_key=api_key)

# 创建带缓存上限控制的Session缓存
response = client.context.create(
    model="<YOUR_ENDPOINT_ID>",
    messages=[
        {"role": "system", "content": "你是李雷，你只会说\"我是李雷\""}
    ],
    ttl=3600,
    mode="session",
    truncation_strategy={
        "type": "last_history_tokens",
        "last_history_tokens": 4096
    }
)

print("带缓存上限控制的Session缓存创建成功:")
print(f"缓存ID: {response.id}")
print(f"截断策略: {response.truncation_strategy}")
```

**参数说明：**

- `$ARK_API_KEY` 替换为您的 API Key，或者配置 API Key 至环境变量。
- `<YOUR_ENDPOINT_ID>` 替换为您的推理接入点 ID。
- `"ttl":3600` 代表 Session 缓存 TTL，当前为 3600 秒。
- `"mode": "session"` 代表使用的 Session 缓存模式。
- `"type":"last_history_tokens"` 代表使用了last_history_tokens模式。
- `"last_history_tokens": 4096` 代表缓存最大长度为 4096 token，您根据自己的业务情况调整值大小。

#### 手动管理 Session 缓存

使用了支持rolling_tokens模式的模型，可以通过下面方法创建 Session 缓存，并可以根据需要来启用自动管理和手动管理 Session 缓存。

##### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/context/create' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model":"<YOUR_ENDPOINT_ID>",
  "messages":[
    {"role":"system","content":"你是李雷，你只会说\"我是李雷\""}
  ],
  "ttl":3600,
  "mode": "session",
  "truncation_strategy":{
    "type":"rolling_tokens",
    "rolling_tokens": false
  }
}'
```

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY
api_key = os.getenv('ARK_API_KEY')
client = Ark(api_key=api_key)

# 创建手动管理的Session缓存
response = client.context.create(
    model="<YOUR_ENDPOINT_ID>",
    messages=[
        {"role": "system", "content": "你是李雷，你只会说\"我是李雷\""}
    ],
    ttl=3600,
    mode="session",
    truncation_strategy={
        "type": "rolling_tokens",
        "rolling_tokens": False  # 手动管理
    }
)

print("手动管理的Session缓存创建成功:")
print(f"缓存ID: {response.id}")
print(f"截断策略: {response.truncation_strategy}")
```

设置`truncation_strategy.type`为`rolling_tokens`，即可创建 Session 缓存。

- 当您希望自行控制触发 Session 缓存上限时的处理，可以将`truncation_strategy.rolling_tokens`设置为`"false"`，在历史消息长度超过上下文长度时模型会停止输出，并在返回信息中返回`finish_reason`为`length`，您获取此信息后可以根据您按需进行后续处理。

> 当您希望自动控制触发 Session 缓存上限时的处理，可以将`truncation_strategy.rolling_tokens`设置为`"true"`，这是会按照默认的方式进行处理，处理方式请参见rolling_tokens 模式。

### 使用说明

- Session 缓存 API 为有状态 API，不支持并发调用同一 Session 缓存，即不能在同一时刻发起多个带相同 Session 缓存 ID（`context_id`）的请求。
- 不支持 Partial 模式（又称[Prefill Response](/docs/82379/1359497)），调用[创建上下文缓存 API](https://www.volcengine.com/docs/82379/1528789)时，提交的`messages`数组的最后一条消息`role`可以是`user`或`system`，而不能为`assistant`。

```json
// 正例
"messages":[
  {"role":"user","content":"你是谁"},
  {"role":"assistant","content":"我是李雷"},
  {"role":"user","content":"今天天气如何"}
]
```

```json
// 反例
"messages":[
  {"role":"user","content":"你是谁"},
  {"role":"assistant","content":"我是李雷"}
]
```

- Session 缓存当前只支持在线推理，不支持与批量推理一起使用。

### 缓存上限说明

随着对话轮数增加，内容会达到 Session 缓存的上限。按照处理方式的不同，可以分为 2 种模式。

#### last_history_tokens 模式

触发上限则滚动信息窗口，遵循先进先出的策略。触发缓存上限时，先删除最早的缓存对话记录（初始消息不会删除，即在创建 session 缓存时写入缓存的信息不会删除），再存入新的对话信息。这个模式下，滚动数据不会产生额外的计算成本。

#### rolling_tokens 模式

触发上限则定量删除信息并重新计算，使用固定长度 A 来限制 Session 缓存上限，固定长度 B 来控制删除上下文的长度。当 Session 缓存达到上限时，即达到 A 长度时，会进行下面两个动作：

- 清除 Session 缓存 B 长度的陈旧消息（初始消息不会删除，即在创建 session 缓存时写入的信息不会删除），为后续新的消息腾挪存储空间。
- 重新计算缓存中历史信息，以确保模型回复与历史交互的连贯性。

> 具体计算逻辑供您了解：以Doubao-pro-32k模型为例，Session 缓存的 token 量达到`32k（最大上下文长度）-4k（最大输出长度）`时，会删除 4k 陈旧的历史信息（除了初始消息），然后重新计算和存储保留的缓存内容。

触发 Session 缓存上限引起重新计算的轮次，会将保留的历史信息和新消息一样进行计算和存储。表现为此轮 Session 缓存的 token 比例降低为 0，该轮无缓存输入 token，后续又会趋于正常。

### 过期时间

Session 缓存未被使用时会开始计时，达到 TTL（Time To Live），会被删除；如果中途被使用，那么此缓存 TTL 会被重置，并继续保留。

> 举例：您在 8:00 创建了 Session 缓存 A、B，并设置 TTL 为 2 小时。10:00 时，缓存 A 没被使用，缓存 B 在 9:00 被使用。那么，缓存 A 会被删除，B TTL 还有 1 小时。

**注意**

没有触发清除的 Session 缓存，均会占用缓存，从而产生存储费用。您可以根据自己业务合理设置 TTL，保证请求的内容能享受 Session 缓存带来的低成本；又避免 Session 缓存删除前的长期空闲时间。

### 计费说明

计费单价请参见：[模型服务价格](/docs/82379/1544106)。

与未使用 Session 缓存相比，模型服务费用会产生在：

- **输入**（元/千 token）：新的请求中您无需重新发送历史对话，输入 token 仅代表添加到正在进行的对话中的新文本。
  > 在 rolling_tokens 模式下触发重新计算时，会将保存的历史对话重新计算和缓存，与新输入内容一样计费。
- **缓存输入**（元/千 token）：缓存中使用的内容。方舟自动处理历史记录，并输入给模型，这部分内容即缓存输入内容，他们也会产生费用，但是减少了计算和存储开销，计费费率会显著低于新输入内容。
- **存储**（元/千 token/小时）：历史对话存储在 Session 缓存中，会产生存储费用。计算方式根据每个自然小时使用缓存的最大量乘以单价进行累加。举例说明（单价仅为举例使用）：单价为 0.000017 元/千 token/小时，第 1 小时 Session 缓存最大的缓存用量 10k token，第 2 小时 Session 缓存最大的缓存用量 15k token，那么存储费用为：`0.000017*10+0.000017*15 = 0.000425 元`

  **注意**
  - 在 Session 缓存创建即产生，直到该 Session 缓存被删除（一直未被使用，达 TTL 被删除），停止计费。
  - 存储费用在每个自然小时如 8:00，9:00 等整点出账，不足 1 小时按照 1 小时计算。
- **输出**（元/千 token）：模型根据输入信息生成的内容。计费方式与未使用 Session 缓存的调用方式一致。

### 工作原理

请参见[Session 缓存](/docs/82379/1398933#78048664)。

## 前缀缓存教程

> 快速跳转至[上下文缓存(Context API)](#上下文缓存context-api)

使用前缀缓存可以降低模型调用的成本。您可以预先存储常用信息如角色、背景等信息作为初始化信息，后续调用模型时无需重复发送此信息给模型，降低开销和成本，尤其适用于具有重复提示或标准化开头文本的应用。

### 快速开始

#### 1.创建前缀缓存

使用前缀缓存前，您需要调用[创建上下文缓存 API](https://www.volcengine.com/docs/82379/1528789)创建缓存，并写入初始信息。后续只要在[上下文缓存对话 API](https://www.volcengine.com/docs/82379/1529329)中引入此缓存，即可让方舟为您保留初始信息以及享受使用缓存带来的费用折扣。

##### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/context/create' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model":"<YOUR_ENDPOINT_ID>",
  "messages":[
    {"role":"system","content":"你是李雷，你只会说\"我是李雷\""}
  ],
  "ttl":3600,
  "mode": "common_prefix"
}'
```

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY
api_key = os.getenv('ARK_API_KEY')
client = Ark(api_key=api_key)

# 创建前缀缓存
response = client.context.create(
    model="<YOUR_ENDPOINT_ID>",
    messages=[
        {"role": "system", "content": "你是李雷，你只会说\"我是李雷\""}
    ],
    ttl=3600,
    mode="common_prefix"
)

print("前缀缓存创建成功:")
print(f"缓存ID: {response.id}")
print(f"模型: {response.model}")
print(f"TTL: {response.ttl}")
print(f"模式: {response.mode}")
print(f"使用情况: {response.usage}")
```

##### OpenAI Python SDK 示例

```python
import os
import requests

# 使用requests直接调用API（OpenAI SDK不直接支持Context API）
def create_prefix_cache():
    url = "https://ark.cn-beijing.volces.com/api/v3/context/create"
    headers = {
        "Authorization": f"Bearer {os.getenv('ARK_API_KEY')}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "<YOUR_ENDPOINT_ID>",
        "messages": [
            {"role": "system", "content": "你是李雷，你只会说\"我是李雷\""}
        ],
        "ttl": 3600,
        "mode": "common_prefix"
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()

# 创建前缀缓存
cache_response = create_prefix_cache()
print("前缀缓存创建成功:")
print(f"缓存ID: {cache_response['id']}")
print(f"模型: {cache_response['model']}")
print(f"TTL: {cache_response['ttl']}")
print(f"模式: {cache_response['mode']}")
```

**参数说明：**

- `$ARK_API_KEY` 替换为您的 API Key，或者配置 API Key 至环境变量。
- `<YOUR_ENDPOINT_ID>` 替换为您的推理接入点 ID。
- `"ttl":3600` 代表前缀缓存 TTL，当前为 3600 秒。
- `"mode": "common_prefix"` 代表使用的前缀缓存模式。

**模型回复预览：**

```json
{
  "id": "<YOUR_CONTEXT_ID>",
  "model": "<YOUR_ENDPOINT_ID>",
  "ttl": "259200",
  "mode": "common_prefix",
  "usage": {
    "prompt_tokens": 18,
    "completion_tokens": 0,
    "total_tokens": 18,
    "prompt_tokens_details": {
      "cached_tokens": 0
    }
  }
}
```

返回的创建的前缀缓存的基本信息，其中`<YOUR_CONTEXT_ID>`是创建的前缀缓存的 ID，格式类似`ctx-****`，需要记录并在后面请求模型推理服务时使用。

#### 2.使用前缀缓存进行对话

我们使用接口，来进行使用前缀缓存的对话。

##### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/context/chat/completions' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "context_id": "<YOUR_CONTEXT_ID>",
  "model": "<YOUR_ENDPOINT_ID>",
  "messages":[
    {
      "role":"user",
      "content": "你好"
    }
  ]
}'
```

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY
api_key = os.getenv('ARK_API_KEY')
client = Ark(api_key=api_key)

# 使用前缀缓存进行对话
response = client.context.chat.completions.create(
    context_id="<YOUR_CONTEXT_ID>",
    model="<YOUR_ENDPOINT_ID>",
    messages=[
        {
            "role": "user",
            "content": "你好"
        }
    ]
)

print("对话响应:")
print(f"内容: {response.choices[0].message.content}")
print(f"使用情况: {response.usage}")
print(f"缓存Token数: {response.usage.prompt_tokens_details.cached_tokens}")
```

##### OpenAI Python SDK 示例

```python
import os
import requests

def chat_with_prefix_cache(context_id, message):
    url = "https://ark.cn-beijing.volces.com/api/v3/context/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('ARK_API_KEY')}",
        "Content-Type": "application/json"
    }
    data = {
        "context_id": context_id,
        "model": "<YOUR_ENDPOINT_ID>",
        "messages": [
            {
                "role": "user",
                "content": message
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()

# 使用前缀缓存进行对话
chat_response = chat_with_prefix_cache("<YOUR_CONTEXT_ID>", "你好")
print("对话响应:")
print(f"内容: {chat_response['choices'][0]['message']['content']}")
print(f"使用情况: {chat_response['usage']}")
print(f"缓存Token数: {chat_response['usage']['prompt_tokens_details']['cached_tokens']}")
```

**参数说明：**

- `$ARK_API_KEY` 替换为您的 API Key，或者配置 API Key 至环境变量。
- `<YOUR_CONTEXT_ID>` 替换为之前创建的缓存 ID。
- `<YOUR_ENDPOINT_ID>` 替换为您的推理接入点 ID。

**模型回复预览：**

```json
{
  "id": "****",
  "object": "chat.completion",
  "created": 167765****,
  "model": "<YOUR_ENDPOINT_ID>",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "我是李雷。"
    },
    "logprobs": null,
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 28,
    "completion_tokens": 5,
    "total_tokens": 33,
    "prompt_tokens_details": {
      "cached_tokens": 18
    }
  }
}
```

### 支持的模型

请参见文档[上下文缓存](/docs/82379/1330310#e6772192)。

### 使用限制

- 与 Session 缓存不同，前缀缓存支持并发调用。
- 不支持 Partial 模式（又称[Prefill Response](/docs/82379/1359497)），调用[上下文缓存对话 API](https://www.volcengine.com/docs/82379/1529329)时，`messages`数组的最后一条消息的`role`字段取值可以是`user`或`system`，而不能为`assistant`。

```json
// 正例
"messages":[
  {"role":"user","content":"你是谁"},
  {"role":"assistant","content":"我是李雷"},
  {"role":"user","content":"今天天气如何"}
]
```

```json
// 反例
"messages":[
  {"role":"user","content":"你是谁"},
  {"role":"assistant","content":"我是李雷"}
]
```

- 当前前缀缓存过期时长可配置范围在1小时到7天，即`ttl`字段设置范围（单位：秒）为 [3600, 604800]。具体字段配置说明，请参见[请求体](/docs/82379/1346559#%E8%AF%B7%E6%B1%82%E4%BD%93)。
- 前缀缓存当前只支持在线推理，不支持与批量推理一起使用。

如果您需要使用Java来调用模型推理服务，您可以使用方舟的 Java SDK 来很方便使用前缀缓存。

### 计费说明

计费单价请参见：[上下文缓存计费](/docs/82379/1099320#191d02ec)。

与 Session 缓存类似，前缀缓存采用透明的计费方式，基于以下四个关键因素：

- 输入（元/千 token）：输入 tokens 代表发送给大语言模型的新文本，不包括缓存的前缀。
- 输出（元/千 token）：输出标记代表大语言模型生成的文本。输出标记的计费与标准大语言模型使用方式一致。
- 缓存输入（元/千 token）：每次从前缀缓存中检索标记都会产生缓存输入费用。此费用通常低于输入标记费用。
- 存储（元/千 token/小时）：存储费用按小时计费，基于每个自然小时内所有前缀存储的最大标记数。存储费用将持续到前缀的生存时间 (TTL) 到期。

### 工作原理

请参见文档[前缀缓存](/docs/82379/1398933#51929890)。
