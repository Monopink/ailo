# 数据库设计文档

## 设计原则

1. 不使用外键约束：通过代码逻辑维护数据一致性，提高性能和灵活性
2. 统一标识符命名：外部标识符统一使用`qiao_id`格式，内部使用Snowflake ID
3. 枚举值使用整型：所有枚举字段使用TINYINT类型，在代码中定义枚举约束
4. 核心业务表使用Snowflake ID：用户、消息、AI等核心表使用BIGINT类型的Snowflake ID
5. 配置表使用自增ID：系统配置、统计等辅助表使用AUTO_INCREMENT
6. 完善的索引设计：为高频查询字段添加合适的索引
7. 时间字段自动管理：created_at和updated_at字段自动设置和更新

## 详细表结构

## users

用户基础信息表，存储用户账户数据。

```txt
id -- Snowflake ID
qiao_id -- qiao_+随机字符，外部使用，唯一标识
username -- 用户名，初始默认为qiao_id
phone -- 手机号(E.164格式)，用于登录验证，必填，唯一
email -- 邮箱地址
password_hash -- 密码哈希值
is_verified -- 是否实名验证：1=yes, 0=no
verified_at -- 实名认证通过时间
verify_source -- 实名验证来源（如公安三要素、支付宝、微信、腾讯云等）
verification_info -- 实名验证详细信息JSON存储
status -- 账户状态：1=active, 2=inactive, 3=suspended
user_type -- 用户类型：1=normal, 2=official, 3=virtual
last_login -- 最后登录时间
created_at
updated_at
```

## user_tokens

用户令牌表（Hybrid 架构）：管理 JWT 登录令牌、设备限制与吊销。

```txt
id -- Snowflake ID
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id，冗余字段便于查询
token -- JWT令牌（唯一）
device_type -- 设备类型：1=ios, 2=android, 3=web, 4=mini_program
device_id -- 设备唯一标识
platform_info -- 平台信息（JSONB，可选）
ip_address -- 登录IP地址
user_agent -- UA信息
expires_at -- 过期时间
status -- 令牌状态：1=active, 2=revoked
last_activity_at -- 最后活动时间
revoked_at -- 吊销时间
created_at
updated_at
```

## user_auths

第三方身份绑定表（仅存储身份映射，不保存登录会话与第三方长期令牌）。

```txt
id -- Snowflake ID
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id，冗余字段便于查询
auth_type -- 授权平台类型：1=apple, 2=qq, 3=wechat
provider_uid -- 平台用户唯一ID（WeChat openid / Apple sub / 抖音 open_id / 支付宝 user_id）
unionid -- 跨应用统一ID（仅微信，可选）
app_id -- 平台应用标识（可选，用于多应用区分）
extra_data -- 附加信息（JSONB）
status -- 状态：1=active, 2=revoked
revoked_at -- 解绑时间（可选）
created_at
updated_at
```

## contacts

联系人关系表，管理用户之间的联系关系。

```txt
id -- Snowflake ID
conv_id -- conv_+随机字符，外部使用，对话标识
user_id -- 联系人所属用户ID，NULL表示公共联系人
user_qiao_id -- 联系人所属用户外部ID，NULL表示公共联系人
contact_type -- 联系人类型：1=user, 2=ai, 3=official
contact_id -- 联系人内部ID
contact_qiao_id -- 联系人外部ID
alias -- 备注名称
custom_avatar_url -- 备注头像URL
tags -- 标签JSON数组：["tag1","tag2"]
remark -- 备注描述
source -- 添加来源：discovery=发现页, search=搜索, recommend=推荐等
is_pinned -- 是否置顶：1=yes, 0=no
is_muted -- 是否免打扰：1=yes, 0=no
is_blocked -- 是否屏蔽：1=yes, 0=no
is_deleted -- 是否删除：1=yes, 0=no
deleted_at -- 删除时间
created_at
updated_at
```

## square_type_entries

Square 曝光表，决定哪些 `type_id` 被上架到 Square 以及采用何种曝光策略。

```txt
id -- 自增ID
square_category -- Square 分类枚举：1=friend, 2=love, 3=talk, 4=bestie, 5=hobby
type_id -- 关联 ai_types.id，代表被曝光的角色类型
exposure_strategy -- 曝光策略枚举：1=random
status -- 1=active, 2=inactive（inactive 时该 type_id 不出现在 Square）
created_at
updated_at
```

