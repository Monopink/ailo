# Image Process 图像处理工具

**最近更新时间：2025.09.04 15:20:18**
**首次发布时间：2025.08.25 17:19:58**

Image Process 图像处理工具支持通过 API 调用对输入图片执行画点、画线、旋转、缩放、框选/裁剪关键区域等基础操作，适用于需模型通过视觉处理提升图片理解的场景（如图文内容分析、物体定位标注、多轮视觉推理等）。工具通过模型自动判断图像处理逻辑，支持与自定义 Function 混合使用，且可处理多轮视觉输入（上一轮输出图片作为下一轮输入）。

> **说明**
>
> 功能当前处于邀测阶段，仅对部分用户开放，测试期间免费试用，正式发布时间将另行通知。

## 核心功能

- 丰富的图像处理工具：支持启用/禁用画点（POINT）、框选（GROUNDING）、缩放（ZOOM）、旋转（ROTATE）等子功能，满足不同视觉处理需求。
- 支持多轮图像处理：复杂视觉任务（如多步缩放+旋转）支持多轮工具调用，上一轮输出图片自动作为下一轮输入（例：image0→image1→image2）。
- 支持混合调用：可与用户自定义 Function 混合使用，暂不支持与 Web Search 工具混合调用。
- 广泛的图片格式兼容：支持 Base64 编码的 .gif、.jpg、.jpeg 等主流图片格式，明确限制图片大小、像素、长宽比例（避免处理异常）。

## 支持模型列表

- doubao-seed-1-6-vision-250815

> 模型调用需确保已开通图像处理工具权限，未开白用户无法触发工具功能。

## 注意事项

- **Function 命名冲突**：若用户自定义 Function 与 "image_process" 重名，由模型自行判断调用工具（无需额外配置）。
- **图片规格限制**：输入图片需满足以下条件：
  - 文件体积≤10MB、≤36000000像素、宽和高的长度>14像素、长宽比<150:1，超出规格将导致处理失败；
  - 文件格式支持情况如下：
    - **支持** .gif，.jpg，.jpeg，.png，.webp，.bmp，.tiff，.ico， .icns， .jp2 格式。
    - **不支持** .dib、.sgi、.heic、.heif 格式。
- **暂未支持功能**：当前不支持与 Web Search 工具混合使用，也不支持通过`tool_choice`参数指定调用 image_process，后续将逐步上线。
- **Tokens 消费提示**：多轮图像处理会增加 Tokens 消费（上一轮图片输入计入下一轮 Tokens），需注意调用成本。

## 计费说明

- **公测期间**：暂时免费使用，无额外收费。
- 我们将会提前 2 周通过官方渠道告知用户具体收费标准，保障您的使用权益。

## 参数说明

详情请参见[创建 Responses 模型请求](https://www.volcengine.com/docs/82379/1569618)。

## 快速开始

以下提供两种常用调用方式示例，需先替换`<ARK_API_KEY>`为实际密钥。

### 示例一：缩放（zoom）工具

#### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--header 'ark-beta-image-process: true' \
--data '{
  "model": "doubao-seed-1-6-vision-250815",
  "stream": true,
  "tools": [
    {"type": "image_process"}
  ],
  "input": [
    {
      "type": "message",
      "role": "system",
      "content": [
        {
          "type": "input_text",
          "text": "前方路牌写了什么？"
        },
        {
          "type": "input_image",
          "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/image_process_1.jpg"
        }
      ]
    }
  ]
}'
```

#### Python SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 调用图像处理工具 - 缩放示例
response = client.responses.create(
    model="doubao-seed-1-6-vision-250815",
    stream=True,
    tools=[
        {"type": "image_process"}
    ],
    input=[
        {
            "type": "message",
            "role": "system",
            "content": [
                {
                    "type": "input_text",
                    "text": "前方路牌写了什么？"
                },
                {
                    "type": "input_image",
                    "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/image_process_1.jpg"
                }
            ]
        }
    ],
    extra_headers={"ark-beta-image-process": "true"}
)

# 处理流式响应
for chunk in response:
    chunk_type = getattr(chunk, 'type', '')

    if chunk_type == "response.output_text.delta":
        print(getattr(chunk, 'delta', ''), end="", flush=True)
    elif "image_process_call" in chunk_type:
        if "in_progress" in chunk_type:
            print("\n🖼️ 开始图像处理...")
        elif "completed" in chunk_type:
            print("✅ 图像处理完成")

print("\n处理完成")
```

### 示例二：画点（point）工具

#### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--header 'ark-beta-image-process: true' \
--data '{
  "model": "doubao-seed-1-6-vision-250815",
  "stream": true,
  "tools": [
    {"type": "image_process"}
  ],
  "input": [
    {
      "type": "message",
      "role": "system",
      "content": [
        {
          "type": "input_text",
          "text": "数一数有多少颗草莓？"
        },
        {
          "type": "input_image",
          "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/image_process_2.jpg"
        }
      ]
    }
  ]
}'
```

#### Python SDK 示例

```python
import os
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv('ARK_API_KEY')
)

# 调用图像处理工具 - 画点示例
response = client.responses.create(
    model="doubao-seed-1-6-vision-250815",
    stream=True,
    tools=[
        {"type": "image_process"}
    ],
    input=[
        {
            "type": "message",
            "role": "system",
            "content": [
                {
                    "type": "input_text",
                    "text": "数一数有多少颗草莓？"
                },
                {
                    "type": "input_image",
                    "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/image_process_2.jpg"
                }
            ]
        }
    ],
    extra_headers={"ark-beta-image-process": "true"}
)

# 处理流式响应
for chunk in response:
    chunk_type = getattr(chunk, 'type', '')

    if chunk_type == "response.output_text.delta":
        print(getattr(chunk, 'delta', ''), end="", flush=True)
    elif "image_process_call" in chunk_type:
        if "in_progress" in chunk_type:
            print("\n🖼️ 开始图像处理...")
        elif "completed" in chunk_type:
            print("✅ 图像处理完成")

print("\n处理完成")
```

## 使用示例

### 多轮图像处理示例

#### Curl 示例

```bash
# 第一轮：缩放图像
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--header 'ark-beta-image-process: true' \
--data '{
  "model": "doubao-seed-1-6-vision-250815",
  "stream": true,
  "tools": [
    {
      "type": "image_process",
      "enabled_tools": ["ZOOM", "POINT", "GROUNDING", "ROTATE"]
    }
  ],
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "请先放大图片中的文字部分，然后标记出所有的文字位置"
        },
        {
          "type": "input_image",
          "image_url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD..."
        }
      ]
    }
  ],
  "max_tool_calls": 3
}'
```

#### Python SDK 示例（完整多轮处理）

```python
import os
import base64
from openai import OpenAI
from datetime import datetime

