"""
Pydantic schemas module.

This module imports all Pydantic schemas for API request/response validation
and serialization.
"""

# Common schemas
from .common import (
    BaseResponse,
    ErrorResponse,
    PaginationParams,
    PaginatedResponse,
    SuccessResponse,
    IDResponse,
    BaseSchema,
)

# User schemas
from .user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    TokenCreate,
    TokenResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    ChangePasswordRequest,
    ResetPasswordRequest,
    ConfirmResetPasswordRequest,
)

# Contact schemas
from .contact import (
    ContactBase,
    ContactCreate,
    ContactUpdate,
    ContactResponse,
    ContactListResponse,
    ContactInfoBase,
    ConversationInfoResponse,
    ContactRequestBase,
    ContactRequestCreate,
    ContactRequestResponse,
    ContactRequestUpdate,
    ContactSearchRequest,
    ContactSearchResult,
    BatchContactUpdate,
    BatchContactDelete,
)

# Message schemas
from .message import (
    MediaFileBase,
    MediaFileUpload,
    MediaFileResponse,
)

# AI schemas
from .ai import (
    AIInstanceBase,
    AIInstanceCreate,
    AIInstanceUpdate,
    AIInstanceResponse,
    AIInstanceListResponse,
    AIStyleBase,
    AIStyleCreate,
    AIStyleResponse,
    AIPersonalityBase,
    AIPersonalityCreate,
    AIPersonalityResponse,
    AIRequestLogBase,
    AIRequestLogCreate,
    AIRequestLogResponse,
    AIChatRequest,
    AIChatResponse,
    BatchAIInstanceDelete,
)

# Admin schemas
from .admin import (
    AdminUserBase,
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserResponse,
    AdminUserListResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminChangePasswordRequest,
    AdminOperationLogBase,
    AdminOperationLogCreate,
    AdminOperationLogResponse,
    AdminLoginLogResponse,
    AdminDashboardStats,
    AdminSystemInfo,
    BatchAdminUserUpdate,
)

# System schemas
from .system import (
    SystemConfigBase,
    SystemConfigCreate,
    SystemConfigUpdate,
    SystemConfigResponse,
    SystemConfigListResponse,
    ConfigValueResponse,
    BatchConfigUpdate,
    BatchConfigDelete,
    DashboardStats,
    SystemHealthStats,
)

# Export all schemas
__all__ = [
    # Common
    "BaseResponse",
    "ErrorResponse",
    "PaginationParams",
    "PaginatedResponse",
    "SuccessResponse",
    "IDResponse",
    "BaseSchema",
    # User
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    "TokenCreate",
    "TokenResponse",
    "LoginRequest",
    "LoginResponse",
    "LogoutRequest",
    "ChangePasswordRequest",
    "ResetPasswordRequest",
    "ConfirmResetPasswordRequest",
    # Contact
    "ContactBase",
    "ContactCreate",
    "ContactUpdate",
    "ContactResponse",
    "ContactListResponse",
    "ContactInfoBase",
    "ConversationInfoResponse",
    "ContactRequestBase",
    "ContactRequestCreate",
    "ContactRequestResponse",
    "ContactRequestUpdate",
    "ContactSearchRequest",
    "ContactSearchResult",
    "BatchContactUpdate",
    "BatchContactDelete",
    # Message
    "MediaFileBase",
    "MediaFileUpload",
    "MediaFileResponse",
    # AI
    "AIInstanceBase",
    "AIInstanceCreate",
    "AIInstanceUpdate",
    "AIInstanceResponse",
    "AIInstanceListResponse",
    "AIStyleBase",
    "AIStyleCreate",
    "AIStyleResponse",
    "AIPersonalityBase",
    "AIPersonalityCreate",
    "AIPersonalityResponse",
    "AIRequestLogBase",
    "AIRequestLogCreate",
    "AIRequestLogResponse",
    "AIChatRequest",
    "AIChatResponse",
    "BatchAIInstanceDelete",
    # Admin
    "AdminUserBase",
    "AdminUserCreate",
    "AdminUserUpdate",
    "AdminUserResponse",
    "AdminUserListResponse",
    "AdminLoginRequest",
    "AdminLoginResponse",
    "AdminChangePasswordRequest",
    "AdminOperationLogBase",
    "AdminOperationLogCreate",
    "AdminOperationLogResponse",
    "AdminLoginLogResponse",
    "AdminDashboardStats",
    "AdminSystemInfo",
    "BatchAdminUserUpdate",
    # System
    "SystemConfigBase",
    "SystemConfigCreate",
    "SystemConfigUpdate",
    "SystemConfigResponse",
    "SystemConfigListResponse",
    "ConfigValueResponse",
    "BatchConfigUpdate",
    "BatchConfigDelete",
    "DashboardStats",
    "SystemHealthStats",
]
