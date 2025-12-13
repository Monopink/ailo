# TDesign 迁移总体规划

**创建日期**: 2025-12-12
**状态**: 执行中
**预计完成**: 3-5天

---

## 执行摘要

将小程序UI从自研组件库迁移到 TDesign 官方组件库，保留业务组件，优化开发流程。

### 关键指标
- **页面总数**: 21
- **已完成页面**: 2 (index, chat)
- **待迁移页面**: 19
- **自研组件**: 27个 (102个文件)
- **待删除通用组件**: 24个 (~95个文件)
- **保留业务组件**: 3个 (gender-badge, message-bubble, message-input)

---

## 第一阶段: 组件映射与清理 (Day 1)

### 1.1 组件替换映射表

| 自研组件 | TDesign组件 | 状态 | 备注 |
|---------|------------|------|------|
| `ui-avatar` | `t-avatar` | ✅ 可替换 | |
| `ui-badge` | `t-badge` | ✅ 可替换 | |
| `ui-button` | `t-button` | ✅ 可替换 | |
| `ui-cell` | `t-cell` | ✅ 可替换 | |
| `ui-cells` | `t-cell-group` | ✅ 可替换 | 名称不同 |
| `ui-card` | `t-card` | ✅ 可替换 | |
| `ui-dialog` | `t-dialog` | ✅ 可替换 | |
| `ui-divider` | `t-divider` | ✅ 可替换 | |
| `ui-empty` | `t-empty` | ✅ 可替换 | |
| `ui-icon` | `t-icon` | ✅ 可替换 | 图标库不同，需调整 |
| `ui-input` | `t-input` | ✅ 可替换 | |
| `ui-loading` | `t-loading` | ✅ 可替换 | |
| `ui-picker` | `t-picker` | ✅ 可替换 | |
| `ui-tag` | `t-tag` | ✅ 可替换 | |
| `ui-switch` | `t-switch` | ✅ 可替换 | |
| `ui-checkbox` | `t-checkbox` | ✅ 可替换 | |
| `ui-checkbox-group` | `t-checkbox-group` | ✅ 可替换 | |
| `ui-radio` | `t-radio` | ✅ 可替换 | |
| `ui-radio-group` | `t-radio-group` | ✅ 可替换 | |
| `ui-navbar` | `t-navbar` | ✅ 可替换 | |
| `ui-toast` | `t-toast` | ✅ 可替换 | API方式调用 |
| `ui-action-sheet` | `t-action-sheet` | ✅ 可替换 | |
| `ui-actionsheet` | `t-action-sheet` | ✅ 可替换 | 重复组件 |
| **业务组件** |
| `ui-gender-badge` | - | 🔒 保留 | 业务逻辑 |
| `ui-message-bubble` | - | 🔒 保留 | 聊天业务 |
| `ui-message-input` | - | 🔒 保留 | 聊天业务 |

### 1.2 文件清理计划

**立即删除（移动到 deleted/）：**

```bash
# 通用组件（24个组件，约95个文件）
frontend/wx-minipg/components/ui/avatar/
frontend/wx-minipg/components/ui/badge/
frontend/wx-minipg/components/ui/button/
frontend/wx-minipg/components/ui/card/
frontend/wx-minipg/components/ui/cell/
frontend/wx-minipg/components/ui/cells/
frontend/wx-minipg/components/ui/checkbox/
frontend/wx-minipg/components/ui/checkbox-group/
frontend/wx-minipg/components/ui/dialog/
frontend/wx-minipg/components/ui/divider/
frontend/wx-minipg/components/ui/empty/
frontend/wx-minipg/components/ui/icon/
frontend/wx-minipg/components/ui/input/
frontend/wx-minipg/components/ui/loading/
frontend/wx-minipg/components/ui/navbar/
frontend/wx-minipg/components/ui/picker/
frontend/wx-minipg/components/ui/radio/
frontend/wx-minipg/components/ui/radio-group/
frontend/wx-minipg/components/ui/switch/
frontend/wx-minipg/components/ui/tag/
frontend/wx-minipg/components/ui/toast/
frontend/wx-minipg/components/ui/action-sheet/
frontend/wx-minipg/components/ui/actionsheet/  # 重复组件
```

**保留文件：**

```bash
# 业务组件（3个）
frontend/wx-minipg/components/ui/gender-badge/
frontend/wx-minipg/components/ui/message-bubble/
frontend/wx-minipg/components/ui/message-input/

# 文档和工具
frontend/wx-minipg/components/ui/README.md  # 更新说明保留业务组件
frontend/wx-minipg/utils/component-validators.ts  # 业务组件仍需使用
```