Square 只消费该表的数据，与模板库存隔离；模板体系的状态不会直接影响 Square 曝光。接口端会根据 `type_id` 实时选择可用 persona/qiao_id，并直接复用 persona/profile 的展示信息。每个 Square 分类下，每个 AI 类型只能出现一次（UNIQUE 约束：square_category, type_id）。

- `square_category` 现在直接存储整数（无需额外的字符串映射），`exposure_strategy` 只保留 `random=1`，`fixed/weighted` 枚举已移除，并且 `last_featured_at` 字段不再存在，Square 只控制分类/策略/状态。

## login_records

用户登录记录表，记录所有登录尝试。

```txt
id -- Snowflake ID
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id
login_time -- 登录时间
login_type -- 登录方式：1=password, 2=sms, 3=wechat, 4=apple
platform -- 平台：1=ios, 2=android, 3=web, 4=mini_program
device_id -- 设备ID/标识
ip_address -- 登录IP（兼容IPv6）
user_agent -- 浏览器/设备UA信息
result -- 登录结果：1=success, 2=fail
fail_reason -- 失败原因
token -- 关联的会话令牌
created_at
```

## message_history

消息历史记录表，消息发送成功后写入数据。

```txt
id -- Snowflake ID
direction -- 消息方向：1=inbound, 2=outbound
platform -- 平台：1=ios, 2=android, 3=web, 4=mini_program（入站消息使用）
conversation_id -- 对话ID，关联contacts.conv_id
msg_id_server -- msg_+(Snowflake字符串)，外部使用，发送消息使用
msg_id_provider -- 第三方消息服务生成的消息ID
msg_id_client -- 客户端消息ID，接收消息使用
client_sent_time -- 消息中包含的客户端发送时间
from_type -- 发送方类型：1=user, 2=ai, 3=admin, 4=system
from_id -- 发送方内部ID
from_qiao_id -- 发送方外部ID
to_type -- 接收方类型：1=user, 2=ai, 3=admin, 4=system
to_id -- 接收方内部ID
to_qiao_id -- 接收方外部ID
service_provider -- 服务提供商：1=internal, 2=leancloud
message_type -- 消息类型：1=text, 2=typing, 3=typing_end, 4=chat_info, 9=notification
content -- 消息内容
status -- 消息状态：1=sent, 2=delivered, 3=read, 4=failed
message_metadata -- 消息元数据JSON
created_at
```

## notification_push_history

通知推送历史表，记录所有发送的通知消息。

**说明**: 通知消息不存入 message_history，单独存储用于调试、分析和重试。

```txt
id -- Snowflake ID
to_qiao_id -- 接收者 qiao_id
notification_type -- 通知类型：1=contact_request
action_data -- 操作数据（action + data），JSONB类型
status -- 状态：1=sent, 2=failed
error_message -- 错误信息（失败时），TEXT类型
created_at
updated_at
```

## media_files

媒体文件管理表，统一管理头像、表情、图片等资源。

```txt
id -- Snowflake ID
file_id -- file_+随机字符，外部使用
file_type -- 文件类型：1=avatar, 2=emoji, 3=image, 4=document
original_name -- 原始文件名
file_path -- 文件存储路径
file_url -- 文件访问URL
file_size -- 文件大小（字节）
mime_type -- MIME类型
upload_by_type -- 上传者类型：1=user, 2=admin, 3=system
upload_by_id -- 上传者ID
upload_by_qiao_id -- 上传者外部ID
status -- 文件状态：1=active, 2=inactive, 3=deleted
created_at
updated_at
```

## message_delivery_failures

消息投递失败记录表，成功重发后删除记录。

```txt
id -- Snowflake ID
msg_id_server -- 原消息ID，关联message_history.msg_id_server
from_id -- 发送方内部ID
from_qiao_id -- 发送方外部ID
from_type -- 发送方类型：1=user, 2=ai, 3=admin, 4=system
to_id -- 接收方内部ID
to_qiao_id -- 接收方外部ID
to_type -- 接收方类型：1=user, 2=ai, 3=admin, 4=system
service_provider -- 服务提供商：1=internal, 2=leancloud 
message_type -- 消息类型：1=text, 2=typing, 3=typing_end, 4=system
content -- 消息内容
fail_reason_code -- 失败原因代码
fail_detail -- 详细错误信息/堆栈，TEXT类型
retry_count -- 重试次数，默认0
max_retry_count -- 最大重试次数，默认3
next_retry_at -- 下次重试时间
created_at
updated_at
```

