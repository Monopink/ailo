from .auth import CredentialsSchema, JWTOut, JWTPayload
from .base import Success, Fail, SuccessExtra
from .users import (
    BaseUser,
    UserCreate,
    UserUpdate,
    AdminChangePasswordRequest,
    AdminOperationLogBase,
    AdminOperationLogCreate,
    AdminOperationLogResponse,
    AdminLoginLogResponse,
    AdminDashboardStats,
    AdminSystemInfo,
    BatchAdminUserUpdate,
)

# Aliases for backward compatibility
AdminUserBase = BaseUser
AdminUserCreate = UserCreate
AdminUserUpdate = UserUpdate
AdminUserResponse = BaseUser
AdminUserListResponse = BaseUser
AdminLoginRequest = CredentialsSchema
AdminLoginResponse = JWTOut

__all__ = [
    # Auth schemas
    "CredentialsSchema",
    "JWTOut",
    "JWTPayload",
    # Base response schemas
    "Success",
    "Fail",
    "SuccessExtra",
    # User schemas
    "BaseUser",
    "UserCreate",
    "UserUpdate",
    "AdminChangePasswordRequest",
    "AdminOperationLogBase",
    "AdminOperationLogCreate",
    "AdminOperationLogResponse",
    "AdminLoginLogResponse",
    "AdminDashboardStats",
    "AdminSystemInfo",
    "BatchAdminUserUpdate",
    # Aliases
    "AdminUserBase",
    "AdminUserCreate",
    "AdminUserUpdate",
    "AdminUserResponse",
    "AdminUserListResponse",
    "AdminLoginRequest",
    "AdminLoginResponse",
]
