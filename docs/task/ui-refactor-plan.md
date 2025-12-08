# 小程序 UI 重构任务计划

## 项目背景

### 当前问题
1. **样式混乱**：26+ 种颜色硬编码，单位混用（px/rpx），间距不统一
2. **缺乏规范**：每个页面自行定义样式，无统一设计系统
3. **维护困难**：AI 生成代码不一致，人工审核成本高
4. **调试低效**：缺乏组件库，重复编写基础 UI

### 项目现状
- **页面数量**：17 个页面
- **现有组件**：2 个（captcha, chat-navbar）
- **颜色硬编码**：26 种不同颜色值
- **单位问题**：app.wxss 使用 px，页面使用 rpx

## 重构目标

### 核心原则
1. **零硬编码**：所有样式值必须引用变量
2. **组件化**：基础 UI 封装为组件，页面只组合组件
3. **模板化**：统一页面布局结构
4. **规范化**：建立严格的 UI 开发规则

### 预期效果
- AI 生成代码自动符合规范
- 人工审核仅需验证是否正确使用变量与组件
- 样式系统化，视觉一致性显著提升
- 团队整体开发效率大幅提升

### 强制约束
1. **一次性完成改造**：所有 17 个页面以及全局样式、组件、模板必须在本次重构中全部替换到新体系，不接受渐进式或权宜方案。
2. **文档与代码完全一致**：文档中出现的组件、模板、规范立刻在代码中实现，不允许“待实现”或“TODO”。
3. **内建微信 Dark Mode 支持**：Design Tokens、组件、页面样式必须落实 `prefers-color-scheme` 适配，保证浅色/深色模式一致可用。
4. **自动化校验同时升级**：`npm run check` 必须在重构交付前扩展包含 stylelint/postcss 与自定义检测，阻断硬编码颜色、px 单位、未使用组件库等问题。

---

## 任务分解

### 阶段一：建立设计系统（Foundation）

#### 任务 1.1：校准 Design Tokens 文件
**文件**：`frontend/wx-minipg/styles/design-tokens.wxss`

> 该文件已经存在，需审查并补充，而不是重新创建。重点是保证变量覆盖范围与命名一致性，可在现有基础上扩展。

**要求**：
1. 基于微信官方规范（750rpx 屏幕宽度）
2. 定义完整的设计变量系统
3. 所有变量使用 CSS Custom Properties（`--var-name`）
4. 必须包含以下类别：
   - 颜色系统（主题色、中性色、状态色；允许多种颜色，默认主色可参考微信绿 `#07C160`）
   - 间距系统（8rpx 基准）
   - 字体系统（字号、行高、字重）
   - 圆角系统（4 个级别）
   - 阴影系统（3 个级别）
   - 尺寸系统（头像、图标、按钮高度）
   - 动画系统（过渡时间、缓动函数）
5. 针对浅色与深色模式分别定义变量集，使用 `@media (prefers-color-scheme: dark)` 或 `page[theme='dark']` 确保 Dark Mode 即刻可用。

**验收标准**：
- [ ] 文件经审查后变量覆盖上述类别且有注释说明
- [ ] 新增/调整的变量命名语义化（如 `--color-bg-card`），无需 BEM 命名
- [ ] 同时支持浅色/深色模式变量，默认主色可参考微信绿 #07C160，但允许根据产品策略扩展
- [ ] 通过设计评审确认变量足以支撑组件库与页面模板

**参考**：
- 微信官方设计规范：750rpx 屏幕宽度
- 间距基准：8rpx（8, 16, 24, 32, 40, 48...）
- 默认主题色：`#07C160`（可按产品策略调整）

---

#### 任务 1.2：重构 app.wxss
**文件**：`frontend/wx-minipg/app.wxss`

