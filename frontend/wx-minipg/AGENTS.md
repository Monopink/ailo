# 微信小程序开发规则

## 技术栈

- **语言**: TypeScript 5.3+
- **运行时**: 微信小程序 (ES2020)
- **即时通讯**: Leancloud IM SDK
- **代码检查**: ESLint + @typescript-eslint
- **代码格式化**: Prettier
- **类型定义**: miniprogram-api-typings

## 参考资料

- [微信小程序官方文档](https://developers.weixin.qq.com/miniprogram/dev/framework/)
- [API文档](../../docs/api/)
- [数据字典](../../docs/data-dict/)
- [代码检查](../../docs/tech/CODE_QUALITY.md)
- [Leancloud IM 文档](../../references/leancloud-docs/)

## 架构约束

### 分层依赖规则

**层级结构** (从上到下):
```
Pages / Components (UI 层)
    ↓
Utils (工具层)
    ↓
Libs (第三方库)
```

**依赖规则**:
- Pages/Components 可以调用 Utils
- Utils 可以调用 Libs
- 禁止反向依赖 (下层不能依赖上层)

### 目录结构

```
frontend/wx-minipg/
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
- Leancloud 仅用于消息传输，不存储业务逻辑
- 消息发送: `utils/message/service.ts`
- 消息接收: `app.ts` 监听，分发到各页面
- 消息重试: 队列机制 (`utils/message/queue.ts`)
- 会话状态: 本地存储 (`utils/message/conversation-store.ts`)

## 编程规范

### 命名规范

- **文件**: kebab-case (`contact-info.ts`, `message-queue.ts`)
- **变量/函数**: camelCase (`userName`, `fetchUserInfo`)
- **类型/接口**: PascalCase (`UserInfo`, `ApiResponse`)
- **常量**: UPPER_CASE (`API_BASE_URL`, `MAX_RETRY_COUNT`)
- **事件处理器**: 以 `handle` 或 `on` 开头 (`handleTap`, `onLoad`)

### 类型注解

- 函数必须有明确的参数和返回值类型
- 禁止使用 `any` 类型，使用 `unknown` 或具体类型
- 禁止使用 `var`，使用 `const` 或 `let`
- Page 必须定义类型参数: `Page<PageData>`
- 事件处理器必须明确事件类型: `WechatMiniprogram.TouchEvent`

### API 调用规范

- 所有 API 调用必须通过 `utils/api.ts`
- 禁止直接使用 `wx.request`
- 使用泛型指定返回类型: `get<UserInfo>('/users/123')`

### 存储操作规范

- 所有存储操作必须通过 `utils/storage.ts`
- 禁止直接使用 `wx.getStorageSync` / `wx.setStorageSync`
- 使用泛型指定存储类型: `getStorage<string>('token')`

### 状态管理规范

- 使用 TypeScript 接口定义 Page Data
- setData 必须批量更新，禁止多次调用
- 使用路径更新: `this.setData({ 'user.name': newName })`

## 环境配置

### 安装依赖

```bash
cd frontend/wx-minipg
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

**注意**: 微信开发者工具的编译器只移除类型注解，不进行类型检查。必须使用 `npm run type-check` 进行类型检查。

### 提交前检查

```bash
cd frontend/wx-minipg
npm run check  # 必须通过
```

检查内容:
- TypeScript 类型检查 (`npm run type-check`)
- ESLint 检查 (`npm run lint`)
- 代码格式化 (`npm run format`)

详细说明: [docs/tech/CODE_QUALITY.md](../../docs/tech/CODE_QUALITY.md)

## 禁止行为

- ❌ 跳过代码检查 (`npm run check`)
- ❌ 使用 `any` 类型
- ❌ 使用 `var` 声明变量
- ❌ 直接使用 `wx.request` (必须通过 `utils/api.ts`)
- ❌ 直接使用 `wx.getStorageSync` (必须通过 `utils/storage.ts`)
- ❌ 在 Leancloud 中存储业务逻辑
- ❌ 修改第三方库代码 (`libs/` 目录)
- ❌ 多次调用 setData (必须批量更新)
- ❌ 提交未格式化的代码
- ❌ 提交有类型错误的代码

## Page 定义规范

定义 Page Data 接口并使用类型参数:

```typescript
interface PageData {
  userInfo: UserInfo | null;
  messageList: Message[];
  isLoading: boolean;
}

Page<PageData>({
  data: {
    userInfo: null,
    messageList: [],
    isLoading: false,
  },

  onLoad(options: Record<string, string>) {
    // 生命周期方法
  },

  handleTap(e: WechatMiniprogram.TouchEvent) {
    // 事件处理器
    const id = e.currentTarget.dataset.id as string;
  },
});
```

## 错误处理

统一错误处理模式:

```typescript
try {
  const data = await api.get('/data');
  this.setData({ data });
} catch (error) {
  logger.error('Failed to fetch data:', error);
  wx.showToast({
    title: '加载失败',
    icon: 'none',
  });
}
```

## 类型定义

为第三方库创建类型定义 (`typings/leancloud.d.ts`):

```typescript
declare module './libs/im.min.js' {
  export class Realtime {
    constructor(options: any);
    createIMClient(clientId: string): Promise<IMClient>;
  }
  // ... 其他类型
}
```

## 性能优化

- setData 批量更新，避免多次调用
- 使用防抖节流 (`utils/format.ts` 的 `debounce`)
- 避免不必要的数据传输

## 手动测试要求

修改后必须在微信开发者工具中测试:
1. 编译无错误
2. 功能正常运行
3. 界面显示正确
4. 无控制台错误
