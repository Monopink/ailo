# 小程序原型文档

## 页面

### 欢迎页（未登录）

- 作为未登录状态的入口页面，展示品牌与“开始使用/登录”等操作。
- 不展示底部 tabBar（聊天/发现/我的）。
- 点击操作进入登录页（微信授权或手机号登录）。
- 未登录状态下不允许访问聊天、发现、我的等 tab 页。
- 陌生人详情页（`pages/stranger-info`）为公开页面，可通过分享/外链直达；但从应用内部导航到该页通常发生在登录后（从发现页进入）。

### 注册登录页

#### 微信登录流程

**流程说明**:

1. 用户点击【微信登录】按钮
2. 调用wx.login()获取login_code
3. 显示【获取手机号】按钮
4. 用户点击【获取手机号】按钮
5. 用户授权后获取phone_code
6. 调用后端API: POST /api/v1/auth/wechat/login
7. 后端返回结果:
   - 如果是+86手机号: 直接登录成功
   - 如果是国际手机号: 显示手机号绑定页面
8. 登录成功后检查用户资料,如果nickname为NULL则强制跳转资料设置页面

**微信授权页面**:

- 【微信登录】按钮
- 点击后调用wx.login()获取login_code
- 显示【获取手机号】按钮
- 用户点击【获取手机号】按钮(`<button open-type="getPhoneNumber">`)
- 用户授权后bindgetphonenumber事件返回phone_code
- 调用后端API: POST /api/v1/auth/wechat/login
- 请求参数: {login_code, phone_code}

**手机号绑定页面(回退方案)**:

- 使用场景:
  1. 微信获取手机号接口失败
  2. 微信返回国际手机号(非+86)
- 【国家代码】固定显示+86,不可选择
- 【手机号输入框】输入11位手机号(不含国家代码)
- 【获取验证码】按钮,60秒倒计时
- 【验证码输入框】输入6位验证码
- 【确认绑定】按钮
- 调用后端API: POST /api/v1/auth/bind-phone
- 请求参数: phone字段传入+8613800138000格式

**资料设置页面**:

- 当用户nickname为NULL时强制显示,不能跳过
- 【头像】显示默认头像,点击弹出选择框,从内置的默认头像中选择
  - 头像格式: assets://1234, assets://2345等
  - 小程序内置6-12个默认头像
- 【昵称】必填,最大长度由环境变量控制
- 【性别】男、女、其他。必填
- 【个人简介】可选,最大长度由环境变量控制
- 【地区】可选,前端维护地区列表
- 【完成】按钮,点击后调用API更新资料,成功后跳转主界面

**错误处理**:

- 微信授权失败: 显示错误提示,提供重试按钮
- 手机号绑定失败: 显示具体错误信息(验证码错误、手机号已注册等)
- 资料设置失败: 显示错误提示,不允许跳过

**注意事项**:

- 强制绑定手机号,不能跳过
- MVP阶段只支持+86(中国大陆)手机号
- 一个手机号只能绑定一个账号
- 如果手机号已注册,通过手机号关联账号
- 资料设置页面根据nickname是否为NULL判断是否需要显示
- 手机号存储格式: E.164标准格式(+8613800138000)
- 手机号显示格式: +86 138******00(脱敏)

### 主界面底部导航栏（登录后）

【聊天】主界面默认页面，点击进入聊天页。

【发现】点击进入发现页。

【我的】点击进入我的页。

说明：未登录状态不展示 tabBar，由 `app.js` 的统一鉴权逻辑重定向至欢迎/登录。

### 聊天

#### 顶栏

【信息区域】默认情况为「敲敲(3)」显示品牌名（来自环境变量），括号展示未读消息数量，最高为99+，如果为0则不显示。

网络、服务异常时显示「正在连接…」。

加载内容时显示「正在加载…」。

#### 聊天列表

聊天列表按照最后消息的日期顺序排列。置顶的的聊天显示在最前，并且按照日期顺序排列。

点击聊天列表进入聊天页面，右滑聊天列表出现右滑菜单。

【搜索栏】下滑出现在顶部，点击进入搜索页。

【头像】显示用户设置的头像,如果头像未设置则使用默认头像(default)。

【名称】备注或nickname，备注优先。如果为空则显示空白，不要设置默认值。

【日期】最近的一条消息的日期。

【最近的一条消息缩略】不包括系统消息或输入状态消息。

【标签】显示在名称右侧，标签形式。

【消息圆点/消息数量红点】根据「消息免打扰」设置决定显示圆点还是消息数量。

