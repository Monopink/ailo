# Base URL及鉴权

**最近更新时间：2025.09.08 21:07:58**
**首次发布时间：2024.07.10 15:12:25**

火山方舟API分为模型调用的API（数据面 API），及管理推理接入点等管控相关的管控面 API。他们支持的鉴权方式有所不同，下面介绍方舟API的鉴权方式。

## 概念解释

- **数据面 API**：是直接面向**业务数据传输、实时交互、用户请求处理**的接口，聚焦于 "实际业务数据的流转与处理"，是系统对外提供核心服务能力的载体。请求大模型服务的 Chat API、Responses API 均为数据面 API。

- **管控面 API**：面向**系统资源管理、配置控制、状态监控**的接口，聚焦于 "对数据面及系统资源的管理与调度"，是保障系统稳定运行的 "控制中枢"。方舟的管理API Key、管理基础模型等均数据管控面 API。

- **Base URL**：是构建完整 API 请求 URL 的 "基础模板"，包含**协议（如 http/https）、host（主机域名或 IP）、端口（可选）和基础路径（可选）**，是所有具体接口路径的 "公共前缀"。你可以根据Base URL 加接口/版本等参数拼接出完整接口 URL ，典型结构：`[协议]://[host]/[基础路径（可选）]`

## Base URL

方舟不同的接口使用的 Base URL 有所不同。

**数据面 API：**

- 模型调用：`https://ark.cn-beijing.volces.com/api/v3/`。
- 应用调用：`https://ark.cn-beijing.volces.com/api/v3/bots/`。

**管控面 API：**`https://ark.cn-beijing.volcengineapi.com/`。

## 数据面 API 鉴权

支持两种鉴权方式，API Key 鉴权（简单方便），与 Access Key 鉴权（传统云上资源权限管控，可以分资源组云产品等维度管理，面向企业精细化管理）。

### API Key 签名鉴权

#### 前提条件

- [获取 API Key](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey)。
  - 使用 Access Key 鉴权请参考[Access Key 签名鉴权](/docs/82379/1298459#21bff83b)。
- [开通模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&OpenTokenDrawer=false)。
- 在[模型列表](/docs/82379/1330310)获取所需 Model ID 。
  - 通过 Endpoint ID 调用模型服务请参考[获取 Endpoint ID（创建自定义推理接入点）](/docs/82379/1099522)。

#### 签名构造

API Key 签名鉴权方式要求在 HTTP 请求 header 中按如下方式添加`Authorization` header:

```bash
Authorization: Bearer <ARK_API_KEY>
```

#### API 调用示例

##### Curl 示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer <ARK_API_KEY>" \
-d '{
  "model": "<Model ID>",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "Hello!"
    }
  ]
}'
```

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    api_key=api_key,
)

response = client.chat.completions.create(
    model="<Model ID>",
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Hello!"
        }
    ]
)

print(response.choices[0].message.content)
```

##### OpenAI Python SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

response = client.chat.completions.create(
    model="<Model ID>",
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Hello!"
        }
    ]
)

print(response.choices[0].message.content)
```

### Access Key 签名鉴权

#### 前提条件

您已获取到Access Key。如需创建/查看Access Key，请参见[API访问密钥管理](https://www.volcengine.com/docs/6257/64983)。

> 由于主账号的Access Key拥有较大权限，建议您创建IAM用户并授予方舟等权限，然后使用IAM用户的Access Key来进行操作，具体请参见[使用IAM进行访问控制教程](/docs/82379/1263493)。

#### 方法：使用SDK（简单，推荐）

使用方舟提供的SDK，可直接使用 Access Key 进行鉴权，无需自行实现签名。具体请参见[使用Access Key鉴权](/docs/82379/1544136#fa44b913)。

> 通过Access Key 鉴权，只支持通过Endpoint ID调用，不支持通过Model ID 调用，即请求体中`model`字段需要配置为[Endpoint ID](https://www.volcengine.com/docs/82379/1099522#%E8%8E%B7%E5%8F%96-endpoint-id)。

##### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

# 使用Access Key进行鉴权
client = Ark(
    region="cn-beijing",
    ak=os.getenv('VOLC_ACCESSKEY'),
    sk=os.getenv('VOLC_SECRETKEY')
)

response = client.chat.completions.create(
    model="<Endpoint ID>",  # 注意：必须使用Endpoint ID，不能使用Model ID
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Hello!"
        }
    ]
)

print(response.choices[0].message.content)
```

