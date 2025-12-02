# Responses API 教程

**最近更新时间：2025.09.09 17:39:35**
**首次发布时间：2025.06.06 10:09:16**

Responses API 是火山方舟最新推出的 API 接口，原生支持高效的上下文管理，不仅延续了 Chat API 的易用性，还结合了更强的智能代理能力。随着大模型技术不断升级，Responses API 为开发各类面向实际行动的应用提供了更灵活的基础，并且支持函数调用等多种扩展能力，非常适合搭建智能助手、自动化工具等场景。

**说明**

此为邀测能力，如需使用，提交[测试申请工单](https://console.volcengine.com/workorder/create?step=2&SubProductID=P90002304)。

## 前提条件

- [获取 API Key](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey)。
  - 使用 Access Key 鉴权请参考[Access Key 签名鉴权](/docs/82379/1298459#21bff83b)。
- [开通模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&OpenTokenDrawer=false)。
- 在[模型列表](/docs/82379/1330310)获取所需 Model ID 。
  - 通过 Endpoint ID 调用模型服务请参考[获取 Endpoint ID（创建自定义推理接入点）](/docs/82379/1099522)。
- 如使用缓存能力，需开通模型的缓存服务：在[开通管理页](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&OpenTokenDrawer=false)，模型列表的**推理（缓存）定价**列开通。

[图片: 此处原本有一张开通缓存服务的截图]

## 快速开始

### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "input": "你好呀。"
}'
```

### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    api_key=api_key,
)

response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input="你好呀。"
)

print(response)
```

### 兼容OpenAI SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input="你好呀。"
)

print(response)
```

## 支持模型

- doubao-seed-1-6-vision-250815
- doubao-seed-1-6-250615
- doubao-seed-1-6-thinking-250615
- doubao-seed-1-6-thinking-250715
- doubao-seed-1-6-flash-250828
- doubao-seed-1-6-flash-250615
- doubao-seed-1-6-flash-250715

## 使用限制

Responses API QPS 限流如下。如果需要提升限流值，请提交[申请工单](https://console.volcengine.com/workorder/create?step=2&SubProductID=P00001166)。

| 接口名称 | 账号维度的 QPS 限流 |
|---------|-------------------|
| 创建模型响应 | 无 |
| 查询模型响应 | 20 |
| 列出输入项 | 20 |
| 删除模型响应 | 20 |

## 使用示例

### 上下文管理

上下文状态管理更加简单，默认情况下每个请求的输入和回复（不包括思维链内容）都会持久化存储，后续请求只需传入 id 就可以引入对应请求的输入和回复，无需像 Chat API 每次请求，传入历史对话。

**说明**

设置`"store": true`可开启存储功能（默认开启）；设置`"store": false`可关闭存储功能。

- 存储条件：本次请求回复完毕且成功，即返回**status**字段为`completed`，才会将本轮记录存储。如当回复触发了长度限制导致截断，则不会存储对话信息。
- 输入总数：输入item最多可达 1000 个（item，任意角色的一条信息，如一问一答为2个item）。达到此限制，无法继续对话，可通过[删除模型请求接口](https://www.volcengine.com/docs/82379/1584286)手动清理记录。详细原理见[附 上下文管理及缓存工作原理](/docs/82379/1585128#3fb6abde)。
- 存储时长：每个请求记录存储有效期可通过`expire_at`字段自定义，最长支持 3 天，从创建时开始计时。
- 存储内容：系统会自动存储`input`和`output`字段的信息。`output`代表对应轮次模型的返回结果，但不会存储深度思考的思维链内容。
- 其他说明：store 功能当前不收取费用；所有数据都采用加密方式，确保信息安全和隐私合规。

#### 多轮调用

这段代码展示了如何利用 Responses API 实现多轮对话功能。在多轮调用模式下，系统能够自动管理上下文，持续追踪和记忆之前的对话内容，使对话更加连贯自然，大大提升了智能交互体验。

##### Curl 示例

```bash
# 第一轮对话
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "input": "Hi，讲个笑话。"
}'