## ai_message_buffer

消息缓冲窗口表；将用户端多条消息聚合为一个窗口，驱动双计时器逻辑（micro/macro）并控制抢占。

```txt
id -- Snowflake ID
user_qiao_id -- 用户 external ID
instance_qiao_id -- AI external ID
aggregate_state -- 0=WAKE, 1=OPEN, 2=LOCKED, 3=COMPLETE, 4=CANCELLED
micro_expires_at_ms -- 微计时器到期时间（毫秒）
macro_expires_at_ms -- 宏计时器到期时间（毫秒，可为空）
buffer_expires_at_ms -- 缓冲窗口到期时间（毫秒）
wake_expires_at_ms -- Wake timer expiration (ms), NULL if already awake or in OPEN state
last_message_category -- VARCHAR(32)，CONTENT_TYPING / CONTENT_NO_TYPING / typing_start / typing_end
first_msg_id_client -- 窗口内第一条客户端消息ID
last_msg_id_client -- 窗口内最后一条客户端消息ID
message_count -- 窗口内消息条数，默认1
last_msg_time_ms -- 窗口最后一条消息的毫秒时间戳
locked_at -- 进入 LOCKED 状态的时间（用于超时检测）
wake_adjustment_count -- Number of times wake time was adjusted by new messages
created_at
updated_at
```

## ai_conversation_items

对话历史表，使用简单字段存储消息内容（不再直接存储 LLM provider block）。

```txt
id -- Snowflake ID
user_qiao_id -- 用户 external ID
instance_qiao_id -- AI external ID
role -- system / user / assistant
message_type -- text / image / audio
text_content -- 文本内容（message_type=text 必填）
media_url -- 媒体地址（message_type=image/audio 必填）
media_metadata -- JSONB 元数据（如宽高、时长、transcript 等）
client_msg_ids -- 聚合的客户端消息ID
buffer_id -- 关联 ai_message_buffer.id，user 必填、assistant 可选
is_excluded_from_context -- 是否从 LLM 上下文中剔除（攻击/敏感内容），默认false
created_at
```

## ai_conversation_items_archive

与主表结构一致，存放冷数据（同样使用 message_type/text_content/media_* 字段）。

```txt
id -- Snowflake ID
user_qiao_id -- 用户 external ID
instance_qiao_id -- AI external ID
role -- system / user / assistant
message_type -- text / image / audio
text_content -- 文本内容
media_url -- 媒体地址
media_metadata -- 媒体元数据
client_msg_ids -- 客户端消息ID
buffer_id -- 原始缓冲窗口ID
is_excluded_from_context -- 是否排除上下文
created_at -- 原始创建时间
archived_at -- 归档时间
```

## preset_assets

预设资源管理表，统一管理预设图片资源（头像、表情贴图等）和对应的AI提示词。

```txt
id -- Snowflake ID
asset_type -- 资源类型：1=avatar, 2=emoticon
name -- 资源唯一标识，4位随机数字，如"8923", "7452"（默认头像使用"default"）
category -- 分类
is_client_preset -- 是否客户端预设：1=yes, 0=no
file_id -- 关联media_files.id（云端预设资源，客户端预设为NULL）
url -- 资源URL（客户端预设：assets://1234；云端：https://...）
prompt -- AI提示词（用于AI生成内容时的描述）
description -- 资源描述（用于管理后台显示）
status -- 状态：1=active, 2=inactive
sort_order -- 排序顺序
created_at
updated_at
```

## profiles

统一资料表，管理用户、AI、官方账号的公开资料。

```txt
id -- Snowflake ID
owner_id -- 所有者内部ID
owner_qiao_id -- 所有者外部ID（全局唯一，每个 qiao_id 只能有一个 profile）
owner_type -- 所有者类型：1=user (包括所有用户类型: normal, official, virtual), 2=ai_persona (AI角色原型，被多个instance共享), 3=ai_instance (仅限管理员手动创建的instance)
nickname -- 昵称
gender -- 性别：1=male, 2=female, 3=other, 4=unknown
avatar_file_id -- 头像文件ID，关联media_files.id（自定义头像）
avatar_url -- 头像URL（客户端预设：assets://1234；云端：https://...）
avatar_prompt -- 头像描述，用于AI生成头像的占位符覆盖
bio -- 个人简介
region -- 地区
created_at
updated_at
```

