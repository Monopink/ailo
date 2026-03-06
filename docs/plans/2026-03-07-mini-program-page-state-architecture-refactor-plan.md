# 小程序页面状态架构重构方案

## 1. 目标与范围

- 重构微信小程序页面状态架构，解除“页面可进入”和“远程请求成功”的绑定。
- 覆盖页面打开链路、页面状态契约、静默失败策略、空状态体系、页面 Service 职责边界。
- 覆盖页面：`login`、`chat`、`contact-info`、`chat-detail`、`setup`、`account-security`、`profile`、`profile-detail`、`stranger-info`、`legal-document`、`index`、`square`、`contact-requests`、`profile-edit`。
- 覆盖所有直接或间接使用 `page-layout`、`t-empty` 的页面状态展示。
- 不做向后兼容，整体替换旧三布尔组合逻辑。

## 2. 当前问题

### 2.1 页面可用性依赖远程成功

- 页面普遍使用 `isLoading / hasError / isEmpty` 三个布尔值表达整页状态。
- 三布尔模型混合“页面可渲染性”和“远程结果状态”。
- 远程请求失败时，页面容易进入全屏错误，不能稳定展示已有内容。

### 2.2 页面层承担过多编排责任

- 页面层直接拼装 `pageLayoutData` 并切换整页状态。
- 页面层直接调用 API、直接拼装 ViewModel、直接处理错误分支。
- 页面、组件、Service 三层存在重复判断。

### 2.3 加载节奏不统一

- 多页面存在 `onLoad`、`onShow` 多次触发远程加载。
- 失败后行为不一致，缺少统一白屏与静默策略。

## 3. 固化决策

- 移除 `blocking` 设计与 `blockingResult` 契约。
- 页面层只消费页面 Service 返回的 `screenModel` 与页面 ViewModel。
- 页面默认单次加载：每次页面进入生命周期内只执行一次页面远程加载。
- 页面失败且无可降级内容时统一进入 `ready + blank`。
- 有可降级内容时保留内容并标记 `refreshState=degraded`，不改变页面结构。
- 一级页面（Tab 页）在无可降级内容失败时必须自动重试，不能依赖“返回上一级再进入”触发重试。
- `index` 失败且无内容时不使用纯白屏，进入 blank 态后执行自动重试。
- 一级页面自动重试保持静默：不展示“重试中”文案，不弹 toast。
- `legal-document` 失败保持纯白屏静默，不显示 toast。
- 有可降级内容的失败场景不显示 toast。
- 白屏场景按需显示一次简短 toast（每次页面生命周期最多一次）。
- 鉴权失败使用 modal，用户确认后跳转登录页。
- `square` 非实时订阅，进入页面时刷新。
- 所有空状态统一接入新空状态组件，不直接依赖默认 `t-empty` 外观。

## 4. 状态模型

### 4.1 输出契约

- 页面 Service 输出 `screenModel` 与页面 ViewModel。
- `screenModel` 仅表达可渲染状态。

### 4.2 状态定义

- `screenState`：`booting`、`ready`。
- `contentVariant`：`data`、`empty`、`blank`。
- `refreshState`：`idle`、`refreshing`、`degraded`。
- 错误语义用于 Service 内部决策与日志，不作为页面阻断契约。

## 5. 页面 Service 架构

### 5.1 目录组织

- 页面 Service 统一放在 `frontend/wx-minipg/services/pages/`。
- 页面层调用页面 Service，不直接编排数据获取流程。

### 5.2 页面 Service 责任

- 构造最小可用模型（`bootstrap`）。
- 执行一次性远程补全（`load`）。
- 输出 `screenModel`、`refreshState` 与页面 ViewModel。
- 执行错误语义分类、静默失败决策与并发控制。

### 5.3 页面层责任

- 绑定 `screenModel` 与 ViewModel。
- 处理用户动作。
- 处理鉴权失效 modal 与登录跳转。
- 不直接调用 API，不直接构造 ViewModel，不直接解释原始错误对象。

## 6. 生命周期模型

### 6.1 One-shot 加载

