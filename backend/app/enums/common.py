"""
Common enumeration definitions for database fields.

All enum values correspond to the integer values defined in the database schema.
These enums ensure type safety and consistency across the application.
"""

from enum import IntEnum, Enum


# User Management Related Enums


class UserStatus(IntEnum):
    """User account status (users.status)"""

    ACTIVE = 1  # Normal active user
    DEACTIVATED = 2  # Account deactivated (user-initiated)
    SUSPENDED = 3  # Account suspended (admin-initiated)


class UserType(IntEnum):
    """User type classification (users.user_type).

    Design document standard: 1=normal, 2=official, 3=virtual (test/virtual user)
    """

    NORMAL = 1  # Regular user
    OFFICIAL = 2  # Official account
    VIRTUAL = 3  # Virtual user (for AI testing)


class DeviceType(IntEnum):
    """Device type for sessions and login records"""

    IOS = 1  # iOS device
    ANDROID = 2  # Android device
    WEB = 3  # Web browser
    MINI_PROGRAM = 4  # Mini program


class LoginType(IntEnum):
    """Login method (login_records.login_type)"""

    PASSWORD = 1  # Password login
    SMS = 2  # SMS verification code
    WECHAT = 3  # WeChat login
    APPLE = 4  # Apple ID login


class AuthType(IntEnum):
    """Third-party identity provider type (user_auths.auth_type)."""

    APPLE = 1
    QQ = 2
    WECHAT = 3


class LoginResult(IntEnum):
    """Login attempt result (login_records.result)"""

    SUCCESS = 1  # Login successful
    FAIL = 2  # Login failed


# Contact Management Related Enums


class ContactType(IntEnum):
    """Contact type classification (contacts.contact_type)"""

    USER = 1  # User contact
    AI = 2  # AI character
    OFFICIAL = 3  # Official account


class ContactRequestSource(IntEnum):
    """Contact request source (contact_requests.source)"""

    SEARCH = 1  # Added through search
    ADMIN = 2  # Added by admin
    SYSTEM = 3  # Added by system
    RECOMMEND = 4  # Added through recommendation


class ContactRequestStatus(IntEnum):
    """Contact request status (contact_requests.status)"""

    PENDING = 1  # Pending approval
    ACCEPTED = 2  # Accepted
    IGNORED = 3  # Ignored (AI decided not to accept, or user actively ignored)
    PROCESSING = 8  # Processing by worker (prevents duplicate processing)
    FAILED = 9  # Processing failed due to system error  # Processing by worker (prevents duplicate processing)  # Rejected (future: explicit rejection with notification)


# Message System Related Enums


class MessageDirection(IntEnum):
    """Message direction (message_history.direction)"""

    INBOUND = 1  # Incoming message
    OUTBOUND = 2  # Outgoing message


class MessageParticipantType(IntEnum):
    """Message sender/receiver type"""

    USER = 1  # User
    AI = 2  # AI character
    ADMIN = 3  # Administrator
    SYSTEM = 4  # System


class ServiceProvider(IntEnum):
    """Message service provider (message_history.service_provider)"""

    INTERNAL = 1  # Internal system
    LEANCLOUD = 2  # LeanCloud service


class MessageType(IntEnum):
    """Message type classification (message_history.message_type)"""

    TEXT = 1  # Text message
    TYPING = 2  # Typing indicator
    TYPING_END = 3  # Typing end indicator
    CHAT_INFO = 4  # Chat interface informational message
    NOTIFICATION = 9  # Notification message


class ChatInfoType(IntEnum):
    """Chat interface informational message subtypes"""

    CONTACT_ADDED = 1  # Contact has added you
    MESSAGE_BLOCKED = 2  # Message sent but blocked by recipient
    NOT_FRIEND = 3  # Recipient hasn't added you as contact


class NotificationType(IntEnum):
    """Notification message subtypes"""

    CONTACT_REQUEST = 1  # Contact request notification


class NotificationActionType(str, Enum):
    """Notification action types"""

    NAVIGATE = "navigate"  # Navigate to a page
    REFRESH = "refresh"  # Refresh data
    BADGE = "badge"  # Update badge count


class NotificationTarget(str, Enum):
    """Notification action targets"""

    CONTACT_REQUESTS = "contact_requests"  # Contact requests page
    CONTACTS = "contacts"  # Contacts list page


class NotificationStatus(IntEnum):
    """Notification push status"""

    SENT = 1  # Sent successfully
    FAILED = 2  # Send failed


