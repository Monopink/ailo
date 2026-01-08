# Fix Setup Page Blank Issue

**Date**: 2026-01-07
**Status**: 待实施
**Priority**: High (阻塞新用户注册流程)

## Problem Description

### Symptom
用户注册后，跳转到 `pages/setup/setup` 页面时显示空白。

### Root Cause
`page-layout` 组件引用了已删除的自定义 UI 组件：
- `<ui-loading>` - 在 page-layout.wxml:43
- `<ui-empty>` - 在 page-layout.wxml:48, 56

这些组件在 commit `6e30407` (Introduce the TDesign) 中被删除，但 `page-layout` 组件未完成迁移：
1. `page-layout.wxml` 仍使用旧的组件标签
2. `page-layout.json` 的 `usingComponents` 为空对象 `{}`，未注册任何组件

### Why Other Pages Work
其他页面可能：
- 未触发 loading/error/empty 状态
- 未使用 `page-layout` 组件

## Solution

### Approach: 完成 TDesign 迁移（推荐）

将 `page-layout` 组件完全迁移到 TDesign 组件库。

#### Changes Required

##### 1. Update page-layout.json

**File**: `frontend/wx-minipg/components/page-layout/page-layout.json`

```json
{
  "component": true,
  "usingComponents": {
    "t-loading": "tdesign-miniprogram/loading/loading",
    "t-empty": "tdesign-miniprogram/empty/empty"
  }
}
```

##### 2. Update page-layout.wxml

**File**: `frontend/wx-minipg/components/page-layout/page-layout.wxml`

需要替换的组件和属性：

| 旧组件 | 新组件 | 注意事项 |
|--------|--------|----------|
| `<ui-loading text="加载中...">` | `<t-loading theme="circular" text="加载中..." size="48rpx">` | 参考 chat.wxml |
| `<ui-empty type="error" message="..." action-text="重试" bindaction="...">` | `<t-empty icon="error-circle" description="..." action-text="重试" bind:action="...">` | TDesign 支持 action-text |
| `<ui-empty type="empty" message="...">` | `<t-empty icon="info-circle" description="...">` | - |

**具体修改**：

1. **Loading State** (line ~43):
   ```xml
   <!-- 旧代码 -->
   <ui-loading text="加载中..." />

   <!-- 新代码 -->
   <t-loading theme="circular" size="48rpx" text="加载中..." />
   ```

2. **Error State** (line ~48):
   ```xml
   <!-- 旧代码 -->
   <ui-empty
     type="error"
     message="{{errorMessage || '加载失败，请重试'}}"
     action-text="重试"
     bindaction="onRetryClick" />

   <!-- 新代码 -->
   <t-empty
     icon="error-circle"
     description="{{errorMessage || '加载失败，请重试'}}"
     action-text="重试"
     bind:action="onRetryClick" />
   ```

3. **Empty State** (line ~56):
   ```xml
   <!-- 旧代码 -->
   <ui-empty type="empty" message="{{emptyMessage || '暂无数据'}}" />

   <!-- 新代码 -->
   <t-empty
     icon="info-circle"
     description="{{emptyMessage || '暂无数据'}}" />
   ```

### API 对照

**TDesign Empty 组件属性** (参考 chat.wxml 实际使用):
- `icon`: 图标类型，如 `"error-circle"`, `"info-circle"`
- `description`: 描述文字 (对应旧的 `message`)
- `action-text`: 操作按钮文字
- `bind:action`: 操作按钮点击事件 (对应旧的 `bindaction`)

**TDesign Loading 组件属性** (参考 chat.wxml 实际使用):
- `theme`: 主题，通常用 `"circular"`
- `size`: 尺寸，如 `"48rpx"`
- `text`: 加载提示文字

### Why This Approach?

1. **符合设计决策**: 项目已引入 TDesign，应全面使用而非部分保留旧组件
2. **减少技术债**: 避免混用自定义组件和 TDesign 组件
3. **更好的维护性**: TDesign 组件有官方维护和文档
4. **一致性**: 与其他已迁移的页面保持一致 (chat.wxml, index.wxml 等)
5. **TDesign 支持 action-text**: 不需要额外封装按钮

## Implementation Checklist

- [ ] 检查 TDesign Empty 组件在 chat.wxml 的实际用法
- [ ] 检查 TDesign Loading 组件在 chat.wxml 的实际用法
- [ ] 更新 page-layout.json 注册 TDesign 组件
- [ ] 更新 page-layout.wxml 替换 ui-loading 为 t-loading
- [ ] 更新 page-layout.wxml 替换 ui-empty 为 t-empty (error 状态)
- [ ] 更新 page-layout.wxml 替换 ui-empty 为 t-empty (empty 状态)
- [ ] 测试 setup 页面是否正常显示
- [ ] 测试 loading 状态
- [ ] 测试 error 状态和重试按钮
- [ ] 测试 empty 状态
- [ ] 检查其他使用 page-layout 的页面是否正常

## Testing

### Test Cases

1. **Setup 页面加载状态**:
   - 访问 /pages/setup/setup
   - 应显示 loading 状态 (圆形加载动画 + "加载中..." 文字)
   - 加载完成后显示表单

2. **Error 状态**:
   - 模拟网络错误
   - 应显示错误图标 + 错误提示 + "重试" 按钮
   - 点击重试应触发 onRetryClick 事件

3. **Empty 状态**:
   - 在其他使用 page-layout 的页面测试
   - 应显示空状态图标 + 提示文字

4. **其他页面回归测试**:
   - 检查所有使用 page-layout 的页面
   - 确保功能正常

## References

- TDesign 小程序组件库文档: https://tdesign.tencent.com/miniprogram/components/empty
- TDesign 小程序组件库文档: https://tdesign.tencent.com/miniprogram/components/loading
- 参考实现: `frontend/wx-minipg/pages/chat/chat.wxml` (line 59-67)
- 相关 commit: `6e30407` (Introduce the TDesign)
- 计划文档: `docs/task-finished/ui-refactor-plan.md` (阶段三)

## Notes

- **重要发现**: TDesign 的 `t-empty` 组件支持 `action-text` 和 `bind:action` 属性，不需要单独添加按钮
- 参考 `chat.wxml` 中的实际用法确保一致性
- 旧的 `ui-empty` 组件代码可以在 git 历史中找到（commit 6e30407 之前）
- 属性名映射: `message` → `description`, `bindaction` → `bind:action`
