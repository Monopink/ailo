# 上下文缓存(Responses API)

**最近更新时间：2025.09.08 16:41:37**
**首次发布时间：2025.06.17 13:42:31**

设置`"caching": {"type": "enabled"}`，可以将本轮输入输出（不包括思维链内容）信息写入缓存。在新一轮的对话中传入请求 ID ，可将上轮缓存的输入输出信息传入新一轮对话。缓存输入的信息的单价远低于未缓存的输入的信息的单价，您可以通过缓存输入，来大幅降低成本。

> - 工作原理和缓存介绍请参见[什么是上下文缓存](/docs/82379/1398933#b4d60b6c)。
> - API 结构及参数请参见[Responses API](https://www.volcengine.com/docs/82379/1569618)。

## 支持模型

参见文档[上下文缓存](/docs/82379/1330310#e6772192)。

## 前提条件

使用前请确保您已完成下列操作。

- [获取 API Key](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey)。
  - 使用 Access Key 鉴权请参考[Access Key 签名鉴权](/docs/82379/1298459#21bff83b)。
- [开通模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&OpenTokenDrawer=false)。
- 在[模型列表](/docs/82379/1330310)获取所需 Model ID 。
  - 通过 Endpoint ID 调用模型服务请参考[获取 Endpoint ID（创建自定义推理接入点）](/docs/82379/1099522)。
- 开通模型的缓存服务：在[开通管理页](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&OpenTokenDrawer=false)，模型列表的**推理（缓存）定价**列开通。

[图片: 此处原本有一张开通缓存服务的截图]

## 快速开始

### Curl 示例

```bash
# 第一次请求：创建缓存
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "input": [
    {
      "role": "system",
      "content": "你是分析小说的专家，请根据下面内容分析三国演义相关问题。\n\n<三国演义1~25章内容>\n\n回复 OK，并等待用户的提问"
    }
  ],
  "caching": {"type": "enabled"},
  "thinking": {"type": "disabled"}
}'

# 第二次请求：使用缓存
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "previous_response_id": "<第一次请求返回的ID>",
  "input": [
    {
      "role": "user",
      "content": "上文表达的主旨是什么？"
    }
  ],
  "caching": {"type": "enabled"},
  "thinking": {"type": "disabled"}
}'
```

### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    base_url='http://ark.cn-beijing.volces.com/api/v3',
    api_key=api_key,
)

# 缓存的信息，可根据实际进行替换
input_text = '''你是分析小说的专家，请根据下面内容分析三国演义相关问题。

<三国演义1~25章内容>

回复 OK，并等待用户的提问'''

# 将长文本写入缓存中
response = client.responses.create(
    # 替换为实际调用模型
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "system",
            "content": input_text,
        }
    ],
    caching={"type": "enabled"},
    thinking={"type": "disabled"},
)

print(response.output[0].content[0].text)
print(response.usage.model_dump_json())

# 在后续请求中输入缓存信息
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "上文表达的主旨是什么？"}],
    caching={"type": "enabled"},
    thinking={"type": "disabled"},
)

print(second_response.output[0].content[0].text)
print(second_response.usage.model_dump_json())
```

### OpenAI Python SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 缓存的信息
input_text = '''你是分析小说的专家，请根据下面内容分析三国演义相关问题。

<三国演义1~25章内容>

回复 OK，并等待用户的提问'''

# 第一次请求：创建缓存
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "system",
            "content": input_text
        }
    ],
    extra_body={
        "caching": {"type": "enabled"},
        "thinking": {"type": "disabled"}
    }
)

print("第一次响应:", response.output[0].content[0].text)
print("第一次用量:", response.usage)

# 第二次请求：使用缓存
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "user",
            "content": "上文表达的主旨是什么？"
        }
    ],
    extra_body={
        "previous_response_id": response.id,
        "caching": {"type": "enabled"},
        "thinking": {"type": "disabled"}
    }
)

print("第二次响应:", second_response.output[0].content[0].text)
print("第二次用量:", second_response.usage)
```

**返回预览：**