## user_profile_logs

用户资料变更日志表，只存储用户资料变更记录。

```txt
id -- Snowflake ID
owner_id -- 所有者内部ID
owner_qiao_id -- 所有者外部ID
owner_type -- 所有者类型：1=user (包括所有用户类型: normal, official, virtual), 2=ai_persona (AI角色原型，被多个instance共享), 3=ai_instance (仅限管理员手动创建的instance)
modified_by_type -- 修改者类型：1=user, 2=admin, 3=system
field_name -- 修改的字段名，例如 nickname, avatar_url, bio
old_value -- 旧值
new_value -- 新值
change_reason -- 修改原因（例如用户提交、管理员修改）
created_at
```

## ai_relationships

AI关系类型表，定义 AI 实例的关系类型。

```txt
id -- 自增ID
display_name -- 显示名称
prompt_fragment -- 提示词片段
status -- 状态：1=active, 2=inactive
wake_time_min_ms -- INTEGER NOT NULL DEFAULT 3000，微计时器下限（毫秒），CHECK >= 500
wake_time_max_ms -- INTEGER NOT NULL DEFAULT 3000，微计时器上限（毫秒），CHECK >= wake_time_min_ms
wake_time_bias -- VARCHAR(20) NOT NULL DEFAULT 'balanced'，响应时间倾向，CHECK IN ('balanced', 'centered', 'fast', 'slow', 'very_fast', 'very_slow')
wake_window_ms -- INTEGER NOT NULL DEFAULT 60000，跳过唤醒窗口（毫秒），CHECK >= 0
wake_time_adjustment -- VARCHAR(20) NOT NULL DEFAULT 'random_half'，等待时间调整策略
no_reply_probability -- DECIMAL(3,2) NOT NULL DEFAULT 0.00，不回复概率（0.00-1.00），CHECK >= 0 AND <= 1
followup_delay_ms -- INTEGER NOT NULL DEFAULT 5000，跟进消息延迟（毫秒），CHECK >= 0
created_at
updated_at
```

## ai_styles

AI风格表，定义 AI 实例的风格类型和评分维度。

```txt
id -- 自增ID
display_name -- 用于显示的名称
status -- 状态：1=active, 2=inactive
created_at
updated_at
```

## ai_dimensions

```txt
id -- 自增ID
name -- 用于通过llm响应查询的名称
display_name -- 用于显示的名称
description -- 用于管理后台参考
created_at
updated_at
```

## ai_style_dimensions

```txt
id
style_id  -- 关联 ai_styles.id
dimension_id  -- 关联 ai_dimensions.id
initial_position -- 该风格下的初始位置
created_at
```

## ai_dimension_relationship_mappings

AI关系映射表，定义风格评分与关系类型的映射关系。

```txt
id -- 自增ID
dimension_id -- 关联ai_dimensions.id
start_position -- 起始位置，0-1000千分比
end_position -- 结束位置，0-1000千分比
relationship_id -- 关联ai_relationships.id
priority -- 优先级，数字越小优先级越高
limit_count -- 出现的次数限制
created_at
updated_at
```

## ai_personalities

AI人格表，定义 AI 实例的人格特征和提示词模板。

```txt
id -- 自增ID
display_name -- 显示名称
prompt -- 人格提示词模板
json_schema -- JSON模式定义
status -- 状态：1=active, 2=inactive
created_at
updated_at
```

## ai_personality_placeholders

AI人格占位符表，定义人格模板中的占位符。是一种声明，在编辑其他内容时会对照此表检查。

```txt
id -- 自增ID
personality_id -- 关联ai_personalities.id，NULL表示公共数据
placeholder_key -- 占位符键名
display_name -- 显示名称
description -- 描述说明
example_value -- 示例值
is_required -- 是否必填：1=required, 0=optional
created_at
updated_at
```

## ai_types

AI类型表，用于内部管理分组。

```txt
id -- 自增ID
display_name -- 显示名称
description -- 描述说明
created_at
updated_at
```

## ai_personas

AI设定表，管理角色的唯一qiao_id（类似商品SKU）。

```txt
id -- Snowflake ID
qiao_id -- qiao_+随机字符，外部使用，唯一标识
type_id -- 关联ai_types.id（内部管理）
is_reusable -- 是否可以复用：1=reusable（多用户可添加）, 0=single_use（仅一个用户可添加）
status -- 状态：1=active, 2=inactive, 3=used
created_at
updated_at
```