**要求**：
1. 引入 `design-tokens.wxss`
2. 将所有硬编码值替换为 CSS 变量
3. 将所有 `px` 单位改为 `rpx`（除了 1px 边框）
4. 保留现有工具类，但使用变量
5. 删除过时和冗余的样式
6. 通过 CSS 变量和匹配规则适配微信暗色模式（例如 `page[theme='dark']`），确保全局样式在浅/深模式一致。

**验收标准**：
- [ ] 第一行引入 `@import "styles/design-tokens.wxss";`
- [ ] 无任何硬编码颜色值（`#xxx`）
- [ ] 无 `px` 单位（除了 `1px` 边框）
- [ ] 所有间距为 8 的倍数
- [ ] 深色模式与浅色模式显示一致（依赖 design tokens）
- [ ] 通过 `npm run check`

---

### 阶段二：建立组件库（Component Library）

#### 任务 2.1：创建组件库目录结构
**目录**：`frontend/wx-minipg/components/ui/`

**要求**：
创建以下基础组件目录：
```
components/ui/
├── button/           # 按钮组件
├── cell/             # 单元格（列表项）
├── avatar/           # 头像组件
├── badge/            # 徽章组件
├── tag/              # 标签组件
├── dialog/           # 对话框组件
├── loading/          # 加载组件
├── empty/            # 空状态组件
└── divider/          # 分割线组件
```

**验收标准**：
- [ ] 所有目录创建完成
- [ ] 每个组件包含 4 个文件（.wxml, .wxss, .ts, .json）

---

#### 任务 2.2：开发 Button 组件
**文件**：`components/ui/button/`

**功能要求**：
- 支持 4 种类型：`primary`, `secondary`, `danger`, `text`
- 支持 3 种尺寸：`small`, `medium`, `large`
- 支持禁用状态
- 支持加载状态
- 支持块级按钮（full-width）

**API 设计**：
```xml
<ui-button
  type="primary"
  size="medium"
  disabled="{{false}}"
  loading="{{false}}"
  block="{{false}}"
  bindtap="handleTap">
  按钮文字
</ui-button>
```

**样式要求**：
- 所有颜色、间距、圆角使用 CSS 变量
- 禁止硬编码任何样式值
- 必须有 hover 效果
- 必须有 active 效果

**验收标准**：
- [ ] 组件功能完整
- [ ] 无硬编码样式
- [ ] 通过 TypeScript 类型检查
- [ ] 通过 ESLint 检查

---

#### 任务 2.3：开发 Cell 组件
**文件**：`components/ui/cell/`

**功能要求**：
- 支持左侧图标/头像
- 支持标题 + 描述
- 支持右侧文字/箭头
- 支持点击跳转
- 支持自定义插槽

**API 设计**：
```xml
<ui-cell
  title="标题"
  value="右侧文字"
  label="描述文字"
  icon="{{iconUrl}}"
  link="{{true}}"
  bindtap="handleTap">
  <view slot="icon">自定义图标</view>
  <view slot="footer">自定义右侧</view>
</ui-cell>
```

**验收标准**：
- [ ] 组件功能完整
- [ ] 无硬编码样式
- [ ] 支持插槽
- [ ] 通过代码检查

---

#### 任务 2.4：开发 Avatar 组件
**文件**：`components/ui/avatar/`

**功能要求**：
- 支持 4 种尺寸：`small`(64rpx), `medium`(80rpx), `large`(100rpx), `xlarge`(128rpx)
- 支持圆形/方形（微信风格为方形圆角）
- 支持加载失败占位图
- 支持性别图标叠加

**API 设计**：
```xml
<ui-avatar
  src="{{avatarUrl}}"
  size="medium"
  shape="square"
  gender="male" />
```

**验收标准**：
- [ ] 组件功能完整
- [ ] 尺寸使用 CSS 变量
- [ ] 有加载失败处理
- [ ] 通过代码检查

---

#### 任务 2.5：开发其他基础组件
**组件列表**：
- Badge（徽章）
- Tag（标签）
- Dialog（对话框）
- Loading（加载）
- Empty（空状态）
- Divider（分割线）