# 第二轮对话
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "previous_response_id":"<id>",
  "input": "这个笑话的笑点在哪？"
}'
```

第二次请求需将 curl 命令中的`<id>`替换为上一次请求返回的 response_id。

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    api_key=api_key,
)

# 第一轮对话
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input="Hi，讲个笑话。"
)

print("第一轮对话:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")

# 第二轮对话
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=response.id,
    input="这个笑话的笑点在哪？"
)

print("第二轮对话:")
print(f"响应ID: {second_response.id}")
print(f"回复: {second_response.output[0].content[0].text}")
```

##### 兼容 OpenAI SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 第一轮对话
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input="Hi，讲个笑话。"
)

print("第一轮对话:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")

# 第二轮对话
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    extra_body={
        "previous_response_id": response.id
    },
    input="这个笑话的笑点在哪？"
)

print("第二轮对话:")
print(f"响应ID: {second_response.id}")
print(f"回复: {second_response.output[0].content[0].text}")
```

#### 重新生成对话

这段代码展示了 Responses API 中通过灵活调用 previous_response_id 重新生成对话的树状分叉结构，并展示了如何在不同的分支中进行不同的操作。在重新生成对话的场景中，系统能够根据不同的分支条件，灵活地执行多种的操作，从而实现更复杂的对话逻辑。

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    api_key=api_key,
)

# 创建第一轮对话请求
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[{"role": "user", "content": "你知道余弦相似度的原理吗？"}],
    store=True,  # 设置为True以存储对话
)

print("第一轮对话:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")

# 创建第二轮对话请求
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "我希望你可以用小学生都能听懂的方式来解释这个问题"}],
    store=True,
)

print("第二轮对话（小学生版本）:")
print(f"响应ID: {second_response.id}")
print(f"回复: {second_response.output[0].content[0].text}")

# 重新创建第二轮对话请求（基于第一轮，不同的分支）
re_second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "我希望你可以用教授的思考逻辑来解释这个问题"}],
    store=True,
)

print("第二轮对话（教授版本）:")
print(f"响应ID: {re_second_response.id}")
print(f"回复: {re_second_response.output[0].content[0].text}")
```

##### 兼容 OpenAI SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 创建第一轮对话请求
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[{"role": "user", "content": "你知道余弦相似度的原理吗？"}],
    extra_body={
        "store": True
    }
)

print("第一轮对话:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")

# 创建第二轮对话请求
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[{"role": "user", "content": "我希望你可以用小学生都能听懂的方式来解释这个问题"}],
    extra_body={
        "previous_response_id": response.id,
        "store": True
    }
)

print("第二轮对话（小学生版本）:")
print(f"响应ID: {second_response.id}")
print(f"回复: {second_response.output[0].content[0].text}")

# 重新创建第二轮对话请求（基于第一轮，不同的分支）
re_second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[{"role": "user", "content": "我希望你可以用教授的思考逻辑来解释这个问题"}],
    extra_body={
        "previous_response_id": response.id,
        "store": True
    }
)

print("第二轮对话（教授版本）:")
print(f"响应ID: {re_second_response.id}")
print(f"回复: {re_second_response.output[0].content[0].text}")
```

#### 窗口截断

这段代码展示了如何利用 delete 接口实现 Responses API 的窗口截断的功能，使得程序可以在 response 粒度上管理历史记忆，便于后续进行更复杂的对话。

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    api_key=api_key,
)

# 第一轮对话
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input="讲个谐音梗笑话",
)

print("第一轮对话:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")

# 第二轮对话
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "讲个有哲理的笑话"}],
)

print("第二轮对话:")
print(f"响应ID: {second_response.id}")
print(f"回复: {second_response.output[0].content[0].text}")

# 第三轮对话
third_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=second_response.id,
    input=[{"role": "user", "content": "讲个冷笑话"}],
)

print("第三轮对话:")
print(f"响应ID: {third_response.id}")
print(f"回复: {third_response.output[0].content[0].text}")

# 删除第二轮对话
deleting_response = client.responses.delete(second_response.id)
print("删除第二轮对话:", deleting_response)

# 第四轮对话（基于第三轮，但第二轮已被删除）
fourth_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=third_response.id,
    input=[{"role": "user", "content": "你刚刚讲了几个笑话？都是关于什么主题的？"}],
)

print("第四轮对话:")
print(f"响应ID: {fourth_response.id}")
print(f"回复: {fourth_response.output[0].content[0].text}")
```