## ai_templates

AI模板表，管理实例化时所需的 Prompt、记忆、维度配置与打字参数。

```txt
id -- 自增ID
type_id -- 关联ai_types.id（内部管理）
display_name -- 显示名称
style_id -- 关联ai_styles.id
personality_id -- 关联ai_personalities.id
memory -- 记忆设定
prompt_variables -- 占位符覆盖值，JSON格式
request_params -- LLM请求参数覆盖配置，JSONB格式，用于覆盖默认LLM设置
timezone -- 默认 IANA 时区标识（如 Asia/Shanghai），用于实例化拷贝
typing_speed_wpm -- 模板层的打字速度（词/分钟，整数，必填），角色创建时拷贝，运行阶段若遇到非法值再退回 35 WPM
position_mapping_config -- JSON格式，存储各维度的mapping配置,示例：
{
  "foo": {"algorithm": 1, "params": {}},
  "bar": {
    "algorithm": 2,
    "params": {
      "left_sensitivity": 5,
      "right_sensitivity": -3,
      "left_positive_gain": 45,
      "left_negative_gain": 39,
      "right_positive_gain": 45,
      "right_negative_gain": 39
    }
  }
}
is_reusable -- 是否可以复用：1=reusable（可创建多个角色）, 0=single_use（仅创建一次）
priority -- 优先级，数字越小优先级越高（不可复用模板优先）
status -- 状态：1=active, 2=inactive, 3=used（仅单次模板会被置为已使用）
created_at
updated_at
```

## ai_instances

AI实例表，存储"用户 × persona"实例化后的联系人。

```txt
id -- Snowflake ID
user_id -- 关联 users.id
user_qiao_id -- 用户的 qiao_id
qiao_id -- persona 的对外 ID（可重复，多个用户可添加同一 persona）
style_id -- 关联 ai_styles.id
personality_id -- 关联 ai_personalities.id
status -- 状态：1=active, 2=inactive, 3=blocking
relationship_id -- 当前关系ID
relationship_counts -- 各关系类型使用次数统计，JSONB，如 {"friend":5,"lover":2}
memory -- 实例级记忆
prompt_variables -- 实例级占位符覆盖
request_params -- 实例级LLM请求参数覆盖
typing_speed_wpm -- 打字速度（词/分钟），默认沿用模板值
timezone -- IANA时区标识（如 Asia/Shanghai）
creation_metadata -- JSONB，创建时的完整快照（不可变），包含 source、persona_id、persona_qiao_id、persona_type_id、persona_type_name、persona_is_reusable、template_id、template_display_name、template_priority、assigned_at、assigned_by 等字段
created_by -- 创建者类型：1=user, 2=admin, 3=system
created_at
updated_at
```

**设计说明**：

- `user_id + qiao_id` 保证同一用户对同一 persona 只有一个实例（UNIQUE 约束）。
- `creation_metadata` 保存创建时的完整快照（persona、template、type 信息），用于审计和溯源，不受后续数据变更影响。
- 运行时只依赖 `qiao_id`（通过 profiles 获取展示信息）和实例自身的配置字段，不需要读取 persona 或 template 表。
- 所有与联系人、关系状态、消息记忆相关的字段仅保存在 `ai_instances`。
- persona 元数据（昵称、头像等）统一从 `profiles` 获取。

## ai_instance_dimensions

AI实例关系评分表，存储每个 `ai_instance` 的维度分值与位置。

```txt
id -- Snowflake ID
instance_id -- 关联 ai_instances.id
dimension_id -- 关联 ai_dimensions.id
score -- 当前分数值
position -- 千分比位置（0-1000）
position_mapping_algorithm -- 位置映射算法：1=直接映射, 2=V1独立双向偏移
position_mapping_params -- 位置映射参数（V1 算法必须提供 6 个字段）：
  {"left_sensitivity": 0, "right_sensitivity": 0, "left_positive_gain": 45, "left_negative_gain": 39, "right_positive_gain": 45, "right_negative_gain": 39}
created_at
updated_at
```

## llm_providers

LLM提供商配置表，管理不同的大模型提供商信息。