#### 方法：自行实现签名（实现成本高，不推荐）

您可以使用下面方式来间接完成 Access Key 签名鉴权。

1. 获取临时 API Key：使用 Access Key 调用[GetApiKey - 获取临时API Key](/docs/82379/1262825)接口，获取指定资源（推理接入点/应用）的临时 API Key。
2. 使用临时 API Key，来鉴权模型/应用调用，方式同上，见[API Key 签名鉴权](/docs/82379/1298459#60db1ed6)。

##### 获取临时API Key示例

```bash
# 使用Access Key获取临时API Key
curl -X POST \
'https://ark.cn-beijing.volcengineapi.com/?Action=GetApiKey&Version=2024-01-01' \
-H 'Authorization: HMAC-SHA256 Credential=<Access Key>/20240710/cn-beijing/ark/request, SignedHeaders=host;x-content-sha256;x-date, Signature=<Signature>' \
-H 'Content-Type: application/json' \
-H 'Host: ark.cn-beijing.volcengineapi.com' \
-H 'X-Content-Sha256: <Content Hash>' \
-H 'X-Date: 20240710T042925Z' \
-d '{
  "ResourceType": "endpoint",
  "ResourceId": "<Endpoint ID>"
}'
```

然后使用返回的临时API Key进行模型调用：

```bash
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer <Temporary API Key>" \
-d '{
  "model": "<Endpoint ID>",
  "messages": [
    {
      "role": "user",
      "content": "Hello!"
    }
  ]
}'
```

## 管控面 API 鉴权

管控面的API，如管理API Key、管理推理接入点等接口。

### Access Key 签名鉴权

#### 前提条件

您已获取到Access Key。如需创建/查看Access Key，请参见[API访问密钥管理](https://www.volcengine.com/docs/6257/64983)。

> 由于主账号的Access Key拥有较大权限，建议您创建IAM用户并授予方舟等权限，然后使用IAM用户的Access Key来进行操作，具体请参见[使用IAM进行访问控制教程](/docs/82379/1263493)。

#### 方法：使用SDK（简单，推荐）

请参见[SDK 接入指南](https://api.volcengine.com/api-sdk/view?serviceCode=ark&version=2024-01-01&language=Java)。

##### Java SDK 示例

```java
import com.volcengine.ark.runtime.model.completion.chat.ChatCompletionRequest;
import com.volcengine.ark.runtime.model.completion.chat.ChatMessage;
import com.volcengine.ark.runtime.model.completion.chat.ChatMessageRole;
import com.volcengine.ark.runtime.service.ArkService;

import java.util.ArrayList;
import java.util.List;

public class ArkExample {
    public static void main(String[] args) {
        String ak = System.getenv("VOLC_ACCESSKEY");
        String sk = System.getenv("VOLC_SECRETKEY");
        String region = "cn-beijing";

        ArkService service = ArkService.builder()
                .ak(ak)
                .sk(sk)
                .region(region)
                .build();

        System.out.println("\n----- standard request -----");
        final List<ChatMessage> messages = new ArrayList<>();
        final ChatMessage systemMessage = ChatMessage.builder()
                .role(ChatMessageRole.SYSTEM)
                .content("You are a helpful assistant.")
                .build();
        final ChatMessage userMessage = ChatMessage.builder()
                .role(ChatMessageRole.USER)
                .content("Hello!")
                .build();
        messages.add(systemMessage);
        messages.add(userMessage);

        ChatCompletionRequest chatCompletionRequest = ChatCompletionRequest.builder()
                .model("<Endpoint ID>")
                .messages(messages)
                .build();

        service.createChatCompletion(chatCompletionRequest).getChoices().forEach(choice -> {
            System.out.println(choice.getMessage().getContent());
        });

        // 关闭服务
        service.shutdownExecutor();
    }
}
```

##### Python SDK 示例

```python
import os
from volcenginesdkark import ArkClient

# 使用Access Key进行管控面API调用
client = ArkClient(
    region="cn-beijing",
    ak=os.getenv('VOLC_ACCESSKEY'),
    sk=os.getenv('VOLC_SECRETKEY')
)

# 示例：列出推理接入点
try:
    response = client.list_endpoints()
    print("推理接入点列表:")
    for endpoint in response.get('Result', {}).get('Items', []):
        print(f"- ID: {endpoint.get('Id')}, Name: {endpoint.get('Name')}")
except Exception as e:
    print(f"调用失败: {e}")
```

#### 方法：自行实现签名（实现成本高，不推荐）

- 使用 Access Key 构造签名。具体方法请参见[签名方法](https://www.volcengine.com/docs/6369/67269)。

> 签名用到的方舟相关字段信息：
>
> - Service：`ark`
> - Region：`cn-beijing`

- 使用cURL发起请求，请求示例如下：

##### Curl 示例

```bash
curl -X POST \
'https://ark.cn-beijing.volcengineapi.com/?Action=ListEndpoints&Version=2024-01-01' \
-H 'Authorization: HMAC-SHA256 Credential=AKL**/20240710/cn-beijing/ark/request, SignedHeaders=host;x-content-sha256;x-date, Signature=a7a****' \
-H 'Content-Type: application/json' \
-H 'Host: ark.cn-beijing.volcengineapi.com' \
-H 'X-Content-Sha256: 44***' \
-H 'X-Date: 20240710T042925Z' \
-d '{}'
```

##### 签名构造步骤

1. **创建规范请求**：按照特定格式组织HTTP请求信息
2. **创建待签名字符串**：包含算法、时间戳、凭证范围和规范请求的哈希值
3. **计算签名**：使用HMAC-SHA256算法计算签名
4. **添加签名到请求**：将签名添加到Authorization头部

详细的签名构造过程请参考[火山引擎API签名方法](https://www.volcengine.com/docs/6369/67269)。

## 鉴权方式对比

| 特性 | API Key 鉴权 | Access Key 鉴权 |
|------|-------------|-----------------|
| **使用场景** | 数据面API（模型调用） | 数据面API + 管控面API |
| **复杂度** | 简单，直接使用Bearer Token | 复杂，需要签名计算 |
| **权限控制** | 基于API Key的简单权限 | 基于IAM的精细化权限控制 |
| **企业管理** | 适合个人和小团队 | 适合企业级精细化管理 |
| **模型调用** | 支持Model ID | 仅支持Endpoint ID |
| **推荐程度** | 推荐用于模型调用 | 推荐用于企业级管理 |

## 最佳实践

1. **开发测试阶段**：使用API Key鉴权，简单快速
2. **生产环境**：根据需求选择：
   - 简单应用：API Key鉴权
   - 企业级应用：Access Key鉴权，配合IAM进行权限管理
3. **安全建议**：
   - 不要在代码中硬编码密钥
   - 使用环境变量或密钥管理服务
   - 定期轮换API Key和Access Key
   - 为不同环境使用不同的密钥

## 常见问题

### Q: API Key和Access Key有什么区别？

A: API Key是方舟专用的认证方式，使用简单但功能相对基础；Access Key是火山引擎通用的认证方式，支持更精细的权限控制和企业级管理。

### Q: 为什么Access Key鉴权只能使用Endpoint ID？

A: Access Key鉴权基于资源级权限控制，需要明确指定具体的推理接入点资源，而Model ID是逻辑概念，不对应具体的资源实例。

### Q: 如何选择合适的鉴权方式？

A:

- 个人开发者或简单应用：推荐API Key鉴权
- 企业用户需要精细权限控制：推荐Access Key鉴权
- 需要调用管控面API：必须使用Access Key鉴权
