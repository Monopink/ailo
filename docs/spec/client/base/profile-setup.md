# 资料设置

本规范定义首次登录/需要补全资料时的通用设置流程。

## 触发条件

- 后端返回 `needs_profile_setup=true`
- 用户 `nickname` 为空

## 字段要求

- 头像：可选；未设置时由后端返回默认头像 URL
- 昵称：必填，长度由环境变量控制
- 性别：必填（男/女/其他）
- 个性签名：可选，长度由环境变量控制
- 地区：可选，字段规范与展示规范见 `profile-and-settings.md`

## 提交流程

1. 用户填写资料
2. 地区字段提交 `region_country_code`、`region_cn_city_code`、`region_province_name`、`region_city_name`
3. 调用 [更新资料接口](../../../api/user.md#更新用户资料)
4. 成功后进入主界面

## 错误处理

- 提交失败：提示错误并停留本页，不允许跳过
- 必填项缺失：禁用完成按钮或提示缺失
