# 续写模式 Prefill Response

**最近更新时间：2025.09.08 20:27:52**
**首次发布时间：2024.11.01 13:00:06**

在使用或调用大模型时，如果希望控制和引导模型的输出，可以通过预填（Prefill）部分`assistant`角色的内容，来引导和控制模型的输出。输出的控制可以应用在多个方面：强制按照 JSON 或 XML 等特定格式输出；绕过模型最大输出限制，输出超长的回答；控制大模型在角色扮演场景中保持同一角色。

## 支持模型

[文本生成能力](/docs/82379/1330310#15a31773)

**注意**

Responses API 暂未支持该模式，即传入的消息列表中，最后一个消息的**role**不能是`assistant`。

## 主要用法

设置`messages`最后一个`role`为`Assistant`，模型会对`Assistant`已有的内容按照现有格式和内容进行续写。

### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(api_key=os.environ.get("ARK_API_KEY"))

completion = client.chat.completions.create(
    model="ep-2024****-**zpz",  # 你的推理接入点 ID
    messages=[
        {"role": "user", "content": "你是一个计算器，请计算： 1 + 1 "},
        # 最后Role为Assistant
        {"role": "assistant", "content": "="}
    ]
)

print(completion.choices[0].message.content)
```

### Curl 示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "ep-2024****-**zpz",
  "messages": [
    {"role": "user", "content": "你是一个计算器，请计算： 1 + 1 "},
    {"role": "assistant", "content": "="}
  ]
}'
```

[图片: 此处原本有一张图片展示续写模式示例]

> 续写即内容继续写作，输出内容不会包括用户填充的部分。

## 模式对比

### 普通模式

#### 请求示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(api_key=os.environ.get("ARK_API_KEY"))

completion = client.chat.completions.create(
    model="ep-2024****-**zpz",  # 你的推理接入点 ID
    messages=[
        {"role": "user", "content": "你是一个计算器，请计算： 1 + 1 "}
    ]
)

print(completion.choices[0].message.content)
```

#### 返回示例

输出会按照模型根据问题的完整自然语言回复。

```text
1+1等于2。
```

### 续写模式

#### 请求示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(api_key=os.environ.get("ARK_API_KEY"))

completion = client.chat.completions.create(
    model="ep-2024****-**zpz",  # 你的推理接入点 ID
    messages=[
        {"role": "user", "content": "你是一个计算器，请计算： 1 + 1 "},
        # 额外传入 = 的模型信息,模型据此续写
        {"role": "assistant", "content": "="}
    ]
)

print(completion.choices[0].message.content)
```

#### 返回示例

模型根据信息"="续写，保持对应的格式和行文风格。

```text
2
```

---

接下来，对于几种典型使用场景进行举例说明。

## 场景：改善输出格式

由于模型自身会基于自己的理解去响应用户的请求，会导致输出无法直接被其他程序解析。可以通过预填充`"{"`符号，引导模型跳过一些场景回复，直接输出 JSON 对象，会让回答更加简洁和工整，可以被其他程序更好地解析。

### 普通模式

#### 请求示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(api_key=os.environ.get("ARK_API_KEY"))

completion = client.chat.completions.create(
    model="ep-2024****-**",  # 你的Endpoint ID
    messages=[
        {"role": "user", "content": "用 JSON 描述豆包模型的name和function"}
    ]
)

print(completion.choices[0].message.content)
```

#### 返回示例

返回一些说明性语言，无法直接按照 JSON 解析。

```text
以下是一个简单的 JSON 示例来描述豆包模型的名称和功能：

```json
{
  "name": "豆包",
  "function": [
    "回答各种各样的知识类问题，包括但不限于科学知识（如物理、化学、生物等）、历史事件、文化传统、地理信息等",
    "提供关于语言学习方面的帮助，如语法解释、词汇辨析、翻译建议等",
    "对各种创意性话题进行讨论，例如给出故事创意、艺术创作的思路等",
    "解答生活常识问题，像家居维修建议、健康生活小贴士等"
  ]
}
```

当然，您可以根据更详细和具体的需求来进一步完善和扩展这个 JSON 描述。

### 续写模式

#### 请求示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(api_key=os.environ.get("ARK_API_KEY"))

completion = client.chat.completions.create(
    model="ep-****-**",  # 你的Endpoint ID
    messages=[
        {"role": "user", "content": "用 JSON 描述豆包模型的name和function"},
        # 额外传入一个 { 的模型信息,模型据此续写
        {"role": "assistant", "content": "{"}
    ]
)

print(completion.choices[0].message.content)
```

#### 返回示例

和前置的`assistant`信息组合成 JSON 格式的内容。

```json
"name": "豆包",
"function": [
  "回答各种各样的知识类问题，包括但不限于科学知识（如物理、化学、生物等）、历史事件、文化传统、地理信息等",
  "提供关于语言学习方面的帮助，如语法解释、词汇辨析、翻译建议等",
  "对各种创意性话题进行讨论，例如给出故事创意、艺术创作的思路等",
  "解答生活常识问题，像家居维修建议、健康生活小贴士等"
]
}
```

### 注意事项

- 方舟已提供结构化输出能力，可以让模型输出严格的 JSON 格式的回答，请参见[结构化输出](/docs/82379/1568221)。
- 由于模型具有一定的随机性，无法 100% 保证回复为标准JSON对象。建议您对模型的回复进行校验，下面示例使用[json_repair](https://github.com/mangiucugna/json_repair)库校验返回的是否为合法的 JSON 对象。

#### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark
import json
# 通过命令 pip install json-repair 安装json_repair库
import json_repair

PREFILL_PREFIX = "{"

client = Ark(api_key=os.environ.get("ARK_API_KEY"))

completion = client.chat.completions.create(
    model="ep-2024****-**",  # 你的Endpoint ID
    messages=[
        {"role": "user", "content": "用 JSON 描述豆包模型的名称和功能"},
        {"role": "assistant", "content": PREFILL_PREFIX}
    ]
)

# 拼接 PREFILL_PREFIX 和模型输出
json_string = PREFILL_PREFIX + completion.choices[0].message.content

# 解析 JSON Object
obj = {}
try:
    obj = json.loads(json_string)
except json.JSONDecodeError as e:
    obj = json_repair.loads(json_string)

print(obj)
```

