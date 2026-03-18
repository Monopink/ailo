# 微信小程序开发规则

## 技术栈

- **语言**: TypeScript 5.3+
- **运行时**: 微信小程序 (ES2020)
- **UI组件库**: TDesign MiniProgram
- **即时通讯**: Leancloud IM SDK
- **代码检查**: ESLint + @typescript-eslint + eslint-plugin-wxml
- **代码格式化**: Prettier (TS/JS/JSON/WXSS)
- **类型定义**: miniprogram-api-typings

## 参考资料

### 架构与规范
- [Service 层架构规范](../../docs/spec/client/mini-program/service-layer.md)
- [枚举与常量管理规范](../../docs/spec/client/mini-program/constants-enums.md)
- [UI 体系规范](../../docs/spec/client/mini-program/ui.md)
- [头像上传规范](../../docs/spec/client/mini-program/avatar-upload.md)
- [Device ID 规范](../../docs/spec/client/base/device-id.md)

### API 与数据
- [API文档](../../docs/api/)
- [数据字典](../../docs/data-dict/)
- [Leancloud IM 文档](../../docs/references/leancloud-docs/)
- [微信小程序官方文档](https://developers.weixin.qq.com/miniprogram/dev/framework/)

## 架构约束

### 分层依赖规则

```
Pages / Components (UI 层)
    ↓
Services (业务逻辑层)
    ↓
Utils (工具层)
    ↓
Libs (第三方库)
```

**依赖规则**: Pages/Components 可调用 Services 和 Utils；Services 可调用 Utils；Utils 可调用 Libs；禁止反向依赖。

### Service 层规范

详见 [Service 层架构规范](../../docs/spec/client/mini-program/service-layer.md)

核心约束：
- 所有 API 数据获取必须通过 Service 层
- 禁止在页面层直接调用 API 或手动构建 ViewModel
- 默认禁止内存缓存（全局共享资料除外）

### 目录结构

```
frontend/mp-weixin/
├── pages/              # 页面
├── components/         # 自定义组件
├── utils/              # 工具函数
│   ├── api.ts          # API 调用封装
│   ├── storage.ts      # 存储封装
│   └── message/        # 消息相关工具
├── typings/            # 类型定义
├── libs/               # 第三方库
├── app.ts              # 应用入口
└── app.json            # 应用配置
```

### Leancloud 集成规则

- IM 客户端在 `app.ts` 中初始化
- 全局使用唯一系统对话 ID
- Leancloud 仅用于消息传输
- 消息发送: `utils/message/service.ts`
- 消息接收: `app.ts` 监听，分发到各页面
- 消息重试: 队列机制 (`utils/message/queue.ts`)
- 会话状态: 本地存储 (`utils/message/conversation-store.ts`)
- 禁止在 Leancloud 中存储业务逻辑

## 编程规范

### 枚举管理

详见 [枚举与常量管理规范](../../docs/spec/client/mini-program/constants-enums.md)

核心约束：
- 所有枚举集中管理在 `utils/constants/` 目录
- 枚举值必须与后端完全一致
- 禁止在页面/组件中定义本地枚举

### 类型系统

- Page 必须定义类型参数: `Page<PageData>`
- 事件处理器必须明确事件类型: `WechatMiniprogram.TouchEvent`
- 第三方库创建类型定义: `typings/*.d.ts`

### API 与存储

- 所有 API 调用通过 `utils/api.ts`，使用泛型指定返回类型: `get<UserInfo>('/users/123')`
- 所有存储操作通过 `utils/storage.ts`，使用泛型指定类型: `getStorage<string>('token')`
- 禁止直接使用 `wx.request` / `wx.getStorageSync` / `wx.setStorageSync`

**运行时验证（新代码必须使用 Zod）**:

<critical-rules>
**必须使用 Zod 的场景**:
- 用户认证相关（登录、注册、获取用户信息）
- 关键业务数据（消息、会话、联系人）
- 所有新功能的 API 调用
</critical-rules>

**使用方法**: 在 `utils/schemas.ts` 定义 Schema，使用 `getValidated()` 替代 `get()`。参考 `utils/api-validated.ts` 和现有 Schema 定义。

### 状态管理

- 使用 TypeScript 接口定义 Page Data
- setData 必须批量更新，使用路径更新: `this.setData({ 'user.name': newName })`
- 禁止修改第三方库代码 (`libs/` 目录)

### UI 开发

详见 [UI 体系规范](../../docs/spec/client/mini-program/ui.md)

核心规则:
- 使用 TDesign 组件库
- 禁止硬编码样式值，仅使用语义化变量（`var(--color-*)`）
- 禁止使用 px 单位（除了 1px 边框），使用 rpx

### 代码检查

提交前必须运行 `npm run check` 并通过，禁止跳过检查或提交未格式化代码。

```bash
cd frontend/mp-weixin
npm run check  # type-check + lint + lint:style + ui:audit
```

常用命令: `npm run lint:fix`（自动修复）、`npm run format`（代码格式化）。Pre-commit Hook 自动执行检查和格式化。

## 环境配置

### 安装依赖

```bash
cd frontend/mp-weixin
npm install
```

### 微信开发者工具配置

确认 `project.config.json` 配置:
```json
{
  "setting": {
    "useCompilerPlugins": ["typescript"]
  }
}
```

注意: 微信开发者工具的编译器只移除类型注解，不进行类型检查。必须使用 `npm run type-check` 进行类型检查。