**要求**：
每个组件参考微信原生组件设计，但使用 CSS 变量实现。

**验收标准**：
- [ ] 所有组件开发完成
- [ ] 无硬编码样式
- [ ] 通过代码检查

---

### 阶段三：建立页面布局组件（Page Layout Component）

> **重要说明**：page-layout 必须实现为**自定义组件（Component）**而非 template，因为需要使用具名 slot 传递页面内容和底部操作区。微信小程序的 template 不支持 slot 功能。

#### 任务 3.1：创建页面布局组件
**目录**：`frontend/wx-minipg/components/page-layout/`

**要求**：
创建标准页面布局组件，包含：
1. 页面容器（固定 class 名称）
2. 内容区域（scroll-view）
3. 底部操作区（可选）
4. 加载状态
5. 空状态
6. 错误状态

**组件结构**：
```xml
<!-- page-layout.wxml -->
<view class="page-layout">
  <!-- Loading State -->
  <view wx:if="{{isLoading}}" class="page-layout__state">
    <ui-loading text="加载中..." />
  </view>

  <!-- Error State -->
  <view wx:elif="{{hasError}}" class="page-layout__state">
    <ui-empty
      type="error"
      message="{{errorMessage || '加载失败，请重试'}}"
      action-text="重试"
      bindaction="onRetryClick" />
  </view>

  <!-- Empty State -->
  <view wx:elif="{{isEmpty}}" class="page-layout__state">
    <ui-empty type="empty" message="{{emptyMessage || '暂无数据'}}" />
  </view>

  <!-- Content -->
  <scroll-view
    wx:else
    class="page-layout__content"
    scroll-y="{{true}}"
    enhanced="{{true}}"
    show-scrollbar="{{false}}"
    scroll-into-view="{{contentScrollIntoView}}"
    scroll-with-animation="{{contentScrollWithAnimation}}">
    <slot name="content" />
  </scroll-view>

  <!-- Footer Actions (Optional) -->
  <view wx:if="{{hasFooter && !isLoading && !hasError}}" class="page-layout__footer">
    <slot name="footer" />
  </view>
</view>
```

**组件配置**：
```json
{
  "component": true,
  "usingComponents": {
    "ui-loading": "/components/ui/loading/loading",
    "ui-empty": "/components/ui/empty/empty"
  }
}
```

**组件逻辑**：
```typescript
Component({
  options: {
    multipleSlots: true, // 启用多个具名 slot
  },

  properties: {
    isLoading: { type: Boolean, value: false },
    hasError: { type: Boolean, value: false },
    errorMessage: { type: String, value: '' },
    isEmpty: { type: Boolean, value: false },
    emptyMessage: { type: String, value: '' },
    hasFooter: { type: Boolean, value: false },
    contentScrollIntoView: { type: String, value: '' },
    contentScrollWithAnimation: { type: Boolean, value: true },
  },

  methods: {
    onRetryClick() {
      this.triggerEvent('retry');
    },
  },
});
```

**验收标准**：
- [ ] 组件文件创建完成（.wxml, .wxss, .ts, .json）
- [ ] 包含所有必需状态
- [ ] 启用 multipleSlots 支持具名 slot
- [ ] 使用 CSS 变量定义样式
- [ ] 有完整的注释说明

---

#### 任务 3.2：创建组件样式
**文件**：`frontend/wx-minipg/components/page-layout/page-layout.wxss`

**要求**：
1. 定义页面容器样式（100vh 高度）
2. 定义内容区域样式（flex: 1）
3. 定义底部操作区样式（固定底部）
4. 所有样式使用 CSS 变量

**验收标准**：
- [ ] 样式文件创建完成
- [ ] 无硬编码样式值
- [ ] 适配 iPhone X 安全区域

---

