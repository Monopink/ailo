"""Pydantic schemas module.

This module imports all Pydantic schemas for API request/response validation
and serialization.
"""

# Admin schemas
from .admin import (
    AdminChangePasswordRequest,
    AdminDashboardStats,
    AdminLoginLogResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminOperationLogBase,
    AdminOperationLogCreate,
    AdminOperationLogResponse,
    AdminSystemInfo,
    AdminUserBase,
    AdminUserCreate,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdate,
    BatchAdminUserUpdate,
)

# AI schemas
from .ai import (
    AIChatRequest,
    AIChatResponse,
    AIInstanceBase,
    AIInstanceCreate,
    AIInstanceListResponse,
    AIInstanceResponse,
    AIInstanceUpdate,
    AIPersonalityBase,
    AIPersonalityCreate,
    AIPersonalityResponse,
    AIRequestLogBase,
    AIRequestLogCreate,
    AIRequestLogResponse,
    AIStyleBase,
    AIStyleCreate,
    AIStyleResponse,
    BatchAIInstanceDelete,
)

# Auth schemas
from .auth import (
    RefreshTokenRequest,
    RefreshTokenResponse,
    VerifyPhoneRequest,
    VerifyPhoneResponse,
    WeChatLoginRequest,
    WeChatLoginResponse,
    WeChatRefreshPhoneRequest,
    WeChatRefreshPhoneResponse,
)

# Common schemas
from .common import (
    BaseResponse,
    BaseSchema,
    ErrorResponse,
    IDResponse,
    PaginatedResponse,
    PaginationParams,
    SuccessResponse,
)

# Contact schemas
from .contact import (
    BatchContactDelete,
    BatchContactUpdate,
    ContactCreate,
    ContactDetailResponse,
    ContactListItem,
    ContactListResult,
    ContactProfileSummary,
    ContactRequestAccept,
    ContactRequestBase,
    ContactRequestCreate,
    ContactRequestListResponse,
    ContactRequestUpdate,
    ContactRequestWithProfile,
    ContactSearchRequest,
    ContactSearchResult,
    ContactUpdate,
    ConversationInfoResponse,
)

# Message schemas
from .media import MediaAccessResponse, MediaUploadResponse
from .message import MediaFileBase, MediaFileResponse, MediaFileUpload

# System schemas
from .system import (
    BatchConfigDelete,
    BatchConfigUpdate,
    ConfigValueResponse,
    DashboardStats,
    SystemConfigBase,
    SystemConfigCreate,
    SystemConfigListResponse,
    SystemConfigResponse,
    SystemConfigUpdate,
    SystemHealthStats,
)

# User schemas
from .user import (
    ChangePasswordRequest,
    ConfirmResetPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    ResetPasswordRequest,
    TokenCreate,
    TokenResponse,
    UserBase,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
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
    "ContactCreate",
    "ContactUpdate",
    "ContactDetailResponse",
    "ContactListItem",
    "ContactListResult",
    "ContactProfileSummary",
    "ConversationInfoResponse",
    "ContactRequestBase",
    "ContactRequestCreate",
    "ContactRequestWithProfile",
    "ContactRequestUpdate",
    "ContactRequestListResponse",
    "ContactRequestAccept",
    "ContactSearchRequest",
    "ContactSearchResult",
    "BatchContactUpdate",
    "BatchContactDelete",
    # Message
    "MediaFileBase",
    "MediaFileUpload",
    "MediaFileResponse",
    # Media (Object Storage)
    "MediaAccessResponse",
    "MediaUploadResponse",
    # App content
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
    # Auth
    "WeChatLoginRequest",
    "WeChatLoginResponse",
    "WeChatRefreshPhoneRequest",
    "WeChatRefreshPhoneResponse",
    "VerifyPhoneRequest",
    "VerifyPhoneResponse",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
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