【右滑聊天】点击进入聊天界面，右滑选项：标为未读、删除。点击标为未读可以增加消息圆点。点击删除选项扩大文字变为：确认删除。点击确认删除删除聊天记录并将聊天从聊天列表移除。

### 发现（登录后可访问）

#### 筛选栏

【交友】

【恋爱（限时免费）】

【倾诉（限时免费）】

【闺蜜（限时免费）】

【同好（限时免费）】

默认为交友（登录后可访问，切换分类加载对应推荐）。

大按钮，每个按钮都有图案装饰，默认展开。点击后收起，上滑收起。

#### 功能栏

【刷新按钮】遵守刷新频率限制（超限返回提示，保持当前数据）。

#### 结果栏

展示搜索到的联系人结果

【头像】

【nickname】

【性别】

【标签】添加后自动添加到联系人的标签中。

【添加】发送联系人申请（统一 API：`POST /api/v1/contact-requests`，统一返回“请求已发送”）。

后端返回为空时均不设置默认值。

### 我的

【个人资料缩略】头像、昵称。点击进入个人资料页。

【会员等级】点击进入会员页面。

【通讯录】点击进入通讯录页。

【设置】点击进入设置页。

### 对话页面

#### 顶栏

【<】后退按钮。

【信息区域】正常情况备注或nickname，备注优先。如果为空则显示空白，不要设置默认值。

当输入状态显示「对方正在输入…」

【…】更多按钮。点击进入聊天详情页面。

#### 聊天区域

【日期】小号字体，水平居中。

【系统消息】样式和日期一致。

【对方头像和气泡】气泡为无颜色灰度和背景区分。

【自己的头像和气泡】气泡为绿色（产品主色调）。

#### 输入区域

【表情按钮】点击出现表情选择，表情选择框对表情进行分组展示。

表情包括emoji字符、自定义emoji。点击emoji分组的表情加入到输入框。

【输入框】输入框从空白输入内容后（包括输入法的开始输入状态）发送开始输入的状态，输入框从有内容删除所有内容（且输入法的没有输入状态）发送结束输入状态。输入框字符上限为 49（MVP 固定）。

【发送按钮】点击发送内容。

### 搜索页

搜索现有联系人的页面。

#### 搜索栏

【搜索输入框】输入联系人昵称或备注进行搜索。

#### 搜索结果

- 联系人列表：显示匹配的联系人
- 头像：显示联系人头像（昵称首字符+颜色算法生成）
- 名称：显示备注或nickname，备注优先
- 标签：显示联系人标签
- 最近消息：显示最近一条消息内容和时间

#### 搜索历史

显示最近搜索的关键词，点击可快速搜索。

### 聊天详情页

对话页面点击"更多按钮"进入的详情页面。

#### 联系人信息区域

- 头像：显示联系人头像
- 名称：显示备注或nickname
- 标签：显示和编辑联系人标签
- 查看资料：点击进入联系人资料页面

#### 聊天设置

- 置顶聊天：开关控制，设置聊天是否置顶
- 消息免打扰：开关控制，设置是否接收消息通知
- 聊天背景：设置聊天背景（2.0功能，暂时不开发）

#### 聊天管理

- 搜索聊天记录：在当前对话中搜索消息内容
- 清空聊天记录：清空所有聊天记录，保留联系人关系
- 删除聊天：删除聊天记录并从聊天列表移除

### 个人资料页

显示和编辑用户个人资料，对应profiles表数据。

#### 基本信息

- 头像：显示当前头像，点击可从预设头像中选择更换
  - 调用`GET /api/v1/preset-assets?asset_type=1`获取预设头像列表
  - 显示预设头像选择器，按category分组显示
  - 选择头像后调用`PUT /api/v1/user/profile`更新头像
  - 头像URL格式：`assets://1234`
  - 客户端识别`assets://`前缀后，从本地assets加载对应图片
- 昵称：显示和编辑用户昵称
- 性别：显示和编辑性别（男、女、其他）
- 个人简介：显示和编辑个人简介
- 地区：显示和编辑所在地区

#### 账户信息

- 敲敲账号：显示用户的username(默认为qiao_id)
- 手机号：显示绑定的手机号

### 通讯录页

管理用户的所有联系人。

#### 联系人列表

- 分组显示：按标签自动分组显示联系人
- 搜索功能：快速搜索联系人
- 联系人信息：头像、名称、标签、最近活动时间

#### 标签管理

- 标签筛选：按标签筛选联系人
- 标签编辑：为联系人添加、删除、修改标签
- 标签统计：显示各标签下的联系人数量

#### 联系人操作

- 查看资料：查看联系人详细资料
- 发送消息：直接进入对话页面
- 编辑备注：修改联系人备注名称

### 设置页

