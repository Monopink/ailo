"""Custom authentication provider for Starlette-Admin with security features."""

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import FormData
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.templating import Jinja2Templates
from starlette_admin import BaseAdmin
from starlette_admin.auth import AdminConfig, AdminUser, AuthProvider

from app.core.database import get_sessionmaker
from app.core.security import verify_password
from app.crud.admin import admin_user as admin_user_crud
from app.models.admin import AdminUser as AdminUserModel
from app.services.security.auth_tracker import (
    check_lockout,
    record_auth_failure,
    reset_failures,
    should_require_captcha,
)
from app.services.security.captcha.factory import create_captcha_provider
from app.services.system_config import get_config_str
from app.utils.admin_logs import create_login_log
from app.utils.client_ip import ClientIPResolutionError, get_client_ip
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Templates
templates = Jinja2Templates(directory="app/admin/templates")


class CustomAuthProvider(AuthProvider):
    """Custom authentication provider using session-based authentication."""

    async def render_login(self, request: Request, admin: BaseAdmin) -> Response:
        """Handle both GET (display form) and POST (process login) for custom login page."""
        if request.method == "GET":
            return await self._render_login_form(request, admin)
        if request.method == "POST":
            return await self._process_login(request, admin)
        return self._create_login_failure_response(request, admin)

    async def _render_login_form(self, request: Request, admin: BaseAdmin) -> Response:
        """Render the custom login template."""
        session_factory = get_sessionmaker()
        async with session_factory() as db:
            try:
                client_ip = get_client_ip(request)
            except ClientIPResolutionError as exc:
                logger.warning(
                    "admin_login_form_client_ip_invalid",
                    reason=exc.reason,
                    detail=str(exc),
                )
                return templates.TemplateResponse(
                    "login.html",
                    {
                        "request": request,
                        "admin": admin,
                        "show_captcha": False,
                        "turnstile_site_key": "",
                        "error": "Invalid request source",
                    },
                    status_code=400,
                )
            turnstile_site_key = await get_config_str(
                db,
                key="admin_turnstile_site_key",
                required=False,
                default="",
            )
            show_captcha_raw = await should_require_captcha(client_ip, "admin_auth", db)
            show_captcha = bool(turnstile_site_key) and show_captcha_raw
            error = request.query_params.get("error")
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "admin": admin,
                    "show_captcha": show_captcha,
                    "turnstile_site_key": turnstile_site_key,
                    "error": error,
                },
            )

    async def _process_login(self, request: Request, admin: BaseAdmin) -> Response:
        """Process POST login form submission."""
        session_factory = get_sessionmaker()
        async with session_factory() as db:
            try:
                client_ip = get_client_ip(request)
                form_data = await request.form()
                username = str(form_data.get("username", ""))
                password = str(form_data.get("password", ""))

                # Chain validation steps - any failure returns error response
                if error_response := await self._check_ip_lockout(
                    client_ip, username, request, admin, db
                ):
                    return error_response

                if error_response := await self._check_captcha(
                    client_ip, username, form_data, request, admin, db
                ):
                    return error_response

                if error_response := await self._verify_user_credentials(
                    username, password, client_ip, request, admin, db
                ):
                    return error_response

                # All validations passed - complete login
                return await self._complete_login(username, client_ip, request, admin, db)

            except ClientIPResolutionError as exc:
                logger.warning(
                    "admin_login_client_ip_invalid",
                    reason=exc.reason,
                    detail=str(exc),
                )
                return self._create_login_failure_response(request, admin)
            except Exception as e:
                logger.error("admin_login_unexpected_error", error=str(e), exc_info=True)
                return self._create_login_failure_response(request, admin)

    async def _check_ip_lockout(
        self,
        client_ip: str,
        username: str,
        request: Request,
        admin: BaseAdmin,
        db: AsyncSession,
    ) -> Response | None:
        """Check if IP is locked. Returns error response if locked, None otherwise."""
        is_locked, _ = await check_lockout(client_ip, "admin_auth", db)
        if is_locked:
            await create_login_log(
                db=db,
                username=username,
                result=2,
                fail_reason="ip_locked",
                request=request,
            )
            return self._create_login_failure_response(request, admin)
        return None

    async def _check_captcha(
        self,
        client_ip: str,
        username: str,
        form_data: FormData,
        request: Request,
        admin: BaseAdmin,
        db: AsyncSession,
    ) -> Response | None:
        """Verify CAPTCHA if required. Returns error response if failed, None otherwise."""
        captcha_required = await should_require_captcha(client_ip, "admin_auth", db)
        if not captcha_required:
            return None

        turnstile_token = str(form_data.get("cf_turnstile_response", ""))
        if not turnstile_token:
            await record_auth_failure(client_ip, "admin_auth", db)
            await create_login_log(
                db=db,
                username=username,
                result=2,
                fail_reason="captcha_not_completed",
                request=request,
            )
            return self._create_login_failure_response(request, admin)

        provider = await create_captcha_provider("admin", db)
        turnstile_valid, turnstile_error = await provider.verify_token(turnstile_token, client_ip)
        if not turnstile_valid:
            await record_auth_failure(client_ip, "admin_auth", db)
            await create_login_log(
                db=db,
                username=username,
                result=2,
                fail_reason=f"captcha_failed: {turnstile_error}",
                request=request,
            )
            return self._create_login_failure_response(request, admin)

        return None

    async def _verify_user_credentials(
        self,
        username: str,
        password: str,
        client_ip: str,
        request: Request,
        admin: BaseAdmin,
        db: AsyncSession,
    ) -> Response | None:
        """Verify user exists, password is correct, and account is active."""
        admin_user = await admin_user_crud.get_by_username(db, username=username)
        if not admin_user:
            await record_auth_failure(client_ip, "admin_auth", db)
            await create_login_log(
                db=db,
                username=username,
                result=2,
                fail_reason="user_not_found",
                request=request,
            )
            return self._create_login_failure_response(request, admin)

        if not verify_password(password, admin_user.password_hash):
            await record_auth_failure(client_ip, "admin_auth", db)
            await create_login_log(
                db=db,
                username=username,
                result=2,
                admin_user_id=admin_user.id,
                fail_reason="invalid_password",
                request=request,
            )
            return self._create_login_failure_response(request, admin)

        if not await admin_user_crud.is_active(admin_user):
            await create_login_log(
                db=db,
                username=username,
                result=2,
                admin_user_id=admin_user.id,
                fail_reason="account_disabled",
                request=request,
            )
            return self._create_login_failure_response(request, admin)

        return None

    async def _complete_login(
        self,
        username: str,
        client_ip: str,
        request: Request,
        admin: BaseAdmin,
        db: AsyncSession,
    ) -> Response:
        """Complete successful login by setting session and logging."""
        admin_user: AdminUserModel = await admin_user_crud.get_by_username(db, username=username)  # type: ignore[assignment]

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

        await reset_failures(client_ip, "admin_auth")

        await create_login_log(
            db=db,
            username=username,
            result=1,
            admin_user_id=admin_user.id,
            request=request,
        )

        logger.info(
            "admin_login_success",
            username=username,
            admin_user_id=admin_user.id,
            ip=client_ip,
        )

        next_url = request.query_params.get("next", request.url_for(admin.route_name + ":index"))
        return RedirectResponse(url=next_url, status_code=303)

    def _create_login_failure_response(self, request: Request, admin: BaseAdmin) -> Response:
        """Generate a consistent failure redirect."""
        login_url = str(request.url_for(admin.route_name + ":login")) + "?error=Login failed"
        return RedirectResponse(url=login_url, status_code=303)

    async def is_authenticated(self, request: Request) -> bool:
        """Check if user is authenticated."""
        return request.session.get("admin_user") is not None

    def get_admin_config(self, request: Request) -> AdminConfig | None:
        """Get admin configuration for current user."""
        admin_user_data = request.session.get("admin_user")
        if not admin_user_data:
            return None

        return AdminConfig(
            app_title="Qiao Dashboard",
            logo_url=None,
        )

    def get_admin_user(self, request: Request) -> AdminUser | None:
        """Get current admin user."""
        admin_user_data = request.session.get("admin_user")
        if not admin_user_data:
            return None

        return AdminUser(
            username=admin_user_data["username"],
            photo_url=None,
        )

    async def render_logout(self, request: Request, admin: BaseAdmin) -> Response:
        """Handle admin logout with custom logic."""
        admin_user_data = request.session.get("admin_user")
        if admin_user_data:
            logger.info("admin_logout", username=admin_user_data["username"])

        request.session.clear()
        return RedirectResponse(url=request.url_for(admin.route_name + ":login"))