**删除后的目录结构：**

```
frontend/wx-minipg/components/ui/
├── gender-badge/       # 保留：业务组件
├── message-bubble/     # 保留：业务组件
├── message-input/      # 保留：业务组件
└── README.md           # 更新：说明使用TDesign
```

---

## 第二阶段: 页面迁移 (Day 2-4)

### 2.1 迁移优先级

#### Tier 1: 核心页面（高优先级）
✅ **已完成**:
1. index (首页联系人列表) - 已完成
2. chat (聊天详情页) - 已完成

⏳ **待迁移**:
3. **chat-detail** - 聊天详情，使用频率最高
4. **square** - 广场页，核心功能
5. **profile** - 个人中心，核心入口

#### Tier 2: 用户功能页（中优先级）
6. **profile-edit** - 个人资料编辑
7. **profile-detail** - 资料详情查看
8. **contact-info** - 联系人信息
9. **stranger-info** - 陌生人信息
10. **contact-requests** - 好友请求

#### Tier 3: 账号与认证（中优先级）
11. **login** - 登录页
12. **phone-login** - 手机登录
13. **phone-bind** - 绑定手机
14. **phone-manage** - 手机管理
15. **verify** - 验证码
16. **account-security** - 账号安全

#### Tier 4: 辅助页面（低优先级）
17. **setup** - 设置页
18. **avatar-selector** - 头像选择
19. **welcome** - 欢迎页
20. **boot** - 启动页
21. **about** - 关于页

### 2.2 单页迁移SOP（标准操作流程）

每个页面按以下步骤迁移：

#### Step 1: 更新 .json 配置（1分钟）

```json
{
  "usingComponents": {
    // 删除所有 ui-* 引用
    // 添加 TDesign 组件引用
    "t-cell": "tdesign-miniprogram/cell/cell",
    "t-avatar": "tdesign-miniprogram/avatar/avatar",
    "t-badge": "tdesign-miniprogram/badge/badge",
    // ... 按需添加

    // 保留业务组件引用
    "ui-gender-badge": "/components/ui/gender-badge/gender-badge"
  }
}
```

#### Step 2: 更新 .wxml 模板（5-10分钟）

**替换规则：**
```xml
<!-- 旧语法 -->
<ui-cell
  title="{{title}}"
  value="{{value}}"
  link="{{true}}" />

<!-- 新语法 -->
<t-cell
  title="{{title}}"
  note="{{value}}"
  arrow
  bindtap="handleTap" />
```

