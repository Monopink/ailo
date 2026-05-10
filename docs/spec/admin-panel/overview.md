# 管理端总览

管理端是内部运营与联调工具，不直接面向终端用户。

## 产品定位

- 提供系统可观测能力：指标、状态、日志、调试链路
- 提供系统可控能力：配置管理、运行参数调整
- 提供联调能力：以 Chat Console 进行端到端消息链路验证

## 页面结构

### 1) 登录页

- 用户名 + 密码登录
- 记录管理员登录日志

### 2) 仪表盘

- 展示系统关键指标概览
- 展示近 30 天趋势

详见 [dashboard.md](dashboard.md)。

### 3) 系统设置

- 配置项管理（分组、类型、历史、快捷编辑）
- LLM 配置管理规则（`json_schema_mode`、`api_key_env`）

详见 [system-settings.md](system-settings.md)。

### 4) 安全管理

- 用户违规日志
- 用户风险统计
- IP 风险统计
- IP 封禁记录

### 5) 自定义页面

- Chat Console（消息系统联调主工具）
- Entitlement Operations（通用权益发放/调整台，归属 `App Content` 菜单）
  - 操作流程固定为：搜索并选择用户 -> 配置权益操作 -> 数量确认（当前可用/结果可用）-> 提交并查看语义化结果
- 分数算法测试（关系算法输入输出验证）
- AI Advanced Edit（personality/style 高级配置编辑）
- Persona Batch Create（按 AI Type 批量生成 persona 队列，支持批量编辑导入并逐条提交 persona/profile 字段）
- Profile Avatar Advanced Edit（profile 头像上传、裁切与覆盖）

其中 Chat Console 详见 [chat-console.md](chat-console.md)。
AI Advanced Edit 详见 [ai-advanced-edit.md](ai-advanced-edit.md)。

### 6) 统计报表

- 用户统计、消息统计、AI 统计

详见 [reports.md](reports.md)。

## 全局约束

- 管理端调试能力仅用于内部联调，不影响生产主路径
- 管理端页面中的消息联调必须复用生产消息管线，不允许临时协议
- 权限控制必须按角色边界执行，不允许前端绕过后端鉴权
- 管理端界面支持 `zh_Hant` 与 `en` 切换，默认 `zh_Hant`
- 多语言覆盖范围包含导航与菜单等主页面文案
- 中文界面统一使用简体中文用词，按当前语言单语显示，不混合双语文案
- 对外文档路径统一以本目录入口 [README.md](README.md) 为准
