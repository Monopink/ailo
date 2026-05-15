# `page-layout` 组件契约

`page-layout` 是小程序页面结构与内容滚动容器组件，负责统一页面状态展示、内容区滚动、触底分页与下拉刷新事件。

## 状态契约

- `screenState`: `booting` | `ready`
- `contentVariant`: `data` | `empty` | `blank`
- `refreshState`: `idle` | `refreshing` | `degraded`

## 结构契约

- `header` slot：页面头部区域
- `content` slot：页面数据内容区域
- `empty` slot：空态内容区域
- `blank` slot：白屏内容区域
- `footer` slot：页面底部区域

## 内容滚动契约

当 `contentVariant='data'` 且 `disableScroll=false` 时，组件提供内容区滚动容器并发出滚动相关事件。

### 属性

- `disableScroll` (boolean)：是否禁用组件内容区滚动；默认 `false`
- `lowerThreshold` (number)：触底阈值；单位为 px，默认 `200`
- `enableContentRefresh` (boolean)：是否启用内容区下拉刷新；默认 `false`

### 事件

- `contentscroll`：内容区滚动事件
- `contentreachbottom`：内容区触底事件
- `contentrefresh`：内容区下拉刷新触发事件
- `contentrefresherrestore`：内容区下拉刷新复位事件

## 页面接入规则

- 使用 `page-layout` 内容滚动容器的页面，通过 `contentreachbottom` 触发分页加载。
- 使用 `page-layout` 内容滚动容器的页面，通过 `contentrefresh` 触发数据刷新。
- 页面分页状态与刷新状态通过业务层状态机驱动，`page-layout` 仅承载事件与结构。