## 场景：输出超过模型输出上限的内容

使用续写模式让大模型根据前轮请求续写内容，并拼接多次输出的内容，组合成超长输出。可以避免因为**max_tokens**（最大输出长度）限制，导致无法获取完整内容。

> 这种方式会将模型输出多次返回给模型，会有更多 token 用量。注意增加循环次数限制等兜底，防止死循环输出等特殊情况，导致意外花费。

### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(api_key=os.environ.get("ARK_API_KEY"))

messages = [
    {"role": "user", "content": "请翻译下面的文本为英文：******"},
    {"role": "assistant", "content": ""}
]

ark_model = "ep-2024****-**"

completion = client.chat.completions.create(
    model=ark_model,
    messages=messages
)

# 初始化循环计数器
loop_count = 0
max_loops = 20  # 设置最大循环次数为20

# 触发因为输出长度限制，循环生成 assistant 回复
while completion.choices[0].finish_reason == "length":
    messages[-1]["content"] += completion.choices[0].message.content
    completion = client.chat.completions.create(
        model=ark_model,
        messages=messages
    )

    # 增加计数器
    loop_count += 1

    # 检查是否超过最大循环次数
    if loop_count >= max_loops:
        print(f"警告：已达到最大循环次数 {max_loops}，停止生成内容")
        break

# 不管是否触发 finish_reason == "length"，都返回最后一条回复
messages[-1]["content"] += completion.choices[0].message.content
print(messages[-1]["content"])
```

### Curl 示例

```bash
# 第一次请求
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "ep-2024****-**",
  "messages": [
    {"role": "user", "content": "请翻译下面的文本为英文：******"},
    {"role": "assistant", "content": ""}
  ]
}'

# 如果返回的finish_reason为"length"，则继续请求
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "ep-2024****-**",
  "messages": [
    {"role": "user", "content": "请翻译下面的文本为英文：******"},
    {"role": "assistant", "content": "第一次返回的内容"}
  ]
}'
```

## 场景：增强角色扮演一致性

我们通常使用系统消息来设置角色的一些信息，但是随着对话轮次的增多，模型可能会跳脱出角色的约束，通过续写模式，提醒模型本次输出扮演的角色，保证对话符合预期。

### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(api_key=os.environ.get("ARK_API_KEY"))

ark_model = "ep-2024****-**"

messages = [
    {
        "role": "system",
        "content": "下面是一个西游记中的场景，请按照指定的角色来进行对话，每轮对话只用回复当前角色的内容，不要再回复新的内容。：\n\n唐僧师徒离了五庄观，又走了一个多月，来到一座大山前。悟空一看，四周崇山峻岭，杂草丛生，山势十分险恶。"
    },
    {"role": "assistant", "content": "悟空说："}
]

completion = client.chat.completions.create(
    model=ark_model,
    messages=messages
)

print(messages[-1]['content'] + completion.choices[0].message.content)
```

**模型输出示例：**

```text
悟空说："师父，这山看起来险恶得很，俺老孙先去探探路，你们且在此等候。"
```

您也可以通过变更`messages`最后消息，实现角色切换。

```python
# 角色切换示例
messages[-1] = {"role": "assistant", "content": "唐僧说："}

completion = client.chat.completions.create(
    model=ark_model,
    messages=messages
)

print(messages[-1]['content'] + completion.choices[0].message.content)
```

**模型输出示例：**

```text
唐僧说："悟空，此山看起来甚是险恶，你定要小心查看，莫要着了妖怪的道。"
```

### Curl 示例

```bash
# 悟空角色
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "ep-2024****-**",
  "messages": [
    {
      "role": "system",
      "content": "下面是一个西游记中的场景，请按照指定的角色来进行对话，每轮对话只用回复当前角色的内容，不要再回复新的内容。：\n\n唐僧师徒离了五庄观，又走了一个多月，来到一座大山前。悟空一看，四周崇山峻岭，杂草丛生，山势十分险恶。"
    },
    {"role": "assistant", "content": "悟空说："}
  ]
}'

# 唐僧角色
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "ep-2024****-**",
  "messages": [
    {
      "role": "system",
      "content": "下面是一个西游记中的场景，请按照指定的角色来进行对话，每轮对话只用回复当前角色的内容，不要再回复新的内容。：\n\n唐僧师徒离了五庄观，又走了一个多月，来到一座大山前。悟空一看，四周崇山峻岭，杂草丛生，山势十分险恶。"
    },
    {"role": "assistant", "content": "唐僧说："}
  ]
}'
```