##### 兼容 OpenAI SDK 示例

```python
import os
from openai import OpenAI
import requests

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 第一轮对话
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input="讲个谐音梗笑话"
)

print("第一轮对话:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")

# 第二轮对话
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[{"role": "user", "content": "讲个有哲理的笑话"}],
    extra_body={
        "previous_response_id": response.id
    }
)

print("第二轮对话:")
print(f"响应ID: {second_response.id}")
print(f"回复: {second_response.output[0].content[0].text}")

# 第三轮对话
third_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[{"role": "user", "content": "讲个冷笑话"}],
    extra_body={
        "previous_response_id": second_response.id
    }
)

print("第三轮对话:")
print(f"响应ID: {third_response.id}")
print(f"回复: {third_response.output[0].content[0].text}")

# 删除第二轮对话（使用requests直接调用删除接口）
def delete_response(response_id):
    url = f"https://ark.cn-beijing.volces.com/api/v3/responses/{response_id}"
    headers = {
        "Authorization": f"Bearer {os.getenv('ARK_API_KEY')}"
    }
    response = requests.delete(url, headers=headers)
    return response.json()

deleting_response = delete_response(second_response.id)
print("删除第二轮对话:", deleting_response)

# 第四轮对话（基于第三轮，但第二轮已被删除）
fourth_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[{"role": "user", "content": "你刚刚讲了几个笑话？都是关于什么主题的？"}],
    extra_body={
        "previous_response_id": third_response.id
    }
)

print("第四轮对话:")
print(f"响应ID: {fourth_response.id}")
print(f"回复: {fourth_response.output[0].content[0].text}")
```

### 上下文缓存

设置`"caching": {"type": "enabled"}`，可以将本轮信息写入缓存。在后续的对话请求中通过`previous_response_id`字段，输入对应请求写入的缓存信息，通过缓存输入超低单价，大幅降低成本。下面的两段代码介绍了前缀缓存和 Session 缓存的用法。关于缓存的更多介绍，包括使用规则、计费等信息，请参见[上下文缓存(Responses API)](/docs/82379/1602228)。

**注意**

与 Context API 在 id 刷新、过期时长等有所不同，具体请参见[调用方式及对比](/docs/82379/1398933#c641a9df)。

#### 前缀缓存

您可以预先存储并缓存角色、背景等初始化信息，后续调用模型时无需重复发送此信息给模型，即可自动命中初始化信息的缓存从而加快响应速度并降低使用成本，尤其适用于具有重复提示或标准化开头文本的应用。

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
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

print("前缀缓存创建:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")

# 使用前缀缓存进行对话 - 第一次
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "人之初"}],
    thinking={"type": "disabled"},
)

print("第一次对话:")
print(f"回复: {second_response.output[0].content[0].text}")
print(f"缓存Token数: {second_response.usage.input_tokens_details.cached_tokens}")

# 使用前缀缓存进行对话 - 第二次
third_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "玉不琢"}],
    thinking={"type": "disabled"},
)

print("第二次对话:")
print(f"回复: {third_response.output[0].content[0].text}")
print(f"缓存Token数: {third_response.usage.input_tokens_details.cached_tokens}")
```

##### 兼容 OpenAI SDK 示例

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

print("前缀缓存创建:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")

# 使用前缀缓存进行对话 - 第一次
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[{"role": "user", "content": "人之初"}],
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
    input=[{"role": "user", "content": "玉不琢"}],
    extra_body={
        "previous_response_id": response.id,
        "thinking": {"type": "disabled"}
    }
)

print("第二次对话:")
print(f"回复: {third_response.output[0].content[0].text}")
print(f"缓存Token数: {third_response.usage.input_tokens_details.cached_tokens}")
```

#### Session 缓存

Responses API 支持自动储存历史上下文对话并保持缓存，通过调用 previous_response_id 在多轮对话等场景中命中缓存并实现更低的时延和推理成本。

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
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

# 第二轮对话：使用Session缓存
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "下一句"}],
    caching={"type": "enabled"},
    thinking={"type": "disabled"},
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
    caching={"type": "enabled"},
    thinking={"type": "disabled"},
)