```shell
OK
{"input_tokens":108553,"input_tokens_details":{"cached_tokens":0},"output_tokens":1,"output_tokens_details":{"reasoning_tokens":0},"total_tokens":108554}

《三国演义》前25章通过描写东汉末年朝廷腐败...
{"input_tokens":108570,"input_tokens_details":{"cached_tokens":108554},"output_tokens":106,"output_tokens_details":{"reasoning_tokens":0},"total_tokens":108676}
```

> 在如上在长文本场景下，第2次请求`"cached_tokens":108554`，以`doubao-seed-1-6-250615`模型为例，相比未使用缓存，带缓存的请求费用下降 86%。在超长输入，如超长文本或超长历史对话场景下，成本下降将更加明显。

## 前缀缓存

您可以预先存储并缓存角色、背景等初始化信息，后续调用模型时无需重复发送此信息给模型，而将缓存的处理后的初始化信息作为缓存输入，减少重复计算和存储开销，降低使用成本，尤其适用于具有重复提示或标准化开头文本的应用。

Note：首轮输入时，需设置`"store": true`（默认`"true"`），`"caching": {"type": "enabled" }`，以创建前缀缓存。后续轮次即可通过 previous_response_id 引用缓存信息。

**注意**

这里使用Context API 和 Responses API 实现前缀缓存能力有所区别：

- Context API 在创建前缀缓存时，模型不会回复，缓存的信息 = 输入的内容。
- Responses API 在创建前缀缓存时，模型根据内容回复，缓存的信息=输入的内容+模型回答内容。

### Curl 示例

```bash
# 创建前缀缓存
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "input": [
    {
      "role": "system",
      "content": "你是三字经小能手。每次用户输入时，你只能用三个汉字作出回应。用户输入如果是三个字，就用三个字像对对联一样进行匹配回应；如果不是三个字，就将用户输入的意思总结成三个字。无论何时，回复都严格限制为三个字。"
    }
  ],
  "caching": {"type": "enabled"},
  "thinking": {"type": "disabled"}
}'

# 使用前缀缓存 - 第一次对话
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "previous_response_id": "<第一次请求返回的ID>",
  "input": [
    {
      "role": "user",
      "content": "人之初"
    }
  ],
  "thinking": {"type": "disabled"}
}'

# 使用前缀缓存 - 第二次对话
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "previous_response_id": "<第一次请求返回的ID>",
  "input": [
    {
      "role": "user",
      "content": "玉不琢"
    }
  ],
  "thinking": {"type": "disabled"}
}'
```

### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    base_url='http://ark.cn-beijing.volces.com/api/v3',
    api_key=api_key,
)

# 创建前缀缓存
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "system",
            "content": "你是三字经小能手。每次用户输入时，你只能用三个汉字作出回应。用户输入如果是三个字，就用三个字像对对联一样进行匹配回应；如果不是三个字，就将用户输入的意思总结成三个字。无论何时，回复都严格限制为三个字。"
        }
    ],
    caching={"type": "enabled"},
    thinking={"type": "disabled"},
)

print("前缀缓存创建成功:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")

# 使用前缀缓存进行对话 - 第一次
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "人之初"}],
    extra_body={
        "thinking": {"type": "disabled"}
    }
)

print("第一次对话:")
print(f"回复: {second_response.output[0].content[0].text}")
print(f"缓存Token数: {second_response.usage.input_tokens_details.cached_tokens}")

# 使用前缀缓存进行对话 - 第二次
third_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "玉不琢"}],
    extra_body={
        "thinking": {"type": "disabled"}
    }
)

