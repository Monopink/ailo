"""Admin i18n helpers and configuration."""

from __future__ import annotations

import re

from starlette_admin import I18nConfig
from starlette_admin.i18n import get_locale

_PLURAL_IES_SUFFIX_LEN = 3
_MIN_PLURAL_IES_WORD_LEN = 3
_MIN_PLURAL_S_WORD_LEN = 1

_LEANCLOUD_CALLBACK_HINT = (
    "Configure this URL in LeanCloud console: Developer Center > IM > Settings > "
    "Service Account Callback"
)
_WEBHOOK_REGEN_NOTICE = (
    "Regenerating the token will invalidate the current webhook URL. "
    "You must update the URL in LeanCloud console immediately."
)
_SYSTEM_CONVERSATION_REGEN_WARNING = (
    "WARNING: This will create a new system conversation and invalidate the old one!\n\n"
    "You should update any references to the old conversation ID.\n\nContinue?"
)
_WEBHOOK_REGEN_WARNING = (
    "WARNING: This will invalidate the current webhook URL!\n\n"
    "You MUST update the webhook URL in LeanCloud console immediately after "
    "regeneration.\n\nContinue?"
)

_ADMIN_TEXT_MAP: dict[str, tuple[str, str]] = {
    "Users": ("用户", "Users"),
    "Messages": ("消息", "Messages"),
    "AI Configuration": ("AI 配置", "AI Configuration"),
    "AI Runtime": ("AI 运行态", "AI Runtime"),
    "LLM": ("大模型", "LLM"),
    "Growth": ("增长", "Growth"),
    "Entitlement": ("权益", "Entitlement"),
    "Security": ("安全", "Security"),
    "Authorization": ("鉴权", "Authorization"),
    "Media": ("媒体", "Media"),
    "App Content": ("内容", "App Content"),
    "Statistics": ("统计", "Statistics"),
    "System": ("系统", "System"),
    "System Settings": ("系统设置", "System Settings"),
    "Operation Settings": ("运营设置", "Operation Settings"),
    "System Management": ("系统管理", "System Management"),
    "LeanCloud System": ("LeanCloud 系统", "LeanCloud System"),
    "System Conversation ID": ("系统会话 ID", "System Conversation ID"),
    "App ID": ("App ID", "App ID"),
    "Master Key": ("Master Key", "Master Key"),
    "Base URL": ("基础 URL", "Base URL"),
    "Configuration Status": ("配置状态", "Configuration Status"),
    "Regenerate Conversation": ("重新生成会话", "Regenerate Conversation"),
    "Webhook Management": ("Webhook 管理", "Webhook Management"),
    "Webhook URL": ("Webhook URL", "Webhook URL"),
    "Token Status": ("Token 状态", "Token Status"),
    "Token generated": ("Token 已生成", "Token generated"),
    "Token not generated": ("Token 未生成", "Token not generated"),
    "characters": ("字符", "characters"),
    _LEANCLOUD_CALLBACK_HINT: (
        "请在 LeanCloud 控制台配置此 URL：开发者中心 > 即时通讯 > 设置 > 服务号消息回调",
        _LEANCLOUD_CALLBACK_HINT,
    ),
    _WEBHOOK_REGEN_NOTICE: (
        "重新生成 Token 会使当前 webhook URL 失效。你必须立即在 LeanCloud 控制台更新 URL。",
        _WEBHOOK_REGEN_NOTICE,
    ),
    "Regenerate Token": ("重新生成 Token", "Regenerate Token"),
    "Warning:": ("警告：", "Warning:"),
    "The following configuration keys are not displayed in the UI:": (
        "以下配置键未在页面中显示：",
        "The following configuration keys are not displayed in the UI:",
    ),
    "Default item:": ("默认项：", "Default item:"),
    "(not set)": ("（未设置）", "(not set)"),
    "Default:": ("默认值：", "Default:"),
    "-- No Change --": ("-- 不修改 --", "-- No Change --"),
    "Leave empty for no change": ("留空表示不修改", "Leave empty for no change"),
    'Leave empty for no change. Example: ["value1","value2"]': (
        '留空表示不修改。例如：["value1","value2"]',
        'Leave empty for no change. Example: ["value1","value2"]',
    ),
    "Use current value": ("使用当前值", "Use current value"),
    "Reset to default": ("填充默认值", "Reset to default"),
    "Toggle delete state": ("切换删除状态", "Toggle delete state"),
    "Copy": ("复制", "Copy"),
    "Save Settings": ("保存设置", "Save Settings"),
    "No changes to save. All modification fields are empty.": (
        "没有可保存的修改，所有修改输入框均为空。",
        "No changes to save. All modification fields are empty.",
    ),
    "You are about to modify the following configuration(s):": (
        "你即将修改以下配置：",
        "You are about to modify the following configuration(s):",
    ),
    "Are you sure you want to save these changes?": (
        "确认保存这些修改吗？",
        "Are you sure you want to save these changes?",
    ),
    "Current value is not available in selectable options.": (
        "当前值不在可选项中。",
        "Current value is not available in selectable options.",
    ),
    "-- Select --": ("-- 请选择 --", "-- Select --"),
    "Enter JSON item": ("输入 JSON 项", "Enter JSON item"),
    "Enter value": ("输入值", "Enter value"),
    "Add row": ("新增一行", "Add row"),
    "(new item)": ("（新增项）", "(new item)"),
    "Reload CDN config will clear caches on all workers.\n\nApply the latest domain now?": (
        "重新加载 CDN 配置会清空所有 worker 缓存。\n\n是否立即应用最新域名？",
        "Reload CDN config will clear caches on all workers.\n\nApply the latest domain now?",
    ),
    "Conversation ID copied!": ("会话 ID 已复制！", "Conversation ID copied!"),
    "Failed to copy": ("复制失败", "Failed to copy"),
    _SYSTEM_CONVERSATION_REGEN_WARNING: (
        "警告：这会创建新的系统会话并使旧会话失效！\n\n"
        "你应更新所有旧会话 ID 的引用。\n\n是否继续？",
        _SYSTEM_CONVERSATION_REGEN_WARNING,
    ),
    "System conversation regenerated successfully!": (
        "系统会话重新生成成功！",
        "System conversation regenerated successfully!",
    ),
    "New ID": ("新 ID", "New ID"),
    "Failed:": ("失败：", "Failed:"),
    "Failed to regenerate conversation": ("重新生成会话失败", "Failed to regenerate conversation"),
    "Webhook URL copied to clipboard!": (
        "Webhook URL 已复制到剪贴板！",
        "Webhook URL copied to clipboard!",
    ),
    "Failed to copy URL": ("复制 URL 失败", "Failed to copy URL"),
    _WEBHOOK_REGEN_WARNING: (
        "警告：这会使当前 webhook URL 失效！\n\n"
        "重新生成后你必须立即在 LeanCloud 控制台更新 webhook URL。\n\n是否继续？",
        _WEBHOOK_REGEN_WARNING,
    ),
    "Token regenerated successfully!": ("Token 重新生成成功！", "Token regenerated successfully!"),
    "New webhook URL has been loaded.": (
        "新的 webhook URL 已加载。",
        "New webhook URL has been loaded.",
    ),
    "Unknown error": ("未知错误", "Unknown error"),
    "Failed to regenerate token": ("重新生成 Token 失败", "Failed to regenerate token"),
    "Permission denied": ("无权限", "Permission denied"),
    "Admin user not found in session": (
        "会话中未找到管理员用户",
        "Admin user not found in session",
    ),
    "Successfully updated {count} configuration(s)": (
        "成功更新 {count} 个配置项",
        "Successfully updated {count} configuration(s)",
    ),
    "No changes to save (all modification fields were empty)": (
        "没有可保存的修改（所有修改输入框均为空）",
        "No changes to save (all modification fields were empty)",
    ),
    "Failed to update settings: {error}": (
        "保存设置失败：{error}",
        "Failed to update settings: {error}",
    ),
    "Failed to load settings: {error}": (
        "加载设置失败：{error}",
        "Failed to load settings: {error}",
    ),
    "Operation Configuration": ("运营配置", "Operation Configuration"),
    "System Configuration": ("系统配置", "System Configuration"),
    "Dashboard": ("仪表盘", "Dashboard"),
    "Admin": ("管理端", "Admin"),
    "Theme Switch": ("主题切换", "Theme Switch"),
    "Theme": ("主题", "Theme"),
    "Auto": ("跟随系统", "Auto"),
    "Light": ("浅色", "Light"),
    "Dark": ("深色", "Dark"),
    "Language": ("语言", "Language"),
    "Open user menu": ("打开用户菜单", "Open user menu"),
    "Create": ("新建", "Create"),
    "Edit": ("编辑", "Edit"),
    "Detail": ("详情", "Detail"),
    "Cancel": ("取消", "Cancel"),
    "Save": ("保存", "Save"),
    "Save and add another": ("保存并继续新增", "Save and add another"),
    "Save and continue editing": ("保存并继续编辑", "Save and continue editing"),
    "Attribute": ("属性", "Attribute"),
    "Value": ("值", "Value"),
    "Logout": ("退出登录", "Logout"),
    "Dev": ("开发", "Dev"),
    "Staging": ("预发", "Staging"),
    "Prod": ("生产", "Prod"),
    "Message Historys": ("消息历史", "Message Historys"),
    "Message History": ("消息历史", "Message History"),
    "Instance Memories": ("实例记忆", "Instance Memories"),
    "Template Memories": ("模板记忆", "Template Memories"),
    "Styles": ("风格", "Styles"),
    "Personas - Active Reusable": ("人设 - 活跃可复用", "Personas - Active Reusable"),
    "Personas - Active Single-use": ("人设 - 活跃单次", "Personas - Active Single-use"),
    "Templates - Active Reusable": ("模板 - 活跃可复用", "Templates - Active Reusable"),
    "Templates - Active Single-use": ("模板 - 活跃单次", "Templates - Active Single-use"),
    "Invite Codes": ("邀请码", "Invite Codes"),
    "Invite Bindings": ("邀请码绑定", "Invite Bindings"),
    "Invite Events": ("邀请码事件", "Invite Events"),
    "Campaigns": ("活动", "Campaigns"),
    "Reward Rules": ("奖励规则", "Reward Rules"),
    "Reward Applies": ("奖励发放记录", "Reward Applies"),
    "Redeem Code Batches": ("兑换码批次", "Redeem Code Batches"),
    "Redeem Codes": ("兑换码", "Redeem Codes"),
    "Redeem Claims": ("兑换码领取记录", "Redeem Claims"),
    "Entitlement Operations": ("权益操作", "Entitlement Operations"),
    "Entitlement Types": ("权益类型字典", "Entitlement Types"),
    "Entitlement Reason Codes": ("权益原因码", "Entitlement Reason Codes"),
    "Applies To": ("适用操作", "Applies To"),
    "User Entitlement Accounts": ("用户权益账户", "User Entitlement Accounts"),
    "User Entitlement Ledger": ("用户权益账本", "User Entitlement Ledger"),
    "Owner User": ("拥有者用户", "Owner User"),
    "Invitee User ID": ("被邀请用户ID", "Invitee User ID"),
    "Invite Code ID": ("邀请码ID", "Invite Code ID"),
    "Inviter User ID Snapshot": ("邀请人用户ID快照", "Inviter User ID Snapshot"),
    "Actor User ID": ("操作用户ID", "Actor User ID"),
    "Event Source": ("事件来源", "Event Source"),
    "Code Snapshot": ("邀请码快照", "Code Snapshot"),
    "Event Payload": ("事件载荷", "Event Payload"),
    "Resolve Valid Count": ("有效解析次数", "Resolve Valid Count"),
    "Bind Success Count": ("绑定成功次数", "Bind Success Count"),
    "Is System": ("系统内置", "Is System"),
    "Entitlement Type": ("权益类型", "Entitlement Type"),
    "Entitlement Type ID": ("权益类型ID", "Entitlement Type ID"),
    "Rule ID": ("规则ID", "Rule ID"),
    "Trigger Event": ("触发事件", "Trigger Event"),
    "Target Role": ("目标角色", "Target Role"),
    "Scope Type": ("作用域类型", "Scope Type"),
    "Scope ID": ("作用域ID", "Scope ID"),
    "Beneficiary User ID": ("受益用户ID", "Beneficiary User ID"),
    "Source Type": ("来源类型", "Source Type"),
    "Source ID": ("来源ID", "Source ID"),
    "Campaign Scope": ("活动作用域", "Campaign Scope"),
    "Redeem Batch Scope": ("兑换批次作用域", "Redeem Batch Scope"),
    "Delta": ("增量", "Delta"),
    "Delta Granted": ("发放增量", "Delta Granted"),
    "Delta Used": ("消耗增量", "Delta Used"),
    "Granted Total": ("累计发放", "Granted Total"),
    "Used Total": ("累计消耗", "Used Total"),
    "Available Total": ("可用总量", "Available Total"),
    "Action Type": ("动作类型", "Action Type"),
    "Effective At": ("生效时间", "Effective At"),
    "Ledger ID": ("账本ID", "Ledger ID"),
    "Idempotency Key": ("幂等键", "Idempotency Key"),
    "Operator Admin User ID": ("操作管理员用户ID", "Operator Admin User ID"),
    "Batch": ("批次", "Batch"),
    "Operation Builder": ("操作面板", "Operation Builder"),
    "Execute Operation": ("执行操作", "Execute Operation"),
    "Latest Ledger Records (50)": ("最近50条账本记录", "Latest Ledger Records (50)"),
    "No operation records.": ("暂无操作记录。", "No operation records."),
    "Find User": ("查找用户", "Find User"),
    "Please search and select one user": (
        "请先搜索并选择一个用户",
        "Please search and select one user",
    ),
    "Search": ("搜索", "Search"),
    "Searching users...": ("正在搜索用户...", "Searching users..."),
    "User search failed.": ("用户搜索失败。", "User search failed."),
    "No matching users found.": ("未找到匹配用户。", "No matching users found."),
    "Failed to load user entitlement assets.": (
        "加载用户权益资产失败。",
        "Failed to load user entitlement assets.",
    ),
    "No entitlement assets found for this user.": (
        "该用户暂无权益资产。",
        "No entitlement assets found for this user.",
    ),
    "Available": ("可用", "Available"),
    "Grant": ("发放", "Grant"),
    "Grant (positive only)": ("发放（仅正数）", "Grant (positive only)"),
    "Adjust": ("调整", "Adjust"),
    "Adjust (positive add / negative deduct)": (
        "调整（正数增加 / 负数扣减）",
        "Adjust (positive add / negative deduct)",
    ),
    "grant": ("发放", "grant"),
    "adjust": ("调整", "adjust"),
    "After Operation": ("操作后", "After Operation"),
    "Granted": ("已发放", "Granted"),
    "Used": ("已消耗", "Used"),
    "Description (Optional)": ("描述（可选）", "Description (Optional)"),
    "Leave empty if no extra context is needed.": (
        "如无额外说明可留空。",
        "Leave empty if no extra context is needed.",
    ),
    "Invalid operation result": ("操作结果无效", "Invalid operation result"),
    "Failed to load entitlement snapshot.": (
        "加载权益快照失败。",
        "Failed to load entitlement snapshot.",
    ),
    "Please select a user first.": ("请先选择用户。", "Please select a user first."),
    "Confirm Operation": ("确认操作", "Confirm Operation"),
    "Please confirm operation details before execution.": (
        "执行前请再次确认操作信息。",
        "Please confirm operation details before execution.",
    ),
    "Confirm and Execute": ("确认并执行", "Confirm and Execute"),
    "Please enter a valid adjustment amount.": (
        "请输入有效的调整数量。",
        "Please enter a valid adjustment amount.",
    ),
    "Please enter a valid adjustment amount according to the selected operation type.": (
        "请根据当前操作类型输入合法的调整数量。",
        "Please enter a valid adjustment amount according to the selected operation type.",
    ),
    "Please select a reason code": ("请选择原因码", "Please select a reason code"),
    "Please select a reason code.": ("请选择原因码。", "Please select a reason code."),
    "No reason code is configured for the selected operation type.": (
        "当前操作类型没有可用原因码，请先在原因码字典配置。",
        "No reason code is configured for the selected operation type.",
    ),
    "User {user}, entitlement {type}, operation {operation}, adjustment {delta}.": (
        "用户 {user}，权益类型 {type}，操作 {operation}，调整量 {delta}。",
        "User {user}, entitlement {type}, operation {operation}, adjustment {delta}.",
    ),
    "Available after operation: {available}": (
        "操作后可用：{available}",
        "Available after operation: {available}",
    ),
    "Operation failed": ("操作失败", "Operation failed"),
    "Operation succeeded": ("操作成功", "Operation succeeded"),
    "Request accepted (idempotent hit, no duplicate write)": (
        "请求已受理（命中幂等，未重复写入）",
        "Request accepted (idempotent hit, no duplicate write)",
    ),
    "Operation": ("操作", "Operation"),
    "Viewer role is read-only and cannot submit operations.": (
        "Viewer 角色为只读，不能提交操作。",
        "Viewer role is read-only and cannot submit operations.",
    ),
    "Grant or adjust user entitlements through the unified ledger service.": (
        "通过统一账本服务发放或调整用户权益。",
        "Grant or adjust user entitlements through the unified ledger service.",
    ),
    "Reference ID": ("引用ID", "Reference ID"),
    "Phone Number": ("手机号", "Phone Number"),
    "Top P": ("采样上限 P", "Top P"),
}

