# 对话(Chat) API

**最近更新时间：2025.09.05 17:49:02**
**首次发布时间：2025.03.25 17:34:30**

**POST** `https://ark.cn-beijing.volces.com/api/v3/chat/completions`

本文介绍文本生成模型和视觉理解模型调用 API 的输入输出参数，供您使用接口时查阅字段含义。

## 在线调试

### 鉴权说明

### 快速入口

**API Explorer**

您可以通过 API Explorer 在线发起调用，无需关注签名生成过程，快速获取调用结果。

[去调试](https://api.volcengine.com/api-explorer/?action=ChatCompletions&groupName=%E5%AF%B9%E8%AF%9D%28Chat%29%20API&serviceCode=ark&version=2024-01-01)

## 请求参数

### 请求体

#### model

- **类型**: string
- **必选**: 是
- **说明**: 您需要调用的模型的 ID （Model ID），[开通模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&OpenTokenDrawer=false)，并[查询 Model ID](https://www.volcengine.com/docs/82379/1330310)。

您也可通过 Endpoint ID 来调用模型，获得限流、计费类型（前付费/后付费）、运行状态查询、监控、安全等高级能力，可参考[获取 Endpoint ID](https://www.volcengine.com/docs/82379/1099522)。

#### messages

- **类型**: object[]
- **必选**: 是
- **说明**: 到目前为止的对话组成的消息列表。不同模型支持不同类型的消息，如文本、图片、视频等。

##### 消息类型

###### 系统消息 (object)

开发人员提供的指令，模型应遵循这些指令。如模型扮演的角色或者目标等。

**属性**

- `messages.role` (string, 必选): 发送消息的角色，此处应为`system`。
- `messages.content` (string / object[], 必选): 系统信息内容。

**属性**

- **纯文本消息内容** (string): 纯文本消息内容，大语言模型支持传入此类型。
- **多模态消息内容** (object[]): 支持文本、图像、视频等类型，视觉理解模型等多模态模型、部分大语言模型支持此字段。

**各模态消息部分**

**文本消息部分** (object)
多模态消息中，内容文本输入。[具备视觉理解能力模型](https://www.volcengine.com/docs/82379/1330310#%E8%A7%86%E8%A7%89%E7%90%86%E8%A7%A3%E8%83%BD%E5%8A%9B)、部分大语言模型支持此类型消息。

**属性**

- `messages.content.text` (string, 必选): 文本消息部分的内容。
- `messages.content.type` (string, 必选): 文本消息类型，此处应为 `text`。

**图像消息部分** (object)
多模态消息中，图像内容部分。[具备视觉理解能力模型](https://www.volcengine.com/docs/82379/1330310#%E8%A7%86%E8%A7%89%E7%90%86%E8%A7%A3%E8%83%BD%E5%8A%9B)支持此类型消息。

**属性**

- `messages.content.image_url` (object, 必选): 图片消息的内容部分。

**属性**

- `messages.content.image_url.url` (string, 必选): 支持传入图片链接或图片的Base64编码，具体使用请参见[使用说明](https://www.volcengine.com/docs/82379/1362931#%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E)。
- `messages.content.image_url.detail` (string, 默认值 auto): 支持手动设置图片的质量，取值范围high、low、auto。
  - **high**: 高细节模式，适用于需要理解图像细节信息的场景，如对图像的多个局部信息/特征提取、复杂/丰富细节的图像理解等场景，理解更全面。
  - **low**: 低细节模式，适用于简单的图像分类/识别、整体内容理解/描述等场景，理解更快速。
  - **auto**: 默认模式，不同模型选择的模式略有不同，具体请参见[理解图像的深度控制](https://www.volcengine.com/docs/82379/1362931#bf4d9224)。
- `messages.content.type` (string, 必选): 图像消息类型，此处应为 `image_url`。

**视频信息部分** (object)
视频理解模型请参见[视频理解模型](https://www.volcengine.com/docs/82379/1330310#%E8%A7%86%E8%A7%89%E7%90%86%E8%A7%A3%E8%83%BD%E5%8A%9B)。多模态消息中，视频内容部分。

**属性**

- `messages.content.type` (string, 必选): 视频消息类型，此处应为`video_url`。
- `messages.content.video_url` (object, 必选): 视频消息的内容部分。
- `messages.content.video_url.url` (string, 必选): 支持传入视频链接或视频的Base64编码。具体使用请参见[视频理解说明](https://www.volcengine.com/docs/82379/1362931#%E8%A7%86%E9%A2%91%E7%90%86%E8%A7%A3)。

**属性**

- `messages.content.video_url.fps` (float/null, 默认值 1): 取值范围：[0.2, 5]。每秒钟从视频中抽取指定数量的图像。取值越高，对于视频中画面变化理解越精细；取值越低，对于视频中画面变化感知减弱，但是使用的 token 花费少，速度也更快。详细说明见[用量说明](https://www.volcengine.com/docs/82379/1362931#%E7%94%A8%E9%87%8F%E8%AF%B4%E6%98%8E)。

###### 用户消息 (object)

用户发送的消息，包含提示或附加上下文信息。不同模型支持的字段类型不同，最多支持文本、图片、视频形式的消息。

**属性**

- `messages.role` (string, 必选): 发送消息的角色，此处应为`user`。
- `messages.content` (string / object[], 必选): 用户信息内容。

**内容类型**

- **纯文本消息内容** (string): 纯文本消息内容，大语言模型支持传入此类型。
- **多模态消息内容** (object[]): 支持文本、图像、视频等类型，视觉理解模型等多模态模型、部分大语言模型支持此字段。

**内容类型**

**文本消息部分** (object)
多模态消息中，内容文本输入。视觉理解模型、部分大语言模型支持此类型消息。

**属性**

- `messages.content.text` (string, 必选): 文本消息部分的内容。
- `messages.content.type` (string, 必选): 文本消息类型，此处应为 `text`。

**图像消息部分** (object)
多模态消息中，图像内容部分。视觉理解模型支持此类型消息。

**属性**

- `messages.content.type` (string, 必选): 图像消息类型，此处应为 `image_url`。
- `messages.content.image_url` (object, 必选): 图片消息的内容部分。

**属性**

- `messages.content.image_url.url` (string, 必选): 支持传入图片链接或图片的Base64编码，不同模型支持图片大小略有不同，具体请参见[使用说明](https://www.volcengine.com/docs/82379/1362931#%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E)。
- `messages.content.image_url.detail` (string/null, 默认值 low): 取值范围：high、low、auto。支持手动设置图片的质量。
  - **high**: 高细节模式，适用于需要理解图像细节信息的场景，如对图像的多个局部信息/特征提取、复杂/丰富细节的图像理解等场景，理解更全面。此时 min_pixels 取值3136、max_pixels 取值4014080。
  - **low**: 低细节模式，适用于简单的图像分类/识别、整体内容理解/描述等场景，理解更快速。此时 min_pixels 取值3136、max_pixels 取值1048576。
  - **auto**: 默认模式，不同模型选择的模式略有不同，具体请参见[理解图像的深度控制](https://www.volcengine.com/docs/82379/1362931#bf4d9224)。

- `messages.content.image_url.image_pixel_limit` (object/null, 默认值 null): 允许设置图片的像素大小限制，如果不在此范围，则会等比例放大或者缩小至该范围内。生效优先级：高于 detail 字段，即同时配置 detail 与 image_pixel_limit 字段时，生效 image_pixel_limit 字段配置。若 min_pixels / max_pixels 字段未设置，使用 detail 设置配置的值对应的 min_pixels / max_pixels 值。子字段取值逻辑：3136 ≤ min_pixels ≤ max_pixels ≤ 4014080
  - `messages.content.image_url.image_pixel_limit.max_pixels` (integer): 取值范围：(min_pixels, 4014080]。传入图片最大像素限制，大于此像素则等比例缩小至 max_pixels 字段取值以下。若未设置，则取值为 detail 设置配置的值对应的 max_pixels 值。
  - `messages.content.image_url.image_pixel_limit.min_pixels`: 取值范围：[3136, max_pixels)。传入图片最小像素限制，小于此像素则等比例放大至 min_pixels 字段取值以上。若未设置，则取值为 detail 设置配置的值对应的 min_pixels 值（3136）。

**视频信息部分** (object)
视频理解模型请参见[视频理解模型](https://www.volcengine.com/docs/82379/1330310#%E8%A7%86%E8%A7%89%E7%90%86%E8%A7%A3%E8%83%BD%E5%8A%9B)。多模态消息中，视频内容部分。

**属性**

- `messages.content.type` (string, 必选): 视频消息类型，此处应为`video_url`。
- `messages.content.video_url` (object, 必选): 视频消息的内容部分。

**属性**

- `messages.content.video_url.url` (string, 必选): 支持传入视频链接或视频的Base64编码。具体使用请参见[视频理解说明](https://www.volcengine.com/docs/82379/1362931#%E8%A7%86%E9%A2%91%E7%90%86%E8%A7%A3)。
- `messages.content.video_url.fps` (float/null, 默认值 1): 取值范围：[0.2, 5]。每秒钟从视频中抽取指定数量的图像。取值越高，对于视频中画面变化理解越精细；取值越低，对于视频中画面变化感知减弱，但是使用的 token 花费少，速度也更快。详细说明见[用量说明](https://www.volcengine.com/docs/82379/1362931#%E7%94%A8%E9%87%8F%E8%AF%B4%E6%98%8E)。

###### 模型消息 (object)

历史对话中，模型回复的消息。往往在多轮对话传入历史对话记录以及[Prefill Response](https://www.volcengine.com/docs/82379/1359497)时让模型按照预置的回复内容继续回复时使用。

**属性**

说明：`messages.content` 与 `messages.tool_calls` 字段二者至少填写其一。

- `messages.role` (string, 必选): 发送消息的角色，此处应为`assistant`。
- `messages.content` (string / array): 模型回复的消息。
- `messages.tool_calls` (object[]): 历史对话中，模型回复的工具调用信息。

**显示子字段**

- `messages.tool_calls.function` (object, 必选): 模型调用工具对应的函数信息。

**显示子字段**

- `messages.tool_calls.function.name` (string, 必选): 模型需要调用的函数名称。
- `messages.tool_calls.function.arguments` (string, 必选): 模型生成的用于调用函数的参数，JSON 格式。

**说明**
模型并不总是生成有效的 JSON，并且可能会虚构出一些您的函数参数规范中未定义的参数。在调用函数之前，请在您的代码中验证这些参数是否有效。

- `messages.tool_calls.id` (string, 必选): 调用的工具的 ID。
- `messages.tool_calls.type` (string, 必选): 工具类型，当前仅支持`function`。

###### 工具消息 (object)

历史对话中模型调用工具的消息。往往在多轮对话传入历史对话记录。

**属性**

- `messages.role` (string, 必选): 发送消息的角色，此处应为`tool`。
- `messages.content` (string / array, 必选): 工具返回的消息。
- `messages.tool_call_id` (string, 必选): 模型调用的工具的 ID。

#### thinking

- **类型**: object
- **默认值**: `{"type":"enabled"}`
- **说明**: 控制模型是否开启深度思考模式。默认开启深度思考模式，可以手动关闭。支持此字段的模型以及使用示例请参见[文档](https://www.volcengine.com/docs/82379/1449737#0002)。

**属性**

- `thinking.type` (string, 必选): 取值范围：enabled， disabled，auto。
  - **enabled**: 开启思考模式，模型一定先思考后回答。
  - **disabled**: 关闭思考模式，模型直接回答问题，不会进行思考。
  - **auto**: 自动思考模式，模型根据问题自主判断是否需要思考，简单题目直接回答。

#### stream

- **类型**: boolean / null
- **默认值**: false
- **说明**: 响应内容是否流式返回：
  - **false**: 模型生成完所有内容后一次性返回结果。
  - **true**: 按 SSE 协议逐块返回模型生成内容，并以一条 `data: [DONE]` 消息结束。当 stream 为 true 时，可设置 stream_options 字段以获取 token 用量统计信息。

#### stream_options

- **类型**: object / null
- **默认值**: null
- **说明**: 流式响应的选项。当 stream 为 true 时，可设置 stream_options 字段。

**属性**

- `stream_options.include_usage` (boolean / null, 默认值 false): 模型流式输出时，是否在输出结束前输出本次请求的 token 用量信息。
  - **true**: 在 `data: [DONE]` 消息之前会返回一个额外的 chunk。此 chunk 中， usage 字段中输出整个请求的 token 用量，choices 字段为空数组。
  - **false**: 输出结束前，没有一个 chunk 来返回 token 用量信息。
- `stream_options.chunk_include_usage` (boolean / null, 默认值 false): 模型流式输出时，输出的每个 chunk 中是否输出本次请求到此 chunk 输出时刻的累计 token 用量信息。
  - **true**: 在返回的 usage 字段中，输出本次请求到此 chunk 输出时刻的累计 token 用量。
  - **false**: 不在每个 chunk 都返回 token 用量信息。

#### max_tokens

- **类型**: integer / null
- **默认值**: 4096
- **取值范围**: 各个模型不同，详细见[模型列表](https://www.volcengine.com/docs/82379/1330310)。
- **说明**: 模型回答最大长度（单位 token）。

**说明**

- 模型回答不包含思维链内容。模型回答 = 模型输出 - 模型思维链（如有）
- 输出 token 的总长度还受模型的上下文长度限制。

#### max_completion_tokens

- **类型**: integer / null
- **说明**: 支持该字段的模型及使用说明见[文档](https://www.volcengine.com/docs/82379/1449737#0001)。取值范围：[0, 64k]。控制模型输出的最大长度（包括模型回答和模型思维链内容长度，单位 token）。配置了该参数后，可以让模型输出超长内容，max_tokens （默认值 4k）与思维链最大长度将失效，模型按需输出内容，直到达到 max_completion_tokens 配置的值。不可与 max_tokens 字段同时设置，会直接报错。

#### service_tier

- **类型**: string / null
- **默认值**: auto
- **说明**: 指定是否使用[TPM保障包](https://www.volcengine.com/docs/82379/1510762)。生效对象为购买了保障包推理接入点。取值范围
  - **auto**: 优先使用TPM保障包。如果有TPM保障包额度的推理接入点，本次请求将会使用 TPM 保障包用量，获得更高限流以及响应速度。否则不使用，使用默认的限流和普通的服务响应速度。
  - **default**: 本次请求，不使用 TPM 保障包，使用默认的限流和普通的服务响应速度，即使请求的是有TPM保障包额度的推理接入点。

#### stop

- **类型**: string / string[] / null
- **默认值**: null
- **说明**: 模型遇到 stop 字段所指定的字符串时将停止继续生成，这个词语本身不会输出。最多支持 4 个字符串。[深度思考能力模型](https://www.volcengine.com/docs/82379/1330310#%E8%A7%86%E8%A7%89%E7%90%86%E8%A7%A3%E8%83%BD%E5%8A%9B)不支持该字段。

**示例**: `["你好", "天气"]`

#### reasoning_effort

- **类型**: string / null
- **默认值**: medium
- **说明**: 暂无模型支持该字段。取值范围：low，medium，high。限制深度思考的工作量。减少深度思考工作量可使响应速度更快，并且深度思考的 token 用量更小。

#### response_format

- **类型**: object
- **默认值**: `{"type": "text"}`
- **说明**: 模型输出内容须遵循此处指定的格式。

**遵循格式**

**遵循文本格式** (object)
模型默认回复文本格式内容。

**属性**

- `response_format.type` (string, 必选): 此处应为 `text`。

**遵循JSON对象结构** (object)
模型回复内容以JSON对象结构来组织。支持该字段的模型请参见文档。

**属性**

- `response_format.type` (string, 必选): 此处应为`json_object`。

**遵循JSON Schema定义的结构** (object) **beta功能**
模型回复内容以JSON对象结构来组织，遵循 schema 字段定义的JSON结构。支持该字段的模型请参见文档。该能力尚在 beta 阶段，请谨慎在生产环境使用。

**属性**

- `response_format.type` (string, 必选): 此处应为`json_schema`。
- `response_format.json_schema` (object, 必选): JSON结构体的定义。

**属性**

- `response_format.json_schema.name` (string, 必选): 用户自定义的JSON结构的名称。
- `response_format.json_schema.description` (string / null): 回复用途描述，模型将根据此描述决定如何以该格式回复。
- `response_format.json_schema.schema` (object, 必选): 回复格式的 JSON 格式定义，以 JSON Schema 对象的形式描述。
- `response_format.json_schema.strict` (boolean / null, 默认值 false): 是否在生成输出时，启用严格遵循模式。
  - **true**: 模型将始终严格遵循schema字段中定义的格式。
  - **false**: 模型会尽可能遵循schema字段中定义的结构。

#### frequency_penalty

- **类型**: float / null
- **默认值**: 0
- **取值范围**: [-2.0, 2.0]
- **说明**: 频率惩罚系数。如果值为正，会根据新 token 在文本中的出现频率对其进行惩罚，从而降低模型逐字重复的可能性。

#### presence_penalty

- **类型**: float / null
- **默认值**: 0
- **取值范围**: [-2.0, 2.0]
- **说明**: 存在惩罚系数。如果值为正，会根据新 token 到目前为止是否出现在文本中对其进行惩罚，从而增加模型谈论新主题的可能性。

#### temperature

- **类型**: float / null
- **默认值**: 1
- **取值范围**: [0, 2]
- **说明**: 采样温度。控制了生成文本时对每个候选词的概率分布进行平滑的程度。当取值为 0 时模型仅考虑对数概率最大的一个 token。较高的值（如 0.8）会使输出更加随机，而较低的值（如 0.2）会使输出更加集中确定。通常建议仅调整 temperature 或 top_p 其中之一，不建议两者都修改。

#### top_p

- **类型**: float / null
- **默认值**: 0.7
- **取值范围**: [0, 1]
- **说明**: 核采样概率阈值。模型会考虑概率质量在 top_p 内的 token 结果。当取值为 0 时模型仅考虑对数概率最大的一个 token。0.1 意味着只考虑概率质量最高的前 10% 的 token，取值越大生成的随机性越高，取值越低生成的确定性越高。通常建议仅调整 temperature 或 top_p 其中之一，不建议两者都修改。

#### logprobs

- **类型**: boolean / null
- **默认值**: false
- **说明**: 带深度思考能力模型不支持该字段，深度思考能力模型参见[文档](https://www.volcengine.com/docs/82379/1330310#%E6%B7%B1%E5%BA%A6%E6%80%9D%E8%80%83%E8%83%BD%E5%8A%9B)。是否返回输出 tokens 的对数概率。
  - **false**: 不返回对数概率信息。
  - **true**: 返回消息内容中每个输出 token 的对数概率。

#### top_logprobs

- **类型**: integer / null
- **默认值**: 0
- **取值范围**: [0, 20]
- **说明**: 带深度思考能力模型不支持该字段，深度思考能力模型参见[文档](https://www.volcengine.com/docs/82379/1330310#%E6%B7%B1%E5%BA%A6%E6%80%9D%E8%80%83%E8%83%BD%E5%8A%9B)。指定每个输出 token 位置最有可能返回的 token 数量，每个 token 都有关联的对数概率。仅当 logprobs为true 时可以设置 top_logprobs 参数。

#### logit_bias

- **类型**: map / null
- **默认值**: null
- **说明**: 带深度思考能力模型不支持该字段，深度思考能力模型参见[文档](https://www.volcengine.com/docs/82379/1330310#%E6%B7%B1%E5%BA%A6%E6%80%9D%E8%80%83%E8%83%BD%E5%8A%9B)。调整指定 token 在模型输出内容中出现的概率，使模型生成的内容更加符合特定的偏好。logit_bias 字段接受一个 map 值，其中每个键为词表中的 token ID（使用 tokenization 接口获取），每个值为该 token 的偏差值，取值范围为 [-100, 100]。-1 会减少选择的可能性，1 会增加选择的可能性；-100 会完全禁止选择该 token，100 会导致仅可选择该 token。该参数的实际效果可能因模型而异。

**示例**: `{"1234": -100}`

#### tools

- **类型**: object[] / null
- **默认值**: null
- **说明**: 待调用工具的列表，模型返回信息中可包含。当您需要让模型返回待调用工具时，需要配置该结构体。支持该字段的模型请参见[文档](https://www.volcengine.com/docs/82379/1330310#%E5%B7%A5%E5%85%B7%E8%B0%83%E7%94%A8%E8%83%BD%E5%8A%9B)。

**属性**

- `tools.type` (string, 必选): 工具类型，此处应为 `function`。
- `tools.function` (object, 必选): 模型返回中可包含待调用的工具。

**属性**

- `tools.function.name` (string, 必选): 调用的函数的名称。
- `tools.function.description` (string): 调用的函数的描述，大模型会使用它来判断是否调用这个工具。
- `tools.function.parameters` (object): 函数请求参数，以 JSON Schema 格式描述。具体格式请参考 JSON Schema 文档，格式如下：

其中，所有字段名大小写敏感。parameters 须是合规的 JSON Schema 对象。建议用英文字段名，中文置于 description 字段中。

#### parallel_tool_calls

- **类型**: boolean
- **默认值**: true
- **说明**: 本次请求，模型返回是否允许包含多个待调用的工具。
  - **true**: 允许返回多个待调用的工具。
  - **false**: 允许返回的待调用的工具小于等于1，本取值当前仅 doubao-seed-1-6-*** 模型生效。

#### tool_choice

- **类型**: string / object
- **说明**: 仅 doubao-seed-1-6-*** 模型支持此字段。本次请求，模型返回信息中是否有待调用的工具。当没有指定工具时，none 是默认值。如果存在工具，则 auto 是默认值。

**可选类型**

**工具选择模式** (string)
控制模型返回是否包含待调用的工具。

- **none**: 模型返回信息中不可含有待调用的工具。
- **required**: 模型返回信息中必须含待调用的工具。选择此项时请确认存在适合的工具，以减少模型产生幻觉的情况。
- **auto**: 模型自行判断返回信息是否有待调用的工具。

**工具调用** (object)
指定待调用工具的范围。模型返回信息中，只允许包含以下模型信息。选择此项时请确认该工具适合用户需求，以减少模型产生幻觉的情况。

**属性**

- `tool_choice.name` (string): 待调用工具的名称。
- `tool_choice.type` (string): 调用的类型，此处应为 `function`。

## 响应参数

### 非流式调用返回

#### id

- **类型**: string
- **说明**: 本次请求的唯一标识。

#### model

- **类型**: string
- **说明**: 本次请求实际使用的模型名称和版本。

#### service_tier

- **类型**: string
- **说明**: 本次请求是否使用了TPM保障包。
  - **scale**: 本次请求使用TPM保障包额度。
  - **default**: 本次请求未使用TPM保障包额度。

#### created

- **类型**: integer
- **说明**: 本次请求创建时间的 Unix 时间戳（秒）。

#### object

- **类型**: string
- **说明**: 固定为 `chat.completion`。

#### choices

- **类型**: object[]
- **说明**: 本次请求的模型输出内容。

**属性**

- `choices.index` (integer): 当前元素在 choices 列表的索引。
- `choices.finish_reason` (string): 模型停止生成 token 的原因。取值范围：
  - **stop**: 模型输出自然结束，或因命中请求参数 stop 中指定的字段而被截断。
  - **length**: 模型输出因达到模型输出限制而被截断，有以下原因：
    - 触发max_tokens限制（回答内容的长度限制）。
    - 触发max_completion_tokens限制（思维链内容+回答内容的长度限制）。
    - 触发context_window限制（输入内容+思维链内容+回答内容的长度限制）。
  - **content_filter**: 模型输出被内容审核拦截。
  - **tool_calls**: 模型调用了工具。
- `choices.message` (object): 模型输出的内容。

**属性**

- `choices.message.role` (string): 内容输出的角色，此处固定为 `assistant`。
- `choices.message.content` (string): 模型生成的消息内容。
- `choices.message.reasoning_content` (string / null): 模型处理问题的思维链内容。仅深度推理模型支持返回此字段，深度推理模型请参见[支持模型](https://www.volcengine.com/docs/82379/1449737#5f0f3750)。
- `choices.message.tool_calls` (object[] / null): 模型生成的工具调用。

**属性**

- `choices.message.tool_calls.id` (string): 调用的工具的 ID。
- `choices.message.tool_calls.type` (string): 工具类型，当前仅支持`function`。
- `choices.message.tool_calls.function` (object): 模型调用的函数。

**属性**

- `choices.message.tool_calls.function.name` (string): 模型调用的函数的名称。
- `choices.message.tool_calls.function.arguments` (string): 模型生成的用于调用函数的参数，JSON 格式。模型并不总是生成有效的 JSON，并且可能会虚构出一些您的函数参数规范中未定义的参数。在调用函数之前，请在您的代码中验证这些参数是否有效。

#### usage

- **类型**: object
- **说明**: 本次请求的 token 用量。

**属性**

- `usage.total_tokens` (integer): 本次请求消耗的总 token 数量（输入 + 输出）。
- `usage.prompt_tokens` (integer): 输入给模型处理的内容 token 数量。
- `usage.prompt_tokens_details` (object): 输入给模型处理的内容 token 数量的细节。
  - `usage.prompt_tokens_details.cached_tokens` (integer): 缓存输入内容的 token 用量，此处应为 0。
- `usage.completion_tokens` (integer): 模型输出内容花费的 token。
- `usage.completion_tokens_details` (object): 模型输出内容花费的 token 的细节。
  - `usage.completion_tokens_details.reasoning_tokens` (integer): 输出思维链内容花费的 token 数。支持输出思维链的模型请参见[文档](https://www.volcengine.com/docs/82379/1449737#5f0f3750)。

### 流式调用返回

流式调用返回的字段与非流式调用基本相同，主要区别：

- `object` 字段固定为 `chat.completion.chunk`
- `choices.delta` 替代 `choices.message`，包含增量内容
- `usage` 字段默认为null，需设置 `stream_options.include_usage=true` 才返回

## 示例

### 默认示例

#### Curl 示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "doubao-1-5-pro-32k-250115",
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

#### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(
    api_key=os.getenv('ARK_API_KEY'),
)

completion = client.chat.completions.create(
    model="doubao-1-5-pro-32k-250115",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ],
)

print(completion.choices[0].message.content)
```

#### OpenAI Python SDK 示例

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

completion = client.chat.completions.create(
    model="doubao-1-5-pro-32k-250115",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)

print(completion.choices[0].message.content)
```

### 流式输出示例

#### Curl 示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "doubao-1-5-pro-32k-250115",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "Hello!"
    }
  ],
  "stream": true
}'
```

#### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(
    api_key=os.getenv('ARK_API_KEY'),
)

stream = client.chat.completions.create(
    model="doubao-1-5-pro-32k-250115",
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

### 图片理解示例

#### Curl 示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "model": "doubao-vision-pro-32k",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "这张图片里有什么？"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://example.com/image.jpg"
          }
        }
      ]
    }
  ]
}'
```

#### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(
    api_key=os.getenv('ARK_API_KEY'),
)

completion = client.chat.completions.create(
    model="doubao-vision-pro-32k",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "这张图片里有什么？"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://example.com/image.jpg"
                    }
                }
            ]
        }
    ],
)

print(completion.choices[0].message.content)
```
