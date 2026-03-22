# 发现页

本规范定义小程序发现页的分类与列表交互。

## 接口依赖

- [获取广场分类](../../../api/discovery.md#获取广场分类)
- [获取广场联系人](../../../api/discovery.md#获取广场联系人)
- [获取陌生人详情](../../../api/discovery.md#获取陌生人详情)

## 入口页（`pages/square-entry/square-entry`）

- 页面进入执行鉴权。
- 分类卡片数据优先读取本地缓存。
- 无分类缓存时展示内置默认卡片。
- 后台刷新分类数据并更新缓存。
- 点击卡片进入 `pages/square/square`，参数为 `category_key`。

## 列表页（`pages/square/square`）

- Tab 数据来自分类接口（缓存优先，后台刷新）。
- 列表请求必须携带 `category_key`。
- 列表缓存按 `category_key` 维度存储。
- 无效或下线 `category_key` 时提示 `暂无内容`，并返回入口页。
- 刷新节奏由响应 `refresh_available_at` 控制。

## 陌生人页（`pages/stranger-info/stranger-info`）

- 从 Square 进入时透传 `category_key`。
- 请求详情时附带 `category_key`。
- 分类展示文案使用响应 `category_title`。

## 图标与主题

- 分类图标来源 `icon_ref`。
- 仅解析 `tdesign:<icon-name>`。
- 解析失败时使用默认图标 `tdesign:chat`。
- `theme_key` 取值集合来源 `backend/app/enums/` 的 `SquareCategoryTheme`。
- 主题样式由 `theme_key` 映射本地 design tokens。
