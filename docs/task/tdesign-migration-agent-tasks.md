# TDesign 迁移 - Agent 任务分配

**创建日期**: 2025-12-12
**总体进度**: 2/20 页面已完成 (10%)
**执行模式**: 两个Agent并行工作

---

## 任务划分原则

**按功能领域划分**，减少文件冲突：
- **Agent A**: 用户与内容域（User & Content Domain）
- **Agent B**: 系统与认证域（System & Auth Domain）+ 清理任务

**优势：**
✅ 两个domain不重叠，无文件冲突
✅ 可以完全并行执行
✅ 职责边界清晰
✅ 工作量相对平衡（9页面 vs 9页面+清理）

---

## Agent A: 用户与内容域

**职责**: 迁移所有与用户资料、社交互动相关的页面
**页面数量**: 9个
**预计耗时**: 4-5小时
**优先级**: 包含3个Tier 1核心页面

### 任务列表

#### Tier 1 - 核心页面（高优先级，先做）

1. **chat-detail** - 聊天详情页
   - 路径: `pages/chat-detail/`
   - 复杂度: ⭐⭐⭐⭐
   - 组件: t-navbar, t-avatar, ui-message-bubble, ui-message-input
   - 注意事项: 聊天UI是核心体验，需要保留业务组件

2. **square** - 广场页
   - 路径: `pages/square/`
   - 复杂度: ⭐⭐⭐⭐
   - 组件: t-cell-group, t-avatar, t-badge, t-tag, ui-gender-badge
   - 注意事项: 陌生人列表展示，使用大量TDesign组件

3. **profile** - 个人中心
   - 路径: `pages/profile/`
   - 复杂度: ⭐⭐⭐
   - 组件: t-cell-group, t-avatar, t-badge, ui-gender-badge
   - 注意事项: 主要入口页面，测试需覆盖所有菜单项

#### Tier 2 - 用户功能页（中优先级）

4. **profile-edit** - 个人资料编辑
   - 路径: `pages/profile-edit/`
   - 复杂度: ⭐⭐⭐⭐
   - 组件: t-cell-group, t-input, t-picker, t-textarea, t-avatar
   - 注意事项: 表单页面，注意输入验证和保存逻辑

5. **profile-detail** - 个人资料详情查看
   - 路径: `pages/profile-detail/`
   - 复杂度: ⭐⭐⭐
   - 组件: t-cell-group, t-avatar, ui-gender-badge, t-tag
   - 注意事项: 展示页面，相对简单

6. **contact-info** - 联系人信息
   - 路径: `pages/contact-info/`
   - 复杂度: ⭐⭐⭐
   - 组件: t-cell-group, t-avatar, ui-gender-badge, t-button
   - 注意事项: 与stranger-info结构类似

7. **stranger-info** - 陌生人信息
   - 路径: `pages/stranger-info/`
   - 复杂度: ⭐⭐⭐
   - 组件: t-cell-group, t-avatar, ui-gender-badge, t-button
   - 注意事项: 与contact-info结构类似，可复用经验

8. **contact-requests** - 好友请求列表
   - 路径: `pages/contact-requests/`
   - 复杂度: ⭐⭐
   - 组件: t-cell-group, t-avatar, t-button
   - 注意事项: 列表页面，相对简单

#### Tier 4 - 辅助页面（低优先级，最后做）

9. **avatar-selector** - 头像选择器
   - 路径: `pages/avatar-selector/`
   - 复杂度: ⭐⭐
   - 组件: t-button, t-image（或原生image）
   - 注意事项: 简单的选择器页面

---

### Agent A 执行计划

#### Phase 1: Tier 1 核心页面（2-3小时）

```bash
cd frontend/wx-minipg

# 1. chat-detail（最复杂，优先完成）
./scripts/migrate-page.sh chat-detail
# 手动修改 .json / .wxml / .wxss / .ts
# 重点：保留 ui-message-bubble 和 ui-message-input
npm run check
# DevTools测试

# 2. square（用户发现页）
./scripts/migrate-page.sh square
# 手动修改
npm run check
# DevTools测试

# 3. profile（个人中心入口）
./scripts/migrate-page.sh profile
# 手动修改
npm run check
# DevTools测试

# 检查进度
./scripts/check-migration-status.sh
# 应该显示: 5/20 pages migrated (25%)
```

