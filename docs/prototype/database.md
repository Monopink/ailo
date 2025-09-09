# 数据库设计文档

## 设计原则

1. 不使用外键约束：通过代码逻辑维护数据一致性，提高性能和灵活性
2. 统一标识符命名：外部标识符统一使用`qiao_id`格式，内部使用Snowflake ID
3. 枚举值使用整型：所有枚举字段使用TINYINT类型，在代码中定义枚举约束
4. 核心业务表使用Snowflake ID：用户、消息、AI等核心表使用BIGINT类型的Snowflake ID
5. 配置表使用自增ID：系统配置、统计等辅助表使用AUTO_INCREMENT
6. 完善的索引设计：为高频查询字段添加合适的索引
7. 时间字段自动管理：created_at和updated_at字段自动设置和更新
8. ID类型使用规范：
   - 内部使用int：后端数据层、服务层统一使用 `int` 类型处理Snowflake ID
   - 外部使用string：API接口、前端交互使用字符串格式避免JavaScript精度问题
   - 转换边界：在API层进行类型转换，保持数据层类型纯净

## 详细表结构

## users

用户基础信息表，存储用户账户数据。

```txt
id -- Snowflake ID
qiao_id -- qiao_+随机字符，外部使用，唯一标识
username -- 用户名，初始默认为qiao_id
phone -- 手机号，用于登录验证
email -- 邮箱地址
password_hash -- 密码哈希值
wechat_openid -- 微信授权登录标识
apple_id -- Apple授权登录标识
status -- 账户状态：1=active, 2=inactive, 3=suspended
user_type -- 用户类型：1=normal, 2=official, 3=admin
last_login -- 最后登录时间
created_at
updated_at
```

## user_sessions

用户会话管理表，管理登录状态和设备限制。