_CONFIG_GROUP_TEXT_MAP: dict[str, tuple[str, str]] = {
    "contacts": ("联系人", "Contacts"),
    "invitations": ("邀请", "Invitations"),
    "profile": ("个人资料", "Profile"),
    "media": ("媒体", "Media"),
    "operation": ("运营", "Operation"),
    "auth": ("认证", "Auth"),
    "api": ("接口", "API"),
    "messaging": ("消息", "Messaging"),
    "im_leancloud": ("即时通讯 LeanCloud", "IM LeanCloud"),
    "admin_auth": ("管理员认证", "Admin Auth"),
    "auth_password": ("密码认证", "Password Auth"),
    "username": ("用户名", "Username"),
    "sms": ("短信", "SMS"),
    "discovery_square": ("广场", "Discovery Square"),
    "ai_conversation": ("AI 对话", "AI Conversation"),
    "alerting": ("告警", "Alerting"),
    "other": ("其他", "Other"),
}

_CONFIG_KEY_TEXT_MAP: dict[str, tuple[str, str]] = {
    "default_nickname_prefix": ("默认昵称前缀", "Default Nickname Prefix"),
    "default_nickname_suffix_length": ("默认昵称后缀长度", "Default Nickname Suffix Length"),
    "invite_share_command_texts": (
        "邀请分享口令模板",
        "Invite Share Command Text Templates",
    ),
    "invite_share_card_titles": (
        "邀请分享卡片标题模板",
        "Invite Share Card Title Templates",
    ),
    "contact_request_expiration_days": ("联系人请求过期天数", "Contact Request Expiration Days"),
    "contacts_initial_ai_contact_limit": ("初始 AI 联系人上限", "Initial AI Contact Limit"),
    "avatar_allowed_formats": ("头像允许格式", "Avatar Allowed Formats"),
}