#### Phase 2: Tier 2 用户功能页（1.5-2小时）

```bash
# 批量生成备份
for page in profile-edit profile-detail contact-info stranger-info contact-requests; do
  ./scripts/migrate-page.sh $page
done

# 逐个手动修改
# 优先顺序: profile-edit > profile-detail > contact-info > stranger-info > contact-requests

# 每完成一个运行检查
npm run check

# 检查进度
./scripts/check-migration-status.sh
# 应该显示: 10/20 pages migrated (50%)
```

#### Phase 3: Tier 4 辅助页面（30分钟）

```bash
# avatar-selector
./scripts/migrate-page.sh avatar-selector
# 手动修改
npm run check

# 最终检查
./scripts/check-migration-status.sh
# 应该显示: 11/20 pages migrated (55%)
```

---

### Agent A 完成标准

#### 代码质量
- [ ] 所有9个页面的 `.json` 已更新（ui-* → t-*）
- [ ] 所有9个页面的 `.wxml` 已更新（组件标签和属性）
- [ ] 所有9个页面的 `.wxss` 已更新（引入theme，删除ui-样式）
- [ ] 所有9个页面的 `.ts` 已更新（如需要）
- [ ] `npm run check` 完全通过

#### 功能测试
- [ ] DevTools预览所有页面 - 浅色模式正常
- [ ] DevTools预览所有页面 - 深色模式正常（如支持）
- [ ] 所有交互功能正常（点击、输入、跳转）
- [ ] 业务组件（ui-gender-badge, ui-message-*）正常工作

#### 提交
- [ ] Git提交所有修改
- [ ] Commit message: `feat(ui): migrate user domain pages to TDesign (9 pages)`
- [ ] 删除所有 `.bak` 备份文件

---

## Agent B: 系统与认证域 + 清理任务

**职责**: 迁移所有认证、系统设置相关页面 + 执行清理和文档更新
**页面数量**: 9个
**额外任务**: 组件清理 + 文档更新
**预计耗时**: 5-6小时
**优先级**: Tier 3优先，Tier 4次之，清理任务最后

### 任务列表

#### Tier 3 - 认证与账号页（中高优先级，先做）

1. **login** - 登录页
   - 路径: `pages/login/`
   - 复杂度: ⭐⭐⭐
   - 组件: t-button, t-input
   - 注意事项: 登录入口，需确保功能正常

2. **phone-login** - 手机号登录
   - 路径: `pages/phone-login/`
   - 复杂度: ⭐⭐⭐
   - 组件: t-input, t-button
   - 注意事项: 与verify配合使用

3. **verify** - 验证码输入
   - 路径: `pages/verify/`
   - 复杂度: ⭐⭐
   - 组件: t-input, t-button
   - 注意事项: 倒计时逻辑不要破坏

4. **phone-bind** - 绑定手机号
   - 路径: `pages/phone-bind/`
   - 复杂度: ⭐⭐⭐
   - 组件: t-input, t-button
   - 注意事项: 与verify类似

5. **phone-manage** - 手机号管理
   - 路径: `pages/phone-manage/`
   - 复杂度: ⭐⭐
   - 组件: t-cell-group, t-button
   - 注意事项: 显示和解绑手机号

6. **account-security** - 账号安全
   - 路径: `pages/account-security/`
   - 复杂度: ⭐⭐⭐
   - 组件: t-cell-group
   - 注意事项: 安全设置入口

#### Tier 4 - 系统辅助页（低优先级，后做）

7. **setup** - 设置页
   - 路径: `pages/setup/`
   - 复杂度: ⭐⭐⭐
   - 组件: t-cell-group, t-switch
   - 注意事项: 系统设置总入口

8. **boot** - 启动页
   - 路径: `pages/boot/`
   - 复杂度: ⭐
   - 组件: t-loading
   - 注意事项: 简单的加载页

9. **about** - 关于页
   - 路径: `pages/about/`
   - 复杂度: ⭐
   - 组件: t-cell-group
   - 注意事项: 简单的信息展示页

---

### Agent B 执行计划

#### Phase 1: Tier 3 认证页（2-3小时）

