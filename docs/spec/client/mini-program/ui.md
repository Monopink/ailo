# 小程序 UI 规范

> **目标**: 统一视觉与交互，减少偏差

## 核心规则（强制）

- 仅使用语义化设计令牌，禁止硬编码颜色/尺寸/阴影
- 基础 UI 统一使用 TDesign，自绘组件仅限 `ui-gender-badge`
- 需要导航栏的页面使用 `t-navbar`，并配置 `navigationStyle: "custom"`
- TabBar 使用 custom tabbar 机制，custom-tab-bar 内部必须使用 TDesign `t-tab-bar`
- 暗色模式跟随系统，暂不考虑手动切换

## 页面结构

- 页面优先使用 `page-layout` 作为根容器
- 导航栏放在 `page-layout` 的 `header` slot
- 固定区（如输入栏）必须处理安全区

## 设计令牌与暗色模式

- 语义变量: `frontend/wx-minipg/styles/design-tokens.wxss`
- TDesign 映射: `frontend/wx-minipg/styles/tdesign-theme.wxss`
- 禁止直接引用 `--td-*` 做业务样式
- 暗色模式仅在 `design-tokens.wxss` 定义变量，`tdesign-theme.wxss` 只做映射
- `app.json` 必须启用 `darkmode: true` 且配置 `themeLocation: "theme.json"`
- `theme.json` 必须同时定义 `light` 与 `dark` 变量
- `app.json` 的 window/tabBar 字段使用 `@变量` 引用

## 页面背景与 TabBar

- 页面默认背景使用 `--color-bg-primary`（浅灰）
- `page-layout` 背景使用 `--color-bg-page`，需要白色背景时在 `page-layout` 上覆写：`--color-bg-page: var(--color-bg-white)`
- 白色页面的具体内容区域背景使用 `--color-bg-white`（不要覆写 `--color-bg-primary`）
- 白色页面的 navbar 固定态背景覆写：`--color-bg-header-solid: var(--color-bg-white)`
- TabBar 使用半透明毛玻璃背景 `--color-navbar-glass-bg` + `backdrop-filter`，顶部边线使用 `--color-separator`

## 自绘组件

- `ui-gender-badge` 仅用于性别展示
- 禁止在页面层自定义其尺寸与颜色
