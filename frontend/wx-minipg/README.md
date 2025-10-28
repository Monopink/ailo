# 乔 - 微信小程序

AI陪聊应用的微信小程序客户端。

## 项目结构

```
frontend/wx-minipg/
├── pages/              # 页面
│   ├── login/          # 登录页面
│   ├── setup/          # 个人资料设置
│   ├── index/          # 聊天列表
│   ├── chat/           # 对话页面
│   ├── square/         # 发现广场
│   ├── profile/        # 个人中心
│   ├── search/         # 搜索页面
│   ├── settings/       # 设置页面
│   ├── contact-info/   # 联系人详情
│   └── contact-requests/ # 联系人申请
├── components/         # 组件
│   ├── avatar-selector/ # 头像选择器
│   ├── message-item/   # 消息项
│   └── contact-card/   # 联系人卡片
├── utils/              # 工具类
│   ├── message/        # 消息相关
│   │   ├── provider/   # Provider架构
│   │   ├── service.js  # 消息服务
│   │   ├── queue.js    # 消息队列
│   │   └── typing.js   # 输入状态管理
│   ├── api.js          # API封装
│   ├── auth.js         # 认证工具
│   ├── storage.js      # 本地存储
│   ├── logger.js       # 日志工具
│   ├── config.js       # 配置
│   ├── format.js       # 格式化工具
│   └── validator.js    # 验证工具
├── styles/             # 全局样式
├── assets/             # 静态资源
│   ├── icons/          # 图标
│   └── avatars/        # 预设头像
├── app.js              # 应用入口
├── app.json            # 应用配置
├── app.wxss            # 全局样式
├── project.config.json # 项目配置
├── package.json        # 依赖配置
└── README.md           # 项目说明
```

## 开发环境

### 前置要求

1. 微信开发者工具
2. Node.js (用于安装依赖)
3. 后端API服务运行在 `http://localhost:8000`

### 安装依赖

```bash
cd frontend/wx-minipg
npm install
```

### 配置

1. 修改 `utils/config.js` 中的配置：
   - `API_CONFIG.baseUrl`: 后端API地址
   - `LEANCLOUD_CONFIG.appId`: LeanCloud App ID
   - `LEANCLOUD_CONFIG.appKey`: LeanCloud App Key

2. 修改 `project.config.json` 中的 `appid`

### 运行

1. 使用微信开发者工具打开项目目录
2. 点击"编译"按钮
3. 在模拟器或真机中预览

## 技术栈

- **渲染引擎**: WebView (兼容微信7.0+)
- **基础库**: 2.4.0+
- **消息服务**: LeanCloud Realtime
- **本地存储**: wx.storage
- **网络请求**: wx.request

## 核心功能

### 认证流程

1. 微信一键登录
2. 手机号登录（SMS验证）
3. 个人资料设置（头像、昵称、性别必填）

### 消息系统

1. 实时消息收发
2. 输入状态指示器（1s防抖，30s超时）
3. 消息队列和失败重试
4. 本地消息存储

### 联系人管理

1. 联系人列表
2. 添加联系人（发送申请）
3. 处理联系人申请
4. 联系人详情和设置

### 发现功能

1. 推荐联系人
2. 分类筛选
3. 联系人卡片展示

## Provider架构

消息服务使用Provider架构，便于未来更换消息服务提供商：

```javascript
// 创建Provider
const provider = createProvider('leancloud');

// 连接
await provider.connect(userId, signature);

// 发送消息
await provider.sendMessage(convId, content, type);

// 监听消息
provider.onMessage(message => {
  console.log('Message received:', message);
});
```

## 本地存储

使用 `utils/storage.js` 管理本地数据：

- `auth_token`: 认证令牌
- `user_info`: 用户信息
- `contacts`: 联系人列表
- `messages_{conv_id}`: 对话消息
- `local_settings`: 本地设置

## API调用

使用 `utils/api.js` 进行API调用：

```javascript
import { get, post } from './utils/api';

// GET请求
const data = await get('/users/me');

// POST请求
const result = await post('/auth/login', { phone, code });
```

## 开发规范

1. 使用英文注释
2. 遵循KISS、YAGNI、SOLID原则
3. 错误信息使用中文（用户可见）
4. 日志信息使用英文（开发者可见）
5. 不暴露AI相关术语，使用"联系人"等人性化词汇

## 待实现功能

- [ ] 页面实现（login, setup, index, chat, square, profile等）
- [ ] 组件实现（avatar-selector, message-item, contact-card等）
- [ ] LeanCloud SDK集成和测试
- [ ] 消息收发功能测试
- [ ] 输入状态指示器测试
- [ ] 本地存储功能测试

## 注意事项

1. **LeanCloud SDK**: 需要安装 `leancloud-realtime` 和 `leancloud-realtime-plugin-typed-messages`
2. **Composition事件**: 使用 `ignoreCompositionEvent="{{false}}"` 处理输入法
3. **资源加载**: 本地资源使用 `assets://` 前缀
4. **签名认证**: 使用后端生成的签名连接LeanCloud
5. **本地设置**: 不同步到服务器，仅存储在本地

## 参考文档

- [微信小程序官方文档](https://developers.weixin.qq.com/miniprogram/dev/framework/)
- [LeanCloud Realtime SDK](https://leancloud.cn/docs/realtime_guide-js.html)
- [项目设计文档](../../docs/prototype/minipg.md)
- [API设计文档](../../docs/prototype/api_design.md)
- [技术文档](../../docs/development/miniprogram-tech.md)