```bash
cd frontend/wx-minipg

# 认证流程相关（6个页面）
# 建议按功能流程顺序迁移

# 1. login（入口）
./scripts/migrate-page.sh login
# 手动修改
npm run check
# DevTools测试

# 2. phone-login + verify（一组）
./scripts/migrate-page.sh phone-login
./scripts/migrate-page.sh verify
# 逐个手动修改
npm run check

# 3. phone-bind + phone-manage（一组）
./scripts/migrate-page.sh phone-bind
./scripts/migrate-page.sh phone-manage
# 逐个手动修改
npm run check

# 4. account-security（总入口）
./scripts/migrate-page.sh account-security
# 手动修改
npm run check

# 检查进度
./scripts/check-migration-status.sh
# 应该显示: 13/20 pages migrated (65%)
```

#### Phase 2: Tier 4 系统页（1小时）

```bash
# 系统设置相关（3个页面）

# 1. setup（设置入口）
./scripts/migrate-page.sh setup
npm run check

# 2. boot（启动页，简单）
./scripts/migrate-page.sh boot
npm run check

# 3. about（关于页，简单）
./scripts/migrate-page.sh about
npm run check

# 检查进度
./scripts/check-migration-status.sh
# 应该显示: 16/20 pages migrated (80%)
```

**等待Agent A完成（同步点）**

#### Phase 3: 组件清理（30分钟）

⚠️ **必须等待Agent A完成所有页面迁移后才能执行此步骤**

```bash
# 1. 确认所有页面已迁移
./scripts/check-migration-status.sh
# 必须显示: 20/20 pages migrated (100%)

# 2. 执行清理脚本
./scripts/cleanup-ui-components.sh
# 确认后回车

# 3. 验证清理结果
ls components/ui/
# 应该只剩下：gender-badge/ message-bubble/ message-input/ README.md

# 4. 验证所有检查通过
npm run check
```

#### Phase 4: 文档更新（30-60分钟）

```bash
# 1. 更新 AGENTS.md
# 修改UI开发规范指向新文档
# 删除旧的ui-*组件说明

# 2. 更新 components/ui/README.md
# 说明只保留3个业务组件
# 说明通用组件已迁移到TDesign

# 3. 验证文档链接
# 确保所有文档链接正确

# 4. 删除旧文档（可选）
# 移动 docs/spec/mini-program/UI-GUIDELINES.md 到 deleted/
# 重命名 UI-GUIDELINES-tdesign.md 为 UI-GUIDELINES.md
```

---

### Agent B 完成标准

#### 页面迁移
- [ ] 所有9个页面的 `.json` 已更新（ui-* → t-*）
- [ ] 所有9个页面的 `.wxml` 已更新（组件标签和属性）
- [ ] 所有9个页面的 `.wxss` 已更新（引入theme，删除ui-样式）
- [ ] 所有9个页面的 `.ts` 已更新（如需要）
- [ ] `npm run check` 完全通过

#### 组件清理
- [ ] 24个通用组件已移至 `deleted/ui-components-YYYYMMDD-HHMMSS/`
- [ ] 只保留3个业务组件：gender-badge, message-bubble, message-input
- [ ] `components/ui/` 目录清爽整洁
- [ ] 清理后 `npm run check` 仍通过

#### 文档更新
- [ ] `frontend/wx-minipg/AGENTS.md` 已更新UI规范章节
- [ ] `components/ui/README.md` 已更新说明保留组件
- [ ] 旧文档已归档或删除
- [ ] 所有文档链接正确

#### 功能测试
- [ ] DevTools预览所有9个页面 - 浅色模式正常
- [ ] DevTools预览所有9个页面 - 深色模式正常（如支持）
- [ ] 认证流程测试通过（login → phone-login → verify）
- [ ] 设置页面所有功能正常

#### 提交
- [ ] Git提交所有修改
- [ ] Commit message: `feat(ui): migrate system domain pages + cleanup (9 pages + cleanup)`
- [ ] 删除所有 `.bak` 备份文件

---

## 并行协作机制

### 同步点

**Sync Point 1: 开始前对齐**
- [ ] 两个Agent都理解任务范围
- [ ] 确认无文件冲突（domain不重叠）
- [ ] 同时开始执行

