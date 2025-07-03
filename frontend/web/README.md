# Says - AI Chat Web Application

Says 是一个现代化的 AI 聊天应用，具有响应式 UI 和渐进式 Web 应用 (PWA) 功能。

## 功能特点

- 响应式设计，适配各种设备尺寸
- 支持深色/浅色模式
- 渐进式 Web 应用 (PWA) 支持
  - 离线使用能力
  - 可安装到主屏幕
  - 推送通知
- 极简线框风格界面
- JWT 认证系统
- 用户注册和登录

## 技术栈

- Vue 3 (Composition API)
- Pinia (状态管理)
- Vue Router
- Vue Toastification (通知提示)
- Service Worker (PWA 功能)

## 开发指南

### 安装依赖
```bash
npm install
```

### 开发服务器启动
```bash
npm run dev
```

### 编译和构建
```bash
npm run build
```

### 运行测试
```bash
npm run test
```

## 项目结构

```
frontend/web/
├── public/               # 静态资源
│   ├── icons/            # PWA 图标
│   ├── manifest.json     # PWA 清单
│   ├── offline.html      # 离线页面
│   └── service-worker.js # 服务工作线程
├── src/
│   ├── assets/           # 静态资源
│   ├── components/       # 组件
│   ├── router/           # 路由配置
│   ├── stores/           # Pinia 状态仓库
│   ├── utils/            # 工具函数
│   ├── views/            # 页面组件
│   ├── App.vue           # 根组件
│   └── main.js           # 入口文件
└── index.html            # HTML 模板
```

## 主题支持

应用支持浅色和深色两种主题，可以通过以下方式切换：

1. 自动跟随系统设置
2. 使用界面上的主题切换按钮手动切换
3. 通过 localStorage 保存用户偏好设置

## 线框设计美学

应用使用极简主义线框设计风格，通过以下元素实现：

- 细边框和极简布局
- 柔和的网格背景
- 清晰的排版和图标
- 高对比度色彩方案

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request 