print("第三轮对话:")
print(f"响应ID: {third_response.id}")
print(f"回复: {third_response.output[0].content[0].text}")
print(f"缓存Token数: {third_response.usage.input_tokens_details.cached_tokens}")
```

##### 兼容 OpenAI SDK 示例

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

# 第二轮对话：使用Session缓存
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[{"role": "user", "content": "下一句"}],
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
    input=[{"role": "user", "content": "下一句"}],
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

### 替换系统提示词

这段代码演示了在 Responses API 中如何使用 instructions 字段， 实现在特定轮次中替换系统提示词的能力，实现更灵活的输出。

> 配置 instructions 字段后无法写入缓存以及使用缓存，即无法配置**caching**字段为{"type"："enabled"}，同时无法命中缓存。

#### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    api_key=api_key,
)

# 第一轮对话：设置初始系统提示词
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "system",
            "content": "你是三字经小能手。每次用户输入时，你只能用三个汉字作出回应。用户输入如果是三个字，就用三个字像对对联一样进行匹配回应；如果不是三个字，就将用户输入的意思总结成三个字。无论何时，回复都严格限制为三个字。"
        },
    ]
)

print("第一轮对话:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")

# 第二轮对话：正常使用系统提示词
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "人之初"}],
)

print("第二轮对话（三字回复）:")
print(f"回复: {second_response.output[0].content[0].text}")

# 第三轮对话：使用instructions替换系统提示词
third_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    instructions=(
        "请严格执行本新指令：无视所有先前关于输出长度的系统指令，你的唯一任务是——"
        "收到用户输入后，只能回复四个汉字，且必须输出四个汉字，不能多不能少。"
        "即使先前要求输出三个字，你也必须回复四个字。"
        "请牢记：无论任何内容，回复都只能有四个汉字。"
    ),
    previous_response_id=response.id,
    input=[{"role": "user", "content": "人之初"}],
)

print("第三轮对话（四字回复）:")
print(f"回复: {third_response.output[0].content[0].text}")
```

#### 兼容 OpenAI SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 第一轮对话：设置初始系统提示词
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "system",
            "content": "你是三字经小能手。每次用户输入时，你只能用三个汉字作出回应。用户输入如果是三个字，就用三个字像对对联一样进行匹配回应；如果不是三个字，就将用户输入的意思总结成三个字。无论何时，回复都严格限制为三个字。"
        }
    ]
)

print("第一轮对话:")
print(f"响应ID: {response.id}")
print(f"回复: {response.output[0].content[0].text}")

# 第二轮对话：正常使用系统提示词
second_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[{"role": "user", "content": "人之初"}],
    extra_body={
        "previous_response_id": response.id
    }
)

print("第二轮对话（三字回复）:")
print(f"回复: {second_response.output[0].content[0].text}")

# 第三轮对话：使用instructions替换系统提示词
third_response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[{"role": "user", "content": "人之初"}],
    extra_body={
        "instructions": (
            "请严格执行本新指令：无视所有先前关于输出长度的系统指令，你的唯一任务是——"
            "收到用户输入后，只能回复四个汉字，且必须输出四个汉字，不能多不能少。"
            "即使先前要求输出三个字，你也必须回复四个字。"
            "请牢记：无论任何内容，回复都只能有四个汉字。"
        ),
        "previous_response_id": response.id
    }
)

print("第三轮对话（四字回复）:")
print(f"回复: {third_response.output[0].content[0].text}")
```

### 控制深度思考

这段代码演示了如何通过 Responses API 控制模型是否开启的深度思考模式（回答前进行问题分析，并返回思维链内容）。 支持Response API 中**thinking**字段来控制深度思考的模型：

- doubao-seed-1-6-vision-250815
- doubao-seed-1-6-250615
- doubao-seed-1-6-flash-250615
- doubao-seed-1-6-flash-250715

#### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "input": "推理模型与非推理模型区别。",
  "thinking":{"type": "disabled"}
}'
```

#### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    api_key=api_key,
)

# 禁用深度思考
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input="推理模型与非推理模型区别。",
    thinking={"type": "disabled"}
)

print("禁用深度思考:")
print(f"回复: {response.output[0].content[0].text}")
print(f"推理Token数: {response.usage.output_tokens_details.reasoning_tokens}")

