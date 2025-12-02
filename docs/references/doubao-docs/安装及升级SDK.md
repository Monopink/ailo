# 安装及升级 SDK

**最近更新时间：2025.07.30 15:44:53**
**首次发布时间：2025.04.21 20:35:02**

方舟提供了 Python 、 Go 和 Java 的 SDK ，方便您使用对应编程语言快速调用/集成方舟的模型服务。

## 安装及升级

### Python SDK

#### 前提条件

您本地已经安装了Python ，且版本不低于 3.7。

> 您可以在终端中输入命令确认Python是否安装以及安装的版本，如未安装，请参考[Python安装教程](https://wiki.python.org/moin/BeginnersGuide/Download)安装，注意选择版本3.7及以上版本。

```bash
python -V
```

#### 安装 Python SDK

在终端中执行以下命令安装Python SDK。

```bash
pip install 'volcengine-python-sdk[ark]'
```

**说明**

- 如果您本地安装错误，可以尝试使用下面方法
  - [Windows系统安装SDK失败，ERROR: Failed building wheel for volcengine-python-sdk](https://www.volcengine.com/docs/82379/1359411#b74e8ad6)
  - 尝试使用下面命令 `pip install volcengine-python-sdk[ark]`
- 如果您需要源码安装可以下载相应版本的 SDK 包，解压后进入目录，执行如下命令：`python setup.py install --user`

#### 升级 Python SDK

如您本地已经安装了 Python SDK，当需要使用方舟提供的最新能力，需要升级SDK至最新版本，可以在命令中增加`"-U"`参数。

```bash
pip install -U 'volcengine-python-sdk[ark]'
```

#### Python SDK 使用示例

```python
import os
from volcenginesdkarkruntime import Ark

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = Ark(
    api_key=api_key,
)

# 非流式
completion = client.chat.completions.create(
    model="doubao-seed-1-6-250615",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ],
)
print(completion.choices[0].message.content)

# 流式
stream = client.chat.completions.create(
    model="doubao-seed-1-6-250615",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ],
    stream=True,
)
for chunk in stream:
    if not chunk.choices:
        continue
    print(chunk.choices[0].delta.content, end="")
```

### Go SDK

#### 前提条件

检查并安装 Go 版本，Go 版本需要 1.18 或以上。

```bash
go version
```

如果未安装 Go 或者版本不满足要求，您可以访问[Go 语言官方网站](https://golang.google.cn/dl/)下载并安装适合您操作系统的 Go 版本。请确保选择 1.18 或以上版本。

#### 安装 Go SDK

1. 火山方舟 Go SDK 使用 go mod 进行管理，如果本地工程没有初始化 go mod，您可以运行以下命令初始化 go mod。`<your-project-name>`替换为您的项目名称。

```bash
# 如在文件夹 ark-demo 下打开终端窗口，运行命令
go mod init ark-demo
go mod init <your-project-name>
```

2. 在本地初始化 go mod 后，运行以下命令安装最新版 SDK。

```bash
go get -u github.com/volcengine/volcengine-go-sdk
```

**说明**

为了保证系统一致性或者稳定性，你需要安装特定版本的SDK，可以通过下面，安装指定的版本。`go get -u github.com/volcengine/volcengine-go-sdk@<VERSION>`

- 其中`<VERSION>`替换为您要安装的SDK版本号，可以从[这里](https://github.com/volcengine/volcengine-go-sdk/releases)查询。

3. 在代码中引入 SDK 使用。

```go
import "github.com/volcengine/volcengine-go-sdk/service/arkruntime"
```

4. 更新依赖后，使用以下命令清理不需要的依赖并整理`go.mod`和`go.sum`文件。

```bash
go mod tidy
```

#### 升级 Go SDK

步骤与安装 Go SDK相同，可参考[安装 Go SDK](/docs/82379/1541595#ae8b42ab)，第1，2步升级至最新/指定版本SDK。

- 升级至最新版本

```bash
go get -u github.com/volcengine/volcengine-go-sdk
```

- 升级至指定版本

```bash
go get -u github.com/volcengine/volcengine-go-sdk@<VERSION>
```

#### Go SDK 使用示例

```go
package main

import (
    "context"
    "fmt"
    "os"

    "github.com/volcengine/volcengine-go-sdk/service/arkruntime"
    "github.com/volcengine/volcengine-go-sdk/service/arkruntime/model"
    "github.com/volcengine/volcengine-go-sdk/volcengine"
)

func main() {
    client := arkruntime.NewClientWithApiKey(
        os.Getenv("ARK_API_KEY"),
    )

    ctx := context.Background()

    req := model.ChatCompletionRequest{
        Model: "doubao-seed-1-6-250615",
        Messages: []*model.ChatCompletionMessage{
            {
                Role: model.ChatMessageRoleSystem,
                Content: &model.ChatCompletionMessageContent{
                    StringValue: volcengine.String("You are a helpful assistant."),
                },
            },
            {
                Role: model.ChatMessageRoleUser,
                Content: &model.ChatCompletionMessageContent{
                    StringValue: volcengine.String("Hello!"),
                },
            },
        },
    }

    resp, err := client.CreateChatCompletion(ctx, req)
    if err != nil {
        fmt.Printf("standard chat completion error: %v\n", err)
        return
    }
    fmt.Println(*resp.Choices[0].Message.Content.StringValue)
}
```

### Java SDK

#### 适用范围

本 SDK 仅适用于 Java 服务端开发，暂不支持 Android 平台。若需在 Android 平台使用相关功能，需由客户自行开发适配方案。

#### 前提条件

- 检查并安装 Java 版本，Java 版本需要 1.8 或以上。

```bash
java -version
```

如果未安装 Java 或者版本不满足要求，您可以访问[Oracle 官方网站](https://www.java.com/en/download/help/index_installing.html)下载并安装适合您操作系统的 Java 版本。请确保选择 1.8 或以上版本。

#### 安装 Java SDK

> 了解 SDK 最新版本，可访问源码地址：[https://github.com/volcengine/volcengine-java-sdk](https://github.com/volcengine/volcengine-java-sdk)

火山方舟 Java SDK 支持通过 Maven 安装、通过 Gradle 安装两种方式。

##### 通过 Maven 安装

在`pom.xml`文件中进行如下配置，完整配置可参考[Maven Central](https://central.sonatype.com/artifact/com.volcengine/volcengine-java-sdk-ark-runtime)：

```xml
<dependency>
    <groupId>com.volcengine</groupId>
    <artifactId>volcengine-java-sdk-ark-runtime</artifactId>
    <version>LATEST</version>
</dependency>
```

**说明**

替换'LATEST' 为 方舟 Java SDK 最新版本号，[点此](https://central.sonatype.com/artifact/com.volcengine/volcengine-java-sdk-ark-runtime)可查询。如果需要安装指定版本SDK，也可以替换为具体版本号。

##### 通过 Gradle 安装

在`build.gradle`文件中进行如下配置，在`dependencies`中添加依赖。

```gradle
implementation 'com.volcengine:volcengine-java-sdk-ark-runtime:LATEST'
```

**说明**

替换'LATEST' 为 方舟 Java SDK 最新版本号，[点此](https://mvnrepository.com/artifact/com.volcengine/volcengine-java-sdk-ark-runtime)可查询。如果需要安装指定版本SDK，也可以替换为具体版本号。

#### 升级 Java SDK

同安装 Java SDK，指定需要升级的版本号即可。

#### Java SDK 使用示例

```java
import com.volcengine.ark.runtime.model.completion.chat.ChatCompletionRequest;
import com.volcengine.ark.runtime.model.completion.chat.ChatMessage;
import com.volcengine.ark.runtime.model.completion.chat.ChatMessageRole;
import com.volcengine.ark.runtime.service.ArkService;

import java.util.ArrayList;
import java.util.List;

public class ArkExample {
    public static void main(String[] args) {
        String apiKey = System.getenv("ARK_API_KEY");

        ArkService service = ArkService.builder()
                .apiKey(apiKey)
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
                .model("doubao-seed-1-6-250615")
                .messages(messages)
                .build();

        service.createChatCompletion(chatCompletionRequest).getChoices().forEach(choice -> {
            System.out.println(choice.getMessage().getContent());
        });

        // 流式请求示例
        System.out.println("\n----- streaming request -----");
        ChatCompletionRequest streamRequest = ChatCompletionRequest.builder()
                .model("doubao-seed-1-6-250615")
                .messages(messages)
                .stream(true)
                .build();

        service.streamChatCompletion(streamRequest)
                .doOnError(Throwable::printStackTrace)
                .blockingForEach(choice -> {
                    if (choice.getChoices().size() > 0) {
                        System.out.print(choice.getChoices().get(0).getDelta().getContent());
                    }
                });

        // 关闭服务
        service.shutdownExecutor();
    }
}
```

## 第三方SDK

火山方舟模型调用 API 与 OpenAI API 协议兼容，您可以使用兼容 OpenAI API 协议的多语言社区 SDK 调用火山方舟大模型或应用。您可以很方便地迁移模型服务至方舟平台以及 Doubao 大模型。具体使用方法请参考[兼容OpenAI API](/docs/82379/1330626)。

### OpenAI Python SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 非流式
completion = client.chat.completions.create(
    model="doubao-seed-1-6-250615",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)
print(completion.choices[0].message.content)

# 流式
stream = client.chat.completions.create(
    model="doubao-seed-1-6-250615",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="")
```

### OpenAI Node.js SDK 示例

```javascript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'https://ark.cn-beijing.volces.com/api/v3',
  apiKey: process.env.ARK_API_KEY,
});

async function main() {
  // 非流式
  const completion = await client.chat.completions.create({
    model: 'doubao-seed-1-6-250615',
    messages: [
      { role: 'system', content: 'You are a helpful assistant.' },
      { role: 'user', content: 'Hello!' },
    ],
  });

  console.log(completion.choices[0].message.content);

  // 流式
  const stream = await client.chat.completions.create({
    model: 'doubao-seed-1-6-250615',
    messages: [
      { role: 'system', content: 'You are a helpful assistant.' },
      { role: 'user', content: 'Hello!' },
    ],
    stream: true,
  });

  for await (const chunk of stream) {
    process.stdout.write(chunk.choices[0]?.delta?.content || '');
  }
}

main();
```

## SDK版本对比

| 特性 | Python SDK | Go SDK | Java SDK | OpenAI SDK |
|------|------------|--------|----------|------------|
| **安装方式** | pip | go get | Maven/Gradle | pip/npm |
| **最低版本要求** | Python 3.7+ | Go 1.18+ | Java 1.8+ | 各语言要求 |
| **流式支持** | ✅ | ✅ | ✅ | ✅ |
| **异步支持** | ✅ | ✅ | ✅ | ✅ |
| **函数调用** | ✅ | ✅ | ✅ | ✅ |
| **多模态** | ✅ | ✅ | ✅ | ✅ |
| **上下文缓存** | ✅ | ✅ | ✅ | ✅ |
| **官方支持** | ✅ | ✅ | ✅ | 社区兼容 |

## 常见问题

### Q: 如何选择合适的SDK？

A:

- **Python SDK**：推荐用于AI/ML项目，数据科学，快速原型开发
- **Go SDK**：推荐用于高性能服务，微服务架构，云原生应用
- **Java SDK**：推荐用于企业级应用，Spring生态系统集成
- **OpenAI SDK**：推荐用于现有OpenAI项目的快速迁移

### Q: SDK版本如何选择？

A:

- **生产环境**：建议使用具体版本号，避免使用LATEST
- **开发环境**：可以使用LATEST获取最新功能
- **版本升级**：建议先在测试环境验证新版本兼容性

### Q: 遇到安装问题怎么办？

A:

- **Python**：尝试使用虚拟环境，检查Python版本
- **Go**：确保Go版本>=1.18，检查GOPROXY设置
- **Java**：确保Java版本>=1.8，检查Maven/Gradle配置
- **网络问题**：可以使用国内镜像源

## 相关文档

[SDK 常见使用示例](/docs/82379/1544136)：包含SDK的常见用法。