class MessageStatus(IntEnum):
    """Message delivery status (message_history.status)"""

    SENT = 1  # Message sent
    DELIVERED = 2  # Message delivered
    READ = 3  # Message read
    FAILED = 4  # Message failed


# Media Files Related Enums


class FileType(IntEnum):
    """Media file type classification (media_files.file_type)"""

    AVATAR = 1  # Avatar image
    EMOJI = 2  # Emoji/emoticon
    IMAGE = 3  # General image
    DOCUMENT = 4  # Document file


class FileStatus(IntEnum):
    """Media file status (media_files.status)"""

    ACTIVE = 1  # Active file
    INACTIVE = 2  # Inactive file
    DELETED = 3  # Deleted file


class UploaderType(IntEnum):
    """File uploader type (media_files.upload_by_type)"""

    USER = 1  # Uploaded by user
    ADMIN = 2  # Uploaded by admin
    SYSTEM = 3  # Uploaded by system


# Profile Management Related Enums


class Gender(IntEnum):
    """Gender classification (profiles.gender)"""

    MALE = 1  # Male
    FEMALE = 2  # Female
    OTHER = 3  # Other
    UNKNOWN = 4  # Unknown/not specified


class ProfileOwnerType(IntEnum):
    """Profile owner type (profiles.owner_type)

    Note: All user types (normal, official, virtual) use owner_type=1 (USER).
    The user_type field in users table distinguishes between them.
    """

    USER = 1  # User profile (includes normal, official, virtual users)
    AI = 2  # AI character profile


class ProfileModifierType(IntEnum):
    """Profile modifier type (user_profile_logs.modified_by_type)"""

    USER = 1  # Modified by user
    ADMIN = 2  # Modified by admin
    SYSTEM = 3  # Modified by system


# Emoticons Related Enums - Removed (emoticons table renamed to preset_assets)


# AI System Related Enums


class AIProfileCategory(IntEnum):
    """AI profile template category (ai_profile_templates.category)

    Stored as string in VARCHAR field for flexibility.
    """

    FRIEND = 1  # 交友
    LOVE = 2  # 恋爱
    TALK = 3  # 倾诉
    BESTIE = 4  # 闺蜜
    HOBBY = 5  # 同好


# Profile category conversion mapping between API (integer) and DB (string)
PROFILE_CATEGORY_API_TO_DB = {
    AIProfileCategory.FRIEND: "friend",
    AIProfileCategory.LOVE: "love",
    AIProfileCategory.TALK: "talk",
    AIProfileCategory.BESTIE: "bestie",
    AIProfileCategory.HOBBY: "hobby",
}

PROFILE_CATEGORY_DB_TO_API = {v: k for k, v in PROFILE_CATEGORY_API_TO_DB.items()}


class AICharacterStatus(IntEnum):
    """AI character status (ai_characters.status)"""

    ACTIVE = 1  # Active character
    INACTIVE = 2  # Inactive character
    BLOCKED = 3  # Blocked character


class AIStyleStatus(IntEnum):
    """AI style status (ai_styles.status)"""

    ACTIVE = 1  # Active style
    INACTIVE = 2  # Inactive style


class AIPersonalityStatus(IntEnum):
    """AI personality status (ai_personalities.status)"""

    ACTIVE = 1  # Active personality
    INACTIVE = 2  # Inactive personality


class AIRelationshipStatus(IntEnum):
    """AI relationship status (ai_relationships.status)"""

    ACTIVE = 1  # Active relationship
    INACTIVE = 2  # Inactive relationship


class AIAggregateState(IntEnum):
    """AI context aggregate state (ai_contexts.aggregate_state)"""

    OPEN = 1  # Waiting for merge/timer
    LOCKED = 2  # Processing (only one per conversation)
    COMPLETE = 3  # Processing completed
    CANCELLED = 4  # Preempted by new window or explicitly terminated


class AICharacterCreator(IntEnum):
    """AI character creator type (ai_characters.created_by)"""

    USER = 1  # Created by user
    ADMIN = 2  # Created by admin
    SYSTEM = 3  # Created by system


class AIContextRole(IntEnum):
    """AI context role type (ai_contexts.role)"""

    SYSTEM = 1  # System message
    USER = 2  # User message
    ASSISTANT = 3  # Assistant response


class AIRequestStatus(IntEnum):
    """AI request status (ai_request_logs.status)"""

    SUCCESS = 1  # Request successful
    FAILED = 2  # Request failed
    TIMEOUT = 3  # Request timeout


class PositionMappingAlgorithm(IntEnum):
    """Position mapping algorithm type (ai_character_dimensions.position_mapping_algorithm, etc.)

    Maps LLM output score to final position value with optional offset adjustments.
    """

    NONE = 1  # No algorithm - direct score mapping (直接映射)
    V1 = 2  # Version 1 algorithm


