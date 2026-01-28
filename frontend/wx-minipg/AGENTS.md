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

- [UI 开发规范](../../docs/spec/mini-program/UI-GUIDELINES.md)
- [头像上传规范](../../docs/spec/mini-program/avatar-upload.md)
- [Device ID 规范](../../docs/spec/app/device-id.md)
- [API文档](../../docs/api/)
- [数据字典](../../docs/data-dict/)
- [Leancloud IM 文档](../../docs/references/leancloud-docs/)
- [微信小程序官方文档](https://developers.weixin.qq.com/miniprogram/dev/framework/)
- 特别提示：用户可以联系到微信文档客服，如果有不确定的问题请报告提问，请勿在一知半解状态实施

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

依赖规则:
- Pages/Components 可以调用 Services 和 Utils
- Services 可以调用 Utils
- Utils 可以调用 Libs
- 禁止反向依赖（下层不能依赖上层）

### Service 层规范

**目的**：封装数据获取、转换和业务逻辑，提供统一的数据访问接口。

**核心原则**：
- 所有 API 数据获取必须通过 Service 层
- Service 负责将 API 返回的原始数据转换为 ViewModel
- Service 提供类型安全的接口（ProfileViewModel, AccountViewModel 等）
- **MVP 阶段禁止实现内存缓存**（增加复杂度，容易出错）

**现有 Services**：
- `profileService`: 用户资料管理（头像、昵称、性别等）
- `accountService`: 账号信息管理（手机号、邮箱等）
- `contact-service`: 联系人管理
- `auth-service`: 认证管理
- `discovery-service`: 发现页管理

**使用示例**：
```typescript
// ✅ 正确：使用 Service 层
import profileService from '../../utils/profile-service';

async loadProfile() {
  const profile = await profileService.loadProfile();
  this.setData({ profile }); // profile 是 ProfileViewModel，包含 displayAvatar, displayUsername
}

// ❌ 错误：直接调用 API
import { fetchCurrentUserProfile } from '../../utils/profile';
const profile = await fetchCurrentUserProfile(); // 绕过 Service 层
```

**Service 实现规范**：
```typescript
// utils/xxx-service.ts
class XxxService {
  private logger = getLogger('XxxService');

  async loadData(): Promise<XxxViewModel> {
    this.logger.debug('Fetching data');
    const data = await fetchXxxFromAPI();
    return this.buildViewModel(data);
  }

  private buildViewModel(data: RawData): XxxViewModel {
    return {
      ...data,
      displayField: transformField(data.field),
    };
  }
}

const xxxService = new XxxService();
export default xxxService;
```

**禁止事项**：
- ❌ 禁止实现内存缓存（`private cachedData`）
- ❌ 禁止防重复请求逻辑（`private loadingPromise`）
- ❌ 禁止在页面层直接调用 `utils/profile.ts` 等 API 函数
- ❌ 禁止在页面层手动构建 ViewModel（如 `displayAvatar = getAvatarUrl(...)`）

**例外场景**：
- setup 页面（首次登录设置资料）可以直接调用 API，因为涉及特殊的初始化逻辑

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
- Leancloud 仅用于消息传输
- 消息发送: `utils/message/service.ts`
- 消息接收: `app.ts` 监听，分发到各页面
- 消息重试: 队列机制 (`utils/message/queue.ts`)
- 会话状态: 本地存储 (`utils/message/conversation-store.ts`)
- 禁止在 Leancloud 中存储业务逻辑

## 编程规范

### 命名规范

- 文件: kebab-case (`contact-info.ts`, `message-queue.ts`)
- 变量/函数: camelCase (`userName`, `fetchUserInfo`)
- 类型/接口: PascalCase (`UserInfo`, `ApiResponse`)
- 常量: UPPER_CASE (`API_BASE_URL`, `MAX_RETRY_COUNT`)
- 事件处理器: 以 `handle` 或 `on` 开头 (`handleTap`, `onLoad`)

### 枚举管理

所有枚举必须集中管理在 `utils/constants/` 目录下，按业务领域分类：

**目录结构**：
```
utils/constants/
├── index.ts           # 统一导出入口
├── user.ts            # 用户相关枚举 (GENDER, USER_TYPE, USER_STATUS)
├── message.ts         # 消息相关枚举 (MESSAGE_STATUS, MESSAGE_TYPE)
└── [domain].ts        # 其他业务领域枚举
```

**枚举定义规范**：
```typescript
// utils/constants/user.ts

/** Gender enum - MUST match backend (1=male, 2=female, 3=other) */
export const GENDER = {
  MALE: 1,
  FEMALE: 2,
  OTHER: 3,
} as const;

export type GenderValue = (typeof GENDER)[keyof typeof GENDER];

/** Gender display options for UI pickers */
export const GENDER_OPTIONS = [
  { value: GENDER.MALE, label: '男' },
  { value: GENDER.FEMALE, label: '女' },
  { value: GENDER.OTHER, label: '其他' },
] as const;

export type GenderOption = (typeof GENDER_OPTIONS)[number];
```

**使用规范**：
```typescript
// 页面中使用
import { GENDER, GENDER_OPTIONS, type GenderValue } from '../../utils/constants/user';

// 或从统一入口导入
import { GENDER, MESSAGE_STATUS } from '../../utils/constants';
```

**关键约束**：
- 所有枚举值必须与后端完全一致，添加注释说明对应关系
- 禁止在页面/组件中定义本地枚举常量
- 使用 `as const` 确保类型安全
- 枚举值变更必须同步更新后端文档链接
- 历史遗留枚举迁移时保留重新导出以维持向后兼容

### 类型系统

- 函数必须有明确的参数和返回值类型
- Page 必须定义类型参数: `Page<PageData>`
- 事件处理器必须明确事件类型: `WechatMiniprogram.TouchEvent`
- 第三方库创建类型定义: `typings/*.d.ts`（示例见文档末尾）
- 禁止使用 `any`，使用 `unknown` 或具体类型
- 禁止使用 `var`，使用 `const` 或 `let`

### API 与存储

- 所有 API 调用通过 `utils/api.ts`，使用泛型指定返回类型: `get<UserInfo>('/users/123')`
- 所有存储操作通过 `utils/storage.ts`，使用泛型指定类型: `getStorage<string>('token')`
- 禁止直接使用 `wx.request` / `wx.getStorageSync` / `wx.setStorageSync`

**运行时验证（新代码必须使用）**：

1. **必须使用 Zod 的场景**：
   - 用户认证相关（登录、注册、获取用户信息）
   - 关键业务数据（消息、会话、联系人）
   - 所有新功能的 API 调用

2. **可选使用 Zod 的场景**：
   - 简单的配置获取
   - 不涉及业务逻辑的 API
   - 修改旧代码但不涉及 API 调用逻辑

3. **使用步骤**：
   ```typescript
   // Step 1: 定义 Schema (utils/schemas.ts)
   export const UserInfoSchema = z.object({
     id: z.number(),
     nickname: z.string(),
     avatar: z.string().url().nullable(),
   });

   // Step 2: 使用验证 API
   import { getValidated } from '../../utils/api-validated';
   import { UserInfoSchema } from '../../utils/schemas';

   const user = await getValidated('/users/123', UserInfoSchema);
   // user 类型安全，且运行时已验证
   ```

4. **错误处理**：
   ```typescript
   try {
     const user = await getValidated('/users/123', UserInfoSchema);
     this.setData({ userInfo: user });
   } catch (error) {
     console.error('数据验证失败', error);
     wx.showToast({ title: '数据加载失败', icon: 'error' });
   }
   ```

### 状态管理

- 使用 TypeScript 接口定义 Page Data
- setData 必须批量更新,禁止多次调用
- 使用路径更新: `this.setData({ 'user.name': newName })`
- 使用防抖节流避免频繁更新 (`utils/format.ts` 的 `debounce`)
- 禁止修改第三方库代码 (`libs/` 目录)

### Custom TabBar 使用规范

所有使用 custom TabBar 的页面必须在 `onShow()` 生命周期中调用 `initTabBar()` 以更新激活状态。

**正确做法**:
```typescript
import { initTabBar } from '../../utils/tab-bar';

Page({
  onShow() {
    initTabBar(this);
    // ... other logic
  }
});
```

**错误做法**:
```typescript
// ❌ 错误：提取函数引用会导致 this 上下文丢失
const tabBar = this.getTabBar();
const initFn = tabBar.init;
initFn(); // TypeError: Cannot read property 'data' of undefined

// ❌ 错误：手动实现类型检查和调用逻辑
const tabBar = typeof this.getTabBar === 'function' ? this.getTabBar() : null;
if (tabBar !== null && typeof tabBar.init === 'function') {
  tabBar.init(); // 容易出错,缺少类型安全
}
```

**为什么要使用工具函数**:
- ✅ 类型安全: `typings/custom-tab-bar.d.ts` 提供完整类型定义
- ✅ this 绑定正确: 直接通过对象调用方法,保持正确的上下文
- ✅ DRY 原则: 避免在多个页面重复相同的初始化代码
- ✅ 防御性编程: 完善的 null/undefined 检查

**相关文件**:
- `typings/custom-tab-bar.d.ts`: TabBar 组件类型定义
- `utils/tab-bar.ts`: TabBar 工具函数
- `custom-tab-bar/index.ts`: TabBar 组件实现

### 错误处理与数据展示

严禁向用户暴露内部错误，开发者层记录详细错误（logger.error），用户层显示友好提示。

**回退值规范（WXML层）**：
- 系统消息（错误/空状态/加载）: 允许回退值 `{{errorMessage || '操作失败'}}`
- 资料数据（用户信息）: 禁止回退值，空就是空 `{{nickname}}`
- 绑定数据（账号关联）: 逻辑层处理 `displayPhone: user.phone ? format(phone) : '未绑定'`
- UI 状态（class/style）: 允许动态逻辑 `{{disabled ? 'button--disabled' : ''}}`
- 表单 placeholder: 属于用户指引，不是回退值

### UI 开发

详见 [UI-GUIDELINES.md](../../docs/spec/mini-program/UI-GUIDELINES.md)

核心规则：
- 使用 TDesign 组件库，页面 WXSS 第一行 `@import '/styles/tdesign-theme.wxss';`
- 所有基础UI使用 `t-*` TDesign组件
- 业务组件使用 `ui-gender-badge`
- 禁止硬编码样式值，使用 `var(--td-*)` CSS Variables
- 禁止使用 px 单位（除了 1px 边框），使用 rpx

### 代码检查

提交前必须运行 `npm run check` 并通过，禁止跳过检查或提交未格式化代码。

```bash
cd frontend/wx-minipg
npm run check  # type-check + lint + lint:style + ui:audit，必须通过
```

检查内容:
- TypeScript 类型检查 (`npm run type-check`)
- ESLint 检查 - TS/JS/WXML (`npm run lint`)
- Stylelint 检查 - WXSS (`npm run lint:style`)
- 自定义 UI Audit (`npm run ui:audit`)

单独工具:
```bash
npm run type-check      # TypeScript 类型检查
npm run lint            # ESLint 检查
npm run lint:fix        # 自动修复
npm run lint:style      # Stylelint 检查 WXSS
npm run format          # 代码格式化
npm run format:check    # 仅检查不修复
npm run ui:audit        # UI规范检查
```

Pre-commit Hook 自动执行:
- TS/JS 文件: ESLint 检查 + Prettier 格式化
- WXML 文件: ESLint 语法检查
- JSON/WXSS 文件: Prettier 格式化

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

注意: 微信开发者工具的编译器只移除类型注解，不进行类型检查。必须使用 `npm run type-check` 进行类型检查。

---

## 附录：代码示例

### Page 定义

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

### 第三方库类型定义

```typescript
// typings/leancloud.d.ts
declare module './libs/im.min.js' {
  export class Realtime {
    constructor(options: any);
    createIMClient(clientId: string): Promise<IMClient>;
  }
  // ... 其他类型
}
```