```txt
id -- 自增ID
name -- 提供商标识，如doubao、openai、claude等（允许重复）
display_name -- 显示名称（必须唯一，用于区分同一 Provider 的不同配置）
api_key_env -- API Key 环境变量名（可选，默认为 {NAME}_API_KEY）
base_url -- API基础URL
default_model -- 默认模型名称
supports_streaming -- 是否支持流式输出：1=yes, 0=no
supports_json_schema -- 是否支持JSON Schema：1=yes, 0=no
supports_thinking -- 是否支持思考模式：1=yes, 0=no
created_at
updated_at
```

## llm_configs

LLM运行时配置表，管理具体的模型配置参数。

```txt
id -- 自增ID
provider_id -- 关联llm_providers.id
name -- 配置标识，如primary、backup、test等，唯一
model_name -- 具体模型名称，可选
temperature -- 温度参数，0.0-2.0
max_tokens -- 最大token数
timeout_seconds -- 超时时间（秒）
thinking_mode -- 思考模式：enabled（强制开启）/disabled（强制关闭）/auto（由模型决定）
top_p -- Nucleus Sampling 阈值，[0,1]
frequency_penalty -- 频率惩罚系数，[-2,2]
presence_penalty -- 存在惩罚系数，[-2,2]
stop_sequences -- 停止序列（JSONB，字符串数组）
json_schema_mode -- JSON Schema支持状态
  - 'strict': 已验证支持JSON Schema（测试通过，可用于AI Instance）
  - 'disabled': 已验证不支持JSON Schema（测试失败，仅供查看测试响应）
  - 'auto': 未验证（默认值，需要先测试）
default_tools -- 默认工具定义（JSONB数组），如[{"type": "web_search"}]
default_tool_choice -- 工具选择策略：auto（自动）/none（不使用）/required（必须使用），默认auto
parallel_tool_calls -- 是否允许并行工具调用：1=yes, 0=no，默认0
max_tool_calls -- 单次请求最大工具调用次数，默认1
default_extra_headers -- 默认额外请求头（JSONB），如{"ark-beta-web-search": "true"}
default_extra_query -- 默认额外查询参数（JSONB）
status -- 状态：1=active, 2=inactive
priority -- 优先级，数字越小优先级越高，用于故障转移
extra_params -- 其他的参数
created_at
updated_at
```

## ai_request_logs

AI请求日志表，记录所有AI请求和响应（包括生产环境和测试环境）。

```txt
id -- Snowflake ID
instance_id -- 关联ai_instances.id
user_id -- 关联users.id
style_id -- 关联ai_styles.id
personality_id -- 关联ai_personalities.id
request_type -- 请求类型：production（生产环境）或test（测试环境），默认production
provider_name -- LLM提供商名称（如doubao, openai, mock等）
model_name -- 使用的模型名称
request -- 请求内容，JSONB格式
response -- 响应内容，JSONB格式
status -- 请求状态：1=success, 2=failed, 3=timeout
token_count -- 消耗的token数量
response_time -- 响应时间（毫秒）
llm_config_id -- 使用的LLM配置ID
buffer_id -- 关联的 ai_message_buffer.id（assistant 消息）
created_at -- 请求创建时间
completed_at -- 请求完成时间
```

## llm_test_logs

LLM配置测试日志表，专门记录通过管理后台进行的LLM配置测试。

```txt
id -- Snowflake ID
config_id -- 关联llm_configs.id
config_name -- 配置名（冗余字段，便于查询）
provider_name -- Provider名称（冗余字段）
model_name -- 使用的模型名称
test_message -- 测试消息内容，TEXT类型
override_temperature -- 覆盖的温度参数（0.0-2.0）
override_max_tokens -- 覆盖的最大token数
thinking_mode -- 思考模式：enabled / disabled / auto
enable_json_schema -- 是否启用json_schema
request -- 完整请求payload，JSONB格式
response -- 完整响应数据，JSONB格式
status -- 状态：1=success, 2=failed, 3=timeout
error_message -- 错误信息（如果失败），TEXT类型
response_time_ms -- 响应时间（毫秒）
prompt_tokens -- 提示词token数
completion_tokens -- 完成token数
total_tokens -- 总token数
reasoning_content -- 思考过程内容（思考模式启用时），TEXT类型
created_at -- 测试创建时间
completed_at -- 测试完成时间
```

## contact_requests

联系人申请表。