**Sync Point 2: Agent A完成通知**
- [ ] Agent A完成9个页面迁移
- [ ] 提交代码并通知Agent B
- [ ] Agent B检查迁移状态后开始清理

**Sync Point 3: 最终验收**
- [ ] Agent B完成清理和文档
- [ ] 两个Agent一起运行最终验收测试
- [ ] 提交最终代码

### 冲突避免

✅ **无文件冲突风险**
- Agent A只修改用户域页面
- Agent B只修改系统域页面
- 清理任务在Agent A完成后才执行

✅ **独立测试**
- 各自运行 `npm run check`
- 各自在DevTools中测试
- 最终一起验收

---

## 验收标准（最终）

两个Agent都完成后，一起执行：

### 代码检查
```bash
cd frontend/wx-minipg

# 1. 类型检查
npm run type-check
# 必须通过，无错误

# 2. ESLint
npm run lint
# 必须通过，无错误

# 3. Stylelint
npm run lint:style
# 必须通过，无错误

# 4. UI Audit
npm run ui:audit
# 必须通过，无错误

# 5. 完整检查
npm run check
# 必须全部通过
```

### 迁移状态
```bash
# 检查迁移完成度
./scripts/check-migration-status.sh
# 必须显示: 20/20 pages migrated (100%)

# 检查组件清理
ls components/ui/
# 只有: gender-badge/ message-bubble/ message-input/ README.md

# 检查deleted目录
ls deleted/
# 应该有: ui-components-YYYYMMDD-HHMMSS/
```

### 功能测试

**Agent A负责测试:**
- [ ] 9个用户域页面全部功能正常
- [ ] 浅色/深色模式切换正常
- [ ] 真机测试通过（iOS + Android）

**Agent B负责测试:**
- [ ] 9个系统域页面全部功能正常
- [ ] 认证流程完整测试通过
- [ ] 浅色/深色模式切换正常
- [ ] 真机测试通过（iOS + Android）

### 最终提交
```bash
# 合并提交（或分别提交）
git add .
git commit -m "feat(ui): complete TDesign migration

- Migrated 18 pages from ui-* to TDesign components
- Agent A: 9 user domain pages
- Agent B: 9 system domain pages + cleanup
- Removed 24 general-purpose components
- Kept 3 business components (gender-badge, message-bubble, message-input)
- Updated documentation and linter rules

Closes #XXX"

git push
```

---

## 预计时间表

| 阶段 | Agent A | Agent B | 总耗时 |
|------|---------|---------|--------|
| **Phase 1** | Tier 1核心页（3个）<br>2-3小时 | Tier 3认证页（6个）<br>2-3小时 | 2-3小时（并行） |
| **Phase 2** | Tier 2用户页（5个）<br>1.5-2小时 | Tier 4系统页（3个）<br>1小时 | 1.5-2小时（并行） |
| **Phase 3** | Tier 4辅助页（1个）<br>30分钟 | 等待Agent A完成<br>- | 30分钟（串行） |
| **Phase 4** | - | 组件清理<br>30分钟 | 30分钟（串行） |
| **Phase 5** | - | 文档更新<br>30-60分钟 | 30-60分钟（串行） |
| **验收** | 测试 + 提交<br>30分钟 | 测试 + 提交<br>30分钟 | 30分钟（并行） |
| **总计** | 4.5-6小时 | 5-6.5小时 | **5.5-7小时** |

**预计完成时间**: 1个工作日（如果两个Agent并行工作）

---

## 快速启动指令

### Agent A 快速启动

```bash
cd frontend/wx-minipg

# 读取任务
cat docs/task/tdesign-migration-agent-tasks.md

# 开始执行
./scripts/migrate-page.sh chat-detail
# ... 按Phase 1-3执行
```

### Agent B 快速启动

```bash
cd frontend/wx-minipg

# 读取任务
cat docs/task/tdesign-migration-agent-tasks.md

# 开始执行
./scripts/migrate-page.sh login
# ... 按Phase 1-5执行
```

---

**准备就绪！两个Agent可以开始并行工作了。**

**记住：Agent B的Phase 3（清理）必须等Agent A完成所有页面后才能执行！**
