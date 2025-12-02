# 工具调用 Function Calling

**最近更新时间：2025.09.05 17:07:17**
**首次发布时间：2024.05.20 14:03:52**

## 功能概述

### 功能简介

工具调用（Function Calling）是一种将大模型与外部工具和 API 相连的关键功能，作为自然语言与信息接口之间的"翻译官"，它能够将用户的自然语言请求智能地转化为对特定工具或 API 的调用，从而高效满足用户的特定需求。

- **核心价值**：实现大模型与外部工具的无缝衔接，使大模型能够借助外部工具处理实时数据查询、任务执行等复杂场景，推动大模型在实际产业中的落地应用。
- **工作原理**：开发者通过自然语言向模型描述工具的功能和定义，模型在对话过程中自主判断是否需要调用工具。当需要调用时，模型会返回符合要求的工具函数及入参，开发者负责实际调用工具并将结果回填给模型，模型再根据结果进行总结或继续规划子任务。

### 适用场景

Function Calling 适用于以下需要大模型与外部工具协同的场景：

| 场景分类 | 核心特征 | 核心价值 | 典型应用 |
|----------|----------|----------|----------|
| 实时数据交互场景 | 需大模型与外部工具协同处理动态信息 | 处理动态信息查询需求 | 天气/股票/航班实时状态查询、数据库检索与 API 数据调用 |
| 任务自动化场景 | 单次工具调用完成操作 | 提升操作效率 | 邮件/消息自动发送、设备控制指令执行（如智能家居开关） |
| 复杂流程编排场景 | 多工具串并联调用 | 跨工具参数传递、子任务依赖关系管理 | 先查天气再发通知等需跨工具传递参数及管理子任务依赖的场景 |
| 智能系统集成场景 | 与业务系统深度耦合 | 实现系统智能化联动 | 智能座舱多设备联动控制、企业级 Bot 工作流（如飞书会议创建→群组管理→任务生成） |

### 典型示例

**用户**：北京今天的天气如何？适合穿什么衣服？

**模型思考**：

- 需要调用天气查询工具获取实时数据（location=北京，unit=摄氏度）
- 天气信息包含温度、天气状况（晴/雨等），需结合数据给出穿衣建议

**工具调用结果**：北京今天晴，气温 18-25℃，北风3级，湿度45%

**模型回答**：北京今天天气晴朗，气温18-25℃，建议穿薄长袖衬衫或短袖T恤，搭配薄外套应对早晚温差。

### 工作原理图

[图片: 此处原本有一张工作原理图展示Function Calling的完整流程]

## 支持模型

