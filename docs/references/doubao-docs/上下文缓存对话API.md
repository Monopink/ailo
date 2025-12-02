# 上下文缓存对话 API

**最近更新时间：2025.07.02 14:29:41**
**首次发布时间：2025.04.10 20:43:38**

**POST** `https://ark.cn-beijing.volces.com/api/v3/context/chat/completions`

上下文缓存（Context API）是方舟提供的一个高效的缓存机制。它通过缓存上下文数据，减少重复加载或处理，提高响应速度和一致性。本文介绍上下文缓存 API 的输入输出参数，供您使用接口时查阅字段含义。

## 快速入口

### 鉴权说明

- [计费说明](https://www.volcengine.com/docs/82379/1099320#%E4%B8%8A%E4%B8%8B%E6%96%87%E7%BC%93%E5%AD%98%E8%AE%A1%E8%B4%B9)
- [API Key](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey?apikey=%7B%7D)
- [支持模型](https://www.volcengine.com/docs/82379/1330310#e6772192)
- [调用教程](https://www.volcengine.com/docs/82379/1396491)
- [开通模型](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&OpenTokenDrawer=false)

## 说明

大部分字段与[对话(Chat)-文本 API](https://www.volcengine.com/docs/82379/1494384)一致，除了下面参数：

- **model**: 暂时不支持直接通过Model ID 调用模型。
- **messages**: 不支持最后一个元素的role设置为assistant。
  - 如使用session 缓存（mode设置为session），传入最新一轮对话的信息，无需传入历史信息。
- **tools**: 不支持 tools 字段。
- **context_id**: 增加的字段，指定本次请求使用上下文缓存。
- **thinking**: 不支持 thinking 字段。
- **response_format**: 不支持结构化输出参数。

## 请求参数

### 请求体

#### model

- **类型**: string
- **必选**: 是
- **说明**: 您需要调用的模型的 ID （Model ID），[开通模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&OpenTokenDrawer=false)，并[查询 Model ID](https://www.volcengine.com/docs/82379/1330310)。您也可通过 Endpoint ID 来调用模型，获得限流、计费类型（前付费/后付费）、运行状态查询、监控、安全等高级能力，可参考[获取 Endpoint ID](https://www.volcengine.com/docs/82379/1099522)。

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
- `messages.content.type` (string, 必选): 文本消息类型，此次应为 `text`。

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
- `messages.content.type` (string, 必选): 文本消息类型，此次应为 `text`。

###### 模型消息 (object)

历史对话中，模型回复的消息。往往在多轮对话传入历史对话记录以及[Prefill Response](https://www.volcengine.com/docs/82379/1359497)时让模型按照预置的回复内容继续回复时使用。

**属性**

**说明**: `messages.content` 与 `messages.tool_calls` 字段二者至少填写其一。

- `messages.role` (string, 必选): 发送消息的角色，此处应为`assistant`。
- `messages.content` (string / array): 模型回复的消息。
- `messages.tool_calls` (object[]): 历史对话中，模型回复的工具调用信息。

**显示子字段**

- `messages.tool_calls.function` (object, 必选): 模型调用工具对应的函数信息。

**显示子字段**

- `messages.tool_calls.function.name` (string, 必选): 模型需要调用的函数名称。
- `messages.tool_calls.function.arguments` (string, 必选): 模型生成的用于调用函数的参数，JSON 格式。

**说明**: 模型并不总是生成有效的 JSON，并且可能会虚构出一些您的函数参数规范中未定义的参数。在调用函数之前，请在您的代码中验证这些参数是否有效。

- `messages.tool_calls.id` (string, 必选): 调用的工具的 ID。
- `messages.tool_calls.type` (string, 必选): 工具类型，当前仅支持`function`。

#### context_id

- **类型**: string
- **必选**: 是
- **说明**: 指定本次请求使用上下文缓存的 ID。在使用[接口](https://www.volcengine.com/docs/82379/1529329)创建缓存时，从返回信息中获得。

#### stream

- **类型**: boolean / null
- **默认值**: false
- **说明**: 响应内容是否流式返回：
  - **false**: 模型生成完所有内容后一次性返回结果。
  - **true**: 按 SSE 协议逐块返回模型生成内容，并以一条 `data: [DONE]` 消息结束。

#### stream_options

- **类型**: object / null
- **默认值**: null
- **说明**: 流式响应的选项。当 stream 为 true 时可设置 stream_options 字段。

**属性**

- `stream_options.include_usage` (boolean / null, 默认值 false): 是否包含本次请求的 token 用量统计信息。
  - **false**: 不返回 token 用量信息。
  - **true**: 在 `data: [DONE]` 消息之前会返回一个额外的块，此块上的 usage 字段代表整个请求的 token 用量，choices 字段为空数组。所有其他块也将包含 usage 字段，但值为 null。

#### max_tokens

- **类型**: integer / null
- **默认值**: 4096
- **说明**: 模型回复最大长度（单位 token），取值范围各个模型不同，详细见[模型列表](https://www.volcengine.com/docs/82379/1330310)。输入 token 和输出 token 的总长度还受模型的上下文长度限制。

#### service_tier

- **类型**: string / null
- **默认值**: auto
- **说明**: 指定是否使用[TPM保障包](https://www.volcengine.com/docs/82379/1510762)。生效对象为购买了保障包推理接入点。取值范围：
  - **default**: 本次请求，不使用 TPM 保障包，使用默认的限流和普通的服务响应速度，即使请求的是有TPM保障包额度的推理接入点。

**注意**: 缓存不支持TPM保障包，故不支持auto。

#### stop

- **类型**: string / string[] / null
- **默认值**: null
- **说明**: 模型遇到 stop 字段所指定的字符串时将停止继续生成，这个词语本身不会输出。最多支持 4 个字符串。[深度思考能力模型](https://www.volcengine.com/docs/82379/1330310#%E8%A7%86%E8%A7%89%E7%90%86%E8%A7%A3%E8%83%BD%E5%8A%9B)不支持该字段。

**示例**: `["你好", "天气"]`

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
- **说明**: 是否返回输出 tokens 的对数概率。
  - **false**: 不返回对数概率信息。
  - **true**: 返回消息内容中每个输出 token 的对数概率。

#### top_logprobs

- **类型**: integer / null
- **默认值**: 0
- **取值范围**: [0, 20]
- **说明**: 指定每个输出 token 位置最有可能返回的 token 数量，每个 token 都有关联的对数概率。仅当 logprobs为true 时可以设置 top_logprobs 参数。

#### logit_bias

- **类型**: map / null
- **默认值**: null
- **说明**: 调整指定 token 在模型输出内容中出现的概率，使模型生成的内容更加符合特定的偏好。logit_bias 字段接受一个 map 值，其中每个键为词表中的 token ID（使用 tokenization 接口获取），每个值为该 token 的偏差值，取值范围为 [-100, 100]。-1 会减少选择的可能性，1 会增加选择的可能性；-100 会完全禁止选择该 token，100 会导致仅可选择该 token。该参数的实际效果可能因模型而异。

**示例**: `{"1234": -100}`

## 响应参数

### 非流式调用返回

#### id

- **类型**: string
- **说明**: 本次请求的唯一标识。

#### model

- **类型**: string
- **说明**: 本次请求实际使用的模型名称和版本。doubao 1.5 代模型的模型名称格式为 doubao-1-5-**。如调用部署doubao-1.5-pro-32k 250115模型的推理接入点，返回model字段信息doubao-1-5-pro-32k-250115。

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
    - 触发max_token限制（回答内容的长度限制）。
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

- `choices.logprobs` (object / null): 当前内容的对数概率信息。

**属性**

- `choices.logprobs.content` (object[] / null): message列表中每个 content 元素中的 token 对数概率信息。

**属性**

- `choices.logprobs.content.token` (string): 当前 token。
- `choices.logprobs.content.bytes` (integer[] / null): 当前 token 的 UTF-8 值，格式为整数列表。当一个字符由多个 token 组成（表情符号或特殊字符等）时可以用于字符的编码和解码。如果 token 没有 UTF-8 值则为空。
- `choices.logprobs.content.logprob` (float): 当前 token 的对数概率。
- `choices.logprobs.content.top_logprobs` (object[]): 在当前 token 位置最有可能的标记及其对数概率的列表。在一些情况下，返回的数量可能比请求参数 top_logprobs 指定的数量要少。

**属性**

- `choices.logprobs.content.top_logprobs.token` (string): 当前 token。
- `choices.logprobs.content.top_logprobs.bytes` (integer[] / null): 当前 token 的 UTF-8 值，格式为整数列表。当一个字符由多个 token 组成（表情符号或特殊字符等）时可以用于字符的编码和解码。如果 token 没有 UTF-8 值则为空。
- `choices.logprobs.content.top_logprobs.logprob` (float): 当前 token 的对数概率。

- `choices.moderation_hit_type` (string/ null): 模型输出文字含有敏感信息时，会返回模型输出文字命中的风险分类标签。

**返回值及含义**：

- **severe_violation**: 模型输出文字涉及严重违规。
- **violence**: 模型输出文字涉及激进行为。

**注意**: 当前只有[视觉理解模型](https://www.volcengine.com/docs/82379/1362931#%E6%94%AF%E6%8C%81%E6%A8%A1%E5%9E%8B)支持返回该字段，且只有在方舟控制台[接入点配置页面](https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint/create?customModelId=)或者[CreateEndpoint](https://www.volcengine.com/docs/82379/1262823)接口中，将内容护栏方案（ModerationStrategy）设置为基础方案（Basic）时，才会返回风险分类标签。

#### usage

- **类型**: object
- **说明**: 本次请求的 token 用量。

**属性**

- `usage.prompt_tokens` (integer): 输入给模型的内容的 token 用量。
- `usage.completion_tokens` (integer): 模型输出内容的 token 用量。
- `usage.total_tokens` (integer): 本次请求消耗的总 token 数量（输入 + 输出）。
- `usage.prompt_tokens_details` (object): 命中上下文缓存的tokens细节。
  - `usage.prompt_tokens_details.cached_tokens` (integer): 提示词命中缓存的 token 用量。
- `usage.completion_tokens_details` (object): 本次请求，模型输出内容的 token 用量的细节。
  - `usage.completion_tokens_details.reasoning_tokens` (integer): 输出思维链内容花费的 token 数 。支持输出思维链的模型请参见[文档](https://www.volcengine.com/docs/82379/1449737#5f0f3750)。

### 流式调用返回

#### id

- **类型**: string
- **说明**: 本次请求的唯一标识。

#### model

- **类型**: string
- **说明**: 本次请求实际使用的模型名称和版本。doubao 1.5 代模型的模型名称格式为 doubao-1-5-**。如调用部署doubao-1.5-pro-32k 250115模型的推理接入点，返回model字段信息doubao-1-5-pro-32k-250115。

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
- **说明**: 固定为 `chat.completion.chunk`。

#### choices

- **类型**: object[]
- **说明**: 本次请求的模型输出内容。

**属性**

- `choices.index` (integer): 当前元素在 choices 列表的索引。
- `choices.finish_reason` (string): 模型停止生成 token 的原因。取值范围：
  - **stop**: 模型输出自然结束，或因命中请求参数 stop 中指定的字段而被截断。
  - **length**: 模型输出因达到模型输出限制而被截断，有以下原因：
    - 触发max_token限制（回答内容的长度限制）。
    - 触发max_completion_tokens限制（思维链内容+回答内容的长度限制）。
    - 触发context_window限制（输入内容+思维链内容+回答内容的长度限制）。
  - **content_filter**: 模型输出被内容审核拦截。
  - **tool_calls**: 模型调用了工具。
- `choices.delta` (object): 模型输出的增量内容。
- `choices.logprobs` (object / null): 当前内容的对数概率信息。
- `choices.moderation_hit_type` (string/ null): 模型输出文字含有敏感信息时，会返回模型输出文字命中的风险分类标签。

**返回值及含义**：

- **severe_violation**: 模型输出文字涉及严重违规。
- **violence**: 模型输出文字涉及激进行为。

**注意**: 当前只有视觉理解模型支持返回该字段，且只有在方舟控制台接入点配置页面或者 CreateEndpoint 接口中，将内容护栏方案（ModerationStrategy）设置为基础方案（Basic）时，才会返回风险分类标签。

**属性**

- `choices.delta.role` (string): 内容输出的角色，此处固定为 `assistant`。
- `choices.delta.content` (string): 模型生成的消息内容。
- `choices.delta.reasoning_content` (string / null): 模型处理问题的思维链内容。仅深度推理模型支持返回此字段，深度推理模型请参见支持模型。
- `choices.delta.tool_calls` (string / null): 模型生成的工具调用。

**属性**

- `choices.delta.tool_calls.id` (string): 调用的工具的 ID。
- `choices.delta.tool_calls.type` (string): 工具类型，当前仅支持`function`。
- `choices.delta.tool_calls.function` (object): 模型调用的函数。

**属性**

- `choices.delta.tool_calls.function.name` (string): 模型调用的函数的名称。
- `choices.delta.tool_calls.function.arguments` (string): 模型生成的用于调用函数的参数，JSON 格式。模型并不总是生成有效的 JSON，并且可能会虚构出一些您的函数参数规范中未定义的参数。在调用函数之前，请在您的代码中验证这些参数是否有效。

**属性**

- `choices.logprobs.content` (object[] / null): message列表中每个 content 元素中的 token 对数概率信息。

**属性**

- `choices.logprobs.content.token` (string): 当前 token。
- `choices.logprobs.content.bytes` (integer[] / null): 当前 token 的 UTF-8 值，格式为整数列表。当一个字符由多个 token 组成（表情符号或特殊字符等）时可以用于字符的编码和解码。如果 token 没有 UTF-8 值则为空。
- `choices.logprobs.content.logprob` (float): 当前 token 的对数概率。
- `choices.logprobs.content.top_logprobs` (object[]): 在当前 token 位置最有可能的标记及其对数概率的列表。在一些情况下，返回的数量可能比请求参数 top_logprobs 指定的数量要少。

**属性**

- `choices.logprobs.content.top_logprobs.token` (string): 当前 token。
- `choices.logprobs.content.top_logprobs.bytes` (integer[] / null): 当前 token 的 UTF-8 值，格式为整数列表。当一个字符由多个 token 组成（表情符号或特殊字符等）时可以用于字符的编码和解码。如果 token 没有 UTF-8 值则为空。
- `choices.logprobs.content.top_logprobs.logprob` (float): 当前 token 的对数概率。

#### usage

- **类型**: object
- **说明**: 本次请求的 token 用量。流式调用时，默认不统计 token 用量信息，返回值为null。如需统计，需设置 stream_options.include_usage为true。

**属性**

- `usage.prompt_tokens` (integer): 输入给模型的内容的 token 用量。
- `usage.completion_tokens` (integer): 模型输出内容的 token 用量。
- `usage.total_tokens` (integer): 本次请求消耗的总 token 数量（输入 + 输出）。
- `usage.prompt_tokens_details` (object): 输入给模型的内容的 token 用量的细节。
  - `usage.prompt_tokens_details.cached_tokens` (integer): 通过缓存输入内容的 token 用量。
- `usage.completion_tokens_details` (object): 本次请求，模型输出内容的 token 用量的细节
  - `usage.completion_tokens_details.reasoning_tokens` (integer): 输出思维链内容花费的 token 数 。支持输出思维链的模型请参见[文档](https://www.volcengine.com/docs/82379/1449737#5f0f3750)。

## 示例

### 默认调用示例

#### Curl 示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/context/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "context_id": "ctx-20250410172958-pv756",
  "messages": [
    {
      "content": "你好",
      "role": "user"
    }
  ],
  "model": "ep-20250410*****-*****"
}'
```

#### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(
    api_key=os.getenv('ARK_API_KEY'),
)

# 使用上下文缓存进行对话
response = client.chat.completions.create(
    model="ep-20250410*****-*****",
    context_id="ctx-20250410172958-pv756",
    messages=[
        {
            "role": "user",
            "content": "你好"
        }
    ]
)

print(f"回复: {response.choices[0].message.content}")
print(f"缓存命中tokens: {response.usage.prompt_tokens_details.cached_tokens}")
```

#### OpenAI Python SDK 示例

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 使用上下文缓存进行对话
response = client.chat.completions.create(
    model="ep-20250410*****-*****",
    messages=[
        {
            "role": "user",
            "content": "你好"
        }
    ],
    extra_body={
        "context_id": "ctx-20250410172958-pv756"
    }
)

print(f"回复: {response.choices[0].message.content}")
print(f"缓存命中tokens: {response.usage.prompt_tokens_details.cached_tokens}")
```

### 流式调用示例

#### Curl 示例

```bash
curl https://ark.cn-beijing.volces.com/api/v3/context/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "context_id": "ctx-20250410172958-pv756",
  "messages": [
    {
      "content": "请介绍一下人工智能的发展历史",
      "role": "user"
    }
  ],
  "model": "ep-20250410*****-*****",
  "stream": true,
  "stream_options": {
    "include_usage": true
  }
}'
```

#### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(
    api_key=os.getenv('ARK_API_KEY'),
)

# 流式调用上下文缓存对话
stream = client.chat.completions.create(
    model="ep-20250410*****-*****",
    context_id="ctx-20250410172958-pv756",
    messages=[
        {
            "role": "user",
            "content": "请介绍一下人工智能的发展历史"
        }
    ],
    stream=True,
    stream_options={
        "include_usage": True
    }
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

    # 最后一个chunk包含usage信息
    if chunk.usage:
        print(f"\n缓存命中tokens: {chunk.usage.prompt_tokens_details.cached_tokens}")
```

### Session缓存多轮对话示例

#### Curl 示例

```bash
# 第一轮对话
curl https://ark.cn-beijing.volces.com/api/v3/context/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "context_id": "ctx-session-20250410-abc123",
  "messages": [
    {
      "content": "我想学习Python编程，请给我一些建议",
      "role": "user"
    }
  ],
  "model": "ep-20250410*****-*****"
}'

# 第二轮对话（基于Session缓存的上下文）
curl https://ark.cn-beijing.volces.com/api/v3/context/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ARK_API_KEY" \
-d '{
  "context_id": "ctx-session-20250410-abc123",
  "messages": [
    {
      "content": "那我应该从哪个版本开始学习？",
      "role": "user"
    }
  ],
  "model": "ep-20250410*****-*****"
}'
```

#### Python SDK 示例

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(
    api_key=os.getenv('ARK_API_KEY'),
)

# Session缓存ID
session_context_id = "ctx-session-20250410-abc123"

# 第一轮对话
response1 = client.chat.completions.create(
    model="ep-20250410*****-*****",
    context_id=session_context_id,
    messages=[
        {
            "role": "user",
            "content": "我想学习Python编程，请给我一些建议"
        }
    ]
)

print("第一轮回复:", response1.choices[0].message.content)
print(f"缓存命中tokens: {response1.usage.prompt_tokens_details.cached_tokens}")

# 第二轮对话（基于Session缓存的上下文）
response2 = client.chat.completions.create(
    model="ep-20250410*****-*****",
    context_id=session_context_id,
    messages=[
        {
            "role": "user",
            "content": "那我应该从哪个版本开始学习？"
        }
    ]
)

print("第二轮回复:", response2.choices[0].message.content)
print(f"缓存命中tokens: {response2.usage.prompt_tokens_details.cached_tokens}")
```

### 响应示例

#### 非流式响应

```json
{
  "id": "02174427747891615208d1b4038f629a958d0e327ef7d338d2d35",
  "object": "chat.completion",
  "created": 1744277479,
  "model": "doubao-1-5-pro-32k-250115",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "我是李雷"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 28,
    "completion_tokens": 4,
    "total_tokens": 32,
    "prompt_tokens_details": {
      "cached_tokens": 18
    },
    "completion_tokens_details": {
      "reasoning_tokens": 0
    }
  }
}
```

#### 流式响应示例

```json
// 第一个chunk
{
  "id": "02174427747891615208d1b4038f629a958d0e327ef7d338d2d35",
  "object": "chat.completion.chunk",
  "created": 1744277479,
  "model": "doubao-1-5-pro-32k-250115",
  "choices": [
    {
      "index": 0,
      "delta": {
        "role": "assistant",
        "content": "我"
      },
      "finish_reason": null
    }
  ],
  "usage": null
}

// 中间chunk
{
  "id": "02174427747891615208d1b4038f629a958d0e327ef7d338d2d35",
  "object": "chat.completion.chunk",
  "created": 1744277479,
  "model": "doubao-1-5-pro-32k-250115",
  "choices": [
    {
      "index": 0,
      "delta": {
        "content": "是李雷"
      },
      "finish_reason": null
    }
  ],
  "usage": null
}

// 最后一个chunk（包含usage信息）
{
  "id": "02174427747891615208d1b4038f629a958d0e327ef7d338d2d35",
  "object": "chat.completion.chunk",
  "created": 1744277479,
  "model": "doubao-1-5-pro-32k-250115",
  "choices": [
    {
      "index": 0,
      "delta": {},
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 28,
    "completion_tokens": 4,
    "total_tokens": 32,
    "prompt_tokens_details": {
      "cached_tokens": 18
    },
    "completion_tokens_details": {
      "reasoning_tokens": 0
    }
  }
}
```

## 使用场景

### 1. 前缀缓存场景

适用于有固定系统提示词或背景信息的应用：

```python
# 创建前缀缓存
context_response = client.context.create(
    model="ep-20250410*****-*****",
    messages=[
        {
            "role": "system",
            "content": "你是一个专业的客服助手，请始终保持礼貌和专业的态度。"
        }
    ],
    mode="common_prefix"
)

context_id = context_response.id

# 使用前缀缓存进行多次对话
for user_query in ["你好", "我想退货", "退货流程是什么"]:
    response = client.chat.completions.create(
        model="ep-20250410*****-*****",
        context_id=context_id,
        messages=[
            {
                "role": "user",
                "content": user_query
            }
        ]
    )
    print(f"用户: {user_query}")
    print(f"助手: {response.choices[0].message.content}")
    print(f"缓存命中: {response.usage.prompt_tokens_details.cached_tokens} tokens\n")
```

### 2. Session缓存场景

适用于需要维护多轮对话上下文的应用：

```python
# 创建Session缓存
context_response = client.context.create(
    model="ep-20250410*****-*****",
    messages=[
        {
            "role": "system",
            "content": "你是一个编程导师，帮助学生学习编程知识。"
        }
    ],
    mode="session",
    truncation_strategy={
        "type": "rolling_tokens",
        "rolling_tokens": True,
        "max_window_tokens": 8192,
        "rolling_window_tokens": 1024
    }
)

session_id = context_response.id

# 多轮对话，每次只传入当前轮次的消息
conversation = [
    "我想学习Python，应该从哪里开始？",
    "那我需要安装什么软件？",
    "请给我写一个Hello World程序",
    "如何运行这个程序？"
]

for question in conversation:
    response = client.chat.completions.create(
        model="ep-20250410*****-*****",
        context_id=session_id,
        messages=[
            {
                "role": "user",
                "content": question
            }
        ]
    )
    print(f"学生: {question}")
    print(f"导师: {response.choices[0].message.content}")
    print(f"缓存命中: {response.usage.prompt_tokens_details.cached_tokens} tokens\n")
```

## 最佳实践

1. **选择合适的缓存类型**：
   - 前缀缓存：适用于固定的系统提示词场景
   - Session缓存：适用于多轮对话场景

2. **合理设置参数**：
   - 根据业务需求设置合适的`max_tokens`
   - 使用`stream`参数提升用户体验
   - 通过`stream_options.include_usage`监控token使用

3. **错误处理**：
   - 检查缓存是否过期
   - 处理网络异常和API限流
   - 验证响应格式的完整性

4. **性能优化**：
   - 监控缓存命中率
   - 根据使用情况调整缓存策略
   - 合理设置TTL避免不必要的成本

## 常见问题

### Q: 如何判断缓存是否生效？

A: 通过响应中的`usage.prompt_tokens_details.cached_tokens`字段可以查看命中缓存的token数量。如果该值大于0，说明缓存生效。

### Q: Session缓存和前缀缓存有什么区别？

A:

- **前缀缓存**：只缓存固定的前缀内容（如系统提示词），适用于重复使用相同背景信息的场景
- **Session缓存**：缓存完整的对话历史，支持多轮对话上下文，适用于需要维护对话状态的场景

### Q: 如何处理缓存过期？

A: 当缓存过期时，API会返回相应的错误信息。此时需要重新创建缓存，然后继续使用新的context_id进行对话。

### Q: 是否支持工具调用？

A: 上下文缓存对话API暂不支持`tools`字段，如需使用工具调用功能，请使用标准的Chat API。
