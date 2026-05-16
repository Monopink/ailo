# 发现页

本规范定义小程序发现页的分类与列表交互。

## 接口依赖

- [获取广场分类](../../../api/discovery.md#获取广场分类)
- [获取广场联系人](../../../api/discovery.md#获取广场联系人)
- [获取陌生人详情](../../../api/discovery.md#获取陌生人详情)

## 入口页（`pages/square-entry/square-entry`）

- 页面进入执行鉴权。
- 青少年模式开启且本地时间在 `22:00-06:00` 时，页面展示白屏提示，不展示分类卡片。
- 分类卡片数据优先读取本地缓存。
- 无分类缓存时展示内置默认卡片。
- 后台刷新分类数据并更新缓存。
- 点击卡片进入 `pkg/square/square`，参数为 `category_key`。

## 列表页（`pkg/square/square`）

- Tab 数据来自分类接口（缓存优先，后台刷新）。
- 青少年模式开启且本地时间在 `22:00-06:00` 时，页面展示白屏提示，不展示联系人列表。
- 列表请求必须携带 `category_key`。
- 页面内容滚动使用 `page-layout` 组件内容区容器。
- 页面实例首次进入时触发远端加载。
- 从 `pkg/stranger-info/stranger-info` 返回时保持当前分类、列表数据与滚动位置。
- 分页请求使用 `cursor` 延续当前列表版本。
- 内容区触底事件触发分页请求，并使用 `cursor` 持续加载。
- 内容区不启用下拉刷新。
- 列表状态在当前页面实例内维护，并保留当前会话分页进度与滚动位置。
- 无效或下线 `category_key` 时提示 `暂无内容`，并返回入口页。
- 刷新节奏按 `user + category_key` 独立控制，刷新间隔取系统配置 `square_refresh_interval_seconds`。
- 页面顶部 info-bar 展示 `refresh_remaining_seconds` 与 `next_refresh_available_at`。
- 每个分类每个 feed 最大分页数由系统配置 `square_max_pages_per_feed` 控制。
- 到达分页上限时，列表底部展示“已经到底啦”。
- `page-layout` 事件契约见：`../mini-program/page-layout.md`。

## 陌生人页（`pkg/stranger-info/stranger-info`）

- 从 Square 进入时透传 `category_key`。
- 请求详情时附带 `category_key`。
- 点击“添加联系人”时：
  - 若联系人上限未达标，弹出验证消息输入框，确认后发送联系人申请
  - 若联系人上限已达标，直接弹窗，标题“联系人达到上限”，内容“联系人达到上限，先和他们聊聊吧。”，按钮为“好 / 增加上限”
  - 点击“增加上限”跳转 `pages/invite-share/invite-share`
  - 提交成功后返回联系人列表页，并从当前 Square 页面内移除目标 `qiao_id` 列表项

## 图标与主题

- 分类图标来源 `icon_ref`。
- 仅解析 `tdesign:<icon-name>`。
- 解析失败时使用默认图标 `tdesign:chat`。
- `theme_key` 取值集合来源 `backend/app/enums/` 的 `SquareCategoryTheme`。
- 主题样式由 `theme_key` 映射本地 design tokens。