全量支持工具调用的模型，请参见[工具调用能力](/docs/82379/1330310#98fee2f1)。基于效果/准确性和时延的权衡原则，推荐选型建议如下：

**效果优先型（高准确性，时延较高）**

- **doubao-seed-1-6-thinking-250615**：强制开启思考模式，不可关闭，专注于**Coding、Math 和逻辑推理**任务，在基础能力上显著优于前代模型（如 doubao-1-5-thinking-pro），适用于高准确性要求的复杂场景。
- **doubao-seed-1-6-250615**：默认开启深度思考模式（支持 auto/thinking/non-thinking），具有自适应思考机制（根据问题难度自动开关思考），适用于通用场景，尤其在**非思考模式下效果大幅提升**。
- **deepseek-v3-250324**：在**数学推理**和**代码生成**场景超越GPT-4.5，支持HTML前端任务的高可用性代码生成。
- **deepseek-r1-250528**：通过强化学习优化参数生成，在**多步骤工具调用**场景中表现优异，需配合系统提示干预参数幻觉。（参考文末FAQ部分）

**时延优先型（快速响应，效果相对宽松）**

- **doubao-seed-1-6-flash-250615**：适用于延迟敏感场景（如实时控制或高速调用），文本理解能力超上一代 lite 模型，且视觉理解比肩旗舰模型。
- **doubao-1-5-lite-32k-250115**：平均响应时延**降低40%**，适用于智能客服、实时控制等场景，支持并行工具调用。

## 使用流程

### 环境准备

调用方舟模型前，需先进行权限配置获取API Key并配置到环境变量。若通过火山引擎官方SDK或OpenAI SDK调用，需提前安装对应SDK，方舟已提供Go、Python、Java的SDK，便于快速集成模型服务。

**环境配置参考：**

- [获取 API Key](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey)。
  - 使用 Access Key 鉴权请参考[Access Key 签名鉴权](/docs/82379/1298459#21bff83b)。
- [开通模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&OpenTokenDrawer=false)。
- 在[模型列表](/docs/82379/1330310)获取所需 Model ID 。
  - 通过 Endpoint ID 调用模型服务请参考[获取 Endpoint ID（创建自定义推理接入点）](/docs/82379/1099522)。
- [安装及升级 SDK](/docs/82379/1541595)。

### 基本使用流程

#### 步骤 1：定义工具

通过`tools`字段向模型描述可用工具，支持 JSON 格式，包含工具名称、描述、参数定义等信息。

**定义工具函数**

```python
def get_current_weather(location, unit="摄氏度"):
    # 实际调用天气查询 API 的逻辑
    # 此处为示例，返回模拟的天气数据
    return f"{location}今天天气晴朗，温度 25 {unit}。"
```

- 代码中定义了一个名为`get_current_weather`的工具函数，用于获取指定地点的天气信息。
  - `location`：必需的参数，表示地点。
  - `unit`：可选参数，默认值为`摄氏度`，表示温度单位。
- 函数内部目前只是返回模拟的天气数据，实际应用中需要调用真实的天气查询 API。

**定义 Tools**

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "获取指定地点的天气信息，支持摄氏度和华氏度两种单位",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "地点的位置信息，例如北京、上海"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["摄氏度", "华氏度"],
                        "description": "温度单位，可选值为摄氏度或华氏度"
                    }
                },
                "required": ["location"]
            }
        }
    }
]
```

- `tools`是一个列表，其中每个元素代表一个工具。这里定义了一个名为`get_current_weather`的工具。
- `type`：工具的类型，这里是`function`，表示这是一个工具调用工具。
- `function`：包含工具的详细信息，如名称、描述和参数。
  - `name`：工具的名称，即`get_current_weather`。
  - `description`：工具的描述，说明该工具用于获取指定地点的天气信息。
  - `parameters`：工具所需的参数，这里是一个对象，包含`location`和`unit`两个属性。
    - `location`：地点的位置信息，是一个字符串类型的参数。
    - `unit`：温度单位，是一个字符串类型的参数，可选值为`摄氏度`或`华氏度`。
    - `required`：指定必需的参数，这里只有`location`是必需的。

更多关于工具构造相关的规范和注意事项，请参见[附1：工具参数构造规范](/docs/82379/1262342#4d571c97)。

#### 步骤 2：发起模型请求

在请求中包含用户问题和工具定义，模型会根据需求返回需要调用的工具及参数。

### Curl 示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "<MODEL>",
  "messages": [
    {"role": "user", "content": "北京今天的天气如何？"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_current_weather",
        "description": "获取指定地点的天气信息，支持摄氏度和华氏度两种单位",
        "parameters": {
          "type": "object",
          "properties": {
            "location": {
              "type": "string",
              "description": "地点的位置信息，例如北京、上海"
            },
            "unit": {
              "type": "string",
              "enum": ["摄氏度", "华氏度"],
              "description": "温度单位，可选值为摄氏度或华氏度"
            }
          },
          "required": ["location"]
        }
      }
    }
  ]
}'
```

### Python SDK 示例

```python
import os
import json
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

# 初始化Ark客户端
client = Ark(api_key=api_key)

# 用户问题
messages = [
    {"role": "user", "content": "北京今天的天气如何？"}
]

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "获取指定地点的天气信息，支持摄氏度和华氏度两种单位",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "地点的位置信息，例如北京、上海"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["摄氏度", "华氏度"],
                        "description": "温度单位，可选值为摄氏度或华氏度"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

# 发起模型请求
completion = client.chat.completions.create(
    model="<MODEL>",  # 替换为实际的Model ID
    messages=messages,
    tools=tools
)
```

#### 步骤 3：调用外部工具

根据模型返回的工具名称和参数，调用对应的外部工具或 API，获取工具执行结果。

### Curl 示例