print("第二次对话:")
print(f"回复: {third_response.output[0].content[0].text}")
print(f"缓存Token数: {third_response.usage.input_tokens_details.cached_tokens}")
```

### OpenAI Python SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 创建前缀缓存
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "system",
            "content": "你是三字经小能手。每次用户输入时，你只能用三个汉字作出回应。用户输入如果是三个字，就用三个字像对对联一样进行匹配回应；如果不是三个字，就将用户输入的意思总结成三个字。无论何时，回复都严格限制为三个字。"
        }
    ],
    extra_body={
        "caching": {"type": "enabled"},
        "thinking": {"type": "disabled"}
    }
)

print("前缀缓存创建成功:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")

# 使用前缀缓存进行对话 - 第一次
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "user",
            "content": "人之初"
        }
    ],
    extra_body={
        "previous_response_id": response.id,
        "thinking": {"type": "disabled"}
    }
)

print("第一次对话:")
print(f"回复: {second_response.output[0].content[0].text}")
print(f"缓存Token数: {second_response.usage.input_tokens_details.cached_tokens}")

# 使用前缀缓存进行对话 - 第二次
third_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "user",
            "content": "玉不琢"
        }
    ],
    extra_body={
        "previous_response_id": response.id,
        "thinking": {"type": "disabled"}
    }
)

print("第二次对话:")
print(f"回复: {third_response.output[0].content[0].text}")
print(f"缓存Token数: {third_response.usage.input_tokens_details.cached_tokens}")
```

## Session 缓存

Responses API 支持自动储存历史上下文对话并保持缓存，通过调用 previous_response_id 在多轮对话等场景中使用缓存输入并降低推理成本。

### Curl 示例

```bash
# 第一轮对话：创建Session缓存
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "input": [
    {
      "role": "system",
      "content": "你是三字经小能手。每次用户输入时，你只能用三个汉字作出回应。用户输入如果是三个字，就用三个字像对对联一样进行匹配回应；如果不是三个字，就将用户输入的意思总结成三个字。无论何时，回复都严格限制为三个字。"
    },
    {
      "role": "user",
      "content": "人之初"
    }
  ],
  "caching": {"type": "enabled"},
  "thinking": {"type": "disabled"}
}'

# 第二轮对话：使用Session缓存
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "previous_response_id": "<第一轮请求返回的ID>",
  "input": [
    {
      "role": "user",
      "content": "下一句"
    }
  ],
  "caching": {"type": "enabled"},
  "thinking": {"type": "disabled"}
}'

# 第三轮对话：继续使用Session缓存
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "previous_response_id": "<第二轮请求返回的ID>",
  "input": [
    {
      "role": "user",
      "content": "下一句"
    }
  ],
  "caching": {"type": "enabled"},
  "thinking": {"type": "disabled"}
}'
```

### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    base_url='http://ark.cn-beijing.volces.com/api/v3',
    api_key=api_key,
)

# 第一轮对话：创建Session缓存
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "system",
            "content": "你是三字经小能手。每次用户输入时，你只能用三个汉字作出回应。用户输入如果是三个字，就用三个字像对对联一样进行匹配回应；如果不是三个字，就将用户输入的意思总结成三个字。无论何时，回复都严格限制为三个字。"
        },
        {
            "role": "user",
            "content": "人之初"
        }
    ],
    caching={"type": "enabled"},
    thinking={"type": "disabled"},
)

print("第一轮对话:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")
print(f"使用情况: {response.usage}")

# 第二轮对话：使用Session缓存
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "下一句"}],
    extra_body={
        "caching": {"type": "enabled"},
        "thinking": {"type": "disabled"}
    }
)

print("第二轮对话:")
print(f"响应ID: {second_response.id}")
print(f"回复: {second_response.output[0].content[0].text}")
print(f"缓存Token数: {second_response.usage.input_tokens_details.cached_tokens}")

# 第三轮对话：继续使用Session缓存
third_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=second_response.id,
    input=[{"role": "user", "content": "下一句"}],
    extra_body={
        "caching": {"type": "enabled"},
        "thinking": {"type": "disabled"}
    }
)

