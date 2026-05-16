# 小程序 UI 规范

> **目标**: 统一视觉与交互，减少偏差

## 核心规则（强制）

- 仅使用语义化设计令牌，禁止硬编码颜色/尺寸/阴影
- 基础 UI 统一使用 TDesign，自绘组件仅限 `ui-gender-badge`、`app-avatar`
- 需要导航栏的页面使用 `t-navbar`，并配置 `navigationStyle: "custom"`
- TabBar 使用 custom tabbar 机制，custom-tab-bar 内部必须使用 TDesign `t-tab-bar`
- 暗色模式跟随系统，不提供手动切换入口

## 页面结构

- 页面使用 `page-layout` 作为根容器
- 导航栏放在 `page-layout` 的 `header` slot
- 固定区（如输入栏）必须处理安全区
- `page-layout` 组件契约见：`./page-layout.md`

## 页面状态与提示

- 页面状态使用 `screenModel` 传递，包含 `screenState`、`contentVariant`、`refreshState`
- `page-layout` 提供页面结构与滚动容器
- 使用 `page-layout` 内容滚动容器的页面，通过 `contentreachbottom` 触发分页加载
- 启用内容区下拉刷新的页面，通过 `contentrefresh` 触发数据刷新
- `square` 页面禁用内容区下拉刷新
- 鉴权失效场景使用 modal，用户确认后跳转登录页
- toast 用于动作反馈，以及白屏场景的一次性加载失败提示

## `page-layout` 状态契约

- `screenState`: `booting` / `ready`
- `contentVariant`: `data` / `empty` / `blank`
- `refreshState`: `idle` / `refreshing` / `degraded`

## 失败展示规则

- 有可降级内容时保留内容并标记 `refreshState=degraded`
- 有可降级内容的失败场景不显示 toast
- 无可降级内容时页面显示 `ready + blank`
- 白屏场景可显示一次简短 toast
- 一级页面在白屏失败场景必须执行有上限自动重试
- `legal-document` 失败保持白屏静默

## 统一空状态组件

- 业务空状态使用统一组件
- 空状态仅允许在 `ready` 状态的内容区展示
- 空状态禁止接管整页，禁止替换 header、footer、输入区等结构
- 错误场景禁止使用空状态表达
- 图标使用语义化预设，尺寸固定为 `48rpx`
- 动作按钮为可选配置

## 局部加载占位

- 用于局部模块短暂加载占位

## 设计令牌与暗色模式

- 语义变量: `frontend/mp-weixin/styles/design-tokens.global.wxss` 与 `frontend/mp-weixin/styles/design-tokens.component.wxss`
- TDesign 映射: `frontend/mp-weixin/styles/tdesign-theme.wxss`
- 禁止直接引用 `--td-*` 做业务样式
- 暗色模式仅在 `design-tokens.global.wxss` 与 `design-tokens.component.wxss` 定义变量，`tdesign-theme.wxss` 只做映射
- `app.json` 必须启用 `darkmode: true` 且配置 `themeLocation: "theme.json"`
- `theme.json` 必须同时定义 `light` 与 `dark` 变量
- `app.json` 的 window/tabBar 字段使用 `@变量` 引用

## 页面级主题锁

- 页面主题模式通过页面根容器统一声明，页面内部不做分散式主题判断
- 页面主题模式包含 `system`、`fixed-light`、`fixed-dark`
- `system` 页面使用全局语义颜色变量，颜色跟随系统亮暗切换
- `fixed-light` 与 `fixed-dark` 页面使用页面级主题锁，颜色在系统亮暗切换时保持固定
- 页面级主题锁以页面级颜色变量组为唯一颜色来源，页面样式只引用该变量组
- 页面级主题锁覆盖 `--color-*` 与 `--td-*` 的颜色映射，保证自绘样式与 TDesign 组件颜色一致
- 页面级主题锁页面不定义 `@media (prefers-color-scheme: dark)` 规则
- 固定视觉资产页面归类为页面级主题锁页面
- 当前固定视觉资产页面: `pages/login/login`、`pages/invite-share/invite-share`

## 页面背景与 TabBar

- 页面默认背景使用 `--color-bg-primary`（浅灰）
- `page-layout` 背景使用 `--color-bg-page`，需要白色背景时在 `page-layout` 上覆写：`--color-bg-page: var(--color-bg-white)`
- 白色页面的具体内容区域背景使用 `--color-bg-white`（不要覆写 `--color-bg-primary`）
- 白色页面的 navbar 固定态背景覆写：`--color-bg-header-solid: var(--color-bg-white)`
- 登录页背景采用“本地渐变兜底层 + 远程图片增强层”双层结构
- 登录页远程背景加载失败或超时时保持本地渐变兜底层，不切换为白屏
- 登录页远程背景加载成功后通过透明度过渡显示，交互层始终保持可点击
- 登录页主视觉仅保留品牌文字 logo 与单句 slogan，不展示联系人示例卡片或功能卖点列表
- 登录页品牌文案禁止呼吸、脉冲、浮动等循环动画
- TabBar 使用半透明毛玻璃背景 `--color-navbar-glass-bg` + `backdrop-filter`，顶部边线使用 `--color-separator`

## 自绘组件

- `ui-gender-badge` 仅用于性别展示
- 禁止在页面层自定义其尺寸与颜色
- `app-avatar` 是头像渲染唯一入口，页面禁止直接使用 `t-avatar` 或裸 `image` 渲染业务头像
- `app-avatar` 支持统一尺寸、圆角形态、加载失败占位与 `load/error` 事件透传