```bash
# 解析模型返回的工具调用信息
# 假设模型返回了需要调用 get_current_weather 工具的信息
# 提取工具名称和参数，然后调用实际的工具函数

# 示例响应解析（实际需要根据返回的JSON进行解析）
# {
#   "choices": [{
#     "message": {
#       "tool_calls": [{
#         "id": "call_123",
#         "function": {
#           "name": "get_current_weather",
#           "arguments": "{\"location\": \"北京\"}"
#         }
#       }]
#     }
#   }]
# }

# 调用工具后，将结果回填给模型
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "<MODEL>",
  "messages": [
    {"role": "user", "content": "北京今天的天气如何？"},
    {
      "role": "assistant",
      "content": "",
      "tool_calls": [
        {
          "id": "call_123",
          "type": "function",
          "function": {
            "name": "get_current_weather",
            "arguments": "{\"location\": \"北京\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_123",
      "content": "北京今天天气晴朗，温度 25 摄氏度。"
    }
  ]
}'
```

### Python SDK 示例

```python
# 解析模型返回的工具调用信息
tool_call = completion.choices[0].message.tool_calls[0]

# 工具名称
tool_name = tool_call.function.name

# 如果判断需要调用查询天气工具，则运行查询天气工具
if tool_name == "get_current_weather":
    # 提取的用户参数
    arguments = json.loads(tool_call.function.arguments)
    # 调用工具
    tool_result = get_current_weather(**arguments)
```

- `tool_calls`：获取模型调用的工具列表。
- 如果工具名称是`get_current_weather`，则解析工具调用的参数并调用`get_current_weather`函数获取工具执行结果。

#### 步骤 4：回填工具结果并获取最终回复

将工具执行结果以`role=tool`的消息形式回填给模型，模型根据结果生成最终回复。

### Curl 示例

```bash
# 再次调用模型获取最终回复
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "<MODEL>",
  "messages": [
    {"role": "user", "content": "北京今天的天气如何？"},
    {
      "role": "assistant",
      "content": "",
      "tool_calls": [
        {
          "id": "call_123",
          "type": "function",
          "function": {
            "name": "get_current_weather",
            "arguments": "{\"location\": \"北京\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_123",
      "content": "北京今天天气晴朗，温度 25 摄氏度。"
    }
  ]
}'
```

### Python SDK 示例

```python
messages.append(completion.choices[0].message)
messages.append({
    "role": "tool",
    "tool_call_id": tool_call.id,
    "content": tool_result
})

# 再次调用模型获取最终回复
final_completion = client.chat.completions.create(
    model="<MODEL>",
    messages=messages
)

print(final_completion.choices[0].message.content)
```

### 完整代码示例

#### Python - Ark SDK 示例

```python
import os
import json
from volcenginesdkarkruntime import Ark

def get_current_weather(location, unit="摄氏度"):
    # 实际调用天气查询 API 的逻辑
    # 此处为示例，返回模拟的天气数据
    return f"{location}今天天气晴朗，温度 25 {unit}。"

# 从环境变量中获取您的API KEY
api_key = os.getenv('ARK_API_KEY')

# 初始化Ark客户端
client = Ark(api_key=api_key)

# 用户问题
messages = [
    {"role": "user", "content": "北京今天的天气如何？"}
]

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "获取指定地点的天气信息，支持摄氏度和华氏度两种单位",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "地点的位置信息，例如北京、上海"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["摄氏度", "华氏度"],
                        "description": "温度单位，可选值为摄氏度或华氏度"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

# 发起模型请求
completion = client.chat.completions.create(
    model="doubao-1-5-pro-32k-250115",
    messages=messages,
    tools=tools
)

# 解析模型返回的工具调用信息
if completion.choices[0].message.tool_calls:
    tool_call = completion.choices[0].message.tool_calls[0]
    tool_name = tool_call.function.name

    # 如果判断需要调用查询天气工具，则运行查询天气工具
    if tool_name == "get_current_weather":
        # 提取的用户参数
        arguments = json.loads(tool_call.function.arguments)
        # 调用工具
        tool_result = get_current_weather(**arguments)

        # 回填工具结果
        messages.append(completion.choices[0].message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": tool_result
        })

        # 再次调用模型获取最终回复
        final_completion = client.chat.completions.create(
            model="doubao-1-5-pro-32k-250115",
            messages=messages
        )

        print(final_completion.choices[0].message.content)
else:
    # 模型直接回复，无需调用工具
    print(completion.choices[0].message.content)
```