- 页面远程加载在 `onLoad` 执行一次。
- `onShow` 默认不触发远程加载。
- 默认不做自动重试；一级页面作为例外，在 blank 失败时执行有上限的自动重试。

### 6.2 `square` 特例

- `square` 在进入页面时执行刷新。
- `square` 不绑定实时订阅更新。

## 7. 失败处理策略

### 7.1 最小可用模型已构造

- 保留当前可展示内容。
- 更新 `refreshState=degraded`。
- 不显示 toast。

### 7.2 最小可用模型未构造

- 页面进入 `ready + blank`。
- 可显示一次简短 toast（如“加载失败”）。
- 非一级页面可通过退出或重新进入页面重试；一级页面通过自动重试恢复。

### 7.3 鉴权失效

- 显示 modal。
- 用户确认后跳转登录页。

### 7.4 `legal-document`

- 失败时保持纯白屏静默。
- 不显示 toast。

## 8. 并发控制标准

- 页面 Service 维护 `requestSeq`，每次 `bootstrap()`、`load()` 启动前递增。
- 返回结果若序列号过期则丢弃。
- `bootstrap()` 支持 in-flight 去重。
- 页面或 Service `dispose()` 后，不再写入页面状态。
- 页面 `onUnload` 必须调用页面 Service 的 `dispose()`。

## 9. 组件架构调整

### 9.1 `page-layout` 职责

- 仅负责容器、头部、内容区、页脚、安全区与滚动结构。
- 仅消费 `screenModel` 契约。

### 9.2 `page-layout` 契约字段

- `screenState`：`booting`、`ready`。
- `contentVariant`：`data`、`empty`、`blank`。
- `refreshState`：`idle`、`refreshing`、`degraded`。

### 9.3 统一状态组件

- 空状态组件仅在 `ready + empty` 内容区展示。
- 局部加载占位仅用于局部模块短暂加载。

## 10. 逐页改造要求

- `chat`：首屏不阻塞联系人资料，消息区与输入区可达。
- `login`：页面层只处理授权交互与跳转，登录检查/绑定/后续预热编排下沉至页面 Service。
- `contact-info`、`chat-detail`：失败时保留已有内容；无内容时白屏。
- `setup`、`account-security`、`profile`、`profile-detail`：统一 one-shot 加载与静默失败。
- `stranger-info`：入口最小模型一次性消费，不落地存储。
- `legal-document`：失败纯白屏静默。
- `index`：列表失败时保留现有列表；无内容时进入 blank 并自动重试（避免长期白屏）。
- `square`：进入页面刷新，不走实时更新。
- `contact-requests`、`profile-edit`：统一空状态组件与白屏策略。

## 11. 文档与代码同步清单

- 更新 `docs/spec/client/mini-program/ui.md`。
- 更新 `docs/spec/client/mini-program/service-layer.md`。
- 重构 `frontend/wx-minipg/components/page-layout/*`。
- 重构 `frontend/wx-minipg/templates/page-layout.ts` 类型定义。
- 全量建设 `frontend/wx-minipg/services/pages/*`。
- 重构 `frontend/wx-minipg/utils/error-classifier.ts`。
- 移除 `blocking` 相关代码与页面分支。

## 12. 实施顺序

1. 更新状态契约与页面 Service 输出定义，移除 `blockingResult`。
2. 建立并迁移 `services/pages/*` 到全覆盖页面。
3. 统一 one-shot 加载实现，`square` 加入进入页刷新特例。
4. 重构 `page-layout` 与空状态接入。
5. 清理旧状态代码、旧错误分支、冗余/无用代码。
6. 文档同步与校验。

## 13. 验收标准

- 页面层不再承担远程数据获取、ViewModel 拼装与布尔状态组合。
- 页面失败且无可降级内容时统一进入白屏。
- 有可降级内容时保留内容并静默降级，不显示 toast。
- 白屏场景可按需显示一次简短 toast。
- 一级页面白屏失败场景必须具备有上限自动重试能力。
- `legal-document` 失败保持纯白屏静默。
- 鉴权失效统一 modal + 登录跳转。
- `square` 进入页面触发刷新且不依赖实时订阅。
- 页面 Service、组件层、页面层状态语义一致。
