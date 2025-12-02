# 兼容 OpenAI SDK

**最近更新时间：2025.09.13 17:37:14**
**首次发布时间：2024.09.24 20:15:17**

火山方舟模型 API 大部分兼容 OpenAI SDK。您通过少量代码更改，很方便地方舟的模型服务集成至已有的代码中。

## 前提条件

调用之前，您需要获取以下信息：

- `<ARK_API_KEY>`：您的方舟 API Key，可参考[创建 API Key](https://www.volcengine.com/docs/82379/1361424#f79da451)。
- `<Model>`：[获取 Model ID](https://www.volcengine.com/docs/82379/1099522#c95c138d)（或 [获取 Endpoint ID](https://www.volcengine.com/docs/82379/1099522#f948f953)）。
- `<Base Url>`：`https://ark.cn-beijing.volces.com/api/v3/`

> **说明**
>
> 社区第三方 SDK 不由火山引擎团队维护，本文仅供参考。

## OpenAI SDK

- Python版本：3.7及以上。
- OpenAI SDK：1.0版本及以上，安装命令：

```python
pip install --upgrade "openai>=1.0"
```

### 快速开始示例

```python
from openai import OpenAI
import os

client = OpenAI(
    base_url="<BASE_URL>",  # 替换为您需要调用的模型服务Base Url
    api_key=os.environ.get("ARK_API_KEY"), # 环境变量中配置您的API Key
)

completion = client.chat.completions.create(
    model="<Model>", # 替换为您需要使用的模型 ID 或对应的推理接入点ID
    messages = [
        {"role": "system", "content": "你是豆包，是由字节跳动开发的 AI 人工智能助手"},
        {"role": "user", "content": "常见的十字花科植物有哪些？"},
    ],
)
print(completion.choices[0].message.content)
```

### 设置额外字段

传入OpenAI SDK中不支持的字段，可以通过 **extra_body** 结构体传入，如开关模型是否深度思考的 **thinking** 字段。

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ.get("ARK_API_KEY"), # 从环境变量中获取方舟 API Key
    base_url="<BASE_URL>",  # 替换为您需要调用的模型服务 Base Url
)
completion = client.chat.completions.create(
    model = "doubao-seed-1-6-250615",  # 替换为您需要使用的模型 ID 或对应的推理接入点ID
    messages = [
        {"role": "user", "content": "常见的十字花科植物有哪些？"},
    ],
    extra_body={
         "thinking": {
             "type": "disabled" # 不使用深度思考能力
             # "type": "enabled" # 使用深度思考能力
         }
     }
)
print(completion.choices[0].message.content)
```

### 设置自定义header

可以用于传递额外信息，如配置 ID来串联日志，使能数据加密能力。

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ.get("ARK_API_KEY"), # 从环境变量中获取方舟 API Key
    base_url="<BASE_URL>",  # 替换为您需要调用的模型服务 Base Url
)

completion = client.chat.completions.create(
    model="<Model>",  # 替换为您需要使用的模型 ID 或对应的推理接入点ID
    messages = [
        {"role": "system", "content": "你是豆包，是由字节跳动开发的 AI 人工智能助手"},
        {"role": "user", "content": "常见的十字花科植物有哪些？"},
    ],
    # 自定义request id
    extra_headers={"X-Client-Request-Id": "202406251728190000B7EA7A9648AC08D9"}
)
print(completion.choices[0].message.content)
```

### 文本向量化 Embedding

> **注意**
>
> 由于 OpenAI API 不支持多模态 embedding 模型，**图像向量化模型** doubao-embedding-vision 系列仅支持 火山方舟 SDK，详情请参考 [图像向量化API](https://www.volcengine.com/docs/82379/1523520)。

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ.get("ARK_API_KEY"), # 从环境变量中获取方舟 API Key
    base_url="<BASE_URL>",  # 替换为您需要调用的模型服务 Base Url
)

print("----- embeddings request -----")
resp = client.embeddings.create(
    model="<Model>", # 请输出文本向量化模型的ID或对应的推理接入点ID
    input=["花椰菜又称菜花、花菜，是一种常见的蔬菜。"]
)
print(resp)
```

## LangChain OpenAI SDK

LangChain OpenAI SDK：您可以使用下面命令安装。

```python
pip install langchain-openai
```

### 示例代码

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
import os

llm = ChatOpenAI(
    openai_api_key=os.environ.get("ARK_API_KEY"), # 环境变量中配置您的API Key
    openai_api_base="<BASE_URL>", # 替换为您需要调用的模型服务Base Url
    model_name="<Model>" # 替换为您创建推理接入点 ID
)

template = """Question: {question}

Answer: Let's think step by step."""

prompt = PromptTemplate.from_template(template)

question = "What NFL team won the Super Bowl in the year Justin Beiber was born?"

llm_chain = prompt | llm

print(llm_chain.invoke(question))
```
