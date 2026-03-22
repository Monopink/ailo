# 账户安全：密码管理（change / reset）

## 目标

- 定义并落地“修改密码 / 重置密码”的接口与规则（账号密码登录体系的一部分）。

## 现状

- 后端当前未提供密码管理相关接口实现。
- `docs/api/account-security.md` 已移除密码管理接口入口。

## 预期接口范围

- `PUT /api/v1/user/password`：已登录用户修改密码（要求二次验证，例如 operation_token）
- `POST /api/v1/user/password/reset`：重置密码（需要明确触发前置验证方式）

## 依赖

- 统一验证机制：`POST /api/v1/auth/user/verify/send-code` + `POST /api/v1/auth/user/verify/confirm`
- 登录安全规范：`docs/spec/user/login-security.md`