```txt
id -- Snowflake ID
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id，冗余字段便于查询
session_token -- 会话令牌，唯一
device_type -- 设备类型：1=ios, 2=android, 3=web, 4=mini_program
device_id -- 设备唯一标识
platform_info -- 平台信息JSON
ip_address -- 登录IP地址
user_agent -- 用户代理信息
expires_at -- 会话过期时间
is_active -- 是否活跃：1=active, 0=inactive
last_activity_at -- 最后活动时间
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
avatar_alias_url -- 备注头像URL
tags -- 标签JSON数组：["tag1","tag2"]
remark -- 备注描述
is_pinned -- 是否置顶：1=yes, 0=no
is_muted -- 是否免打扰：1=yes, 0=no
is_blocked -- 是否屏蔽：1=yes, 0=no
is_deleted -- 是否删除：1=yes, 0=no
deleted_at -- 删除时间
created_at
updated_at
```

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
session_token -- 关联的会话令牌
created_at
```

## message_history

消息历史记录表，只有发送成功后才写入数据。

```txt
id -- Snowflake ID
direction -- 消息方向：1=inbound, 2=outbound
platform -- 平台：1=ios, 2=android, 3=web, 4=mini_program（入站消息使用）
conversation_id -- 对话ID，关联contacts.conv_id
msg_id_server -- msg_+(Snowflake+Base36)，外部使用，发送消息使用
msg_id_provider -- 第三方消息服务生成的消息ID
msg_id_client -- 客户端消息ID，接收消息使用
client_sent_time -- 消息中包含的客户端发送时间
from_type -- 发送方类型：1=user, 2=ai, 3=admin, 4=system
from_id -- 发送方内部ID
from_qiao_id -- 发送方外部ID
to_type -- 接收方类型：1=user, 2=ai, 3=admin, 4=system
to_id -- 接收方内部ID
to_qiao_id -- 接收方外部ID
service_provider -- 服务提供商：1=leancloud, 2=internal
message_type -- 消息类型：1=text, 2=typing, 3=typing_end, 4=system, 5=image, 6=emoji
content -- 消息内容
status -- 消息状态：1=sent, 2=delivered, 3=read, 4=failed
message_metadata -- 消息元数据JSON
created_at
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
service_provider -- 服务提供商：1=leancloud, 2=internal
message_type -- 消息类型：1=text, 2=typing, 3=typing_end, 4=system, 5=image, 6=emoji
content -- 消息内容
fail_reason_code -- 失败原因代码
fail_detail -- 详细错误信息/堆栈，TEXT类型
retry_count -- 重试次数，默认0
max_retry_count -- 最大重试次数，默认3
next_retry_at -- 下次重试时间
created_at
updated_at
```

## ai_contexts

AI对话上下文表，收到对AI消息立即写入。

```txt
id -- Snowflake ID
character_id -- 关联ai_characters.id
character_qiao_id -- 关联ai_characters.qiao_id
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id
role -- 角色类型：1=user, 2=ai, 3=system
content -- 消息内容
source_type -- 来源类型：1=original, 2=merged, 3=summarized
source_message_ids -- 源消息ID列表，JSON数组
context_metadata -- 上下文元数据，JSON
position -- 上下文在会话中的顺序位置
token_count -- 消息token数量
is_attack -- 是否为攻击消息：1=yes, 0=no
reply_status -- 回复状态：1=pending 2=processing 3=done
created_at
updated_at
```

## ai_contexts_archive

参照ai_contexts表结构，用于归档。

## emoticons

```txt
id -- 自增ID
code -- 唯一标识，如"smile"或"emoji_1"
category -- 表情分类：1=system, 2=custom, 3=premium
file_id -- 关联media_files.id
url -- 图片资源地址（冗余字段，便于查询）
description -- 表情描述
created_by_type -- 创建者类型：1=user, 2=system, 3=admin
created_by_id -- 创建者ID
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
owner_qiao_id -- 所有者外部ID
owner_type -- 所有者类型：1=user, 2=ai, 3=official
nickname -- 昵称
gender -- 性别：1=male, 2=female, 3=other, 4=unknown
avatar_file_id -- 头像文件ID，关联media_files.id
avatar_url -- 头像URL（冗余字段，便于查询）
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
owner_type -- 所有者类型：1=user, 2=ai, 3=official
modified_by_type -- 修改者类型：1=user, 2=admin, 3=system
field_name -- 修改的字段名，例如 nickname, avatar_url, bio
old_value -- 旧值
new_value -- 新值
change_reason -- 修改原因（例如用户提交、管理员修改）
created_at
```

## ai_relationships

AI关系类型表，定义AI角色的关系类型。usage_count不为0不允许修改status。

```txt
id -- 自增ID
name -- 关系名称
display_name -- 显示名称
prompt_fragment -- 提示词片段
usage_count -- 被引用的数量
status -- 状态：1=active, 2=inactive
created_at
updated_at
```

## ai_styles

AI风格表，定义AI角色的风格类型和评分维度。

```txt
id -- 自增ID
name -- 风格名称
display_name -- 用于显示的名称
usage_count -- 被引用的数量
status -- 状态：1=active, 2=inactive
created_at
updated_at
```

## ai_relationship_dimensions

```txt
id -- 自增ID
style_id
name -- 用于通过llm响应查询的名称
display_name -- 用于显示的名称
initial_position -- 起始位置，0-1000千分比
status
created_at
updated_at
```

## ai_relationship_indexes

AI关系索引表，定义风格评分与关系类型的映射关系。

```txt
id -- 自增ID
style_id -- 关联ai_styles.id
dimension_id
dimension_name -- 维度名称
start_position -- 起始位置，0-1000千分比
end_position -- 结束位置，0-1000千分比
relationship_id -- 关联ai_relationship.id
priority -- 优先级
limit_count -- 出现的最大次数，NULL表示无限制
created_at
updated_at
```

## ai_personalities

AI人格表，定义AI角色的人格特征和提示词模板。

```txt
id -- 自增ID
name -- 人格名称
prompt -- 人格提示词模板
json_schema -- JSON模式定义
typing_speed -- 打字速度
usage_count -- 被引用的数量
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

## ai_profile_templates