#### （推荐）使用方舟智能体SDK Arkitect

```python
from arkitect.core.component.context.context import Context
from enum import Enum
import asyncio
from pydantic import Field

def get_current_weather(location: str = Field(description="地点的位置信息，例如北京、上海"),
                       unit: str = Field(description="温度单位, 可选值为摄氏度或华氏度")):
    """
    获取指定地点的天气信息
    """
    return f"{location}今天天气晴朗，温度 25 {unit}。"

async def chat_with_tool():
    ctx = Context(
        model="doubao-1-5-pro-32k-250115",
        tools=[
            get_current_weather
        ],  # 直接在这个list里传入你的所有python 方法作为tool，tool的描述会自动带给模型推理，tool的执行在ctx.completions.create 中会自动进行
    )
    await ctx.init()

    completion = await ctx.completions.create(
        messages=[
            {"role": "user", "content": "北京和上海今天的天气如何？"}
        ],
        stream=False
    )
    return completion

completion = asyncio.run(chat_with_tool())
print(completion.choices[0].message.content)
```

## 推荐配置与优化

### 新业务接入

- 推荐优选`doubao-seed-1.6`系列模型。
  - FC场景下，关闭 thinking 会提高效率，具体操作请参见[开启关闭深度思考](/docs/82379/1449737#fa3f44fa)。
  - 对速度有较高要求，可以选择`doubao-seed-1-6-flash-******`模型。
- 准备评测集，在FC模型测试，看看准确率，以及业务预期上线准确率。
- 常规调优手段：
  - Functions的params、description等字段准确填写。System prompt中不用再重复介绍函数，（可选）可以描述在何种情况下调用某函数
  - 优化函数、参数的描述，明确不同函数的边界情况；避免歧义；增加示例等。
  - 对模型进行sft（建议至少50条数据，模型越多、参数越多、情况越多，则所需要的数据越多），见[精调优化](/docs/82379/1262342#f118e5a2)。
- 速度优化：对于简单无歧义的函数或参数，适当精简输入输出内容。

### prompt最佳实践

**原则：Treat LLM as a kid**

- 能不用大模型完成的任务，就不要调用大模型，尽量代码完成。
- 和任务无关的信息，避免输入，避免信息干扰。

| 类别 | 问题 | 错误示例 | 改正后示例 |
|------|------|----------|------------|
| 函数 | 命名不规范、描述不规范 | `{"type": "function", "function": {"name": "GPT1", "description": "新建日程"}}` | `{"type": "function", "function": {"name": "CreateEvent", "description": "当需要为用户新建日程时，此工具将创建日程，并返回日程ID"}}` |
| 参数 | 避免不必要的复杂格式（或嵌套） | `{"time": {"type": "object", "description": "事件时间", "properties": {"timestamp": {"description": "事件时间"}}}}` | `{"time": {"type": "string", "description": "事件时间"}}` |
| | 避免固定值 | `{"time": {"type": "object", "description": "事件时间", "properties": {"timestamp": {"description": "固定传2024-01-01即可"}}}}` | 既然参数值固定，删去该参数，由代码处理。 |
| 业务流程 | 尽量缩短LLM调用轮次 | System prompt: `你正在与用户Alan沟通，你需要先查询用户ID，再通过ID创建日程……` | System prompt: `你正在与用户Alan（ID=abc123）沟通，你可以通过ID创建日程……` |
| 歧义消解 | | System prompt: `可以通过ID查找用户，并获得用户的日程ID` 这里两个ID未明确，模型可能会混用 | System prompt: `每个用户具有唯一的用户ID；每个日程有对应的日程ID，两者独立的ID。可以通过用户ID查找用户，并获得用户的所有日程ID` |

### 工具调用异常处理

JSON 格式容错机制：对于轻微不合法的 JSON 格式，可尝试使用`json-repair`库进行容错修复。

### Curl 示例

```bash
# 安装json-repair库（如果使用Python）
pip install json-repair
```

### Python SDK 示例

```python
import json_repair

invalid_json = '{"location": "北京", "unit": "摄氏度"}'
valid_json = json_repair.loads(invalid_json)
```

### 需求澄清

需求澄清（确认需求），不依赖与FC，可独立使用。可在 System prompt 中加入：

### Curl 示例

```bash
# 在请求中添加系统提示
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "<MODEL>",
  "messages": [
    {
      "role": "system",
      "content": "如果用户没有提供足够的信息来调用函数，请继续提问以确保收集到了足够的信息。在调用函数之前，你必须总结用户的描述并向用户提供总结，询问他们是否需要进行任何修改。"
    },
    {"role": "user", "content": "帮我创建一个日程"}
  ],
  "tools": [...]
}'
```

### Python SDK 示例

```python
messages = [
    {
        "role": "system",
        "content": "如果用户没有提供足够的信息来调用函数，请继续提问以确保收集到了足够的信息。在调用函数之前，你必须总结用户的描述并向用户提供总结，询问他们是否需要进行任何修改。"
    },
    {"role": "user", "content": "帮我创建一个日程"}
]

completion = client.chat.completions.create(
    model="<MODEL>",
    messages=messages,
    tools=tools
)
```

在函数的 description 中加入：

### Python SDK 示例

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": "创建日程事件。函数参数除了提取标题和时间，还应要求用户提供地点、参与者、提醒设置和其他相关细节。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "日程标题"},
                    "time": {"type": "string", "description": "日程时间"},
                    "location": {"type": "string", "description": "日程地点"},
                    "participants": {"type": "array", "items": {"type": "string"}, "description": "参与者列表"}
                },
                "required": ["title", "time"]
            }
        }
    }
]
```

或在系统提示中加入参数校验逻辑，当模型生成的参数缺失时，引导模型重新生成完整的参数。

### Python SDK 示例

```python
system_prompt = "如果用户提供的信息缺少工具所需要的必填参数，你需要进一步追问让用户提供更多信息。"

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": "用户查询内容"}
]
```

### 流式输出适配

从 Doubao-1.5 系列模型开始支持流式输出，逐步获取工具调用信息，提升响应效率。详见[Function Calling 流式输出适配](/docs/82379/1449722)。

#### Curl 示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "doubao-1-5-pro-32k-250115",
  "messages": [
    {"role": "user", "content": "北京今天的天气如何？"}
  ],
  "tools": [...],
  "stream": true
}' --no-buffer
```