```txt
id -- Snowflake ID
from_qiao_id -- 申请发起者外部ID
from_type -- 申请发起者类型：1=user (包括所有用户类型), 2=ai
from_id -- 申请发起者内部ID
to_qiao_id -- 申请接收者外部ID
to_type -- 申请接收者类型：1=user (包括所有用户类型), 2=ai
to_id -- 申请接收者内部ID
message -- 附加申请说明（例如“我是xxx”）
source -- 来源渠道：1=search, 2=admin, 3=system, 4=recommend
status -- 申请状态：1=pending, 2=accepted, 3=ignored, 8=processing, 9=failed
failure_code -- 模板不足等业务失败原因（挂起记录会填写）
failure_detail -- JSONB，包含 type_id、qiao_id、request_id 等定位信息
retry_count -- 手动或自动重试次数
last_retry_at -- 最近一次重试时间
expires_at -- 申请过期时间
created_at
updated_at
```

## user_violation_logs

用户安全日志表，记录用户恶意行为检测结果。

```txt
id -- Snowflake ID
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id
instance_id -- 关联ai_instances.id（如果涉及特定AI）
instance_qiao_id -- 关联ai_instances.qiao_id
violation_type -- 违规类型：1=prompt_injection, 2=abuse_content, 3=spam, 4=harassment, 5=other
severity_level -- 严重程度：1=low, 2=medium, 3=high, 4=critical
original_message -- 原始用户消息
auto_action_taken -- 自动处理动作：1=none, 2=warning, 3=restrict, 4=suspend
manual_review_status -- 人工审核状态：1=pending, 2=confirmed, 3=false_positive, 4=ignored
reviewer_id -- 审核管理员ID
review_notes -- 审核备注
created_at
updated_at
```

## user_risk_stats

用户安全统计表，汇总用户的违规行为统计。

```txt
id -- Snowflake ID
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id
total_violations -- 总违规次数
violation_by_type -- 按类型统计，JSON格式：{"prompt_injection": 5, "abuse": 2}
last_violation_at -- 最后违规时间
current_risk_level -- 当前风险等级：1=low, 2=medium, 3=high, 4=banned
consecutive_violations -- 连续违规次数（清零条件：7天无违规）
warning_count -- 警告次数
restriction_count -- 限制次数
suspension_count -- 停用次数
last_action_at -- 最后处理动作时间
created_at
updated_at
```

## system_configs

系统配置表，存储系统级配置参数。

```txt
id -- 自增ID
config_key -- 配置键名，唯一
config_value -- 配置值
default_value -- 默认配置值
config_type -- 配置类型：1=string, 2=number, 3=boolean, 4=json
description -- 配置描述
group_name -- 分组名称，用于显示分组
allowed_values -- 用于枚举类型的可选项存储（JSONB）
updated_by -- 更新者ID
created_at
updated_at
```

## stats_user_daily/weekly/monthly

用户统计表（按日/周/月）。每天凌晨统计daily数据，周一凌晨统计weekly数据，每月1日凌晨统计monthly数据。

```txt
id -- 自增ID
stat_date -- 统计日期
total_users -- 总用户数
new_users -- 新增用户数
active_users -- 活跃用户数
subscriptions -- 总订阅用户数
new_subscriptions -- 新订阅用户数
canceled_subscriptions -- 退订用户数
created_at
```

## stats_revenue_daily/weekly/monthly

收入统计表（按日/周/月）。

```txt
id -- 自增ID
stat_date -- 统计日期
total_revenue -- 总收入
orders_count -- 订单数量
avg_order_amount -- 平均订单金额
refund_amount -- 退款金额
created_at
```

## stats_message_daily/weekly/monthly

消息统计表（按日/周/月）。

```txt
id -- 自增ID
stat_date -- 统计日期
total_messages -- 总消息数
avg_messages_per_user -- 人均消息数
active_conversations -- 活跃对话数
created_at
```

## stats_ai_daily/weekly/monthly

AI统计表（按日/周/月）。

```txt
id -- 自增ID
stat_date -- 统计日期
ai_personas -- Persona 总数
active_ai_personas -- 活跃 Persona 数
ai_requests_count -- 请求总数
avg_ai_requests_per_user -- 人均请求数
created_at
```

## admin_users

管理员用户表，存储后台管理员账户信息。

```txt
id -- 自增ID
username -- 管理员用户名，唯一
password_hash -- 密码哈希值
role -- 角色类型：1=super_admin, 2=admin, 3=viewer
status -- 账户状态：1=active, 2=inactive
last_login -- 最后登录时间
login_count -- 登录次数
created_by -- 创建者ID（admin_user_id或system）
created_at
updated_at
```