print("第三轮对话:")
print(f"响应ID: {third_response.id}")
print(f"回复: {third_response.output[0].content[0].text}")
print(f"缓存Token数: {third_response.usage.input_tokens_details.cached_tokens}")
```

### OpenAI Python SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 第一轮对话：创建Session缓存
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "system",
            "content": "你是三字经小能手。每次用户输入时，你只能用三个汉字作出回应。用户输入如果是三个字，就用三个字像对对联一样进行匹配回应；如果不是三个字，就将用户输入的意思总结成三个字。无论何时，回复都严格限制为三个字。"
        },
        {
            "role": "user",
            "content": "人之初"
        }
    ],
    extra_body={
        "caching": {"type": "enabled"},
        "thinking": {"type": "disabled"}
    }
)

print("第一轮对话:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")
print(f"使用情况: {response.usage}")

# 第二轮对话：使用Session缓存
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "user",
            "content": "下一句"
        }
    ],
    extra_body={
        "previous_response_id": response.id,
        "caching": {"type": "enabled"},
        "thinking": {"type": "disabled"}
    }
)

print("第二轮对话:")
print(f"响应ID: {second_response.id}")
print(f"回复: {second_response.output[0].content[0].text}")
print(f"缓存Token数: {second_response.usage.input_tokens_details.cached_tokens}")

# 第三轮对话：继续使用Session缓存
third_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "user",
            "content": "下一句"
        }
    ],
    extra_body={
        "previous_response_id": second_response.id,
        "caching": {"type": "enabled"},
        "thinking": {"type": "disabled"}
    }
)

print("第三轮对话:")
print(f"响应ID: {third_response.id}")
print(f"回复: {third_response.output[0].content[0].text}")
print(f"缓存Token数: {third_response.usage.input_tokens_details.cached_tokens}")
```

## 控制存储/缓存生命周期

支持通过字段**expire_at**字段指定上下文存储（**store**）及上下文缓存（**caching**）过期时刻。当前最大可存储时间为72小时，即当前UTC Unix 时间戳 + 259200。

**注意**

与 Context API 指定**ttl**（Time To Live，即对应信息保存在方舟平台的时长）不同，Responses API 存储和缓存指定的为过期时刻，具体不同如下。

- Context API ：通过**ttl**指定缓存可存储的时长，当`当前时刻 - 缓存最近使用时刻`大于**ttl**值，则存储过期。会随着缓存被调用，而重置缓存保存时长。
- Responses API：通过**expire_at**指定上下文存储及缓存的过期时刻，当`当前时刻`超过`过期时刻`，则存储过期。不随着缓存/存储的使用而重置缓存生命周期。

使用 Responses API 存储/存储过期，需通过[接口](https://www.volcengine.com/docs/82379/1569618)重新创建存储/缓存内容。

### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "input": [
    {
      "role": "system",
      "content": "你好"
    }
  ],
  "caching": {"type": "enabled"},
  "thinking": {"type": "disabled"},
  "expire_at": 1735689600
}'
```

### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark
import time

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    base_url='http://ark.cn-beijing.volces.com/api/v3',
    api_key=api_key,
)

# 设置过期时间为1小时后
expire_time = int(time.time()) + 3600

response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "system",
            "content": "你好"
        }
    ],
    caching={"type": "enabled"},
    thinking={"type": "disabled"},
    expire_at=expire_time,
)

print("缓存创建成功:")
print(f"响应ID: {response.id}")
print(f"过期时间: {expire_time}")
print(response.model_dump_json())
```

### OpenAI Python SDK 示例

```python
import os
from openai import OpenAI
import time

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 设置过期时间为1小时后
expire_time = int(time.time()) + 3600

response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "system",
            "content": "你好"
        }
    ],
    extra_body={
        "caching": {"type": "enabled"},
        "thinking": {"type": "disabled"},
        "expire_at": expire_time
    }
)

print("缓存创建成功:")
print(f"响应ID: {response.id}")
print(f"过期时间: {expire_time}")
print(f"使用情况: {response.usage}")
```

## 删除缓存

Responses API 支持根据 ID 来删除缓存，与删除历史对话一致，如下所示，便于您根据业务自主控制缓存信息量，如删除不必要的缓存信息，减少冗余输入，降低成本。

### Curl 示例

```bash
curl --location --request DELETE 'https://ark.cn-beijing.volces.com/api/v3/responses/resp_123' \
--header 'Authorization: Bearer $ARK_API_KEY'
```

### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

api_key = os.getenv('ARK_API_KEY')

client = Ark(
    base_url='http://ark.cn-beijing.volces.com/api/v3',
    api_key=api_key,
)

# 删除指定ID的缓存
response = client.responses.delete("resp_123")
print("删除结果:", response)
```

### OpenAI Python SDK 示例

```python
import os
import requests

