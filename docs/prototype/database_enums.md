# 数据库枚举值定义

## 用户管理相关枚举

### 用户状态 (users.status)

```python
class UserStatus:
    ACTIVE = 1      # 正常活跃
    INACTIVE = 2    # 非活跃
    SUSPENDED = 3   # 已停用
```

### 用户类型 (users.user_type)

```python
class UserType:
    NORMAL = 1      # 普通用户
    OFFICIAL = 2    # 官方账号
    ADMIN = 3       # 管理员
```

### 设备类型 (user_sessions.device_type, login_records.platform)

```python
class DeviceType:
    IOS = 1             # iOS设备
    ANDROID = 2         # Android设备
    WEB = 3             # 网页端
    MINI_PROGRAM = 4    # 小程序
```

### 登录方式 (login_records.login_type)

```python
class LoginType:
    PASSWORD = 1    # 密码登录
    SMS = 2         # 短信验证码
    WECHAT = 3      # 微信登录
    APPLE = 4       # Apple ID登录
```

### 登录结果 (login_records.result)

```python
class LoginResult:
    SUCCESS = 1     # 登录成功
    FAIL = 2        # 登录失败
```

## 联系人管理相关枚举

### 联系人类型 (contacts.contact_type)

```python
class ContactType:
    USER = 1        # 用户
    AI = 2          # AI角色
    OFFICIAL = 3    # 官方账号
```

### 联系人申请来源 (contact_requests.source)

```python
class ContactRequestSource:
    SEARCH = 1      # 搜索添加
    ADMIN = 2       # 管理员添加
    SYSTEM = 3      # 系统添加
    RECOMMEND = 4   # 推荐添加
```

### 联系人申请状态 (contact_requests.status)

```python
class ContactRequestStatus:
    PENDING = 1     # 待处理
    ACCEPTED = 2    # 已接受
    IGNORED = 3     # 已忽略（无响应，无通知）
    EXPIRED = 4     # 已过期
    REJECTED = 5    # 已拒绝（未来功能：明确拒绝并通知）
```

## 消息系统相关枚举

### 消息方向 (message_history.direction)

```python
class MessageDirection:
    INBOUND = 1     # 入站消息
    OUTBOUND = 2    # 出站消息
```

### 发送方/接收方类型 (message_history.from_type, message_history.to_type)

```python
class MessageParticipantType:
    USER = 1        # 用户
    AI = 2          # AI角色
    ADMIN = 3       # 管理员
    SYSTEM = 4      # 系统
```

### 服务提供商 (message_history.service_provider)

```python
class ServiceProvider:
    LEANCLOUD = 1   # LeanCloud
    INTERNAL = 2    # 内部系统
```

### 消息类型 (message_history.message_type)

```python
class MessageType:
    TEXT = 1          # 文本消息
    TYPING = 2        # 正在输入
    TYPING_END = 3    # 输入结束
    CHAT_INFO = 4     # 对话界面提示信息
    NOTIFICATION = 9  # 通知消息
```

### 对话提示信息类型 (ChatInfoType)

说明: 用于业务层选择预设文本，不存储在数据库中

```python
class ChatInfoType:
    CONTACT_ADDED = 1      # 对方已将你添加为联系人
    MESSAGE_BLOCKED = 2    # 消息已发出,但对方拒收了
    NOT_FRIEND = 3         # 对方还没有添加你为联系人
```

### 对话提示信息行为类型 (message_history.metadata.action.type)

说明: CHAT_INFO 消息可选的 action 字段类型

```python
class ChatInfoActionType:
    MARK_MESSAGE_FAILED = "mark_message_failed"  # 标记消息为失败
```

### 通知消息类型 (notification_push_history.notification_type)

```python
class NotificationType:
    CONTACT_REQUEST = 1    # 联系人请求通知
```

### 通知行为类型 (action_data.action.type)

```python
class NotificationActionType:
    NAVIGATE = "navigate"  # 导航到页面
    REFRESH = "refresh"    # 刷新数据
    BADGE = "badge"        # 更新角标
```

### 通知目标 (action_data.action.target)

```python
class NotificationTarget:
    CONTACT_REQUESTS = "contact_requests"  # 联系人请求页面
    CONTACTS = "contacts"                  # 联系人列表页面
```

### 通知推送状态 (notification_push_history.status)

```python
class NotificationStatus:
    SENT = 1      # 已发送
    FAILED = 2    # 发送失败
```

### 消息状态 (message_history.status)

```python
class MessageStatus:
    SENT = 1        # 已发送
    DELIVERED = 2   # 已送达
    READ = 3        # 已读
    FAILED = 4      # 发送失败
```

## 媒体文件相关枚举

### 文件类型 (media_files.file_type)

```python
class FileType:
    AVATAR = 1      # 头像
    EMOJI = 2       # 表情
    IMAGE = 3       # 图片
    DOCUMENT = 4    # 文档
```

### 文件状态 (media_files.status)

```python
class FileStatus:
    ACTIVE = 1      # 活跃
    INACTIVE = 2    # 非活跃
    DELETED = 3     # 已删除
```

### 上传者类型 (media_files.upload_by_type)

```python
class UploaderType:
    USER = 1        # 用户上传
    ADMIN = 2       # 管理员上传
    SYSTEM = 3      # 系统上传
```

## 资料管理相关枚举

### 性别 (profiles.gender)

```python
class Gender:
    MALE = 1        # 男性
    FEMALE = 2      # 女性
    OTHER = 3       # 其他
    UNKNOWN = 4     # 未知
```

### 资料所有者类型 (profiles.owner_type)

```python
class ProfileOwnerType:
    USER = 1        # 用户
    AI = 2          # AI角色
    OFFICIAL = 3    # 官方账号
```