用户设置和系统配置页面。

#### 账户设置

- 个人资料：跳转到个人资料页
- 隐私设置：控制个人信息的可见性
- 账户安全：密码修改、手机号绑定等

#### 消息设置

- 消息通知：控制消息推送通知
- 消息提示音：选择消息提示音
- 消息预览：控制锁屏消息预览

#### 通用设置

- 语言设置：选择界面语言
- 字体大小：调整界面字体大小
- 深色模式：开关深色主题

#### 其他

- 关于我们：显示应用信息和版本
- 用户协议：查看用户协议和隐私政策
- 意见反馈：提交意见和建议
- 退出登录：退出当前账户

### 联系人资料页

查看联系人的详细资料页面。

#### 信息展示

- 头像：显示头像
- 昵称：显示昵称
- 性别：显示性别
- 个人简介：显示的个人简介
- 标签：显示的特征标签
- 地区：显示的地区信息

#### 操作按钮

- 发送消息：直接进入对话页面
- 编辑备注：修改对该联系人的备注
- 管理标签：为该联系人添加或删除标签

## 交互细节和状态处理

### 消息状态管理

#### 消息发送状态

- 发送中：消息气泡显示发送中状态（转圈图标）
- 发送成功：正常显示消息内容
- 发送失败：消息气泡旁显示红色感叹号，点击可重试
- 失败原因：点击感叹号显示具体失败原因（网络错误、内容违规等）

#### 消息接收状态

- 正在输入：收到typing类型消息时显示"对方正在输入..."，持续10秒
- 输入结束：收到新消息或typing_end消息时取消输入状态

### 网络状态处理

#### 网络异常

- 连接中断：顶栏显示"正在连接..."
- 重连成功：自动恢复正常状态
- 长时间断网：显示网络错误提示，提供重试按钮

#### 数据加载

- 首次加载：显示加载动画
- 下拉刷新：支持下拉刷新联系人列表和消息
- 加载更多：聊天记录支持上滑加载历史消息

### 错误处理

#### 用户操作错误

- 输入超长：输入框达到字符限制时禁用发送，显示字符计数
- 网络超时：显示超时提示，提供重试选项
- 服务异常：显示友好的错误提示，避免暴露技术细节

#### 数据异常

- 空状态：无联系人时显示引导添加联系人
- 无消息：新对话显示欢迎消息或使用提示
- 加载失败：显示重试按钮，支持手动刷新

### 用户体验优化

#### 界面反馈

- 按钮点击：提供触觉反馈和视觉反馈
- 操作确认：删除等危险操作需要二次确认
- 状态提示：重要操作完成后显示成功提示

#### 性能优化

- 图片懒加载：头像和图片消息支持懒加载
- 消息分页：聊天记录分页加载，避免一次加载过多
- 缓存机制：联系人信息和聊天记录支持本地缓存

### 安全和隐私

#### 内容安全

- 隐私保护：用户数据加密传输和存储

#### 账户安全

- 登录验证：支持手机验证码登录
- 会话管理：支持踢出其他设备（2.0功能）

### 会员页面（2.0功能，暂时不开发）

---

## 客户端逻辑实现

### 1. 输入状态处理

#### 1.1 客户端发送输入状态逻辑

**触发场景：**

1. **输入框无内容 + 输入法开始输入 → 发送TYPING_START**
   - 监听compositionstart事件
   - 检查输入框当前内容为空
   - 发送message_type=2的消息

2. **输入框有内容 + 清空内容 → 发送TYPING_END**
   - 监听bindinput事件
   - 检测从有内容变为无内容
   - 发送message_type=3的消息

3. **输入法开始输入但未上屏 + 取消输入 → 发送TYPING_END**
   - 监听compositionend事件
   - 检查输入框依然为空
   - 发送message_type=3的消息

4. **输入框失去焦点 → 发送TYPING_END**
   - 监听bindblur事件
   - 如果当前处于输入状态，发送TYPING_END

**防抖机制：**

- 1秒防抖延迟
- 防止频繁发送输入状态消息
- 使用setTimeout实现

**实现示例（小程序）：**

