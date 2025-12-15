# 小程序 UI 开发规范

> **组件库**: [TDesign MiniProgram](https://tdesign.tencent.com/miniprogram/overview)
> **主题定制**: `/styles/tdesign-theme.wxss`
> **最后更新**: 2025-12-13

---

## 设计原则

### 1. 使用 TDesign 组件库

- 腾讯官方维护，持续更新
- 企业级质量，经过大量项目验证
- 通过 CSS Variables 定制品牌风格
- 组件按需引入，优化包体积

### 2. 主题一致性

- 所有页面使用统一的 `tdesign-theme.wxss`
- 通过 `--td-*` CSS Variables 定制样式
- 自动支持 Dark Mode（如启用）
- 禁止硬编码颜色、字体、间距等值

### 3. 组件化思维

- 优先使用 TDesign 组件
- 业务组件封装业务逻辑
- 页面只负责布局和组合

### 4. 遵循微信设计规范

- 屏幕宽度基准：750rpx（基于 iPhone 6）
- 间距基准：8rpx（所有间距必须是 8 的倍数）
- 主题色：`#07C160`（微信官方绿）
- 视觉风格：简洁、统一、符合微信原生体验

---

## 强制规则

### 必须遵守
1. 页面 WXSS 第一行 `@import '/styles/tdesign-theme.wxss';`
2. 所有基础UI使用 `t-*` TDesign组件
3. 业务逻辑使用业务组件（`ui-gender-badge` / `ui-message-bubble` / `ui-message-input`）
4. 所有颜色、间距、字体、圆角通过 `var(--td-*)` 引用 CSS Variables
5. 提交前运行 `npm run check` 并通过所有检查
6. 在 WeChat DevTools 中测试浅色/深色模式

### 禁止行为
1. 硬编码样式值（颜色、字体、间距、圆角）
2. 使用非 rpx 单位（除了 1px 边框）
3. 直接修改 TDesign 组件内部样式
4. 在页面中定义基础UI样式（颜色、字体等）
5. 使用已废弃的 `ui-*` 自研组件（除了保留的3个业务组件）

---

## TDesign 组件使用

### 常用基础组件

| 组件 | 用途 | 文档 |
|------|------|------|
| `t-button` | 按钮 | [Button](https://tdesign.tencent.com/miniprogram/components/button) |
| `t-cell` / `t-cell-group` | 列表单元格 | [Cell](https://tdesign.tencent.com/miniprogram/components/cell) |
| `t-avatar` | 头像 | [Avatar](https://tdesign.tencent.com/miniprogram/components/avatar) |
| `t-badge` | 徽章 | [Badge](https://tdesign.tencent.com/miniprogram/components/badge) |
| `t-tag` | 标签 | [Tag](https://tdesign.tencent.com/miniprogram/components/tag) |
| `t-icon` | 图标 | [Icon](https://tdesign.tencent.com/miniprogram/components/icon) |
| `t-input` | 输入框 | [Input](https://tdesign.tencent.com/miniprogram/components/input) |
| `t-dialog` | 对话框 | [Dialog](https://tdesign.tencent.com/miniprogram/components/dialog) |
| `t-toast` | 轻提示 | [Toast](https://tdesign.tencent.com/miniprogram/components/toast) |
| `t-loading` | 加载状态 | [Loading](https://tdesign.tencent.com/miniprogram/components/loading) |
| `t-empty` | 空状态 | [Empty](https://tdesign.tencent.com/miniprogram/components/empty) |
| `t-divider` | 分割线 | [Divider](https://tdesign.tencent.com/miniprogram/components/divider) |

### 表单组件

| 组件 | 用途 | 文档 |
|------|------|------|
| `t-checkbox` / `t-checkbox-group` | 复选框 | [Checkbox](https://tdesign.tencent.com/miniprogram/components/checkbox) |
| `t-radio` / `t-radio-group` | 单选框 | [Radio](https://tdesign.tencent.com/miniprogram/components/radio) |
| `t-switch` | 开关 | [Switch](https://tdesign.tencent.com/miniprogram/components/switch) |
| `t-picker` | 选择器 | [Picker](https://tdesign.tencent.com/miniprogram/components/picker) |
| `t-textarea` | 多行文本 | [Textarea](https://tdesign.tencent.com/miniprogram/components/textarea) |

### 反馈组件

| 组件 | 用途 | 文档 |
|------|------|------|
| `t-action-sheet` | 操作菜单 | [ActionSheet](https://tdesign.tencent.com/miniprogram/components/action-sheet) |
| `t-message` | 消息提示 | [Message](https://tdesign.tencent.com/miniprogram/components/message) |
| `t-notification` | 通知 | [Notification](https://tdesign.tencent.com/miniprogram/components/notification) |

### 导航组件

| 组件 | 用途 | 文档 |
|------|------|------|
| `t-navbar` | 导航栏 | [Navbar](https://tdesign.tencent.com/miniprogram/components/navbar) |
| `t-tabs` | 标签页 | [Tabs](https://tdesign.tencent.com/miniprogram/components/tabs) |

---

## 业务组件

项目中保留了3个业务组件，封装特定业务逻辑：

### `ui-gender-badge` - 性别徽章

显示用户性别（男/女/其他/未知）

```xml
<ui-gender-badge gender="male" />
```

**属性**:
- `gender`: 'male' | 'female' | 'other' | 'unknown'

### `ui-message-bubble` - 消息气泡

聊天消息气泡，支持文本/图片/系统消息

```xml
<ui-message-bubble
  type="text"
  content="{{message}}"
  isSelf="{{true}}"
  status="sent" />
```

**属性**:
- `type`: 'text' | 'image' | 'system'
- `content`: 消息内容
- `isSelf`: 是否为自己发送
- `status`: 'sending' | 'sent' | 'failed'

### `ui-message-input` - 消息输入

聊天输入框，支持文本输入和发送

```xml
<ui-message-input
  value="{{inputValue}}"
  placeholder="请输入消息"
  bind:send="handleSend" />
```

**事件**:
- `send`: 发送消息事件

---

## 页面开发流程

### Step 1: 注册组件（.json）

```json
{
  "navigationBarTitleText": "页面标题",
  "usingComponents": {
    "t-cell": "tdesign-miniprogram/cell/cell",
    "t-cell-group": "tdesign-miniprogram/cell-group/cell-group",
    "t-avatar": "tdesign-miniprogram/avatar/avatar",
    "t-badge": "tdesign-miniprogram/badge/badge",

    "ui-gender-badge": "/components/ui/gender-badge/gender-badge"
  }
}
```

### Step 2: 编写模板（.wxml）

```xml
<view class="page-container">
  <t-cell-group>
    <t-cell
      title="用户昵称"
      note="{{nickname}}"
      arrow
      bindtap="handleTap">
      <t-avatar slot="icon" src="{{avatar}}" size="large" />
    </t-cell>

    <t-cell title="性别">
      <ui-gender-badge slot="note" gender="{{gender}}" />
    </t-cell>
  </t-cell-group>

  <view class="page-actions">
    <t-button type="primary" block bindtap="handleSave">
      保存
    </t-button>
  </view>
</view>
```

### Step 3: 编写样式（.wxss）

```css
/* 第一行：必须引入TDesign主题 */
@import '/styles/tdesign-theme.wxss';

/* 页面容器 */
.page-container {
  min-height: 100vh;
  background-color: var(--td-bg-color-page);
  padding: var(--td-spacer-4);
}

/* 操作按钮区域 */
.page-actions {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: var(--td-spacer-3);
  background-color: var(--td-bg-color-container);
  border-top: 1px solid var(--td-component-border);
}
```

**样式编写规则：**
- 只定义页面布局（flex、grid、position、padding、margin）
- 使用 `var(--td-*)` CSS Variables
- 不定义基础样式（color、font-size、border-radius等由TDesign控制）
- 不硬编码任何样式值

### Step 4: 编写逻辑（.ts）

```typescript
import Toast from 'tdesign-miniprogram/toast/index';

interface PageData {
  nickname: string;
  avatar: string;
  gender: 'male' | 'female' | 'other' | 'unknown';
}

Page<PageData>({
  data: {
    nickname: '',
    avatar: '',
    gender: 'unknown',
  },

  onLoad() {
    this.loadData();
  },

  async loadData() {
    try {
      const user = await api.getUser();
      this.setData({
        nickname: user.nickname,
        avatar: user.avatar,
        gender: user.gender,
      });
    } catch (error) {
      Toast({
        message: '加载失败，请重试',
        icon: 'error',
      });
    }
  },

  handleSave() {
    Toast({
      message: '保存成功',
      icon: 'success',
    });
  },
});
```

### Step 5: 验证

```bash
# 运行完整检查
npm run check

# 单独运行各项检查
npm run type-check    # TypeScript类型检查
npm run lint          # ESLint检查
npm run lint:style    # Stylelint检查
npm run ui:audit      # UI规范检查
```

---

## 主题定制

### 修改主题变量

编辑 `/styles/tdesign-theme.wxss`:

```css
page {
  /* Brand Color - WeChat Green */
  --td-brand-color: #07c160;
  --td-brand-color-light: #38cd7f;
  --td-brand-color-focus: #06ad56;

  /* Spacing System */
  --td-spacer-1: 8rpx;
  --td-spacer-2: 16rpx;
  --td-spacer-3: 24rpx;
  --td-spacer-4: 32rpx;

  /* Border Radius */
  --td-radius-small: 8rpx;
  --td-radius-default: 12rpx;
  --td-radius-large: 16rpx;

  /* Font Sizes */
  --td-font-size-xs: 20rpx;
  --td-font-size-s: 24rpx;
  --td-font-size-base: 28rpx;
  --td-font-size-m: 32rpx;
  --td-font-size-l: 36rpx;
}
```

### 覆盖组件样式

使用 `external-classes`:

```xml
<!-- WXML -->
<t-button t-class="my-custom-button">按钮</t-button>
```

```css
/* WXSS */
.my-custom-button {
  /* 使用CSS Variables覆盖 */
  --td-button-height: 88rpx;
  --td-button-font-size: 32rpx;
}
```

---

## 常见问题

### Q1: 如何迁移旧的 ui-* 组件？

使用迁移脚本辅助：

```bash
cd frontend/wx-minipg

# 检查迁移状态
./scripts/check-migration-status.sh

# 迁移单个页面
./scripts/migrate-page.sh profile
```

### Q2: TDesign 组件API和自研组件不同怎么办？

查阅 [TDesign文档](https://tdesign.tencent.com/miniprogram/overview)，对比API差异：

```xml
<!-- 旧的 ui-cell -->
<ui-cell
  title="标题"
  value="内容"
  link="{{true}}" />

<!-- 新的 t-cell -->
<t-cell
  title="标题"
  note="内容"
  arrow
  hover
  bindtap="handleTap" />
```

### Q3: 图标库如何迁移？

- 旧的 `ui-icon` 使用 WeUI 图标（Base64 SVG）
- 新的 `t-icon` 使用 TDesign 图标
- 查阅 [TDesign图标库](https://tdesign.tencent.com/miniprogram/components/icon)找到对应图标
- 如果没有对应图标，可使用自定义图片

```xml
<!-- TDesign Icon -->
<t-icon name="user" size="48rpx" />

<!-- Custom Image -->
<image src="/assets/icons/custom.png" style="width: 48rpx; height: 48rpx;" />
```

### Q4: 如何显示Toast/Dialog？

TDesign使用API方式调用：

```typescript
// Toast
import Toast from 'tdesign-miniprogram/toast/index';

Toast({
  message: '操作成功',
  icon: 'success',
  duration: 2000,
});

// Dialog
import Dialog from 'tdesign-miniprogram/dialog/index';

Dialog.confirm({
  title: '确认删除',
  content: '删除后无法恢复',
  confirmBtn: '删除',
  cancelBtn: '取消',
}).then(() => {
  // 确认操作
}).catch(() => {
  // 取消操作
});
```

### Q5: 页面样式和TDesign默认样式冲突？

1. 优先通过CSS Variables定制主题
2. 使用 `external-classes` 覆盖组件样式
3. 避免直接修改TDesign组件内部结构

### Q6: 什么时候可以不使用TDesign组件？

只有在以下情况下可以自定义样式：
1. TDesign组件库没有提供该组件
2. TDesign组件无法满足特殊需求
3. 但仍然必须使用 CSS Variables

---

## 参考资料

### 官方文档
- [TDesign MiniProgram 官网](https://tdesign.tencent.com/miniprogram/overview)
- [TDesign GitHub](https://github.com/Tencent/tdesign-miniprogram)
- [组件列表](https://tdesign.tencent.com/miniprogram/components/button)
- [主题定制](https://tdesign.tencent.com/miniprogram/custom-theme)

### 项目文档
- [小程序开发规则](../../frontend/wx-minipg/AGENTS.md)
- [迁移总体规划](../../task/tdesign-migration-master-plan.md)