## admin_operation_logs

管理员操作日志表，记录所有管理员操作。

```txt
id -- 自增ID
admin_user_id -- 关联admin_users.id
operation_type -- 操作类型：1=CREATE, 2=UPDATE, 3=DELETE, 4=ENABLE, 5=DISABLE
resource_type -- 资源类型：1=user, 2=ai_persona, 3=config, 4=admin等
resource_id -- 资源ID
resource_name -- 资源名称
operation_desc -- 操作描述
ip_address -- 操作IP地址
user_agent -- 用户代理信息
created_at
```

## admin_login_logs

管理员登录日志表，记录管理员登录历史。

```txt
id -- 自增ID
admin_user_id -- 关联admin_users.id
username -- 登录用户名
user_agent -- 用户代理信息
ip_address -- 登录IP地址
result -- 登录结果：1=success, 2=fail
fail_reason -- 失败原因
created_at
```

## user_invitations（2.0功能）

id
inviter_id       -- 邀请人用户ID
inviter_qiaoid
invitee_id       -- 被邀请人用户ID（注册后绑定），注册前可以为NULL
invitee_qiaoid
invite_code      -- 邀请码
status           -- pending, accepted, registered, rewarded
created_at
updated_at

## 邀请奖励规则表 invite_reward_rules （2.0功能）

配置不同条件下的奖励内容。

id
event_type       -- 注册完成、新用户活跃7天、首单支付等
reward_type      -- contact_slot, points, quota, subscription_days
reward_value     -- 奖励数值（如1栏位、100积分、30天VIP）
status           -- active, inactive
created_at
updated_at

## 奖励发放记录表 invite_rewards

id
invitation_id    -- 对应 user_invitations
user_id          -- 获奖用户
reward_type      -- contact_slot, points, quota, subscription_days
reward_value
status           -- pending, granted, revoked
granted_at
created_at
updated_at

确保奖励发放有日志，不会丢单。

支持“撤回奖励”（如用户作弊）。

## 用户权益扩展表（选用）

如果奖励是 联系人栏位 +1 这种功能性权益，可以直接存在 quota 表里，或者单独建一张 user_entitlements。

id
user_id
entitlement_type -- contact_slots, search_limit, ai_clone, etc.
value            -- 当前值（默认值 + 奖励值）
source           -- invite, subscription, purchase
expire_at        -- NULL 表示永久
updated_at

统一管理用户的 功能权益（不限于邀请奖励）。

和订阅、商城购买逻辑兼容。

## subscription_plans （2.0功能）

## subscriptions（2.0功能）

```txt
id
user_id
plan -- 等级写死
status -- active,expired,canceled,trial
start_date
end_date
auto_renew
created_at
updated_at
```

## wallets（2.0功能）

```txt
id
user_id
currency_type -- 写死 points,coins,gems
balance
updated_at
```

## wallet_transactions（2.0功能）

```txt
id
user_id
currency_type
change_amount -- 正数增加，负数扣除
balance_after -- 变动后的余额
reason_code -- 'purchase', 'reward', 'exchange', 'refund', 'system_adjustment'
metadata JSON -- 附加信息，比如订单号、活动ID
created_at
```

## quota（2.0功能）

```txt
id
user_id
quota_type -- 写死 chat_tokens
current_usage -- 已用量
total_value -- 配额上限
reset_cycle -- 重置周期
reset_at -- 下次重置时间
updated_at
```

## user_entitlements_summary（汇总表，方便查询总额）

id
user_id
entitlement_type   -- contact_slots
total_value        -- 汇总的有效上限（计算得出）
used_value         -- 已用量
updated_at

## user_entitlement_batches（批次表，精确记录每一份来源）

id
user_id
entitlement_type   -- contact_slots
value              -- 本批次数量 (+10, +5)
used_value         -- 本批次已使用量（可选）
source             -- invite, subscription, promotion, system
expire_at          -- NULL = 永久，否则到期时间
created_at

## quota_usage_log（2.0功能）

```txt
id
user_id
quota_type
reason_code -- 'chat', 'system_adjust', 'purchase_extra'
metadata
created_at
```

## orders（2.0功能）

交易类表要使用事务。

```txt
id
user_id
order_no -- 订单编号
amount -- 金额
currency
pay_method -- wechat,apple,alipay
status -- pending,paid,failed,refunded
created_at
paid_at
```