```javascript
// utils/typing-manager.js
class TypingManager {
  constructor() {
    this.typingState = new Map();
    this.DEBOUNCE_DELAY = 1000; // 1秒防抖
  }

  // 输入法开始输入
  onCompositionStart(convId, toQiaoId, currentValue) {
    if (!currentValue || currentValue.length === 0) {
      this.sendTypingStartDebounced(convId, toQiaoId);
    }
  }

  // 输入法结束输入
  onCompositionEnd(convId, toQiaoId, currentValue) {
    if (!currentValue || currentValue.length === 0) {
      this.sendTypingEnd(convId, toQiaoId);
    }
  }

  // 输入内容变化
  onInputChange(convId, toQiaoId, newValue, oldValue) {
    if (oldValue && oldValue.length > 0 && (!newValue || newValue.length === 0)) {
      this.sendTypingEnd(convId, toQiaoId);
    }
  }

  // 发送TYPING_START（带防抖）
  sendTypingStartDebounced(convId, toQiaoId) {
    const state = this.typingState.get(convId) || {
      status: 'idle',
      lastSendTime: 0,
      timer: null
    };

    if (state.status === 'typing') return;

    const now = Date.now();
    if (now - state.lastSendTime < this.DEBOUNCE_DELAY) {
      if (state.timer) clearTimeout(state.timer);
      state.timer = setTimeout(() => {
        this.sendTypingStart(convId, toQiaoId);
      }, this.DEBOUNCE_DELAY - (now - state.lastSendTime));
      this.typingState.set(convId, state);
      return;
    }

    this.sendTypingStart(convId, toQiaoId);
  }

  async sendTypingStart(convId, toQiaoId) {
    await leancloud.sendMessage(convId, toQiaoId, '', 2, true);
    this.typingState.set(convId, {
      status: 'typing',
      lastSendTime: Date.now(),
      timer: null
    });
  }

  async sendTypingEnd(convId, toQiaoId) {
    const state = this.typingState.get(convId);
    if (!state || state.status !== 'typing') return;

    await leancloud.sendMessage(convId, toQiaoId, '', 3, true);
    state.status = 'idle';
    state.lastSendTime = Date.now();
    this.typingState.set(convId, state);
  }
}
```

#### 1.2 客户端显示输入状态逻辑

**显示规则：**

1. **收到TYPING_START消息 → 显示"正在输入..."**
   - 启动30秒超时定时器
   - 显示输入状态指示器

2. **收到TEXT消息 → 立即隐藏输入状态**
   - 清除超时定时器
   - 隐藏输入状态指示器
   - 显示收到的消息

3. **发送消息 → 立即隐藏输入状态**
   - 清除超时定时器
   - 隐藏输入状态指示器

4. **30秒超时 → 自动隐藏输入状态**
   - 定时器到期自动隐藏

**注意：服务端不会发送TYPING_END消息**

**实现示例（小程序）：**

```javascript
// pages/chat/chat.js
Page({
  data: {
    isContactTyping: false,
    typingTimer: null
  },

  // 收到消息
  onMessageReceived(message) {
    if (message.message_type === 2) {  // TYPING_START
      this.showTypingIndicator();
    } else if (message.message_type === 1) {  // TEXT
      this.hideTypingIndicator();
      this.addMessage(message);
    }
  },

  // 显示输入状态
  showTypingIndicator() {
    // 清除旧的定时器
    if (this.data.typingTimer) {
      clearTimeout(this.data.typingTimer);
    }

    // 显示输入状态
    this.setData({ isContactTyping: true });

    // 设置30秒超时
    const timer = setTimeout(() => {
      this.hideTypingIndicator();
    }, 30000);

    this.setData({ typingTimer: timer });
  },

  // 隐藏输入状态
  hideTypingIndicator() {
    if (this.data.typingTimer) {
      clearTimeout(this.data.typingTimer);
    }
    this.setData({
      isContactTyping: false,
      typingTimer: null
    });
  },

  // 发送消息
  async sendMessage(content) {
    // 隐藏输入状态
    this.hideTypingIndicator();

    // 发送消息逻辑...
  }
});
```

### 2. 消息发送失败处理

#### 2.1 客户端消息状态管理

**消息状态：**

```javascript
const MessageStatus = {
  SENDING: 1,    // 发送中
  SENT: 2,       // 已发送
  FAILED: 3,     // 发送失败
  RECEIVED: 4    // 已接收（对方消息）
};
```

**状态转换：**

1. 用户发送消息 → SENDING
2. LeanCloud确认发送 → SENT
3. LeanCloud发送失败 → FAILED
4. 服务端返回拒收标记 → FAILED

#### 2.2 失败消息UI处理

**显示规则：**

- 消息气泡左侧显示红色感叹号（⚠️）
- 点击感叹号触发重试
- 重试成功后消息移动到最下面（表示最新发送）

**实现示例（小程序）：**

