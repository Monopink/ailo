# 系统配置

管理系统级配置参数。

## system_configs

系统配置表，存储系统级配置参数。

```txt
id -- 自增ID
config_key -- 配置键名，唯一
config_value -- 运行时配置值
default_value -- 管理端展示用默认值
config_type -- 配置类型（enum: ConfigType）
description -- 配置描述
group_name -- 分组名称，用于显示分组
allowed_values -- 用于枚举类型的可选项存储（JSONB）
updated_by -- 更新者ID
created_at
updated_at
```
