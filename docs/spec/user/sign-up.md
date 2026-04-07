## 用户注册初始化规则

- 新创建的用户会在手机号/微信登录阶段立刻生成 profile stub，字段以默认昵称、性别 unknown 填充。默认昵称格式为 `system_configs.default_nickname_prefix + 随机大写字母后缀`，其中后缀长度由 `system_configs.default_nickname_suffix_length` 决定。未上传头像时 avatar_key 和 avatar_media_id 均为空，后端默认 avatars/default.webp，确保任意接口都能获得可用的头像 URL。
- 当 `PUT /api/v1/user/profile` 成功写入资料后，对应 `users.needs_profile_setup` 会变为 0，同时 `profiles` 表保留最新头像、昵称、region 等信息，并追加一条 `user_profile_logs` 记录。