#### 任务 3.3：创建辅助类型定义
**文件**：`frontend/wx-minipg/templates/page-layout.ts`

**要求**：
定义页面布局数据类型和辅助函数：
```typescript
export interface PageLayoutData {
  isLoading: boolean;
  hasError: boolean;
  errorMessage: string;
  isEmpty: boolean;
  emptyMessage: string;
  hasFooter: boolean;
  contentScrollIntoView?: string;
  contentScrollWithAnimation?: boolean;
}

export function createPageLayoutData(options: Partial<PageLayoutData> = {}): PageLayoutData {
  return {
    isLoading: false,
    hasError: false,
    errorMessage: '',
    isEmpty: false,
    emptyMessage: '暂无数据',
    hasFooter: false,
    contentScrollIntoView: '',
    contentScrollWithAnimation: true,
    ...options,
  };
}
```

**验收标准**：
- [ ] 类型文件创建完成
- [ ] 类型定义完整
- [ ] 提供辅助函数

---

### 阶段四：建立开发规范（Development Guidelines）

#### 任务 4.1：创建 UI 开发规范文档
**文件**：`frontend/wx-minipg/UI-GUIDELINES.md`

**要求**：
创建完整的 UI 开发规范文档，包含：

1. **设计原则**
   - 遵循微信官方设计规范
   - 750rpx 屏幕宽度基准
   - 8rpx 间距基准

2. **强制规则**
   - 禁止硬编码颜色、字体、间距
   - 禁止使用 px 单位（除了 1px 边框）
   - 禁止直接使用原生组件（必须使用组件库）
   - 禁止在页面中定义基础样式

3. **组件使用规范**
   - 如何引入组件
   - 组件 API 文档
   - 组件使用示例

4. **页面开发规范**
   - 必须使用 page-layout 模板
   - 页面结构要求
   - 样式命名规范

5. **CSS 变量使用规范**
   - 如何引用变量
   - 变量命名规则
   - 常用变量速查表

6. **代码示例**
   - 正确示例（突出变量/组件用法）
   - 错误示例（说明违规原因）

**验收标准**：
- [ ] 文档创建完成
- [ ] 包含所有必需章节
- [ ] 有完整的代码示例
- [ ] 有清晰的禁止行为列表

---

#### 任务 4.2：更新 AGENTS.md
**文件**：`frontend/wx-minipg/AGENTS.md`

**要求**：
在现有 AGENTS.md 中添加 "UI 开发规范" 章节，包含：

1. **引用 UI-GUIDELINES.md**
   ```markdown
   ## UI 开发规范

   详细规范见 [UI-GUIDELINES.md](./UI-GUIDELINES.md)

   ### 核心规则（必须遵守）
   ```

2. **强制规则清单**
   - ❌ 禁止硬编码颜色值
   - ❌ 禁止使用 px 单位
   - ❌ 禁止直接使用 `<button>` `<view>` 等原生组件
   - ✅ 必须使用 CSS 变量
   - ✅ 必须使用组件库组件
   - ✅ 必须使用 page-layout 模板

3. **代码检查要求**
   添加到 `npm run check` 中：
   - 检查是否有硬编码颜色
   - 检查是否有 px 单位
   - 检查是否使用了组件库

**验收标准**：
- [ ] AGENTS.md 更新完成
- [ ] 规则清晰明确
- [ ] 与 UI-GUIDELINES.md 保持一致

---

#### 任务 4.3：创建组件库文档
**文件**：`frontend/wx-minipg/components/ui/README.md`

**要求**：
创建组件库使用文档，包含：

1. **快速开始**
   - 如何引入组件
   - 全局配置

2. **组件列表**
   每个组件包含：
   - 组件名称和用途
   - API 文档（属性、事件、插槽）
   - 使用示例
   - 效果截图（可选）

3. **开发指南**
   - 如何开发新组件
   - 组件开发规范
   - 组件测试要求

