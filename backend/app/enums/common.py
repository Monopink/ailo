"""
Common enumeration definitions for database fields.

All enum values correspond to the integer values defined in the database schema.
These enums ensure type safety and consistency across the application.
"""

from enum import Enum, IntEnum

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

    IOS = 1
    ANDROID = 2
    WEB = 3
    MINI_PROGRAM = 4


class LoginType(IntEnum):
    """Login method (login_records.login_type)"""

    PASSWORD = 1
    SMS = 2
    WECHAT = 3
    APPLE = 4


class AuthType(IntEnum):
    """Third-party identity provider type (user_auths.auth_type)."""

    APPLE = 1
    QQ = 2
    WECHAT = 3


class LoginResult(IntEnum):
    """Login attempt result (login_records.result)"""

    SUCCESS = 1
    FAIL = 2


# Contact Management Related Enums


class ContactType(IntEnum):
    """Contact type classification (contacts.contact_type)"""

    USER = 1
    AI = 2  # AI instance
    OFFICIAL = 3


class ContactRequestSource(IntEnum):
    """Contact request source (contact_requests.source)"""

    SEARCH = 1
    ADMIN = 2
    SYSTEM = 3
    RECOMMEND = 4


class ContactRequestStatus(IntEnum):
    """Contact request status (contact_requests.status)"""

    PENDING = 1
    ACCEPTED = 2
    IGNORED = 3  # Ignored (AI decided not to accept, or user actively ignored)
    PROCESSING = 8  # Processing by worker (prevents duplicate processing)
    FAILED = 9  # Processing failed due to system error  # Processing by worker (prevents duplicate processing)  # Rejected (future: explicit rejection with notification)


class ContactRequestFailureCode(str, Enum):
    """Contact request failure codes (contact_requests.failure_code)"""

    NO_TEMPLATE_AVAILABLE = "NO_TEMPLATE_AVAILABLE"
    MANUAL_PROVISION_REQUIRED = "MANUAL_PROVISION_REQUIRED"


class SquareEntryStatus(IntEnum):
    """Square exposure status (square_type_entries.status)"""

    ACTIVE = 1
    INACTIVE = 2


# Message System Related Enums


class MessageDirection(IntEnum):
    """Message direction (message_history.direction)"""

    INBOUND = 1
    OUTBOUND = 2


class MessageParticipantType(IntEnum):
    """Message sender/receiver type"""

    USER = 1
    AI = 2  # AI instance
    ADMIN = 3
    SYSTEM = 4


class ServiceProvider(IntEnum):
    """Message service provider (message_history.service_provider)"""

    INTERNAL = 1  # Internal system (Reserved for the future)
    LEANCLOUD = 2  # LeanCloud im service


class MessageType(IntEnum):
    """Message type classification (message_history.message_type)"""

    TEXT = 1
    TYPING_START = 2  # Typing indicator (user started typing)
    TYPING_END = 3  # Typing stopped indicator
    CHAT_INFO = 4  # Chat interface informational message
    NOTIFICATION = 9


class ChatInfoType(IntEnum):
    """Chat interface informational message subtypes"""

    CONTACT_ADDED = 1  # Contact has added you
    MESSAGE_BLOCKED = 2  # Message sent but blocked by recipient
    NOT_FRIEND = 3  # Recipient hasn't added you as contact


class NotificationType(IntEnum):
    """Notification message subtypes"""

    CONTACT_REQUEST = 1


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

    SENT = 1
    FAILED = 2


class MessageStatus(IntEnum):
    """Message delivery status (message_history.status)"""

    SENT = 1
    DELIVERED = 2
    READ = 3
    FAILED = 4


class EncryptionType(str, Enum):
    """Supported message encryption algorithms."""

    BASE64 = "base64"
    AES_256_GCM = "aes_256_gcm"


class EncryptionVersion(str, Enum):
    """Encryption schema version."""

    V1 = "v1"


# Media Files Related Enums


class FileType(IntEnum):
    """Media file type classification (media_files.file_type)"""

    AVATAR = 1
    EMOJI = 2
    IMAGE = 3
    DOCUMENT = 4


class FileStatus(IntEnum):
    """Media file status (media_files.status)"""

    ACTIVE = 1
    INACTIVE = 2
    DELETED = 3


class UploaderType(IntEnum):
    """File uploader type (media_files.upload_by_type)"""

    USER = 1
    ADMIN = 2
    SYSTEM = 3


# Profile Management Related Enums


class Gender(IntEnum):
    """Gender classification (profiles.gender)"""

    MALE = 1
    FEMALE = 2
    OTHER = 3


class ProfileOwnerType(IntEnum):
    """Profile owner type (profiles.owner_type)

    Note: All user types (normal, official, virtual) use owner_type=1 (USER).
    The user_type field in users table distinguishes between them.
    """

    USER = 1  # User profile (includes normal, official, virtual users)
    AI_PERSONA = 2  # AI persona profile (shared by instances created from this persona)
    AI_INSTANCE = 3  # AI instance profile (only for manually created instances)


class ProfileModifierType(IntEnum):
    """Profile modifier type (user_profile_logs.modified_by_type)"""

    USER = 1
    ADMIN = 2
    SYSTEM = 3


# Emoticons Related Enums - Removed (emoticons table renamed to preset_assets)


# AI System Related Enums