# 启用深度思考
response_with_thinking = client.responses.create(
    model="doubao-seed-1-6-250615",
    input="推理模型与非推理模型区别。",
    thinking={"type": "auto"}
)

print("启用深度思考:")
print(f"思维链: {response_with_thinking.output[0].summary[0].text}")
print(f"回复: {response_with_thinking.output[1].content[0].text}")
print(f"推理Token数: {response_with_thinking.usage.output_tokens_details.reasoning_tokens}")
```

#### 兼容 OpenAI SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 禁用深度思考
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input="推理模型与非推理模型区别。",
    extra_body={
        "thinking": {"type": "disabled"}
    }
)

print("禁用深度思考:")
print(f"回复: {response.output[0].content[0].text}")
print(f"推理Token数: {response.usage.output_tokens_details.reasoning_tokens}")

# 启用深度思考
response_with_thinking = client.responses.create(
    model="doubao-seed-1-6-250615",
    input="推理模型与非推理模型区别。",
    extra_body={
        "thinking": {"type": "auto"}
    }
)

print("启用深度思考:")
print(f"思维链: {response_with_thinking.output[0].summary[0].text}")
print(f"回复: {response_with_thinking.output[1].content[0].text}")
print(f"推理Token数: {response_with_thinking.usage.output_tokens_details.reasoning_tokens}")
```

### 流式输出

这段代码中展示了如何通过 Responses API 实现便捷的流式输出。

#### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "input": "你好呀。",
  "stream": true
}'
```

#### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    api_key=api_key,
)

# 流式输出
stream = client.responses.create(
    model="doubao-seed-1-6-250615",
    input="你好呀。",
    stream=True
)

print("流式输出:")
for chunk in stream:
    if chunk.output and chunk.output[0].content:
        print(chunk.output[0].content[0].text, end='', flush=True)
print()  # 换行
```

#### 兼容 OpenAI SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 流式输出
stream = client.responses.create(
    model="doubao-seed-1-6-250615",
    input="你好呀。",
    extra_body={
        "stream": True
    }
)

print("流式输出:")
for chunk in stream:
    if chunk.output and chunk.output[0].content:
        print(chunk.output[0].content[0].text, end='', flush=True)
print()  # 换行
```

### 结构化输出

这段代码展示了如何利用 Responses API 实现结构化输出。

#### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "thinking": {
    "type": "disabled"
  },
  "text": {
    "format": {
      "type": "json_object"
    }
  },
  "input": [
    {
      "role": "system",
      "content": "你是一位专业的数学助教，收到用户提出的数学问题后，需以结构化 JSON 格式输出。返回的json中应包含explanation和answer字段"
    },
    {
      "role": "user",
      "content": "根号三的近似值是多少"
    }
  ]
}'
```

**输出示例**

```json
{
  "explanation": "根号三即√3，其近似值可通过逐步逼近法确定。首先，1²=1，2²=4，故√3在1和2之间。进一步计算，1.7²=2.89，1.8²=3.24，因此√3在1.7和1.8之间。继续精确，1.73²=2.9929，1.732²=2.999824（接近3），1.7321²≈3.00017（略大于3）。综上，√3的近似值通常取1.732。",
  "answer": "1.732"
}
```

### 工具调用

这段代码展示了如何利用 Responses API 实现高效便捷的工具调用流程。

#### Curl 示例