def delete_cache(response_id):
    url = f"https://ark.cn-beijing.volces.com/api/v3/responses/{response_id}"
    headers = {
        "Authorization": f"Bearer {os.getenv('ARK_API_KEY')}"
    }

    response = requests.delete(url, headers=headers)
    return response.json()

# 删除指定ID的缓存
result = delete_cache("resp_123")
print("删除结果:", result)
```

需注意，删除某轮缓存后，其后续轮次缓存的信息在下次请求时将重新计算和存储。如下图所示（图中场景为第5轮请求后调用接口删除第3轮对话信息）。

[图片: 此处原本有一张删除缓存影响示意图]

第6轮请求时，4、5 轮信息将重新计算并缓存，此时其信息将作为输入，而非缓存输入进行计费。

## 使用说明

- **前一轮对话的请求开启了缓存写入，当前轮次对话才能写入缓存。**以此类推，当某轮次请求需写入缓存，则需保证所有前置轮次请求写入缓存状态开启，即前置所有轮次均有`"caching": {"type": "enabled" }`。举例：当希望第 5 轮请求能写入缓存信息，则需要 1~4 轮均保持缓存写入开启。当其中一轮请求关闭缓存写入，则后续轮次对话请求均无法写入缓存。

- 缓存的有效期可以通过`expire_at`字段自定义，最长支持 3 天。

- 深度思考能力的模型返回的思维链内容不会被缓存。

- **store**：若想写入缓存，需开启存储功能，即**store**字段为`"true"`或保持默认（默认为`"true"`）。

- **instructions**：若想写入缓存，**instructions**字段应为空。若在本轮请求里设置了**instructions**，该轮对话不能调用已有缓存，也无法将本轮信息写入缓存。

- **thinking**：请求中**thinking**字段的赋值应该与前一轮保持一致才可使用缓存/写入缓存。

  **说明**

  以`doubao-seed-1-6-250615`模型为例，当第1轮设定`"thinking":{"type":"auto"}`，则后续如需使用或者启用缓存，均需一样赋值。 当第1轮未设置**thinking**字段，即不赋值，后续请求如需写入缓存或者调用已有缓存，也需不设置**thinking**字段。

- **tools**：仅在首轮请求时可以设置**tools**字段，后续所有对话将默认携带 tools 字段信息的缓存输入。
  - 不支持在后续轮次对话请求中设置**tools**字段，会冲突并报错处理。
  - 若首轮对话信息被删除，则后续所有轮次对话都不携带**tools**字段信息的缓存输入，也无法配置**tools**字段。

## 计费说明

计费单价请参见：[模型服务价格](/docs/82379/1544106)。

### 计费项

- **输入**（元/千 token）：正在进行的对话中的新文本，即在删除场景后，需重新计算和缓存的历史对话信息。

- **缓存输入**（元/千 token）：输入为预先处理和缓存的内容，优化了计算和存储的开销，计费费率会显著低于新输入内容。

- **存储**（元/千 token/小时）：历史对话存储在缓存中，会产生存储费用。计算方式根据每个自然小时使用缓存的量乘以单价进行累加。

  **注意**
  - 存储费用在缓存创建即产生，直到该缓存被手动删除或过期，停止计费。
  - 存储费用在每个自然小时如 8:00 整点出账，不足 1 小时按照 1 小时计算。

- **输出**（元/千 token）：模型根据输入信息生成的内容。计费方式与未使用 Session 缓存的调用方式一致。

### 计费逻辑

Responses API 的缓存计费采用透明的计费方式，基于以下四个关键因素：

1. **输入费用**：仅对新输入的内容收费，不包括从缓存中检索的内容
2. **缓存输入费用**：对从缓存中检索的内容收费，费率显著低于新输入内容
3. **存储费用**：按小时计费，基于每个自然小时内所有缓存存储的最大标记数
4. **输出费用**：对模型生成的内容收费，与标准调用方式一致

通过合理使用缓存功能，可以显著降低大规模对话和长文本处理的成本。在超长输入场景下，成本下降可达86%或更高。
