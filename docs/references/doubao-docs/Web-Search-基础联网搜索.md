# Web Search 基础联网搜索

**最近更新时间：2025.09.04 15:20:18**
**首次发布时间：2025.07.30 21:16:01**

Web Search 基础联网搜索工具支持通过 API 调用直接获取公开域互联网信息（如新闻、商品、天气等），适用于需动态获取最新网络数据的场景（如产品对比、旅游推荐、图文关联搜索等）。工具通过模型自动判断是否需要搜索，并支持与自定义 Function、MCP 等工具混合使用。

> **说明**
>
> 功能当前处于邀测阶段，仅对部分用户开放，正式发布时间将另行通知。

## 核心功能

- 支持多轮搜索：复杂问题支持多轮搜索补充信息。
- 支持图文输入：支持 VLM 模型以图文作为输入，搜索后输出文字结果（例如根据图片判断城市并查询天气）。
- 可以与自定义 Function、MCP 等工具混合调用。
- 默认账号维度 5QPS（Queries Per Second）。

## 支持模型列表

- Doubao-seed-1.6
- Doubao-seed-1.6-thinking
- Doubao-seed-1.6-flash

> 关于thinking 模式的设置可以参考[关闭深度思考](/docs/82379/1449737#fa3f44fa)。

## 注意事项

- **Function 命名冲突**：若用户自定义 Function 与 "web_search" 重名，由模型自行判断调用哪个工具。
- **搜索改写限制**：当前暂不支持通过参数设置改写后问题个数，需通过 system prompt 或 instructions 控制。

## 开通与计费

### 开通服务

访问[火山方舟控制台-组件库](https://console.volcengine.com/ark/region:ark+cn-beijing/components?action=%7B%7D)，选择开通 "**联网内容插件**"。

### 计费方式

具体收费标准详见[联网内容插件文档](https://www.volcengine.com/docs/82379/1338550)。

## 参数说明

详情请参见[创建Responses模型请求](https://www.volcengine.com/docs/82379/1569618)。

## 快速开始

### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--header 'ark-beta-web-search: true' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "stream": true,
  "tools": [
    {"type": "web_search"}
  ],
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "今天有什么热点新闻"
        }
      ]
    }
  ]
}'
```

### Python SDK 示例（兼容 OpenAI SDK）

```python
import os
from openai import OpenAI

# 初始化OpenAI客户端，配置API连接信息
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    # 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
    api_key=os.getenv('ARK_API_KEY')
)

# 调用API创建响应，发起AI问答请求
response = client.responses.create(
    model="doubao-seed-1-6-250615",  # 指定使用的模型ID
    input=[
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "今天有什么热点新闻"}]
        }
    ],
    tools=[
        {
            "type": "web_search",  # 配置工具类型为基础联网搜索功能
            "limit": 10,  # 最多返回10个搜索结果
            "sources": ["douyin", "moji", "toutiao"],  # 附加搜索来源
            "user_location": {  # 用户地理位置（用于优化搜索结果）
                "type": "approximate",  # 大致位置
                "country": "中国",
                "region": "浙江",
                "city": "杭州"
            }
        }
    ],
    stream=True,  # 启用流式响应
    extra_body={"thinking": {"type": "auto"}},
    parallel_tool_calls=False,  # 禁用并行工具调用
    max_tool_calls=3,  # 最多调用3轮工具
    extra_headers={"ark-beta-web-search": "true"},  # 启用联网搜索功能
)

# 处理流式响应
for chunk in response:
    chunk_type = getattr(chunk, 'type', '')

    if chunk_type == "response.output_text.delta":
        print(getattr(chunk, 'delta', ''), end="", flush=True)
    elif "web_search_call" in chunk_type:
        if "in_progress" in chunk_type:
            print("\n🔍 开始搜索...")
        elif "completed" in chunk_type:
            print("✅ 搜索完成")