AI资料模板表，存储AI角色的资料模板。索引nickname字段。is_reusable字段需要和info一致才能关联，关联info后不允许修改status。

```txt
id -- 自增ID
qiao_id -- qiao_+随机字符，外部使用
category -- 分类，可选项写死
info_id -- 绑定的ai_info_templates.id
nickname -- 昵称
gender -- 性别：1=male, 2=female, 3=other, 4=unknown
avatar_url -- 头像URL
bio -- 个人简介
region -- 地区
is_reusable -- 是否可以复用：1=reusable, 0=single_use（不可复用使用完后删除）
status -- 状态：1=active, 2=inactive
created_at
updated_at
```

## ai_info_templates

AI信息模板表，存储AI角色的核心配置信息。

```txt
id -- 自增ID
style_id -- 关联ai_styles.id
personality_id -- 关联ai_personalities.id
memory -- 记忆设定
prompt_variables -- 占位符覆盖值，JSON格式
score_offset_algorithm -- 分数偏移算法
score_offset_coefficient -- 分数偏移系数
is_reusable -- 是否可以复用：1=reusable, 0=single_use
profile_count -- 统计关联的资料模板数量
profile_id -- 如果不可复用则存入对应资料模板id
status -- 状态：1=active, 2=inactive
created_at
updated_at
```

## ai_characters

AI角色表，存储具体的AI角色实例。

```txt
id -- Snowflake ID
qiao_id -- qiao_+随机字符，外部使用
category -- 角色分类
user_id -- 关联users.id，所属用户
user_qiao_id -- 关联users.qiao_id，所属用户外部ID
status -- 状态：1=active, 2=inactive，3=blocked
style_id -- 关联ai_styles.id
personality_id -- 关联ai_personalities.id
memory -- 角色记忆设定
prompt_variables -- 占位符覆盖值，JSON格式
score_offset_algorithm -- 分数偏移算法
score_offset_params -- 分数偏移参数
created_by -- 创建者类型：1=user, 2=admin, 3=system
created_at
updated_at
```

## ai_relationship_scores

AI关系评分表，存储AI角色的关系评分数据和关系使用统计。

```txt
id -- Snowflake ID
character_id -- 关联ai_characters.id
dimension_id -- 关联ai_relationship_dimensions.id
dimension_name -- 维度名称
score -- 当前分数值，初始化时根据position和score_offset_algorithm反向计算得出
position -- 千分比位置（0-1000）
relationship_id -- 当前匹配的关系类型ID
relationship_display_name -- 关系类型显示名称
score_offset_algorithm -- 分数偏移算法
score_offset_params -- 分数偏移参数，JSON格式
relationship_counts -- 各关系类型使用次数统计，JSON格式：{"friend":5,"lover":2}
created_at
updated_at
```

## ai_request_logs

AI请求日志表，记录所有AI请求和响应。

```txt
id -- Snowflake ID
character_id -- 关联ai_characters.id
user_id -- 关联users.id
style_id -- 关联ai_styles.id
personality_id -- 关联ai_personalities.id
request -- 请求内容，JSON格式
response -- 响应内容，JSON格式
status -- 请求状态：1=success, 2=failed, 3=timeout
token_count -- 消耗的token数量
response_time -- 响应时间（毫秒）
created_at
```

## contact_requests

联系人申请表，管理用户之间的联系人申请。

```txt
id -- Snowflake ID
from_qiao_id -- 申请发起者外部ID
from_type -- 申请发起者类型：1=user, 2=ai, 3=official
from_id -- 申请发起者内部ID
to_qiao_id -- 申请接收者外部ID
to_type -- 申请接收者类型：1=user, 2=ai, 3=official
to_id -- 申请接收者内部ID
message -- 附加申请说明（例如“我是xxx”）
source -- 来源渠道：1=search, 2=admin, 3=system, 4=invite
status -- 申请状态：1=pending, 2=accepted, 3=rejected, 4=expired
expires_at -- 申请过期时间
created_at
updated_at
```

## user_security_logs

用户安全日志表，记录用户恶意行为检测结果。