_CONFIG_DESCRIPTION_TEXT_MAP: dict[str, tuple[str, str]] = {
    "default_nickname_prefix": (
        "系统生成昵称时使用的前缀",
        "Default prefix for system-generated profile nickname",
    ),
    "default_nickname_suffix_length": (
        "系统生成昵称时追加的随机后缀长度",
        "Random suffix length for system-generated profile nickname",
    ),
    "invite_share_command_texts": (
        "邀请分享口令文本模板列表",
        "Invite share command text templates",
    ),
    "invite_share_card_titles": (
        "邀请分享卡片标题模板列表",
        "Invite share card title templates",
    ),
    "avatar_allowed_formats": (
        "头像上传允许的 MIME 类型列表",
        "Allowed avatar MIME types",
    ),
_SQUARE_CATEGORY_THEME_TEXT_MAP: dict[str, tuple[str, str]] = {
    "blue": ("蓝色", "Blue"),
    "cyan": ("青色", "Cyan"),
    "teal": ("青绿色", "Teal"),
    "green": ("绿色", "Green"),
    "lime": ("荧光黄绿", "Lime"),
    "yellow": ("黄色", "Yellow"),
    "orange": ("橙色", "Orange"),
    "purple": ("紫色", "Purple"),
    "pink": ("粉色", "Pink"),
    "magenta": ("洋红色", "Magenta"),
    "beige": ("米色", "Beige"),
    "charcoal": ("炭黑色", "Charcoal"),
}

_WORD_MAP: dict[str, str] = {
    "Access": "访问",
    "Account": "账号",
    "Ack": "确认",
    "Admin": "管理",
    "Active": "活跃",
    "Activity": "活动",
    "Actions": "操作",
    "Action": "操作",
    "Adjustment": "调整",
    "Advanced": "高级",
    "Agent": "代理",
    "Allowed": "允许",
    "Algorithm": "算法",
    "Alias": "别名",
    "All": "全部",
    "Auth": "认证",
    "App": "应用",
    "Avatar": "头像",
    "Archive": "归档",
    "Archived": "已归档",
    "At": "于",
    "at": "于",
    "Attempt": "尝试",
    "Auto": "自动",
    "Base": "基础",
    "Bias": "偏置",
    "Bio": "简介",
    "Blocked": "已拉黑",
    "Buffer": "缓冲",
    "Batch": "批次",
    "Batches": "批次",
    "Binding": "绑定",
    "Bindings": "绑定",
    "Bucket": "桶",
    "bytes": "字节",
    "By": "自",
    "by": "自",
    "Calls": "调用",
    "Canceled": "已取消",
    "Cache": "缓存",
    "Campaign": "活动",
    "Category": "分类",
    "Change": "变更",
    "Chat": "聊天",
    "Choice": "选择",
    "Client": "客户端",
    "Code": "代码",
    "Completed": "完成",
    "Completion": "完成",
    "Config": "配置",
    "Console": "控制台",
    "Consecutive": "连续",
    "Confirmed": "已确认",
    "Contact": "联系人",
    "Contacts": "联系人",
    "Content": "内容",
    "Context": "上下文",
    "Conversation": "会话",
    "Count": "数量",
    "Creation": "创建",
    "Custom": "自定义",
    "Created": "创建",
    "Current": "当前",
    "Daily": "日",
    "Date": "日期",
    "Data": "数据",
    "Delta": "增量",
    "Deadline": "截止时间",
    "Default": "默认",
    "Delay": "延迟",
    "Deleted": "已删除",
    "Delivery": "投递",
    "Description": "描述",
    "Detail": "详情",
    "Device": "设备",
    "Dimensions": "维度",
    "Dispatched": "已派发",
    "Dispatch": "分发",
    "Dimension": "维度",
    "Direction": "方向",
    "Disabled": "禁用",
    "Display": "显示",
    "Entries": "条目",
    "Email": "邮箱",
    "Address": "地址",
    "Enable": "启用",
    "End": "结束",
    "Duration": "时长",
    "Edit": "编辑",
    "Enabled": "启用",
    "Endpoint": "端点",
    "Environment": "环境",
    "Entitlement": "权益",
    "Entitlements": "权益",
    "Error": "错误",
    "Example": "示例",
    "Exposure": "曝光",
    "Expires": "过期",
    "Extra": "额外",
    "Failed": "失败",
    "Failure": "失败",
    "Field": "字段",
    "File": "文件",
    "Files": "文件",
    "First": "首个",
    "Followup": "追问",
    "Form": "表单",
    "From": "来源",
    "Fragment": "片段",
    "Frequency": "频率",
    "Gender": "性别",
    "Granted": "已发放",
    "Group": "分组",
    "Hash": "哈希",
    "Headers": "请求头",
    "Hit": "命中",
    "History": "历史",
    "IDs": "ID",
    "ID": "ID",
    "Importance": "重要性",
    "IP": "IP",
    "Inbound": "入站",
    "Info": "信息",
    "Ingress": "入口",
    "Initial": "初始",
    "Instance": "实例",
    "Instances": "实例",
    "Interrupted": "中断",
    "Inventory": "清单",
    "Invite": "邀请",
    "Invitee": "被邀请人",
    "Inviter": "邀请人",
    "Item": "项",
    "Items": "项",
    "JSON": "JSON",
    "Key": "键",
    "Kind": "类型",
    "Last": "最近",
    "Lease": "租约",
    "Level": "等级",
    "Limit": "限制",
    "List": "列表",
    "Locked": "已锁定",
    "Login": "登录",
    "Log": "日志",
    "Logs": "日志",
    "Macro": "宏",
    "Mapping": "映射",
    "Mappings": "映射",
    "Max": "最大",
    "Memory": "记忆",
    "Media": "媒体",
    "Message": "消息",
    "Messages": "消息",
    "Metadata": "元数据",
    "Micro": "微",
    "Min": "最小",
    "Mode": "模式",
    "Model": "模型",
    "Modified": "已修改",
    "Monthly": "月",
    "Month": "月",
    "Msg": "消息",
    "Muted": "已静音",
    "Name": "名称",
    "Number": "号码",
    "New": "新增",
    "Next": "下一次",
    "Nickname": "昵称",
    "No": "无",
    "Notification": "通知",
    "Object": "对象",
    "Old": "旧",
    "Operation": "操作",
    "Order": "顺序",
    "Original": "原始",
    "Override": "覆盖",
    "Outbox": "出箱",
    "Outbound": "出站",
    "Owner": "拥有者",
    "Parallel": "并行",
    "Parameters": "参数",
    "Params": "参数",
    "Payload": "载荷",
    "Password": "密码",
    "Penalty": "惩罚",
    "Pending": "待处理",
    "Persona": "人设",
    "Personas": "人设",
    "Personalities": "人格",
    "Personality": "人格",
    "Phone": "手机号",
    "Pinned": "置顶",
    "Placeholder": "占位符",
    "Placeholders": "占位符",
    "Platform": "平台",
    "Position": "位置",
    "Presence": "在线状态",
    "Priority": "优先级",
    "Probability": "概率",
    "Profile": "资料",
    "Prompt": "提示词",
    "Provider": "提供方",
    "Public": "公开",
    "Pull": "拉取",
    "Qiao": "Qiao",
    "Query": "查询",
    "Queue": "队列",
    "Reason": "原因",
    "Reasoning": "推理",
    "both": "全部",
    "Reward": "奖励",
    "Rewards": "奖励",
    "Beneficiary": "受益人",
    "Ledger": "账本",
    "Idempotency": "幂等",
    "Effective": "生效",
    "Applies": "发放记录",
    "Apply": "发放",
    "Redeem": "兑换",
    "Records": "记录",
    "Reply": "回复",
    "Record": "记录",
    "Refreshed": "刷新",
    "Refresh": "刷新",
    "Reference": "引用",
    "Region": "地域",
    "Relationships": "关系",
    "Request": "请求",
    "request": "请求",
    "Requests": "请求",
    "Required": "必填",
    "Response": "响应",
    "Reusable": "可复用",
    "Review": "审核",
    "Reviewer": "审核者",
    "Revoked": "已撤销",
    "Risk": "风险",
    "Restriction": "限制",
    "Relationship": "关系",
    "Result": "结果",
    "Retry": "重试",
    "Role": "角色",
    "Runtime": "运行态",
    "Scope": "作用域",
    "Save": "保存",
    "Schema": "结构",
    "Score": "分数",
    "Search": "搜索",
    "seconds": "秒",
    "Seen": "已看到",
    "Single": "单次",
    "Security": "安全",
    "Sent": "发送",
    "Server": "服务端",
    "Settings": "设置",
    "Size": "大小",
    "Snapshot": "快照",
    "Source": "来源",
    "Square": "广场",
    "Start": "开始",
    "State": "状态",
    "Status": "状态",
    "Storage": "存储",
    "Style": "风格",
    "Strategy": "策略",
    "Stats": "统计",
    "Stop": "停止",
    "Subscriptions": "订阅",
    "Supports": "支持",
    "Streaming": "流式",
    "Suspension": "封禁",
    "System": "系统",
    "Tags": "标签",
    "Template": "模板",
    "Templates": "模板",
    "Temperature": "温度",
    "Test": "测试",
    "test": "测试",
    "Text": "文本",
    "Thinking": "思考",
    "Time": "时间",
    "Timezone": "时区",
    "Timer": "定时器",
    "Timeout": "超时",
    "Trigger": "触发",
    "To": "目标",
    "Token": "令牌",
    "Tokens": "令牌",
    "Top": "最高",
    "Tools": "工具",
    "Tool": "工具",
    "Total": "总",
    "Turn": "轮次",
    "Type": "类型",
    "Types": "类型",
    "UID": "UID",
    "UnionID": "UnionID",
    "Updated": "更新",
    "Uploaded": "上传",
    "Uploader": "上传者",
    "User": "用户",
    "Username": "用户名",
    "Users": "用户",
    "Value": "值",
    "Values": "值",
    "Variable": "变量",
    "Verification": "验证",
    "Verify": "校验",
    "Version": "版本",
    "Verified": "已验证",
    "Violation": "违规",
    "Violations": "违规",
    "Wake": "唤醒",
    "Warning": "警告",
    "Week": "周",
    "Weekly": "周",
    "Typing": "输入",
    "Speed": "速度",
    "Notes": "说明",
    "Remark": "描述",
    "Sequences": "序列",
    "Severity": "严重性",
    "Target": "目标",
    "Window": "窗口",
}


def admin_text(text: str) -> str:
    """Resolve admin text by current locale without mixed-language output."""
    zh, en = _ADMIN_TEXT_MAP.get(text, ("", text))
    locale = get_locale() or ""
    if locale.startswith("en"):
        return en
    if zh:
        return zh
    return _auto_translate(text)


def _auto_translate(text: str) -> str:
    """Apply lightweight token-based translation for unknown labels."""
    if not text or not isinstance(text, str):
        return text
    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
        return text

    segments = re.findall(r"[A-Za-z]+|\d+|[^A-Za-z\d]+", text)
    translated_parts: list[str] = []
    for segment in segments:
        if segment.isalpha():
            translated_parts.append(_translate_word(segment))
        else:
            translated_parts.append(segment)

    result = "".join(translated_parts)
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", result)


def _translate_word(word: str) -> str:
    """Translate alpha token and handle common plural forms."""
    translated = _WORD_MAP.get(word) or _WORD_MAP.get(word.lower())
    if translated:
        return translated

    if word.endswith("ies") and len(word) > _MIN_PLURAL_IES_WORD_LEN:
        singular = word[:-_PLURAL_IES_SUFFIX_LEN] + "y"
        translated = _WORD_MAP.get(singular)
        if translated:
            return translated

    if word.endswith("s") and len(word) > _MIN_PLURAL_S_WORD_LEN:
        singular = word[:-1]
        translated = _WORD_MAP.get(singular)
        if translated:
            return translated

    return word


def _resolve_locale_text(zh_en: tuple[str, str]) -> str:
    zh, en = zh_en
    locale = get_locale() or ""
    if locale.startswith("en"):
        return en
    return zh or en


def _snake_to_title(text: str) -> str:
    special_words = {
        "ip": "IP",
        "id": "ID",
        "ai": "AI",
        "api": "API",
        "url": "URL",
        "json": "JSON",
        "ips": "IPs",
        "ids": "IDs",
        "html": "HTML",
        "css": "CSS",
        "sql": "SQL",
        "http": "HTTP",
        "https": "HTTPS",
        "ssl": "SSL",
        "jwt": "JWT",
        "oauth": "OAuth",
        "sms": "SMS",
        "ttl": "TTL",
        "ws": "WS",
        "ms": "MS",
        "llm": "LLM",
        "cdn": "CDN",
    }
    words = [part for part in text.strip().split("_") if part]
    if not words:
        return text
    normalized_words: list[str] = []
    for word in words:
        mapped = special_words.get(word.lower())
        normalized_words.append(mapped if mapped else word.capitalize())
    return " ".join(normalized_words)


def admin_config_group_title(group_key: str) -> str:
    """Return localized config group title for admin settings pages."""
    mapping = _CONFIG_GROUP_TEXT_MAP.get(group_key)
    if mapping is not None:
        return _resolve_locale_text(mapping)
    return admin_text(_snake_to_title(group_key))


def admin_config_display_name(config_key: str) -> str:
    """Return localized display name for one config key."""
    mapping = _CONFIG_KEY_TEXT_MAP.get(config_key)
    if mapping is not None:
        return _resolve_locale_text(mapping)
    return admin_text(_snake_to_title(config_key))


def admin_config_description(config_key: str, fallback_description: str | None) -> str:
    """Return localized config description with fallback text support."""
    mapping = _CONFIG_DESCRIPTION_TEXT_MAP.get(config_key)
    if mapping is not None:
        return _resolve_locale_text(mapping)
    if not fallback_description:
        return ""
    return admin_text(fallback_description)


def translate_labels(value: object) -> object:
    """Recursively translate `label` fields in model/view payloads."""
    if isinstance(value, dict):
        translated: dict[object, object] = {}
        for key, item in value.items():
            if key == "label" and isinstance(item, str):
                translated[key] = admin_text(item)
            else:
                translated[key] = translate_labels(item)
        return translated
    if isinstance(value, list):
        return [translate_labels(item) for item in value]
    return value


def build_i18n_config() -> I18nConfig:
    """Build i18n config for admin interface."""
    return I18nConfig(
        default_locale="zh_Hant",
        language_cookie_name="language",
        language_header_name="Accept-Language",
        language_switcher=["zh_Hant", "en"],
    )