#### Python SDK 示例

```python
def function_calling_stream():
    completion = client.chat.completions.create(
        model="doubao-1-5-pro-32k-250115",
        messages=messages,
        tools=tools,
        stream=True
    )

    for chunk in completion:
        if chunk.choices[0].delta.tool_calls:
            tool_call = chunk.choices[0].delta.tool_calls[0]
            print(f"工具名称：{tool_call.function.name}，参数：{tool_call.function.arguments}")

function_calling_stream()
```

### 多轮工具调用

当用户需求需要多次调用工具时，维护对话历史上下文，逐轮处理工具调用和结果回填。

#### 示例流程

- **用户提问**："查询北京的天气，并将结果发送给张三"。
- **第一轮**：模型调用`get_current_weather`工具获取北京天气。
- **第二轮**：模型调用`send_message`工具将天气结果发送给张三。
- **第三轮**：模型总结任务完成情况，返回最终回复。

#### 代码示例

**说明**

多轮Function Calling：指用户query需要多次调用工具和大模型才能完成的情况，是多轮对话的子集。

调用Response细节图：[图片: 此处原本有一张多轮调用的流程图]

#### Python SDK 示例

```python
import os
import json
from volcenginesdkarkruntime import Ark

def get_current_weather(location, unit="摄氏度"):
    # 模拟天气查询
    return f"{location}今天天气晴朗，温度 25 {unit}。"

def send_message(receiver, content):
    # 模拟发送消息
    return f"成功发送消息给{receiver}：{content}"

client = Ark(api_key=os.getenv('ARK_API_KEY'))

messages = [
    {"role": "system", "content": "你是豆包，是由字节跳动开发的 AI 人工智能助手"},
    {"role": "user", "content": "查询北京的天气，并将结果发送给张三"}
]

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "获取指定地点的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "地点的位置信息"},
                    "unit": {"type": "string", "description": "温度单位"}
                },
                "required": ["location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "发送消息给指定用户",
            "parameters": {
                "type": "object",
                "properties": {
                    "receiver": {"type": "string", "description": "接收者姓名"},
                    "content": {"type": "string", "description": "消息内容"}
                },
                "required": ["receiver", "content"]
            }
        }
    }
]

# 多轮工具调用处理
while True:
    completion = client.chat.completions.create(
        model="doubao-1-5-pro-32k-250115",
        messages=messages,
        tools=tools
    )

    assistant_message = completion.choices[0].message
    messages.append(assistant_message)

    if assistant_message.tool_calls:
        # 处理工具调用
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            if function_name == "get_current_weather":
                result = get_current_weather(**arguments)
            elif function_name == "send_message":
                result = send_message(**arguments)
            else:
                result = "未知工具调用"

            # 添加工具结果到对话历史
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })
    else:
        # 模型给出最终回复，结束循环
        print(assistant_message.content)
        break
```