class SquareCategory(IntEnum):
    """Square discovery category (square_type_entries.square_category)."""

    FRIEND = 1  # 交友
    LOVE = 2  # 恋爱
    TALK = 3  # 倾诉
    BESTIE = 4  # 闺蜜
    HOBBY = 5  # 同好


class ExposureStrategy(IntEnum):
    """Square exposure strategy (square_type_entries.exposure_strategy)."""

    RANDOM = 1  # Randomized ordering (default). Other strategies are not supported yet.


class AITemplateStatus(IntEnum):
    """AI template status (ai_templates.status)"""

    ACTIVE = 1
    INACTIVE = 2
    USED = 3


class AIInstanceStatus(IntEnum):
    """AI instance status (ai_instances.status)"""

    ACTIVE = 1
    INACTIVE = 2
    BLOCKED = 3


class AIStyleStatus(IntEnum):
    """AI style status (ai_styles.status)"""

    ACTIVE = 1
    INACTIVE = 2


class AIPersonaStatus(IntEnum):
    """AI persona status (ai_personas.status)"""

    ACTIVE = 1
    INACTIVE = 2
    USED = 3


class AIPersonalityStatus(IntEnum):
    """AI personality status (ai_personalities.status)"""

    ACTIVE = 1
    INACTIVE = 2


class AIRelationshipStatus(IntEnum):
    """AI relationship status (ai_relationships.status)"""

    ACTIVE = 1
    INACTIVE = 2


class AIMessageBufferState(IntEnum):
    """Message buffer aggregate state (ai_message_buffer.aggregate_state)"""

    WAITING_WAKEUP = 0  # Waiting to finish wake timer before aggregation
    OPEN = 1  # Waiting for merge/timer
    LOCKED = 2  # Processing (only one per conversation)
    COMPLETE = 3  # Processing completed
    CANCELLED = 4  # Preempted by new window or explicitly terminated


class AIInstanceCreator(IntEnum):
    """AI instance creator type (ai_instances.created_by)"""

    USER = 1
    ADMIN = 2
    SYSTEM = 3


class ConversationRole(str, Enum):
    """Conversation role type (ai_conversation_items.role)"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ConversationItemContextStatus(IntEnum):
    """Conversation item context inclusion status (ai_conversation_items.is_excluded_from_context)"""

    INCLUDED = 0  # Included in LLM context
    EXCLUDED = 1  # Excluded from LLM context (prompt injection, etc.)


class AIRequestStatus(IntEnum):
    """AI request status (ai_request_logs.status)"""

    SUCCESS = 1
    FAILED = 2
    TIMEOUT = 3


class PositionMappingAlgorithm(IntEnum):
    """Position mapping algorithm type (ai_instance_dimensions.position_mapping_algorithm, etc.)

    Maps LLM output score to final position value with optional offset adjustments.
    """

    NONE = 1  # No algorithm - direct score mapping (直接映射)
    V1 = 2  # Version 1 algorithm


class LLMRequestStatus(IntEnum):
    """LLM request status (llm_request_logs.status)"""

    PENDING = 1
    SUCCESS = 2
    ERROR = 3


class RequiredStatus(IntEnum):
    """Required status for placeholders and fields"""

    OPTIONAL = 0
    REQUIRED = 1


class ReusableStatus(IntEnum):
    """Reusable status for templates"""

    SINGLE_USE = 0
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

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AutoAction(IntEnum):
    """Automatic action taken (user_violation_logs.auto_action_taken)"""

    NONE = 1
    WARNING = 2
    RESTRICT = 3
    SUSPEND = 4


class ManualReviewStatus(IntEnum):
    """Manual review status (user_violation_logs.manual_review_status)"""

    PENDING = 1  # Pending review
    CONFIRMED = 2  # Violation confirmed
    FALSE_POSITIVE = 3
    IGNORED = 4


class RiskLevel(IntEnum):
    """User risk level (user_risk_stats.current_risk_level)"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    BANNED = 4


# System Configuration Related Enums


class ConfigType(IntEnum):
    """Configuration value type (system_configs.config_type)"""

    STRING = 1
    NUMBER = 2
    BOOLEAN = 3
    JSON = 4
    ENUM = 5  # Select from allowed_values


# Admin System Related Enums


class AdminRole(IntEnum):
    """Administrator role (admin_users.role)"""

    SUPER_ADMIN = 1
    ADMIN = 2
    VIEWER = 3  # Read-only


class AdminStatus(IntEnum):
    """Administrator status (admin_users.status)"""

    ACTIVE = 1
    INACTIVE = 2


class AdminOperationType(IntEnum):
    """Admin operation type (admin_operation_logs.operation_type)"""

    CREATE = 1
    UPDATE = 2
    DELETE = 3
    ENABLE = 4
    DISABLE = 5
    REFRESH = 6  # E.g., refresh system conversation
    QUERY = 7  # For sensitive queries only
    EXECUTE = 8  # E.g., execute test
    EXPORT = 9
    IMPORT = 10


class AdminLoginResult(IntEnum):
    """Admin login result (admin_login_logs.result)"""

    SUCCESS = 1
    FAIL = 2


# LLM Service Related Enums


class LLMTestStatus(IntEnum):
    """LLM test execution status (llm_test_logs.status)"""

    SUCCESS = 1
    FAILED = 2
    TIMEOUT = 3


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
