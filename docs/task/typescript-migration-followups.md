## TypeScript Migration Follow-ups

以下问题需作为独立子任务推进，以尽快恢复 `npm run check` 可用：

1. **网络适配层 TS 化**
   - 重写 `utils/api.ts`，确保 `wx.request/uploadFile/downloadFile` 的 Promise 封装符合官方类型定义。
   - 统一 `ApiError` 结构，修复 `unknown`/`undefined` 报错。

2. **Captcha 与 Typings 修复**
   - 在 `typings/index.d.ts` 补充 `CaptchaPageInstance`、`SaysAppInstance.globalData` 等接口，确保 `captcha.ts`、`typing-manager.ts` 可直接引用。
   - 检查 `tsconfig.json` 的 `typeRoots` 是否正确覆盖 `typings/` 目录。

3. **LeanCloud Adapter & MessageService 完整 TS 化**
   - 完成 `leancloud.ts` 对 LeanCloud SDK 类型的封装，约束 `BusinessMessage`、`MessageAdapter` 结构。
   - 补完 `service.ts` 中 `_sendViaAdapter`、`handleMessage/Typing/Error` 等函数的类型实现。

4. **消息队列 & Typing 管理器**
   - 调整 `queue.ts` 中 `MessageProvider` 接口与 `MessageService`/`LCAdapter` 保持一致。
   - 合并 `utils/message/typing.ts` 与 `utils/typing-manager.ts` 的配置细节，避免重复逻辑。

5. **环境/调试/存储细节**
   - 修复 `utils/env.ts`、`utils/debug.ts`、`utils/storage.ts` 中剩余的枚举比较、日志类型与小程序 API 类型引用问题。
