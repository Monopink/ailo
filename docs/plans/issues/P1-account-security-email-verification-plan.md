# 账户安全：邮箱验证码（send-code / verify / bind / change）

## 当前实现状态

- 相关实现文件：`backend/app/api/v1/account_security.py`
- 已存在接口：
  - `POST /api/v1/user/email/send-code`
  - `POST /api/v1/user/email`
  - `PUT /api/v1/user/email`
  - `DELETE /api/v1/user/email`
- 目前代码中仍保留 TODO 注释，功能未完整实现。

## 未完成点（代码内 TODO）

1) 发送邮箱验证码
- 位置：`backend/app/api/v1/account_security.py:61`
- TODO：`Implement email verification code sending`
- 当前行为：校验邮箱格式后直接抛出 501。

2) 绑定邮箱验证码校验
- 位置：`backend/app/api/v1/account_security.py:106`
- TODO：`Verify email code`
- 当前行为：跳过验证码校验并直接绑定邮箱。

3) 修改邮箱验证码校验
- 位置：`backend/app/api/v1/account_security.py:161`
- TODO：`Verify email code`
- 当前行为：跳过验证码校验并直接修改邮箱。

## 关联说明

- 文档：`docs/api/account-security.md`
- 错误码注册：`docs/api/error-codes.md` 与 `backend/app/exceptions/error_codes.py`