### 资料修改者类型 (user_profile_logs.modified_by_type)

```python
class ProfileModifierType:
    USER = 1        # 用户自己
    ADMIN = 2       # 管理员
    SYSTEM = 3      # 系统
```

## 表情管理相关枚举

### 表情分类 (emoticons.category)

```python
class EmoticonCategory:
    SYSTEM = 1      # 系统表情
    CUSTOM = 2      # 自定义表情
    PREMIUM = 3     # 付费表情
```

### 表情创建者类型 (emoticons.created_by_type)

```python
class EmoticonCreatorType:
    USER = 1        # 用户创建
    SYSTEM = 2      # 系统创建
    ADMIN = 3       # 管理员创建
```

## AI系统相关枚举

### AI模板分类 (ai_profile_templates.category)

```python
class AIProfileCategory:
    FRIEND = 1      # 交友
    LOVE = 2        # 恋爱
    TALK = 3        # 倾诉
    BESTIE = 4      # 闺蜜
    HOBBY = 5       # 同好
```

**注意**: 数据库字段为VARCHAR(50),存储字符串形式的数字("1","2"等),以保持灵活性。

### AI角色创建者 (ai_characters.created_by)

```python
class AICharacterCreator:
    USER = 1        # 用户创建
    ADMIN = 2       # 管理员创建
    SYSTEM = 3      # 系统创建
```

### AI角色状态 (ai_characters.status)

```python
class AICharacterStatus:
    ACTIVE = 1      # 活跃角色
    INACTIVE = 2    # 非活跃角色
    BLOCKED = 3     # 已封禁角色
```

### AI风格状态 (ai_styles.status)

```python
class AIStyleStatus:
    ACTIVE = 1      # 活跃风格
    INACTIVE = 2    # 非活跃风格
```

### AI人格状态 (ai_personalities.status)

```python
class AIPersonalityStatus:
    ACTIVE = 1      # 活跃人格
    INACTIVE = 2    # 非活跃人格
```

### AI关系状态 (ai_relationships.status)

```python
class AIRelationshipStatus:
    ACTIVE = 1      # 活跃关系
    INACTIVE = 2    # 非活跃关系
```

### AI上下文角色 (ai_contexts.role)

```python
class AIContextRole:
    USER = 1        # 用户消息
    AI = 2          # AI回复
    SYSTEM = 3      # 系统消息
```

### AI上下文来源类型 (ai_contexts.source_type)

```python
class AIContextSourceType:
    ORIGINAL = 1    # 原始消息
    MERGED = 2      # 合并消息
    SUMMARIZED = 3  # 摘要消息
```

### AI请求状态 (ai_request_logs.status)

```python
class AIRequestStatus:
    SUCCESS = 1     # 成功
    FAILED = 2      # 失败
    TIMEOUT = 3     # 超时
```

## 安全监控相关枚举

### 违规类型 (user_security_logs.violation_type)

```python
class ViolationType:
    PROMPT_INJECTION = 1    # 提示词注入
    ABUSE_CONTENT = 2       # 滥用内容
    SPAM = 3                # 垃圾信息
    HARASSMENT = 4          # 骚扰行为
    OTHER = 5               # 其他违规
```

### 严重程度 (user_security_logs.severity_level)

```python
class SeverityLevel:
    LOW = 1         # 低
    MEDIUM = 2      # 中
    HIGH = 3        # 高
    CRITICAL = 4    # 严重
```

### 自动处理动作 (user_security_logs.auto_action_taken)

```python
class AutoAction:
    NONE = 1        # 无动作
    WARNING = 2     # 警告
    RESTRICT = 3    # 限制
    SUSPEND = 4     # 停用
```

### 人工审核状态 (user_security_logs.manual_review_status)

```python
class ManualReviewStatus:
    PENDING = 1         # 待审核
    CONFIRMED = 2       # 确认违规
    FALSE_POSITIVE = 3  # 误报
    IGNORED = 4         # 忽略
```

### 用户风险等级 (user_security_stats.current_risk_level)

```python
class RiskLevel:
    LOW = 1         # 低风险
    MEDIUM = 2      # 中风险
    HIGH = 3        # 高风险
    BANNED = 4      # 已封禁
```

## 系统配置相关枚举

### 配置值类型 (system_configs.config_type)

```python
class ConfigType:
    STRING = 1      # 字符串
    NUMBER = 2      # 数字
    BOOLEAN = 3     # 布尔值
    JSON = 4        # JSON对象
```

## 管理员系统相关枚举

### 管理员角色 (admin_users.role)

```python
class AdminRole:
    SUPER_ADMIN = 1 # 超级管理员
    ADMIN = 2       # 管理员
    VIEWER = 3      # 查看者
```

### 管理员状态 (admin_users.status)

```python
class AdminStatus:
    ACTIVE = 1      # 活跃
    INACTIVE = 2    # 非活跃
```

### 管理员操作类型 (admin_operation_logs.operation_type)

```python
class AdminOperationType:
    CREATE = 1      # 创建
    UPDATE = 2      # 更新
    DELETE = 3      # 删除
    ENABLE = 4      # 启用
    DISABLE = 5     # 禁用
```

### 管理员登录结果 (admin_login_logs.result)

```python
class AdminLoginResult:
    SUCCESS = 1     # 成功
    FAIL = 2        # 失败
```

## 使用说明

1. **代码实现**：在后端代码中定义这些枚举类，确保数据一致性
2. **验证机制**：在数据插入和更新时验证枚举值的有效性
3. **文档同步**：当添加新的枚举值时，同步更新此文档
4. **向后兼容**：新增枚举值时考虑向后兼容性，避免破坏现有功能