```javascript
// pages/chat/chat.js
Page({
  data: {
    messages: []
  },

  // 发送消息
  async sendMessage(content) {
    const msgId = this.generateMsgId();
    const message = {
      msg_id: msgId,
      from: this.data.userQiaoId,
      to: this.data.contactQiaoId,
      conv_id: this.data.convId,
      content: content,
      message_type: 1,
      supports_typing: true,
      sent_time: Date.now(),
      status: 1  // SENDING
    };

    // 添加到消息列表
    this.data.messages.push(message);
    this.setData({ messages: this.data.messages });

    try {
      // 发送到LeanCloud
      await leancloud.sendMessage(message);

      // 更新状态为已发送
      this.updateMessageStatus(msgId, 2);  // SENT
    } catch (error) {
      // 更新状态为失败
      this.updateMessageStatus(msgId, 3);  // FAILED
    }
  },

  // 重试发送
  async retryMessage(msgId) {
    const message = this.data.messages.find(m => m.msg_id === msgId);
    if (!message) return;

    // 更新状态为发送中
    this.updateMessageStatus(msgId, 1);  // SENDING

    try {
      // 重新发送
      await leancloud.sendMessage(message);

      // 更新状态为已发送
      this.updateMessageStatus(msgId, 2);  // SENT

      // 移动到最下面
      this.moveMessageToBottom(msgId);
    } catch (error) {
      // 更新状态为失败
      this.updateMessageStatus(msgId, 3);  // FAILED
    }
  },

  // 更新消息状态
  updateMessageStatus(msgId, status) {
    const message = this.data.messages.find(m => m.msg_id === msgId);
    if (message) {
      message.status = status;
      this.setData({ messages: this.data.messages });
    }
  },

  // 移动消息到最下面
  moveMessageToBottom(msgId) {
    const index = this.data.messages.findIndex(m => m.msg_id === msgId);
    if (index !== -1) {
      const message = this.data.messages.splice(index, 1)[0];
      message.sent_time = Date.now();  // 更新发送时间
      this.data.messages.push(message);
      this.setData({ messages: this.data.messages });
    }
  },

  // 生成客户端消息ID
  generateMsgId() {
    return `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
});
```

#### 2.3 服务端拒收处理

**客户端监听 CHAT_INFO 消息的 action 字段：**

```javascript
// 监听LeanCloud消息
leancloud.on('message', (message) => {
  // 处理 CHAT_INFO 消息
  if (message.message_type === 4) {  // CHAT_INFO
    // 显示提示信息
    this.showChatInfo(message.content);

    // 处理 action（如果有）
    if (message.action && message.action.type === 'mark_message_failed') {
      // 标记消息为失败
      this.updateMessageStatus(message.action.target_msg_id, 3);  // FAILED
    }
  }
});
```

**CHAT_INFO 消息结构示例：**

```json
{
  "msg_id": "223788765171154946",
  "from": "system",
  "to": "qiao_user_001",
  "message_type": 4,
  "content": "消息已发出，但对方拒收了",
  "action": {
    "type": "mark_message_failed",
    "target_msg_id": "client_1710001111222_abc123"
  },
  "sent_time": 1710001113000
}
```

### 3. 通知消息处理

#### 3.1 通知消息类型

```javascript
const NotificationType = {
  CONTACT_REQUEST: 1      // 联系人申请
};
```

#### 3.2 联系人申请通知处理

**消息结构：**

```json
{
  "msg_id": "223788765171154945",
  "from": "system",
  "to": "qiao_user_b",
  "message_type": 5,
  "notification_type": 1,
  "notification_data": {
    "request_id": "req_123",
    "from_qiao_id": "qiao_user_a",
    "from_nickname": "用户A",
    "from_avatar": "avatar_url",
    "message": "你好，我想添加你为联系人"
  },
  "sent_time": 1710001112000
}
```

**客户端处理：**

```javascript
// 处理通知消息
handleNotification(message) {
  if (message.notification_type === 1) {  // CONTACT_REQUEST
    const data = message.notification_data;

    // 更新联系人申请列表
    this.updateContactRequestList({
      request_id: data.request_id,
      from_qiao_id: data.from_qiao_id,
      to_qiao_id: message.to,  // 从消息的to字段获取
      from_nickname: data.from_nickname,
      from_avatar: data.from_avatar,
      message: data.message
    });

    // 显示红点
    this.updateContactRequestBadge();

    // 可选：显示toast
    wx.showToast({
      title: `${data.from_nickname}请求添加你为联系人`,
      icon: 'none'
    });
  }
}

// 更新联系人申请列表
updateContactRequestList(request) {
  // 获取本地存储的申请列表
  let requests = wx.getStorageSync('contact_requests') || [];

  // 检查是否已存在
  const index = requests.findIndex(r => r.request_id === request.request_id);
  if (index === -1) {
    // 新申请，添加到列表
    requests.unshift(request);
  } else {
    // 已存在，更新
    requests[index] = request;
  }

  // 保存到本地存储
  wx.setStorageSync('contact_requests', requests);

  // 更新页面数据
  this.setData({ contactRequests: requests });
}