#### 多轮输出注意事项

**轮次输出顺序**

触发工具调用时，系统先输出`content`给用户，再生成`tool_calls`并结束当前输出；**当前轮次内容不可依赖工具结果**，后续指令需待工具返回`message`后执行。

**多轮输出响应完整性**

严格遵循`assistant（含tool_calls）→ tool（含message）→ assistant`的顺序，禁止跳过`tool message`响应直接发送新的`assistant`消息。每次`tool_calls`需对应`tool`角色的`message`（含成功/错误结果），缺失可能因`prefill`机制触发重复调用或流程中断。

### 精调优化

如果 Function Calling 效果未达预期，可通过精调（SFT）提升模型表现。详情请参见[创建模型精调任务](/docs/82379/1099459)。

#### 精调场景

- 提高工具选择的准确性，确保模型在合适的时机调用正确的工具。
- 优化参数提取能力，使模型能够准确解析用户需求并生成正确的工具入参。
- 改善结果总结质量，让模型能够更自然、准确地总结工具执行结果。

#### 精调样本格式

```json
{
  "messages": [
    {
      "role": "system",
      "content": "你是豆包AI助手"
    },
    {
      "role": "user",
      "content": "把北京的天气发给李四"
    },
    {
      "role": "assistant",
      "content": "",
      "tool_calls": [
        {
          "type": "function",
          "function": {
            "name": "get_current_weather",
            "arguments": "{\"location\": \"北京\"}"
          }
        }
      ],
      "loss_weight": 1.0
    },
    {
      "role": "tool",
      "content": "北京今天晴，25摄氏度"
    },
    {
      "role": "assistant",
      "content": "",
      "tool_calls": [
        {
          "type": "function",
          "function": {
            "name": "send_message",
            "arguments": "{\"receiver\": \"李四\", \"content\": \"北京今天晴，25摄氏度\"}"
          }
        }
      ],
      "loss_weight": 1.0
    },
    {
      "role": "tool",
      "content": "消息发送成功"
    },
    {
      "role": "assistant",
      "content": "已将北京的天气信息发送给李四"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_current_weather",
        "description": "获取指定地点的天气",
        "parameters": {
          "type": "object",
          "properties": {
            "location": {"type": "string", "description": "地点的位置信息"}
          },
          "required": ["location"]
        }
      }
    }
  ]
}
```

## 常见问题

### Q：FC & MCP 的核心区别是什么，使用时如何选型？

**核心区别与典型使用场景**

| 维度 | FC（Function Calling） | MCP（Model Context Protocol） |
|------|------------------------|--------------------------------|
| 本质 | 模型调用外部工具 / 函数的能力（功能扩展） | 定义模型与外部系统交互时的上下文管理协议（流程规范） |
| 目标 | 弥补模型自身能力不足（如计算、数据查询、操作执行） | 标准化交互过程中上下文的传递、解析与状态维护 |
| 核心作用 | 实现模型与外部工具的 "能力集成" | 确保多轮交互中上下文（如对话历史、参数、状态）的一致性 |
| 协议标准 | 厂商自定义格式（如 OpenAI 的 JSON 参数结构） | 强制遵循 JSON-RPC 2.0 标准，强调协议统一性 |
| 架构 | 直接集成于模型 API，用户定义函数后由模型触发调用 | 客户端 - 服务器模式，分离 MCP Host（客户端）与 MCP Server（服务端） |
| 上下文管理 | 单次请求 - 响应模式，上下文依赖需开发者自行处理 | 支持多轮对话、历史状态维护，适用于长序列依赖任务 |
| 典型使用场景 | 外部数据调用与系统操作（如天气查询、复杂运算）；示例：调用天气 API 回复 "东京今日气温" | 多轮对话与跨系统上下文管理（如订餐流程、客服对话）；示例：连贯处理订餐菜品与配送地址 |

