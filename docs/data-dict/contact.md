# 联系人

管理用户之间的联系关系和联系人申请。

## contacts

联系人关系表，管理用户之间的联系关系。

```txt
id -- Snowflake ID
conversation_id -- conv_+随机字符，外部使用，对话标识
user_id -- 联系人所属用户ID，NULL表示公共联系人
user_qiao_id -- 联系人所属用户外部ID，NULL表示公共联系人
contact_type -- 联系人类型：1=user, 2=ai, 3=official
contact_id -- 联系人内部ID
contact_qiao_id -- 联系人外部ID
alias -- 备注称
custom_avatar_key -- 备注头像对象键
custom_avatar_media_id -- 备注头像媒资记录ID，关联 media_files.id
avatar_display_mode -- 头像展示模式：1=original(原始头像), 2=custom(备注头像)
tags -- 标签JSON数组：["tag1","tag2"]
remark -- 备注描述
source -- 添加来源：0=unknown, 1=search, 2=admin, 3=system, 4=recommend, 5=discovery, 6=contact_request
is_pinned -- 是否置顶：1=yes, 0=no
is_muted -- 是否免打扰：1=yes, 0=no
is_blocked -- 是否屏蔽：1=yes, 0=no
is_deleted -- 是否删除：1=yes, 0=no
deleted_at -- 删除时间
created_at
updated_at
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
to_id -- 申请接收者内部ID（可为空：AI instance 未创建时）
message -- 附加申请说明
category_key -- 来源分类键（kebab-case，可为空）
alias -- 申请时备注（可为空）
tags -- 申请时标签数组（jsonb，可为空；非空时用于写入 contacts.tags）
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