def encode_image_to_base64(image_path):
    """将本地图片编码为base64格式"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def main():
    # 初始化客户端
    client = OpenAI(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key=os.getenv('ARK_API_KEY')
    )

    # 编码本地图片（如果使用本地图片）
    # image_base64 = encode_image_to_base64("path/to/your/image.jpg")
    # image_url = f"data:image/jpeg;base64,{image_base64}"

    # 使用在线图片URL
    image_url = "https://ark-project.tos-cn-beijing.volces.com/doc_image/image_process_1.jpg"

    # 调用图像处理工具
    response = client.responses.create(
        model="doubao-seed-1-6-vision-250815",
        stream=True,
        tools=[
            {
                "type": "image_process",
                "enabled_tools": ["ZOOM", "POINT", "GROUNDING", "ROTATE"]  # 启用多种处理工具
            }
        ],
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "请分析这张图片，先放大关键区域，然后标记出重要的物体位置，最后旋转图片到最佳角度"
                    },
                    {
                        "type": "input_image",
                        "image_url": image_url
                    }
                ]
            }
        ],
        max_tool_calls=5,  # 允许多轮工具调用
        extra_headers={"ark-beta-image-process": "true"}
    )

    # 初始化状态变量
    processing_started = False
    answering_started = False
    tool_call_count = 0

    # 处理流式响应
    for chunk in response:
        chunk_type = getattr(chunk, 'type', '')

        # 处理图像处理工具调用
        if "image_process_call" in chunk_type:
            if "in_progress" in chunk_type:
                tool_call_count += 1
                print(f"\n🖼️ 第{tool_call_count}轮图像处理开始... [{datetime.now().strftime('%H:%M:%S')}]")
                processing_started = True
            elif "completed" in chunk_type:
                print("✅ 图像处理完成")

        # 处理工具调用结果
        elif (chunk_type == "response.output_item.done" and
              hasattr(chunk, 'item') and
              str(getattr(chunk.item, 'id', '')).startswith("ip_")):
            # 提取图像处理操作信息
            if hasattr(chunk.item, 'action'):
                action_type = getattr(chunk.item.action, 'type', 'unknown')
                print(f"📝 执行操作: {action_type}")

        # 处理AI的回答内容
        elif chunk_type == "response.output_text.delta":
            if not answering_started:
                print(f"\n💬 AI分析结果 [{datetime.now().strftime('%H:%M:%S')}]:")
                print("-" * 50)
                answering_started = True
            print(getattr(chunk, 'delta', ''), end="", flush=True)

    print(f"\n\n✨ 处理完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
```

### 与自定义Function混合使用示例

#### Curl 示例

```bash
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--header 'ark-beta-image-process: true' \
--data '{
  "model": "doubao-seed-1-6-vision-250815",
  "stream": true,
  "tools": [
    {
      "type": "image_process"
    },
    {
      "type": "function",
      "function": {
        "name": "save_analysis_result",
        "description": "保存图像分析结果到数据库",
        "parameters": {
          "type": "object",
          "properties": {
            "image_id": {
              "type": "string",
              "description": "图像ID"
            },
            "analysis_result": {
              "type": "string",
              "description": "分析结果描述"
            },
            "detected_objects": {
              "type": "array",
              "items": {"type": "string"},
              "description": "检测到的物体列表"
            }
          },
          "required": ["image_id", "analysis_result"]
        }
      }
    }
  ],
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "请分析这张图片中的物体，标记出重要位置，然后将分析结果保存到数据库"
        },
        {
          "type": "input_image",
          "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/image_process_2.jpg"
        }
      ]
    }
  ]
}'
```

#### Python SDK 示例

```python
import os
import json
from openai import OpenAI

def save_analysis_result(image_id, analysis_result, detected_objects=None):
    """模拟保存分析结果到数据库的函数"""
    print(f"保存分析结果:")
    print(f"  图像ID: {image_id}")
    print(f"  分析结果: {analysis_result}")
    if detected_objects:
        print(f"  检测到的物体: {', '.join(detected_objects)}")
    return "分析结果已成功保存到数据库"

def main():
    # 初始化客户端
    client = OpenAI(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key=os.getenv('ARK_API_KEY')
    )

    # 定义工具
    tools = [
        {
            "type": "image_process"
        },
        {
            "type": "function",
            "function": {
                "name": "save_analysis_result",
                "description": "保存图像分析结果到数据库",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_id": {
                            "type": "string",
                            "description": "图像ID"
                        },
                        "analysis_result": {
                            "type": "string",
                            "description": "分析结果描述"
                        },
                        "detected_objects": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "检测到的物体列表"
                        }
                    },
                    "required": ["image_id", "analysis_result"]
                }
            }
        }
    ]

    # 初始化消息历史
    messages = [
        {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "请分析这张图片中的物体，标记出重要位置，然后将分析结果保存到数据库，图像ID为'img_001'"
                },
                {
                    "type": "input_image",
                    "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/image_process_2.jpg"
                }
            ]
        }
    ]

    # 多轮工具调用处理
    while True:
        response = client.responses.create(
            model="doubao-seed-1-6-vision-250815",
            stream=False,  # 使用非流式以便处理工具调用
            tools=tools,
            input=messages,
            extra_headers={"ark-beta-image-process": "true"}
        )

        # 检查是否有工具调用
        if hasattr(response, 'output') and hasattr(response.output, 'tool_calls'):
            tool_calls = response.output.tool_calls

            if tool_calls:
                # 添加助手消息到历史
                messages.append({
                    "type": "message",
                    "role": "assistant",
                    "content": response.output.content or "",
                    "tool_calls": tool_calls
                })

                # 处理每个工具调用
                for tool_call in tool_calls:
                    if tool_call.type == "function":
                        function_name = tool_call.function.name
                        arguments = json.loads(tool_call.function.arguments)

                        if function_name == "save_analysis_result":
                            result = save_analysis_result(**arguments)

                            # 添加工具结果到历史
                            messages.append({
                                "type": "message",
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": result
                            })
                    elif tool_call.type == "image_process":
                        print("🖼️ 图像处理完成")
                        # 图像处理结果会自动包含在响应中
                        messages.append({
                            "type": "message",
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": "图像处理完成"
                        })
            else:
                # 没有工具调用，输出最终结果
                print("💬 最终回答:")
                print(response.output.content)
                break
        else:
            # 没有工具调用，输出结果
            print("💬 回答:")
            if hasattr(response, 'output'):
                print(response.output.content)
            break

if __name__ == "__main__":
    main()
```

## 最佳实践

### 图像格式和质量建议

#### Curl 示例（使用Base64编码）

```bash
# 使用Base64编码的本地图片
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--header 'ark-beta-image-process: true' \
--data '{
  "model": "doubao-seed-1-6-vision-250815",
  "stream": true,
  "tools": [
    {
      "type": "image_process",
      "enabled_tools": ["ZOOM", "POINT", "GROUNDING"]
    }
  ],
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "请分析这张高质量图片中的细节"
        },
        {
          "type": "input_image",
          "image_url": "data:image/jpeg;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        }
      ]
    }
  ]
}'
```

#### Python SDK 示例（图像质量优化）

```python
import os
import base64
from PIL import Image
from io import BytesIO
from openai import OpenAI

def optimize_image_for_processing(image_path, max_size=(2048, 2048), quality=85):
    """优化图像以适合处理"""
    with Image.open(image_path) as img:
        # 转换为RGB模式（如果需要）
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # 调整尺寸
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # 保存为JPEG格式
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        buffer.seek(0)

        return base64.b64encode(buffer.getvalue()).decode('utf-8')

def main():
    client = OpenAI(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key=os.getenv('ARK_API_KEY')
    )

    # 优化本地图片
    # image_base64 = optimize_image_for_processing("path/to/your/image.jpg")
    # image_url = f"data:image/jpeg;base64,{image_base64}"

    # 使用示例图片
    image_url = "https://ark-project.tos-cn-beijing.volces.com/doc_image/image_process_1.jpg"

    response = client.responses.create(
        model="doubao-seed-1-6-vision-250815",
        stream=True,
        tools=[
            {
                "type": "image_process",
                "enabled_tools": ["ZOOM", "POINT", "GROUNDING", "ROTATE"]
            }
        ],
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "请详细分析这张图片，使用所有可用的图像处理工具来增强理解"
                    },
                    {
                        "type": "input_image",
                        "image_url": image_url
                    }
                ]
            }
        ],
        max_tool_calls=3,
        extra_headers={"ark-beta-image-process": "true"}
    )

    for chunk in response:
        chunk_type = getattr(chunk, 'type', '')

        if chunk_type == "response.output_text.delta":
            print(getattr(chunk, 'delta', ''), end="", flush=True)
        elif "image_process_call" in chunk_type:
            if "in_progress" in chunk_type:
                print("\n🖼️ 图像处理中...")
            elif "completed" in chunk_type:
                print("✅ 处理完成")

if __name__ == "__main__":
    main()
```

### 工具选择和配置建议

#### Curl 示例（精确控制工具）

```bash
# 只启用特定工具
curl --location 'https://ark.cn-beijing.volces.com/api/v3/responses' \
--header 'Authorization: Bearer $ARK_API_KEY' \
--header 'Content-Type: application/json' \
--header 'ark-beta-image-process: true' \
--data '{
  "model": "doubao-seed-1-6-vision-250815",
  "stream": true,
  "tools": [
    {
      "type": "image_process",
      "enabled_tools": ["POINT", "GROUNDING"]
    }
  ],
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "请只使用画点和框选功能来标记图片中的重要物体"
        },
        {
          "type": "input_image",
          "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/image_process_2.jpg"
        }
      ]
    }
  ]
}'
```

#### Python SDK 示例（动态工具配置）

```python
import os
from openai import OpenAI

def create_image_analysis_request(task_type, image_url):
    """根据任务类型创建不同的图像分析请求"""

    # 根据任务类型选择合适的工具
    tool_configs = {
        "object_detection": {
            "enabled_tools": ["POINT", "GROUNDING"],
            "prompt": "请识别并标记图片中的所有物体"
        },
        "text_recognition": {
            "enabled_tools": ["ZOOM", "GROUNDING"],
            "prompt": "请放大并框选图片中的文字区域"
        },
        "comprehensive_analysis": {
            "enabled_tools": ["ZOOM", "POINT", "GROUNDING", "ROTATE"],
            "prompt": "请全面分析这张图片，使用所有必要的处理工具"
        }
    }

    config = tool_configs.get(task_type, tool_configs["comprehensive_analysis"])

    return {
        "model": "doubao-seed-1-6-vision-250815",
        "stream": True,
        "tools": [
            {
                "type": "image_process",
                "enabled_tools": config["enabled_tools"]
            }
        ],
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": config["prompt"]
                    },
                    {
                        "type": "input_image",
                        "image_url": image_url
                    }
                ]
            }
        ],
        "max_tool_calls": 3,
        "extra_headers": {"ark-beta-image-process": "true"}
    }

def main():
    client = OpenAI(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key=os.getenv('ARK_API_KEY')
    )

    image_url = "https://ark-project.tos-cn-beijing.volces.com/doc_image/image_process_1.jpg"

    # 不同类型的分析任务
    tasks = ["object_detection", "text_recognition", "comprehensive_analysis"]

    for task in tasks:
        print(f"\n{'='*50}")
        print(f"执行任务: {task}")
        print(f"{'='*50}")

        request_config = create_image_analysis_request(task, image_url)
        response = client.responses.create(**request_config)

        for chunk in response:
            chunk_type = getattr(chunk, 'type', '')

            if chunk_type == "response.output_text.delta":
                print(getattr(chunk, 'delta', ''), end="", flush=True)
            elif "image_process_call" in chunk_type:
                if "in_progress" in chunk_type:
                    print(f"\n🖼️ 开始{task}处理...")
                elif "completed" in chunk_type:
                    print("✅ 处理完成")

        print(f"\n{task}任务完成\n")

if __name__ == "__main__":
    main()
```