**验收标准**：
- [ ] 文档创建完成
- [ ] 所有组件有完整文档
- [ ] 有清晰的使用示例

---

### 阶段五：迁移现有页面（Migration）

#### 任务 5.1：创建迁移检查清单
**文件**：`docs/task/ui-migration-checklist.md`

**要求**：
为每个页面创建迁移检查清单：

```markdown
## 页面迁移检查清单

### 页面：index（联系人列表）
- [ ] 引入 design-tokens.wxss
- [ ] 使用 page-layout 模板
- [ ] 替换为 ui-cell 组件
- [ ] 替换为 ui-avatar 组件
- [ ] 移除所有硬编码样式
- [ ] 通过代码检查
- [ ] 功能测试通过

### 页面：chat（聊天页面）
- [ ] 引入 design-tokens.wxss
- [ ] 使用 page-layout 模板
- [ ] 替换为 ui-avatar 组件
- [ ] 替换为 ui-button 组件
- [ ] 移除所有硬编码样式
- [ ] 通过代码检查
- [ ] 功能测试通过

... (其他 15 个页面)
```

**验收标准**：
- [ ] 检查清单创建完成
- [ ] 包含所有 17 个页面
- [ ] 每个页面有明确的迁移步骤

---

#### 任务 5.2：迁移示例页面
**页面**：`pages/index/` （联系人列表）

**要求**：
作为示例，完整迁移 index 页面：
1. 使用 page-layout 模板
2. 使用 ui-cell 组件替换列表项
3. 使用 ui-avatar 组件替换头像
4. 使用 ui-badge 组件替换未读徽章
5. 移除 index.wxss 中的所有硬编码样式
6. 只保留页面特有的布局样式

**验收标准**：
- [ ] 页面迁移完成
- [ ] 无硬编码样式
- [ ] 功能正常
- [ ] 通过代码检查
- [ ] 可作为其他页面的参考示例

---

#### 任务 5.3：批量迁移其他页面
**页面**：其余 16 个页面

**要求**：
按照 index 页面的示例，迁移所有其他页面。

**优先级**：
1. 高频页面：chat, profile, contact-info
2. 中频页面：login, setup, profile-edit
3. 低频页面：其他页面

**验收标准**：
- [ ] 所有页面迁移完成
- [ ] 所有页面通过检查清单
- [ ] 所有页面功能正常

---

### 阶段六：验收和优化（QA & Optimization）

#### 任务 6.1：创建 UI Demo 页面
**文件**：`pages/ui-demo/`

**要求**：
创建一个 UI 组件展示页面，用于：
1. 展示所有组件的各种状态
2. 快速检查样式一致性
3. 作为组件库文档的可视化补充

**内容**：
- 所有按钮类型和尺寸
- 所有头像尺寸
- 所有 Cell 变体
- 所有状态组件（Loading, Empty, Dialog）
- 颜色系统展示
- 间距系统展示

**验收标准**：
- [ ] Demo 页面创建完成
- [ ] 包含所有组件
- [ ] 可以快速截图检查

---

#### 任务 6.2：代码审查
**要求**：
对所有修改进行代码审查：

1. **样式检查**
   - 无硬编码颜色值
   - 无 px 单位（除了 1px 边框）
   - 所有间距为 8 的倍数

2. **组件检查**
   - 所有组件有完整的 TypeScript 类型
   - 所有组件通过 ESLint 检查
   - 所有组件有使用文档

3. **页面检查**
   - 所有页面使用 page-layout 模板
   - 所有页面使用组件库组件
   - 所有页面功能正常

**验收标准**：
- [ ] 所有检查项通过
- [ ] 无遗留的硬编码样式
- [ ] 代码质量符合规范

---

#### 任务 6.3：性能优化
**要求**：
1. 检查组件渲染性能
2. 优化 setData 调用
3. 检查包体积变化

**验收标准**：
- [ ] 页面渲染流畅
- [ ] 无性能警告
- [ ] 包体积无明显增加