// 更新联系人申请红点
updateContactRequestBadge() {
  const requests = wx.getStorageSync('contact_requests') || [];
  const unreadCount = requests.filter(r => r.status === 1).length;  // status=1表示pending

  if (unreadCount > 0) {
    wx.setTabBarBadge({
      index: 2,  // "我的"页面的索引
      text: unreadCount > 99 ? '99+' : String(unreadCount)
    });
  } else {
    wx.removeTabBarBadge({
      index: 2
    });
  }
}


### 4. 本地功能实现

#### 4.1 搜索聊天记录

**实现方式：** 本地搜索，不调用服务端API

**搜索逻辑：**

```javascript
// 搜索聊天记录
searchMessages(convId, keyword) {
  // 1. 从本地存储获取聊天记录
  const messages = wx.getStorageSync(`messages_${convId}`) || [];

  // 2. 过滤文本消息
  const textMessages = messages.filter(msg => msg.message_type === 1);

  // 3. 搜索关键词
  const results = textMessages.filter(msg =>
    msg.content && msg.content.includes(keyword)
  );

  // 4. 按时间倒序排列
  results.sort((a, b) => b.sent_time - a.sent_time);

  return results;
}
```

**UI展示：**

- 搜索框：输入关键词
- 搜索结果：显示匹配的消息列表
- 高亮显示：关键词高亮
- 点击跳转：点击搜索结果跳转到对应消息位置

#### 4.2 清空聊天记录

**实现方式：** 本地操作，不调用服务端API

**清空逻辑：**

```javascript
// 清空聊天记录
clearChatHistory(convId) {
  wx.showModal({
    title: '清空聊天记录',
    content: '确定要清空所有聊天记录吗？',
    success: (res) => {
      if (res.confirm) {
        // 1. 清空本地存储的消息
        wx.removeStorageSync(`messages_${convId}`);

        // 2. 更新聊天列表
        this.updateChatList(convId, {
          last_message: null,
          last_message_time: null
        });

        // 3. 刷新当前页面
        this.setData({ messages: [] });

        wx.showToast({
          title: '已清空',
          icon: 'success'
        });
      }
    }
  });
}
```

**说明：**

- 清空聊天记录不删除联系人
- 清空后聊天列表中的对话保留，但最后一条消息为空
- 清空操作不可撤销

#### 4.3 删除聊天

**实现方式：** 本地操作，不调用服务端API

**删除逻辑：**

```javascript
// 删除聊天
deleteChat(convId) {
  wx.showModal({
    title: '删除聊天',
    content: '确定要删除此聊天吗？',
    success: (res) => {
      if (res.confirm) {
        // 1. 清空本地存储的消息
        wx.removeStorageSync(`messages_${convId}`);

        // 2. 从聊天列表中移除
        let chatList = wx.getStorageSync('chat_list') || [];
        chatList = chatList.filter(chat => chat.conv_id !== convId);
        wx.setStorageSync('chat_list', chatList);

        // 3. 刷新聊天列表
        this.setData({ chatList });

        // 4. 返回聊天列表页
        wx.navigateBack();

        wx.showToast({
          title: '已删除',
          icon: 'success'
        });
      }
    }
  });
}
```

**说明：**

- 删除聊天会清空聊天记录并从聊天列表移除
- 删除聊天不删除联系人关系
- 删除操作不可撤销
- 如果对方再次发送消息，聊天会重新出现在列表中

#### 4.4 标签管理

**实现方式：** 本地管理，通过联系人更新API同步到服务端

**标签数据结构：**

```javascript
// 本地存储的标签数据
const contactTags = {
  "conv_xyz789": ["朋友", "聊天"],
  "conv_abc456": ["工作", "重要"]
};
```

**标签操作：**

```javascript
// 添加标签
async addTag(convId, tag) {
  let tags = wx.getStorageSync('contact_tags') || {};
  if (!tags[convId]) {
    tags[convId] = [];
  }
  if (!tags[convId].includes(tag)) {
    tags[convId].push(tag);
    wx.setStorageSync('contact_tags', tags);

    // 同步到服务端（使用联系人更新API）
    try {
      await apiClient.put(`/api/v1/contacts/${convId}`, {
        tags: tags[convId]
      });
    } catch (error) {
      console.error('同步标签失败:', error);
      // 标记需要重试
      this.markNeedSync('tags', convId);
    }
  }
}

// 删除标签
async removeTag(convId, tag) {
  let tags = wx.getStorageSync('contact_tags') || {};
  if (tags[convId]) {
    tags[convId] = tags[convId].filter(t => t !== tag);
    wx.setStorageSync('contact_tags', tags);

    // 同步到服务端（使用联系人更新API）
    try {
      await apiClient.put(`/api/v1/contacts/${convId}`, {
        tags: tags[convId]
      });
    } catch (error) {
      console.error('同步标签失败:', error);
      // 标记需要重试
      this.markNeedSync('tags', convId);
    }
  }
}
```