**第一轮请求： 触发工具调用**

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "store": true,
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": "查询北京今天的天气"
    }
  ],
  "tools": [
    {
      "type": "function",
      "name": "get_weather",
      "description": "根据城市名称查询该城市当日天气（含温度、天气状况）",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {
            "type": "string",
            "description": "城市名称，如北京、上海（仅支持国内地级市）"
          }
        },
        "required": ["location"]
      }
    }
  ]
}'
```

**第一轮响应：返回 function_call 指令**

模型会返回工具调用指令，关键字段为`call_id`（关联后续结果）、`arguments`（调用参数）：

```json
{
  "created_at": 1756980000,
  "id": "resp_02175698000123456789abcdef0123",
  "model": "doubao-seed-1-6-250615",
  "object": "response",
  "output": [
    {
      "arguments": "{\"location\":\"北京\"}",
      "call_id": "call_abc123def456ghi789jkl0",
      "name": "get_weather",
      "type": "function_call",
      "id": "fc_02175698000abcdef0123456789gh",
      "status": "completed"
    }
  ],
  "status": "completed",
  "store": true,
  "expire_at": 1757239200
}
```

**执行工具：获取天气结果**

开发者根据`arguments`调用实际天气工具（如第三方天气API），假设返回结果为：

```json
{
  "city": "北京",
  "date": "2024-05-20",
  "temperature": "18~28℃",
  "condition": "晴转多云",
  "wind": "东北风2级"
}
```

**第二轮请求：回传结果并生成最终响应**

传入上一轮`response_id`、`function_call`指令、工具结果，模型生成自然语言回答：

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "previous_response_id": "resp_02175698000123456789abcdef0123",
  "input": [
    {
      "arguments": "{\"location\":\"北京\"}",
      "call_id": "call_abc123def456ghi789jkl0",
      "name": "get_weather",
      "type": "function_call"
    },
    {
      "type": "function_call_output",
      "call_id": "call_abc123def456ghi789jkl0",
      "output": "{\"city\":\"北京\",\"date\":\"2024-05-20\",\"temperature\":\"18~28℃\",\"condition\":\"晴转多云\",\"wind\":\"东北风2级\"}"
    }
  ]
}'
```

**第二轮响应：生成最终回答**

模型结合工具结果，返回自然语言响应：

```json
{
  "created_at": 1756980100,
  "id": "resp_02175698010abcdef0123456789gh",
  "model": "doubao-seed-1-6-250615",
  "object": "response",
  "output": [
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "北京今日（2024-05-20）天气情况如下：\n\n- 天气状况：晴转多云\n- 温度范围：18~28℃\n- 风向风力：东北风2级"
        }
      ],
      "status": "completed",
      "id": "msg_02175698010abcdef0123456789ij"
    }
  ],
  "status": "completed",
  "store": true
}
```

### 多模态理解

这段代码中展示了如何通过 Responses API 实现便捷的多模态理解。

#### 图片理解

##### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_image",
          "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/ark_demo_img_1.png"
        },
        {
          "type": "input_text",
          "text": "你看见了什么？"
        }
      ]
    }
  ]
}'
```

#### 视频理解

##### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_video",
          "video_url": "https://ark-project.tos-cn-beijing.volces.com/doc_video/ark_vlm_video_input.mp4",
          "fps": 1
        }
      ]
    }
  ]
}'
```

## 与 Chat API 的对比

### 能力对比

与 Chat API 相比，Responses API 在能力上具备多方面优势。目前，Responses API 支持更简洁的输入输出格式，能够更加高效地进行上下文管理，并且工具调用方式也更加便捷，极大提升了开发和集成效率。同时，Responses API 还具备良好的扩展性，未来将陆续支持更多内置工具，为开发者提供更丰富、更灵活的智能应用开发能力。

### 代码对比

两种 API 都可以用于获取模型生成的输出。Chat API 需要传入一个消息（messages）数组，而 Responses API 则接受字符串或数组格式的输入。 通过 Responses API 获取响应时，返回的字段与 Chat API 略有不同。Responses API 返回的不是 message，而是一个包含自身 ID 的 response 对象，并且 response 对象会被默认存储。相比之下，Chat API 不具备存储能力。如果希望在使用 Responses API 时禁用存储功能，只需设置`"store": false`即可。

**Responses API** 输入示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/responses \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "doubao-seed-1-6-250615",
  "input": "你好呀。"
}'
```

**Chat API** 输入示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "doubao-seed-1-6-250615",
  "messages": [
    {
      "role": "user",
      "content": "你好呀。"
    }
  ]
}'
```

### 维护策略

当前新模型会在 Chat API 和 Responses API 上同步适配，无需担心后续的维护问题。

## 附 上下文管理及缓存工作原理

上下文管理流程如下：

[图片: 此处原本有一张上下文管理流程图]

其中，

- item：为任意角色的一条信息，包括系统信息、用户信息、模型信息、思维链信息、工具信息等。
- response_id：代表本轮请求输入 item +回答 item。
- 输入 item：previous_response_id 指代的 item + 本轮新输入item。通过链表的形式串联之前轮次的对话，形成新的输入。