**两者之间的关系**

- **互补而非互斥：**
  - MCP 可能在流程中包含 FC 的调用逻辑（如定义何时、如何触发工具调用）
  - FC 的输入输出需遵循 MCP 的上下文规范（如参数格式、返回值解析规则）
- **分层协作**：
  - **MCP 解决连接问题**：标准化协议打通数据孤岛，提供基础设施（如整合用户订单数据）。
  - **FC 解决执行问题**：在协议层之上调用具体函数完成任务（如调用库存 API 生成补货建议）。
- **架构定位**：FC 是**能力接口**，MCP 是**交互框架**，二者常结合使用以构建复杂应用（如智能助手同时需要调用工具和管理多轮对话状态）。

**References**

- **MCP 官方协议规范（草案）**：明确协议核心架构、JSON - RPC 消息格式、状态管理机制与安全策略，是接口设计的权威参考。[Model Context Protocol Specification](https://spec.modelcontextprotocol.io/specification/draft/)
- **MCP 社区与生态发展**：介绍 MCP 发展规划，涵盖远程连接支持、沙箱安全机制及多模态扩展等发展计划。[MCP Development Roadmap](https://modelcontextprotocol.io/development/roadmap)

### Q：Deepseek R1 模型是否支持并行工具调用？

**A：暂不支持`parallel_tool_calls`控制字段，该模型默认采用自动触发并行调用**机制，开发者无需额外配置即可实现多工具并行调用。

### Q：如何处理 Deepseek R1 的参数幻觉问题？

**A：该模型在复杂参数解析时可能出现嵌套调用异常**（如`"get_weather:{city: get_location()}"`），建议通过以下方式干预：

- 在`system prompt`中明确要求**分步调用**（如"请先调用定位工具，再调用天气查询工具"）
- 使用**JSON Schema 校验**强制参数格式

### Q：如何判断模型是否需要调用工具？

A：模型会根据用户问题和工具定义自主判断，若返回结果中包含`tool_calls`字段，则表示需要调用工具；若`content`字段有直接回复，则无需调用工具。

### Q：支持并行调用多个工具吗？

A：支持并行工具调用，通过设置`parallel_tool_calls`参数为`"true"`，模型可同时返回多个工具调用信息，提高处理效率。

### Q：为什么模型返回的工具参数存在幻觉？

A：这是大模型常见的问题，可通过精调（SFT）优化模型的参数生成能力，或在系统提示中明确参数的格式和范围，减少幻觉现象。部分模型（特别是Deepseek R1）存在一些参数幻觉问题。如预期先调用get_location获得城市，再调用get_weather查询，R1模型有概率直接返回get_weather:{city:**get_location()**} 这种嵌套调用，请在system prompt中进行干预解决，分步完成调用。

### Q：如何处理工具调用失败的情况？

A：将工具失败信息以`role=tool`的消息回填给模型，模型会根据错误信息生成相应的回复，例如"抱歉，工具调用失败，请稍后重试。"通过以上优化，开发者能够更高效地使用 Function Calling 功能，实现大模型与外部工具的深度整合，快速构建智能应用。

## 附1：工具参数构造规范

为确保模型正确调用工具功能，需按以下规范构造`tools`对象，遵循 JSON Schema 标准。本文主要讲解如何构造 Function Calling 工具，关于工具的使用请参考[基本使用流程](/docs/82379/1262342#db7321a0)。

### 总体结构

```json
{
  "type": "function",
  "function": {
    "name": "...",        // 函数名称（小写+下划线）
    "description": "...", // 功能描述
    "parameters": { ... } // 参数定义（JSON Schema格式）
  }
}
```

- `type`：工具的类型，这里是固定值`function`，表示这是一个工具调用工具。
- `function`：含函数名称、描述和参数等详细配置。

### 字段解释

#### function 字段

| 字段 | 类型 | 是否必填 | 说明 |
|------|------|----------|------|
| name | string | 是 | 函数名称，唯一标识，建议使用小写加下划线 |
| description | string | 是 | 函数作用的描述 |
| parameters | object | 是 | 函数参数定义，需要符合 JSON Schema 格式 |

#### parameters 字段

`parameters`须为符合 JSON Schema 格式的对象：

```json
{
  "type": "object",
  "properties": {
    "参数名": {
      "type": "string | number | boolean | object | array",
      "description": "参数说明"
    }
  },
  "required": ["必填参数"]
}
```

- `type`：必须是`"object"`。
- `properties`：列出支持的所有参数名及其类型。
  - `参数名`须为英文字符串，且不能重复。
    - 参数`type`需遵循[json规范](https://json-schema.org/docs)，支持类型包括string、number、boolean、integer、object、array。
    - `required`：指定函数中必填的参数名。
    - 其它参数根据`type`的不同稍有区别，详情请参见下表。

| type类型 | 示例 |
|----------|------|
| string、integer、number、boolean | 略 |
| object （对象）<br/>- description：简要说明<br/>- properties 描述该对象所有属性<br/>- required 描述必填属性 | 示例1: 查询特点用户画像（根据年龄、性别、婚姻状况等）<br/>`"person": {"type": "object", "description": "个人特征", "properties": {"age": {"type": "integer", "description": "年龄"}, "gender": {"type": "string", "description": "性别"}, "married": {"type": "boolean", "description": "是否已婚"}}, "required": ["age"]}` |
| array （列表）<br/>- description:简要说明<br/>- "items": {"type": ITEM_TYPE}来表达数组元素的数据类型 | 示例1：文本数组，若干个网页链接<br/>`"url": {"type": "array", "description": "需要解析网页链接,最多3个", "items": {"type": "string"}}`<br/><br/>示例2： 二维数组<br/>`"matrix": {"type": "array", "description": "需要计算的二维矩阵", "items": {"type": "array", "items": {"type": "number"}}}`<br/><br/>示例3: 通过array来实现多选<br/>`"grade": {"description": "年级, 支持多选", "type": "array", "items": {"type": "string", "description": "枚举值有 \"一年级\", \"二年级\", \"三年级\", \"四年级\", \"五年级\", \"六年级\"。"}}` |

### 完整示例

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "获取指定位置的天气信息",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string",
          "description": "城市和国家，例如：北京，中国"
        }
      },
      "required": ["location"]
    }
  }
}
```

### 注意事项

- **大小写敏感**：所有字段名、参数名严格区分大小写（建议统一用小写）。
- **中文处理**：字段名用英文，中文说明置于`description`中（如`location`的描述为 "城市和国家"）。
- **Schema 合规性**：`parameters`必须是有效的 JSON Schema 对象，可通过JSON Schema 校验工具验证。

### 最佳实践

- **工具描述核心准则**
  - 详细说明工具功能、适用场景（及禁用场景）、参数含义与影响、限制条件（如输入长度限制），单工具描述建议3-4句。
  - 优先完善功能、参数等基础描述，示例仅作为补充（推理模型需谨慎添加）。
- **函数设计要点**
  - **命名与参数**：函数名直观（如`parse_product_info`），参数说明包含格式（如`"city: string"`）和业务含义（如"目标城市拼音全称"），明确输出定义（如"返回JSON格式天气数据"）。
  - **系统提示**：通过提示指定调用条件（如"用户询问商品详情时触发`get_product_detail`"）。
  - **工程化设计**：
    - 使用枚举类型（如`StatusEnum`）避免无效参数，确保逻辑直观（最小惊讶原则）。
    - 确保仅凭文档描述，人类可正确调用函数（补充潜在疑问解答）。
  - **调用优化**：
    - 已知参数通过火山方舟代码能力隐式传递（如`submit_order`无需重复声明`user_id`）。
    - 合并固定流程函数（如`query_location`与`mark_location`整合为`query_and_mark_location`）。
  - **数量与性能**：控制函数数量≤20个，通过火山方舟调试工具迭代函数模式（Schema），复杂场景可使用微调能力提升准确率。