```txt
id -- Snowflake ID
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id
character_id -- 关联ai_characters.id（如果涉及特定AI）
character_qiao_id -- 关联ai_characters.qiao_id
violation_type -- 违规类型：1=prompt_injection, 2=abuse_content, 3=spam, 4=harassment, 5=other
severity_level -- 严重程度：1=low, 2=medium, 3=high, 4=critical
original_message -- 原始用户消息
ai_detection_result -- AI检测结果，JSON格式
confidence_score -- 置信度分数（0-100）
auto_action_taken -- 自动处理动作：1=none, 2=warning, 3=restrict, 4=suspend
manual_review_status -- 人工审核状态：1=pending, 2=confirmed, 3=false_positive, 4=ignored
reviewer_id -- 审核管理员ID
review_notes -- 审核备注
created_at
updated_at
```

## user_security_stats

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

## system_config

系统配置表，存储系统级配置参数。

```txt
id -- 自增ID
config_key -- 配置键名，唯一
config_value -- 配置值
config_type -- 配置类型：1=string, 2=number, 3=boolean, 4=json
description -- 配置描述
is_public -- 是否公开：1=public, 0=private
created_at
updated_at
updated_by -- 更新者ID
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
ai_characters -- 角色总数
active_ai_characters -- 活跃角色数
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
resource_type -- 资源类型：1=user, 2=ai_character, 3=config, 4=admin等
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

## llm_providers

LLM提供商配置表，管理不同的大模型提供商信息。

```txt
id -- 自增ID
name -- 提供商标识，如doubao、openai、claude等，唯一
display_name -- 显示名称
base_url -- API基础URL
api_key_env -- 环境变量名，如ARK_API_KEY
default_model -- 默认模型名称
supports_streaming -- 是否支持流式输出：1=yes, 0=no
supports_json_schema -- 是否支持JSON Schema：1=yes, 0=no
supports_thinking -- 是否支持思考模式：1=yes, 0=no
status -- 状态：1=active, 0=inactive
created_at
updated_at
```

## llm_configs

LLM运行时配置表，管理具体的模型配置参数。

```txt
id -- 自增ID
provider_id -- 关联llm_providers.id
config_key -- 配置标识，如primary、backup、test等，唯一
model_name -- 具体模型名称，可选
temperature -- 温度参数，0.0-2.0
max_tokens -- 最大token数
timeout_seconds -- 超时时间（秒）
max_retries -- 最大重试次数
enable_streaming -- 是否启用流式输出：1=yes, 0=no
enable_thinking -- 是否启用思考模式：1=yes, 0=no
json_schema_mode -- JSON Schema模式：auto、strict、disabled
is_active -- 是否激活：1=yes, 0=no
priority -- 优先级，数字越小优先级越高，用于故障转移
created_at
updated_at
```

## 核心架构设计

### 用户管理模块

#### users - 用户账户表

- 主键：id (Snowflake ID)
- 外部标识：qiao_id (qiao_+随机字符)
- 登录方式：支持手机号、微信、Apple ID多种登录
- 状态管理：账户状态、用户类型分级管理
- 关键索引：qiao_id、phone、email、status等

#### user_sessions - 用户会话表

- 会话管理：支持多设备登录，每种设备类型限制一个活跃会话
- 安全控制：记录设备信息、IP地址、用户代理
- 过期机制：自动过期和活跃度跟踪

#### contacts - 联系人关系表

- 关系管理：用户与AI、用户与用户的联系关系
- 对话标识：每个联系关系对应一个conv_id
- 个性化设置：备注、标签、置顶、免打扰等功能
- 软删除：支持删除标记和恢复

### 消息系统模块

#### message_history - 消息历史表

- 消息方向：入站/出站消息区分
- 多端支持：记录消息来源平台
- 服务提供商：支持LeanCloud等第三方消息服务
- 消息类型：文本、输入状态、系统消息、图片、表情等
- 状态跟踪：发送、送达、已读、失败状态

#### message_delivery_failures - 消息投递失败表

- 重试机制：自动重试失败消息，支持指数退避
- 失败分析：详细记录失败原因和错误信息
- 清理机制：成功重发后自动删除记录

### 资料管理模块

#### profiles - 统一资料表

- 多类型支持：用户、AI、官方账号统一管理
- 头像管理：支持文件ID引用和URL冗余
- 个性化信息：昵称、性别、简介、地区等

#### media_files - 媒体文件表

- 文件类型：头像、表情、图片、文档分类管理
- 上传追踪：记录上传者信息和上传时间
- 状态管理：活跃、非活跃、已删除状态

### AI系统模块

#### AI关系系统设计

- ai_relationship：定义关系类型（陌生人、朋友、恋人等）
- ai_styles：定义AI风格
- ai_relationship_dimensions：定义评分维度配置
- ai_relationship_indexes：映射评分区间到关系类型
- ai_personalities：AI人格模板和提示词
- ai_personality_placeholders：人格模板占位符定义

#### AI实例管理

- ai_characters：具体的AI角色实例
- ai_contexts：AI对话上下文管理
- ai_relationship_scores：AI关系评分数据和统计
- ai_request_logs：AI服务请求日志

### 安全监控模块

#### user_security_logs - 用户安全日志

- 违规检测：提示词注入、滥用内容、垃圾信息等
- 严重程度：低、中、高、严重四级分类
- 自动处理：警告、限制、停用等自动措施
- 人工审核：支持管理员人工审核和标记

#### user_security_stats - 用户安全统计

- 风险评估：基于违规历史的用户风险等级
- 统计数据：违规次数、类型分布、处理历史
- 动态调整：连续违规计数和风险等级自动调整

### 系统管理模块

#### system_config - 系统配置

- 配置分类：字符串、数字、布尔值、JSON类型
- 公开配置：区分公开和私有配置
- 变更追踪：记录配置更新者和更新时间

#### 统计报表系统

- 多维度统计：用户、消息、AI、收入四个维度
- 多时间粒度：日、周、月三种统计粒度
- 自动生成：定时任务自动生成统计数据

#### 管理员系统

- 权限分级：超级管理员、管理员、查看者三级权限
- 操作审计：完整记录管理员操作日志
- 登录追踪：管理员登录历史和安全监控

## 索引设计策略

### 主要索引类型

1. 唯一索引：外部标识符、用户名、邮箱等
2. 复合索引：多字段组合查询优化
3. 时间索引：按时间范围查询优化
4. 状态索引：按状态筛选优化
5. 外键索引：关联查询性能优化

### 查询优化考虑

- 聊天列表查询：按用户ID和时间排序
- 消息历史查询：按对话ID和时间范围
- 联系人搜索：按昵称和标签模糊匹配
- 统计报表查询：按日期范围和维度聚合
- 安全监控查询：按用户和违规类型筛选

## 数据一致性保证

### 应用层约束

- 枚举值验证：在应用代码中定义和验证枚举值
- 关联关系检查：在业务逻辑中维护数据关联一致性
- 事务管理：关键操作使用数据库事务保证原子性

### 数据清理策略

- 过期会话清理：定期清理过期的用户会话
- 失败消息清理：成功重试后删除失败记录
- 日志归档：定期归档历史日志数据
- 统计数据维护：定期更新和校验统计数据

## 扩展性考虑

### 水平扩展

- Snowflake ID支持分布式环境
- 无外键约束便于数据分片
- 读写分离友好的索引设计

### 功能扩展

- 预留字段：JSON类型字段支持灵活扩展
- 模块化设计：各功能模块相对独立
- 版本兼容：向后兼容的数据结构设计

## 安全性设计

### 数据保护

- 敏感信息加密：密码哈希、令牌加密
- 访问控制：基于角色的权限管理
- 审计日志：完整的操作审计追踪

### 隐私保护

- 数据脱敏：日志中不记录敏感信息
- 用户控制：用户可控制个人信息可见性
- 数据清理：支持用户数据删除和匿名化