---

#### 任务 6.4：文档完善
**要求**：
1. 补充所有缺失的文档
2. 更新所有过时的文档
3. 添加迁移指南

**验收标准**：
- [ ] 所有文档完整
- [ ] 文档与代码一致
- [ ] 有清晰的使用指南

---

## 实施流程

### 第一周：基础设施
- 完成阶段一：Design Tokens
- 完成阶段二：组件库（至少 Button, Cell, Avatar）
- 完成阶段三：页面模板

### 第二周：规范和示例
- 完成阶段四：开发规范文档
- 完成任务 5.2：迁移示例页面（index）
- 创建 UI Demo 页面

### 第三周：批量迁移
- 完成任务 5.3：迁移其他页面
- 高频页面优先

### 第四周：验收和优化
- 完成阶段六：代码审查和优化
- 文档完善

---

## 验收标准

### 最终验收清单

#### 代码质量
- [ ] 所有文件通过 `npm run check`
- [ ] 无 TypeScript 类型错误
- [ ] 无 ESLint 警告
- [ ] 无硬编码样式值

#### 功能完整性
- [ ] 所有 17 个页面功能正常
- [ ] 所有组件功能完整
- [ ] 所有交互正常

#### 文档完整性
- [ ] Design Tokens 文档完整
- [ ] 组件库文档完整
- [ ] UI 开发规范文档完整
- [ ] 迁移指南完整

#### 视觉一致性
- [ ] 所有页面使用统一的颜色
- [ ] 所有页面使用统一的间距
- [ ] 所有页面使用统一的字体
- [ ] 所有页面使用统一的圆角

#### 性能指标
- [ ] 页面渲染流畅（无卡顿）
- [ ] 包体积无明显增加
- [ ] 无性能警告

---

## 风险和注意事项

### 风险点
1. **迁移工作量大**：17 个页面需要逐一迁移
2. **功能回归风险**：迁移过程中可能引入 bug
3. **学习成本**：AI 需要学习新的组件库和规范

### 缓解措施
1. **分阶段实施**：先完成基础设施，再批量迁移
2. **示例先行**：先迁移一个页面作为示例
3. **充分测试**：每个页面迁移后必须测试
4. **文档先行**：先完善文档，再开始迁移

### 注意事项
1. **不要一次性修改所有文件**：容易出错且难以回滚
2. **保持功能不变**：只改样式，不改逻辑
3. **及时提交**：每完成一个阶段就提交代码
4. **保留旧代码**：迁移前备份，出问题可以回滚

---

## 后续维护

### 新页面开发流程
1. 阅读 UI-GUIDELINES.md
2. 使用 page-layout 模板
3. 使用组件库组件
4. 引用 CSS 变量
5. 通过代码检查

### 新组件开发流程
1. 在 components/ui/ 创建组件目录
2. 使用 CSS 变量定义样式
3. 编写 TypeScript 类型
4. 编写组件文档
5. 添加到 UI Demo 页面

### 代码审查要点
1. 检查是否有硬编码样式
2. 检查是否使用了组件库
3. 检查是否使用了 page-layout 模板
4. 检查是否通过代码检查

---

## 附录

### 参考资料
- [微信小程序官方文档](https://developers.weixin.qq.com/miniprogram/dev/framework/)
- [微信小程序设计规范](https://developers.weixin.qq.com/miniprogram/design/)
- [WXSS 样式文档](https://developers.weixin.qq.com/miniprogram/dev/framework/view/wxss.html)

### 相关文档
- `frontend/wx-minipg/AGENTS.md` - 现有开发规范
- `frontend/wx-minipg/UI-GUIDELINES.md` - UI 开发规范（待创建）
- `frontend/wx-minipg/components/ui/README.md` - 组件库文档（待创建）
- `docs/task/ui-migration-checklist.md` - 迁移检查清单（待创建）
