"""
Custom authentication provider for Starlette-Admin.
"""

from typing import Optional
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette_admin.auth import AdminConfig, AdminUser, AuthProvider
from starlette_admin.exceptions import FormValidationError, LoginFailed

from core.database import SessionLocal
from crud.admin import admin_user as admin_user_crud
from utils.admin_logs import create_login_log
from core.security import verify_password
from utils.logging import get_logger

logger = get_logger(__name__)


class CustomAuthProvider(AuthProvider):
    """
    Custom authentication provider using session-based authentication.
    """

    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        """
        Handle admin login.
        """
        async with SessionLocal() as db:
            try:
                # Find admin user
                admin_user = await admin_user_crud.get_by_username(db, username=username)

                if not admin_user:
                    # Log failed login attempt
                    await create_login_log(
                        db=db,
                        username=username,
                        result=2,  # Failed
                        fail_reason="用户不存在",
                        request=request,
                    )
                    raise LoginFailed("用户名或密码错误")

                # Verify password
                if not verify_password(password, admin_user.password_hash):
                    # Log failed login attempt
                    await create_login_log(
                        db=db,
                        username=username,
                        result=2,  # Failed
                        admin_user_id=admin_user.id,
                        fail_reason="密码错误",
                        request=request,
                    )
                    raise LoginFailed("用户名或密码错误")

                # Check if user is active
                if not await admin_user_crud.is_active(admin_user):
                    # Log failed login attempt
                    await create_login_log(
                        db=db,
                        username=username,
                        result=2,  # Failed
                        admin_user_id=admin_user.id,
                        fail_reason="账户已禁用",
                        request=request,
                    )
                    raise LoginFailed("账户已被禁用")

                # Update last login
                await admin_user_crud.update_last_login(db, user_id=admin_user.id)

                # Log successful login
                await create_login_log(
                    db=db,
                    username=username,
                    result=1,  # Success
                    admin_user_id=admin_user.id,
                    request=request,
                )

                # Store user info in session
                request.session.update(
                    {
                        "admin_user": {
                            "id": admin_user.id,
                            "username": admin_user.username,
                            "role": admin_user.role,
                            "role_display": admin_user.role_display,
                        }
                    }
                )

                logger.info("admin_login_success", username=username, user_id=admin_user.id)
                return response

            except LoginFailed:
                raise
            except Exception as e:
                logger.error("admin_login_error", username=username, error=str(e), exc_info=True)
                raise LoginFailed("登录失败，请稍后重试")

    async def is_authenticated(self, request: Request) -> bool:
        """
        Check if user is authenticated.
        """
        return request.session.get("admin_user") is not None

    def get_admin_config(self, request: Request) -> Optional[AdminConfig]:
        """
        Get admin configuration for current user.
        """
        admin_user_data = request.session.get("admin_user")
        if not admin_user_data:
            return None

        return AdminConfig(
            app_title="Qiao Dashboard",
            logo_url=None,
        )

    def get_admin_user(self, request: Request) -> Optional[AdminUser]:
        """
        Get current admin user.
        """
        admin_user_data = request.session.get("admin_user")
        if not admin_user_data:
            return None

        return AdminUser(
            username=admin_user_data["username"],
            photo_url=None,
        )

    async def logout(self, request: Request, response: Response) -> Response:
        """
        Handle admin logout.
        """
        admin_user_data = request.session.get("admin_user")
        if admin_user_data:
            logger.info("admin_logout", username=admin_user_data["username"])

        request.session.clear()
        return response

    # render_login method is not needed for basic authentication
    # Starlette-Admin will use the default login page