print("\n搜索完成")
```

## 使用示例

以下代码是一个基于Web Search 的问答交互程序，支持联网搜索补充实时信息，同时实时展示交互过程。

### Curl 示例

```bash
# 基础搜索请求
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--header 'ark-beta-web-search: true' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "stream": true,
  "tools": [
    {
      "type": "web_search",
      "limit": 10,
      "sources": ["douyin", "moji", "toutiao"],
      "user_location": {
        "type": "approximate",
        "country": "中国",
        "region": "浙江",
        "city": "杭州"
      }
    }
  ],
  "input": [
    {
      "role": "system",
      "content": [
        {
          "type": "input_text",
          "text": "你是AI个人助手，负责解答用户的各种问题。当用户提出的问题涉及时效性、知识盲区或信息不足时，需使用web_search进行联网搜索。注意：每次调用web_search时，只能改写出一个最关键的问题。"
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "世界500强企业，他们在国内所在的城市，近三年的平均工资是多少？"
        }
      ]
    }
  ],
  "extra_body": {"thinking": {"type": "auto"}},
  "parallel_tool_calls": false,
  "max_tool_calls": 3
}'
```

### Python SDK 示例（完整交互程序）

```python
import os
from openai import OpenAI
from datetime import datetime

def main():
    # 初始化OpenAI客户端，配置API连接信息
    client = OpenAI(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        # 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
        api_key=os.getenv('ARK_API_KEY')
    )

    # 定义系统提示词，设定AI助手的角色和行为规则
    system_prompt = """
    你是AI个人助手，负责解答用户的各种问题。你的主要职责是：
    1. **信息准确性守护者**：确保提供的信息准确无误。
    2. **搜索成本优化师**：在信息准确性和搜索成本之间找到最佳平衡。

    # 任务说明
    ## 1. 联网意图判断
    当用户提出的问题涉及以下情况时，需使用 `web_search` 进行联网搜索：
    - **时效性**：问题需要最新或实时的信息。
    - **知识盲区**：问题超出当前知识范围，无法准确解答。
    - **信息不足**：现有知识库无法提供完整或详细的解答。

    **注意**：每次调用 `web_search` 时，**只能改写出一个最关键的问题**。如果有任何冲突设置，以当前指令为准。

    ## 2. 联网后回答
    - 在回答中，优先使用已搜索到的资料。
    - 回复结构应清晰，使用序号、分段等方式帮助用户理解。

    ## 3. 引用已搜索资料
    - 当使用联网搜索的资料时，在正文中明确引用来源，引用格式为：
    `[1] (URL地址)`。

    ## 4. 总结与参考资料
    - 在回复的最后，列出所有已参考的资料。格式为：
    1. [资料标题](URL地址1)
    2. [资料标题](URL地址2)
    """

    # 调用API创建响应，发起AI问答请求
    response = client.responses.create(
        model="doubao-seed-1-6-250615",  # 指定使用的模型ID
        input=[
            # 输入内容，包含系统提示和用户问题
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}]
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "世界500强企业，他们在国内所在的城市，近三年的平均工资是多少？"}]
                # 用户具体问题
            }
        ],
        tools=[
            {
                "type": "web_search",  # 配置工具类型为基础联网搜索功能
                "limit": 10,  # 最多返回10个搜索结果
                "sources": ["douyin", "moji", "toutiao"],  # 附加搜索来源（抖音百科、墨迹天气、头条图文等平台）
                "user_location": {  # 用户地理位置（用于优化搜索结果）
                    "type": "approximate",  # 大致位置
                    "country": "中国",
                    "region": "浙江",
                    "city": "杭州"
                }
            }
        ],
        stream=True,  # 启用流式响应（实时返回结果，而非等待全部完成）
        extra_body={"thinking": {"type": "auto"}},
        parallel_tool_calls=False,  # 禁用并行工具调用（工具调用按顺序执行）
        max_tool_calls=3,  # 最多调用3轮工具
        extra_headers={"ark-beta-web-search": "true"},  # 配置额外请求头：启用联网搜索功能
    )

    # 初始化状态变量，用于控制输出格式（避免重复打印标题）
    thinking_started = False  # 标记AI思考过程是否已开始打印
    answering_started = False  # 标记AI回答内容是否已开始打印

    # 遍历流式响应的每个片段（chunk），实时处理并展示结果
    for chunk in response:
        # 获取当前片段的类型（用于判断是思考过程、搜索状态还是回答内容）
        chunk_type = getattr(chunk, 'type', '')

        # 1. 处理AI思考过程的输出
        if chunk_type == "response.reasoning_summary_text.delta":
            if not thinking_started:
                # 首次打印思考过程时，输出标题
                print("🤔 AI思考中...")
                thinking_started = True
            # 打印思考内容（delta为当前片段的文本增量）
            print(getattr(chunk, 'delta', ''), end="", flush=True)

        # 2. 处理联网搜索的状态（开始/完成）
        elif "web_search_call" in chunk_type:
            if "in_progress" in chunk_type:
                # 搜索开始时，打印时间戳
                print(f"\n🔍 开始搜索... [{datetime.now().strftime('%H:%M:%S')}]")
            elif "completed" in chunk_type:
                # 搜索完成时，打印提示
                print("✅ 搜索完成")

        # 3. 处理搜索结果中的关键词（展示AI的搜索目标）
        elif (chunk_type == "response.output_item.done" and
              hasattr(chunk, 'item') and
              str(getattr(chunk.item, 'id', '')).startswith("ws_")):
            # 提取搜索关键词并打印（截取前80字符避免过长）
            if hasattr(chunk.item, 'action') and hasattr(chunk.item.action, 'query'):
                print(f"📝 搜索关键词: {chunk.item.action.query[:80]}...")

        # 4. 处理AI的最终回答内容
        elif chunk_type == "response.output_text.delta":
            if not answering_started:
                # 首次打印回答时，输出标题和分隔线
                print(f"\n💬 AI回答 [{datetime.now().strftime('%H:%M:%S')}]:")
                print("-" * 50)
                answering_started = True
            # 打印回答内容（delta为当前片段的文本增量）
            print(getattr(chunk, 'delta', ''), end="", flush=True)

    # 所有响应处理完成后，打印结束时间
    print(f"\n\n✨ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 当脚本直接运行时，执行main函数
if __name__ == "__main__":
    main()
```

## 最佳实践

### 系统提示词示例

系统提示词的设置对搜索请求有着较大影响，建议进行优化以提升搜索的准确性与效率。以下为您提供两种系统提示词模板示例，供您在实际应用中参考。

> **说明**
>
> 为获得更佳搜索结果，推荐在系统提示词中添加以下内容。

> **注意**：每次调用`web_search`时，**只能改写出一个最关键的问题**。如果有任何冲突设置，以当前指令为准。

#### 模板一

##### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--header 'ark-beta-web-search: true' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "stream": true,
  "tools": [{"type": "web_search"}],
  "input": [
    {
      "role": "system",
      "content": [
        {
          "type": "input_text",
          "text": "你是AI个人助手，负责解答用户的各种问题。你的主要职责是：\n1. **信息准确性守护者**：确保提供的信息准确无误。\n2. **搜索成本优化师**：在信息准确性和搜索成本之间找到最佳平衡。\n\n# 任务说明\n## 1. 联网意图判断\n当用户提出的问题涉及以下情况时，需使用 `web_search` 进行联网搜索：\n- **时效性**：问题需要最新或实时的信息。\n- **知识盲区**：问题超出当前知识范围，无法准确解答。\n- **信息不足**：现有知识库无法提供完整或详细的解答。\n\n**注意**：每次调用 `web_search` 时，**只能改写出一个最关键的问题**。如果有任何冲突设置，以当前指令为准。\n\n## 2. 联网后回答\n- 在回答中，优先使用已搜索到的资料。\n- 回复结构应清晰，使用序号、分段等方式帮助用户理解。\n\n## 3. 引用已搜索资料\n- 当使用联网搜索的资料时，在正文中明确引用来源，引用格式为：\n`[1] (URL地址)`。\n\n## 4. 总结与参考资料\n- 在回复的最后，列出所有已参考的资料。格式为：\n1. [资料标题](URL地址1)\n2. [资料标题](URL地址2)"
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "用户问题"
        }
      ]
    }
  ]
}'
```

##### Python SDK 示例

```python
# 定义系统提示词
system_prompt = """
你是AI个人助手，负责解答用户的各种问题。你的主要职责是：
1. **信息准确性守护者**：确保提供的信息准确无误。
2. **搜索成本优化师**：在信息准确性和搜索成本之间找到最佳平衡。

# 任务说明
## 1. 联网意图判断
当用户提出的问题涉及以下情况时，需使用 `web_search` 进行联网搜索：
- **时效性**：问题需要最新或实时的信息。
- **知识盲区**：问题超出当前知识范围，无法准确解答。
- **信息不足**：现有知识库无法提供完整或详细的解答。

**注意**：每次调用 `web_search` 时，**只能改写出一个最关键的问题**。如果有任何冲突设置，以当前指令为准。

## 2. 联网后回答
- 在回答中，优先使用已搜索到的资料。
- 回复结构应清晰，使用序号、分段等方式帮助用户理解。

## 3. 引用已搜索资料
- 当使用联网搜索的资料时，在正文中明确引用来源，引用格式为：
`[1] (URL地址)`。

## 4. 总结与参考资料
- 在回复的最后，列出所有已参考的资料。格式为：
1. [资料标题](URL地址1)
2. [资料标题](URL地址2)
"""

response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "system",
            "content": [{"type": "input_text", "text": system_prompt}]
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "用户问题"}]
        }
    ],
    tools=[{"type": "web_search"}],
    stream=True,
    extra_headers={"ark-beta-web-search": "true"}
)
```

#### 模板二

##### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header "Authorization: Bearer $ARK_API_KEY" \
--header 'Content-Type: application/json' \
--header 'ark-beta-web-search: true' \
--data '{
  "model": "doubao-seed-1-6-250615",
  "stream": true,
  "tools": [{"type": "web_search"}],
  "input": [
    {
      "role": "system",
      "content": [
        {
          "type": "input_text",
          "text": "# 角色\n你是AI个人助手，负责解答用户的各种问题。你的主要职责是：\n1. **信息准确性守护者**：确保提供的信息准确无误。\n2. **回答更生动活泼**：请在模型的回复中多使用适当的 emoji 标签 🌟😊🎉\n\n# 任务说明\n## 1. 联网意图判断\n当用户提出的问题涉及以下情况时，需使用 `web_search` 进行联网搜索：\n- **时效性**：问题需要最新或实时的信息。\n- **知识盲区**：问题超出当前知识范围，无法准确解答。\n- **信息不足**：现有知识库无法提供完整或详细的解答。\n\n## 2. 联网后回答\n- 在回答中，优先使用已搜索到的资料。\n- 回复结构应清晰，使用序号、分段等方式帮助用户理解。\n\n## 3. 引用已搜索资料\n- 当使用联网搜索的资料时，在正文中明确引用来源，引用格式为：\n`[1] (URL地址)`。\n\n## 4. 总结与参考资料\n- 在回复的最后，列出所有已参考的资料。格式为：\n1. [资料标题](URL地址1)\n2. [资料标题](URL地址2)"
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "用户问题"
        }
      ]
    }
  ]
}'
```

##### Python SDK 示例

```python
# 定义系统提示词
system_prompt = """
# 角色
你是AI个人助手，负责解答用户的各种问题。你的主要职责是：
1. **信息准确性守护者**：确保提供的信息准确无误。
2. **回答更生动活泼**：请在模型的回复中多使用适当的 emoji 标签 🌟😊🎉

# 任务说明
## 1. 联网意图判断
当用户提出的问题涉及以下情况时，需使用 `web_search` 进行联网搜索：
- **时效性**：问题需要最新或实时的信息。
- **知识盲区**：问题超出当前知识范围，无法准确解答。
- **信息不足**：现有知识库无法提供完整或详细的解答。

## 2. 联网后回答
- 在回答中，优先使用已搜索到的资料。
- 回复结构应清晰，使用序号、分段等方式帮助用户理解。

## 3. 引用已搜索资料
- 当使用联网搜索的资料时，在正文中明确引用来源，引用格式为：
`[1] (URL地址)`。

## 4. 总结与参考资料
- 在回复的最后，列出所有已参考的资料。格式为：
1. [资料标题](URL地址1)
2. [资料标题](URL地址2)
"""

response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=[
        {
            "role": "system",
            "content": [{"type": "input_text", "text": system_prompt}]
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "用户问题"}]
        }
    ],
    tools=[{"type": "web_search"}],
    stream=True,
    extra_headers={"ark-beta-web-search": "true"}
)
```