class LLMRequestStatus(IntEnum):
    """LLM request status (llm_request_logs.status)"""

    PENDING = 1  # Request pending
    SUCCESS = 2  # Request successful
    ERROR = 3  # Request failed with error


class RequiredStatus(IntEnum):
    """Required status for placeholders and fields"""

    OPTIONAL = 0  # Optional field
    REQUIRED = 1  # Required field


class ReusableStatus(IntEnum):
    """Reusable status for templates"""

    SINGLE_USE = 0  # Single use only
    REUSABLE = 1  # Can be reused


# Security Related Enums


class ViolationType(IntEnum):
    """Security violation type (user_violation_logs.violation_type)"""

    PROMPT_INJECTION = 1  # Prompt injection attack
    ABUSE_CONTENT = 2  # Abusive content
    SPAM = 3  # Spam message
    HARASSMENT = 4  # Harassment behavior
    OTHER = 5  # Other violation


class SeverityLevel(IntEnum):
    """Violation severity level (user_violation_logs.severity_level)"""

    LOW = 1  # Low severity
    MEDIUM = 2  # Medium severity
    HIGH = 3  # High severity
    CRITICAL = 4  # Critical severity


class AutoAction(IntEnum):
    """Automatic action taken (user_violation_logs.auto_action_taken)"""

    NONE = 1  # No action
    WARNING = 2  # Warning issued
    RESTRICT = 3  # Account restricted
    SUSPEND = 4  # Account suspended


class ManualReviewStatus(IntEnum):
    """Manual review status (user_violation_logs.manual_review_status)"""

    PENDING = 1  # Pending review
    CONFIRMED = 2  # Violation confirmed
    FALSE_POSITIVE = 3  # False positive
    IGNORED = 4  # Ignored


class RiskLevel(IntEnum):
    """User risk level (user_risk_stats.current_risk_level)"""

    LOW = 1  # Low risk
    MEDIUM = 2  # Medium risk
    HIGH = 3  # High risk
    BANNED = 4  # Banned user


# System Configuration Related Enums


class ConfigType(IntEnum):
    """Configuration value type (system_configs.config_type)"""

    STRING = 1  # String value
    NUMBER = 2  # Numeric value
    BOOLEAN = 3  # Boolean value
    JSON = 4  # JSON object
    ENUM = 5  # Enum value (select from allowed_values)


# Admin System Related Enums


class AdminRole(IntEnum):
    """Administrator role (admin_users.role)"""

    SUPER_ADMIN = 1  # Super administrator
    ADMIN = 2  # Administrator
    VIEWER = 3  # Viewer (read-only)


class AdminStatus(IntEnum):
    """Administrator status (admin_users.status)"""

    ACTIVE = 1  # Active admin
    INACTIVE = 2  # Inactive admin


class AdminOperationType(IntEnum):
    """Admin operation type (admin_operation_logs.operation_type)"""

    CREATE = 1  # Create resource
    UPDATE = 2  # Update resource
    DELETE = 3  # Delete resource
    ENABLE = 4  # Enable resource
    DISABLE = 5  # Disable resource
    REFRESH = 6  # Refresh operation (e.g., refresh system conversation)
    QUERY = 7  # Query operation (for sensitive queries only)
    EXECUTE = 8  # Execute operation (e.g., execute test)
    EXPORT = 9  # Export operation
    IMPORT = 10  # Import operation


class AdminLoginResult(IntEnum):
    """Admin login result (admin_login_logs.result)"""

    SUCCESS = 1  # Login successful
    FAIL = 2  # Login failed


# LLM Service Related Enums


class LLMTestStatus(IntEnum):
    """LLM test execution status (llm_test_logs.status)"""

    SUCCESS = 1  # Test successful
    FAILED = 2  # Test failed
    TIMEOUT = 3  # Test timeout


class LLMErrorCode(IntEnum):
    """LLM error code classification"""

    UNKNOWN = 0  # Unknown error
    ENDPOINT_NOT_FOUND = 1  # 404: Endpoint not found
    AUTHENTICATION_ERROR = 2  # 401: Invalid API Key
    RATE_LIMIT_EXCEEDED = 3  # 429: Rate limit exceeded
    SERVER_ERROR = 4  # 5xx: Server error
    TIMEOUT = 5  # Request timeout
    NETWORK_ERROR = 6  # Network connection failed
    CONFIGURATION_ERROR = 7  # Configuration error
    NO_CONFIG = 8  # No available configuration
