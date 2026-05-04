# 小程序原型与差异说明

本文件仅描述小程序端特有差异，通用交互请参考：

- `../base/navigation.md`
- `../base/contacts-and-chat.md`
- `../base/discovery.md`
- `../base/profile-and-settings.md`
- `../base/profile-setup.md`
- `../base/ux-states.md`

## 功能范围

小程序功能保持精简，聚焦：聊天、发现联系人、添加联系人。

## 欢迎页（未登录）

- 作为未登录入口页，展示品牌与“开始使用/登录”等操作
- 不展示底部 tabBar
- 未登录状态禁止访问聊天/发现/我的
- 陌生人详情页允许外链直达

## 微信登录流程

**流程说明**:

1. 页面加载时静默调用 `wx.login()` 预取 `login_code`（有效期 5 分钟）
2. 登录页仅保留 `open-type="getPhoneNumber"` 的微信授权登录按钮
3. 用户授权成功后，按以下顺序提交 [微信登录](../../../api/auth.md#微信登录)
   - 回调存在 `code`：提交 `phone_code + login_code + device_id`
   - 回调不存在 `code` 但存在 `encryptedData + iv`：提交 `encrypted_data + iv + login_code + device_id`
4. 后端返回 `needs_profile_setup=true` 时跳转资料设置页

**异常处理**:

- 用户拒绝授权：提示“需要授权手机号才能使用本应用”
- 国际手机号：提示“暂不支持国际手机号，请使用中国大陆手机号”
- 两种授权载荷均不可用或登录失败：提示“登录失败，请尝试更新微信”

**注意事项**:

- 仅支持 +86 手机号
- `getPhoneNumber`（手机号快速验证组件）仅对非个人主体且已完成认证的小程序开放
- 登录按钮触发 `wx.login()` 与 `getPhoneNumber`；绑定阶段根据回调载荷选择协议分支
- 小程序前端不得调用 `/auth/phone` 等短信登录接口
- 开发者工具可通过 `wechat_phone_mock_*` 配置模拟手机号（仅测试）

## 登录页内容数据

- 登录页主视觉仅保留品牌文字 logo（`/assets/wordmark.svg`）与一条静态 slogan
- 登录页不展示示例联系人卡片、功能卖点标签及“AI 伙伴”相关文案
- slogan 与品牌文字保持静态展示，不使用呼吸、脉冲等循环动画
- 登录按钮下展示文案“登录代表您已阅读并同意用户使用协议、隐私政策”，其中“用户使用协议”“隐私政策”为可点击入口
- 协议确认文案下展示“新手机号将自动注册”

## 登录页背景资源

- 登录页背景由两层组成：本地渐变兜底层 + 远程图片增强层
- 页面首帧必须展示本地渐变兜底层与登录按钮，不等待远程背景加载
- 远程背景图配置维护在 `utils/config.ts` 的 `LOGIN_CONFIG.loginBackgroundUrl`
- 远程背景加载超时时间为 1000ms；超时或失败时保持本地渐变兜底层
- 远程背景加载成功后以透明度过渡覆盖兜底层，不影响按钮可用性
- 体验版与正式版使用生产背景域名策略（`trial=prod`）

## 协议入口与展示

- 登录页展示“用户使用协议”“隐私政策”入口，跳转协议详情页。
- 关于页展示“用户协议”“隐私政策”“联系我们（公众号）”入口：
  - 用户协议：`page_key=user_agreement`
  - 隐私政策：`page_key=privacy_policy`
  - 联系我们（公众号关注引导）：
    - 主链路：点击后调用 `wx.openOfficialAccountProfile({ username })` 打开公众号主页。
    - 降级链路：当主链路不可用或调用失败时，展示公众号二维码（支持长按识别）与“复制公众号用户名”按钮。
- 协议详情页为通用页面，按 `page_key` 拉取并使用 `content_rendered` 渲染，渲染格式固定 `html`。
- 协议内容读取请求必须携带 `X-Client=mini-program`。

## 资料设置差异

- 头像与昵称填写能力见 [小程序头像昵称填写](profile-avatar-nickname.md)

## 输入长度

- 小程序当前固定为 49 字符（如需调整再接入配置）

## 图标与 UI 规范

- 图标方案与 UI 组件规范见 [UI 体系规范](ui.md)
- 头像上传流程见 [头像上传规范](avatar-upload.md)