**同步策略：**

- 标签修改后立即通过联系人更新API同步到服务端
- 应用启动时从服务端拉取联系人列表（包含标签数据）
- 同步失败时标记需要重试，下次启动时重试

#### 4.5 搜索历史

**实现方式：** 本地存储，不同步到服务端

**搜索历史管理：**

```javascript
// 添加搜索历史
addSearchHistory(keyword) {
  let history = wx.getStorageSync('search_history') || [];

  // 移除重复项
  history = history.filter(item => item !== keyword);

  // 添加到开头
  history.unshift(keyword);

  // 限制数量（最多保留20条）
  if (history.length > 20) {
    history = history.slice(0, 20);
  }

  wx.setStorageSync('search_history', history);
}

// 获取搜索历史
getSearchHistory() {
  return wx.getStorageSync('search_history') || [];
}

// 清空搜索历史
clearSearchHistory() {
  wx.removeStorageSync('search_history');
}

// 删除单条搜索历史
removeSearchHistory(keyword) {
  let history = wx.getStorageSync('search_history') || [];
  history = history.filter(item => item !== keyword);
  wx.setStorageSync('search_history', history);
}
```

#### 4.6 本地设置

**实现方式：** 本地存储，不同步到服务端

**设置项：**

```javascript
// 本地设置数据结构
const localSettings = {
  // 消息设置
  message_sound: 'default',  // 消息提示音

  // 通用设置
  language: 'zh-CN',         // 语言
  font_size: 'medium',       // 字体大小：small, medium, large
  dark_mode: false,          // 深色模式

  // 其他设置
  auto_download_image: true, // 自动下载图片
  save_to_album: false       // 保存到相册
};
```

**设置操作：**

```javascript
// 获取本地设置
getLocalSettings() {
  return wx.getStorageSync('local_settings') || {
    message_sound: 'default',
    language: 'zh-CN',
    font_size: 'medium',
    dark_mode: false,
    auto_download_image: true,
    save_to_album: false
  };
}

// 更新本地设置
updateLocalSettings(settings) {
  const currentSettings = this.getLocalSettings();
  const newSettings = { ...currentSettings, ...settings };
  wx.setStorageSync('local_settings', newSettings);

  // 应用设置
  this.applySettings(newSettings);
}

// 应用设置
applySettings(settings) {
  // 应用字体大小
  if (settings.font_size) {
    this.setFontSize(settings.font_size);
  }

  // 应用深色模式
  if (settings.dark_mode !== undefined) {
    this.setDarkMode(settings.dark_mode);
  }
}
```

## 5. 消息服务Provider架构

### 5.1 设计原则

1. **抽象接口：** 定义统一的Provider接口，支持多种消息服务提供商
2. **可替换性：** 可以轻松切换不同的消息服务提供商（LeanCloud、Firebase、Pusher等）
3. **准确命名：** 内部代码使用准确的命名（如lc-provider.js表示LeanCloud Provider），不为了隐藏而模糊
4. **面向客户端隐藏：** API响应中使用数字表示provider类型，不出现具体名称

### 5.2 目录结构

```
utils/message/
├── provider.js           # Provider接口定义
├── lc-provider.js        # LeanCloud Provider实现
├── message-service.js    # 消息服务封装
└── provider-types.js     # Provider类型枚举
```

### 5.3 Provider类型枚举

```javascript
/**
 * Message Provider Types
 */
export const ProviderType = {
  LEANCLOUD: 1,  // LeanCloud
  // Future providers can be added here
  // FIREBASE: 2,
  // PUSHER: 3
};
```

### 5.4 Provider接口定义

```javascript
/**
 * Message Provider Interface
 * Defines the interface for message service providers
 */
class MessageProvider {
  /**
   * Initialize provider
   * @param {Object} config - Provider configuration
   */
  async init(config) {
    throw new Error('Method not implemented');
  }

  /**
   * Send message
   * @param {Object} message - Message object
   */
  async sendMessage(message) {
    throw new Error('Method not implemented');
  }

  /**
   * Listen for messages
   * @param {Function} callback - Message callback
   */
  onMessage(callback) {
    throw new Error('Method not implemented');
  }

  /**
   * Disconnect
   */
  async disconnect() {
    throw new Error('Method not implemented');
  }
}

export default MessageProvider;
```