**注意事项：**
- TDesign属性名可能不同（如 `value` → `note`）
- 事件绑定方式可能不同
- 查阅 [TDesign文档](https://tdesign.tencent.com/miniprogram/components/cell)

#### Step 3: 更新 .wxss 样式（2-5分钟）

```css
/* 第一行：引入TDesign主题（必须） */
@import '/styles/tdesign-theme.wxss';

/* 删除所有 .ui-* 相关的自定义样式 */
/* 只保留页面布局样式 */

/* 如需覆盖TDesign样式，使用CSS变量 */
.my-custom-cell {
  /* 不直接修改TDesign组件样式 */
}
```

#### Step 4: 更新 .ts 逻辑（可选，0-5分钟）

- 如果使用了 `ui-toast`，改为 TDesign API方式：
  ```typescript
  // 旧方式
  this.selectComponent('#toast').show('提示信息');

  // 新方式
  import Toast from 'tdesign-miniprogram/toast/index';
  Toast({ message: '提示信息' });
  ```

#### Step 5: 运行检查（1分钟）

```bash
cd frontend/wx-minipg
npm run check  # type-check + lint + lint:style + ui:audit
```

**必须通过所有检查才能继续下一个页面**

#### Step 6: 测试验证（2-3分钟）

- 微信开发者工具预览
- 检查浅色模式显示
- 检查深色模式显示
- 检查交互功能

### 2.3 批量迁移策略

**方式一：串行迁移（稳妥）**
- 一个页面完成后再开始下一个
- 优点：风险可控
- 缺点：耗时较长

**方式二：并行迁移（快速）**
- 同时迁移多个页面
- 优点：速度快
- 缺点：可能产生冲突
- **推荐在Tier内并行，Tier间串行**

---

## 第三阶段: Linter与自动化 (Day 1)

### 3.1 ui-audit.cjs 更新

✅ **已完成** - 简化为检查TDesign规则：

```javascript
// 检查项：
1. 所有页面WXSS必须 @import '/styles/tdesign-theme.wxss'
2. 禁止硬编码px（除1px边框）
3. （删除）不再检查 ui-* 组件使用
4. （删除）不再检查 page-layout
```

### 3.2 ESLint 配置调整

**无需修改** - `.eslintrc.js` 规则与组件库无关

### 3.3 Stylelint 配置调整

**已更新** - `package.json` stylelint规则：

```json
"stylelint": {
  "overrides": [
    {
      "files": [
        "styles/design-tokens.wxss",
        "styles/tdesign-theme.wxss"  // ✅ 已添加豁免
      ],
      "rules": {
        "color-no-hex": null  // 允许主题文件使用hex颜色
      }
    }
  ]
}
```

### 3.4 新增迁移辅助脚本

**创建 `scripts/migrate-page.sh`** - 自动化单页迁移：

```bash
#!/bin/bash
# 用法: ./scripts/migrate-page.sh profile

PAGE_NAME=$1
PAGE_DIR="frontend/wx-minipg/pages/$PAGE_NAME"

echo "🚀 开始迁移页面: $PAGE_NAME"

# 1. 备份原文件
cp "$PAGE_DIR/$PAGE_NAME.json" "$PAGE_DIR/$PAGE_NAME.json.bak"
cp "$PAGE_DIR/$PAGE_NAME.wxml" "$PAGE_DIR/$PAGE_NAME.wxml.bak"
cp "$PAGE_DIR/$PAGE_NAME.wxss" "$PAGE_DIR/$PAGE_NAME.wxss.bak"

# 2. 在WXSS第一行添加TDesign主题引入
sed -i '1i@import "/styles/tdesign-theme.wxss";\n' "$PAGE_DIR/$PAGE_NAME.wxss"

# 3. 检查使用了哪些ui-组件
echo "📋 检测到以下ui-组件："
grep -o '"ui-[^"]*"' "$PAGE_DIR/$PAGE_NAME.json" || echo "  无ui-组件"

echo "✅ 备份完成，请手动完成以下步骤："
echo "  1. 修改 $PAGE_NAME.json - 替换ui-组件为t-组件"
echo "  2. 修改 $PAGE_NAME.wxml - 更新组件标签"
echo "  3. 检查 $PAGE_NAME.wxss - 删除ui-相关样式"
echo "  4. 运行 'npm run check' 验证"
```

### 3.5 批量检查脚本

**创建 `scripts/check-migration-status.sh`**：

```bash
#!/bin/bash
# 检查哪些页面还在使用ui-组件

echo "📊 TDesign迁移状态报告"
echo "================================"

TOTAL=0
MIGRATED=0

for json_file in frontend/wx-minipg/pages/*/*.json; do
  TOTAL=$((TOTAL + 1))
  page_name=$(basename $(dirname $json_file))

  if grep -q '"ui-' "$json_file" 2>/dev/null; then
    echo "❌ $page_name - 使用ui-组件"
  else
    echo "✅ $page_name - 已迁移/无ui-组件"
    MIGRATED=$((MIGRATED + 1))
  fi
done

echo "================================"
echo "进度: $MIGRATED / $TOTAL 页面已迁移"
echo "完成度: $((MIGRATED * 100 / TOTAL))%"
```

---

## 第四阶段: 文档更新 (Day 5)

### 4.1 需要更新的文档

| 文件 | 更新内容 |
|------|---------|
| `frontend/wx-minipg/AGENTS.md` | 更新UI开发规范指向TDesign |
| `docs/spec/mini-program/UI-GUIDELINES.md` | 完全重写为TDesign规范 |
| `frontend/wx-minipg/components/ui/README.md` | 说明保留的业务组件 |
| `docs/task/tdesign-migration-master-plan.md` | 本文档 - 记录进度 |

### 4.2 UI-GUIDELINES.md 重写大纲

```markdown
# 小程序 UI 开发规范（TDesign版）

## 设计原则
- 遵循微信官方设计规范
- 使用TDesign组件库
- 通过CSS Variables定制主题

## 组件使用规范
### 基础组件
- t-button
- t-cell / t-cell-group
- t-avatar
- ...

### 业务组件
- ui-gender-badge（性别徽章）
- ui-message-bubble（消息气泡）
- ui-message-input（消息输入）

## 主题定制
- 修改 /styles/tdesign-theme.wxss
- 使用 --td-* CSS变量

## 页面开发流程
1. 在 .json 中注册TDesign组件
2. 在 .wxss 第一行引入 @import '/styles/tdesign-theme.wxss'
3. 使用 <t-*> 组件标签
4. 运行 npm run check 验证
```

---

## 第五阶段: 验收与优化 (Day 5)

### 5.1 验收清单

**功能验收：**
- [ ] 所有21个页面正常显示
- [ ] 所有交互功能正常
- [ ] 浅色模式正常
- [ ] 深色模式正常（如果支持）
- [ ] 真机测试通过

**代码验收：**
- [ ] `npm run check` 全部通过
- [ ] 无残留的 `ui-*` 组件引用
- [ ] 所有WXSS引入了 `tdesign-theme.wxss`
- [ ] Git提交历史清晰

**清理验收：**
- [ ] 24个通用组件已移至 `deleted/`
- [ ] 只保留3个业务组件
- [ ] 删除未使用的工具函数
- [ ] 更新所有相关文档

### 5.2 性能优化

**包体积对比：**
```bash
# 迁移前
du -sh frontend/wx-minipg/components/ui/
# 预计: ~200-300KB

# 迁移后
du -sh frontend/wx-minipg/components/ui/
# 预计: ~30-50KB (只保留3个业务组件)

# TDesign库大小
du -sh frontend/wx-minipg/miniprogram_npm/tdesign-miniprogram/
# 按需加载，实际只打包用到的组件
```

**优化点：**
- TDesign组件按需加载
- 删除冗余的自研组件代码
- 主题CSS变量复用

---

## 风险与应对

### 风险1: TDesign组件API不兼容

**概率**: 中
**影响**: 高

**应对措施：**
1. 迁移前仔细阅读 [TDesign文档](https://tdesign.tencent.com/miniprogram/overview)
2. 对比自研组件与TDesign的API差异
3. 准备适配层（wrapper组件）如有必要
4. 保留备份，可快速回滚

### 风险2: 样式不一致

**概率**: 高
**影响**: 中

**应对措施：**
1. 通过 `tdesign-theme.wxss` 统一定制
2. 使用 `--td-*` CSS变量覆盖默认样式
3. 必要时使用 `external-classes` 定制组件样式
4. 参考 [TDesign主题定制文档](https://tdesign.tencent.com/miniprogram/custom-theme)

### 风险3: 图标库差异

**概率**: 高
**影响**: 中

**应对措施：**
1. `ui-icon` 使用WeUI图标库（Base64 SVG）
2. `t-icon` 使用TDesign图标库
3. 逐一替换图标名称，查阅 [TDesign图标库](https://tdesign.tencent.com/miniprogram/components/icon)
4. 如TDesign缺少某些图标，可使用自定义图片

### 风险4: 业务组件依赖通用组件

**概率**: 低
**影响**: 高

**应对措施：**
1. 检查3个业务组件是否依赖其他 `ui-*` 组件
2. 如有依赖，迁移业务组件使用TDesign
3. 或将依赖的通用组件也保留（但要说明原因）

---

## 进度追踪

### 当前状态（2025-12-12）

**Phase 1: 组件清理** - ⏳ 待执行
- [ ] 创建迁移脚本
- [ ] 移动24个通用组件到 `deleted/`
- [ ] 更新 `components/ui/README.md`

**Phase 2: 页面迁移** - 🚧 进行中 (2/21)
- ✅ index (首页)
- ✅ chat (聊天页)
- ⏳ 待迁移: 19个页面

**Phase 3: Linter更新** - ✅ 已完成
- ✅ ui-audit.cjs 简化
- ✅ stylelint 添加豁免规则

**Phase 4: 文档更新** - ⏳ 待执行
- [ ] AGENTS.md
- [ ] UI-GUIDELINES.md
- [ ] components/ui/README.md

**Phase 5: 验收** - ⏳ 待执行
- [ ] 功能测试
- [ ] 代码审查
- [ ] 性能测试

### 下一步行动

**立即执行（今天）：**
1. 创建迁移辅助脚本
2. 移动24个通用组件到 `deleted/ui-components-2025-12-12/`
3. 开始迁移 Tier 1 核心页面（chat-detail, square, profile）

**本周执行：**
4. 完成 Tier 2-3 页面迁移
5. 更新所有文档
6. 运行完整验收测试

---

## 参考资料

- [TDesign MiniProgram 官方文档](https://tdesign.tencent.com/miniprogram/overview)
- [TDesign GitHub](https://github.com/Tencent/tdesign-miniprogram)
- [TDesign 主题定制](https://tdesign.tencent.com/miniprogram/custom-theme)
- [TDesign 图标库](https://tdesign.tencent.com/miniprogram/components/icon)

---

**更新记录：**
- 2025-12-12: 创建初版，index和chat已完成迁移