### 5.5 LeanCloud Provider实现

```javascript
import MessageProvider from './provider.js';
import AV from 'leancloud-storage/live-query';

/**
 * LeanCloud Message Provider
 * Implementation of MessageProvider using LeanCloud
 */
class LCProvider extends MessageProvider {
  constructor() {
    super();
    this.client = null;
    this.conversation = null;
  }

  /**
   * Initialize LeanCloud
   * @param {Object} config - LeanCloud configuration
   * @param {string} config.app_id - LeanCloud App ID
   * @param {string} config.app_key - LeanCloud App Key
   * @param {string} config.server_url - LeanCloud Server URL
   * @param {string} config.conversation_id - System conversation ID
   */
  async init(config) {
    // Initialize LeanCloud SDK
    AV.init({
      appId: config.app_id,
      appKey: config.app_key,
      serverURL: config.server_url
    });

    // Create realtime client
    this.client = new AV.Realtime({
      appId: config.app_id,
      appKey: config.app_key,
      server: config.server_url
    });

    // Join system conversation
    this.conversation = await this.client.getConversation(config.conversation_id);
  }

  async sendMessage(message) {
    await this.conversation.send(new AV.TextMessage(JSON.stringify(message)));
  }

  onMessage(callback) {
    this.conversation.on('message', (message) => {
      const data = JSON.parse(message.text);
      callback(data);
    });
  }

  async disconnect() {
    await this.client.close();
  }
}

export default LCProvider;
```

### 5.6 消息服务封装

```javascript
import LCProvider from './lc-provider.js';
import { ProviderType } from './provider-types.js';
import apiClient from '../api.js';

/**
 * Message Service
 * Manages message sending and receiving
 */
class MessageService {
  constructor() {
    this.provider = null;
    this.initialized = false;
  }

  /**
   * Initialize message service
   */
  async init() {
    if (this.initialized) return;

    // Get message config from API
    const response = await apiClient.get('/api/v1/system/message-config');
    const config = response.data;

    // Create provider based on provider type
    switch (config.provider) {
      case ProviderType.LEANCLOUD:
        this.provider = new LCProvider();

        // LeanCloud configuration (hardcoded in code)
        const lcConfig = {
          app_id: 'xxx',
          app_key: 'xxx',
          server_url: 'https://xxx.leancloud.cn',
          conversation_id: config.conversation_id
        };

        await this.provider.init(lcConfig);
        break;

      default:
        throw new Error(`Unsupported provider: ${config.provider}`);
    }

    this.initialized = true;
  }

  async sendMessage(message) {
    if (!this.initialized) {
      throw new Error('Message service not initialized');
    }
    await this.provider.sendMessage(message);
  }

  onMessage(callback) {
    if (!this.initialized) {
      throw new Error('Message service not initialized');
    }
    this.provider.onMessage(callback);
  }

  async disconnect() {
    if (this.provider) {
      await this.provider.disconnect();
    }
  }
}

export default new MessageService();
```

### 5.7 配置管理策略

#### 配置分类

1. **LeanCloud配置（app_id、app_key、server_url）：**
   - 写在小程序代码里（hardcoded）
   - 理由：小程序有域名白名单保护，相对安全

2. **系统对话ID（conversation_id）：**
   - 通过API获取（GET /api/v1/system/message-config）
   - 理由：可能变化，通过接口获取更灵活

#### 初始化流程

```javascript
// 1. 初始化消息服务
await messageService.init();

// 2. 监听消息
messageService.onMessage((message) => {
  console.log('Received message:', message);
});

// 3. 发送消息
await messageService.sendMessage({
  from: 'qiao_user001',
  to: 'qiao_xm001',
  content: '你好',
  message_type: 1
});
```

### 5.8 扩展新Provider

如果需要添加新的消息服务提供商（如Firebase），只需：

1. 在`provider-types.js`中添加新类型：

```javascript
export const ProviderType = {
  LEANCLOUD: 1,
  FIREBASE: 2,  // 新增
};
```

2. 创建新的Provider实现（`firebase-provider.js`）：

```javascript
import MessageProvider from './provider.js';

class FirebaseProvider extends MessageProvider {
  // 实现接口方法
}

export default FirebaseProvider;
```

3. 在`message-service.js`中添加case分支：

```javascript
case ProviderType.FIREBASE:
  this.provider = new FirebaseProvider();
  await this.provider.init(firebaseConfig);
  break;
```
