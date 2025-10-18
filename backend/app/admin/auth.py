"""
Custom authentication provider for Starlette-Admin with security features.
"""

from typing import Optional

from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette_admin.auth import AdminConfig, AdminUser, AuthProvider
from starlette_admin import BaseAdmin

from core.database import SessionLocal
from crud.admin import admin_user as admin_user_crud
from services.system_config import get_config
from services.security.auth_tracker import (
    check_lockout,
    record_auth_failure,
    should_require_captcha,
    reset_failures,
)
from services.security.captcha.factory import create_captcha_provider
from utils.admin_logs import create_login_log
from core.security import verify_password
from utils.logging import get_logger

logger = get_logger(__name__)

# Templates
templates = Jinja2Templates(directory="admin/templates")


class CustomAuthProvider(AuthProvider):
    """
    Custom authentication provider using session-based authentication.
    """

    async def render_login(self, request: Request, admin: BaseAdmin) -> Response:
        """
        Handle both GET (display form) and POST (process login) for custom login page.
        """
        async with SessionLocal() as db:
            # Get client IP
            client_ip = request.client.host if request.client else "unknown"

            # GET: Display login form
            if request.method == "GET":
                # Get Turnstile site key
                turnstile_site_key = await get_config(db, key="admin_turnstile_site_key", default="")

                # Check if should show CAPTCHA (only if site key configured)
                show_captcha_raw = await should_require_captcha(client_ip, "admin_auth", db)
                show_captcha = bool(turnstile_site_key) and show_captcha_raw

                # Get error from query params (if redirected after failed login)
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

            # POST: Process login
            elif request.method == "POST":
                try:
                    # Get form data
                    form_data = await request.form()
                    username = str(form_data.get("username", ""))
                    password = str(form_data.get("password", ""))

                    # Check if IP is locked
                    is_locked, remaining_seconds = await check_lockout(client_ip, "admin_auth", db)
                    if is_locked:
                        await create_login_log(
                            db=db,
                            username=username,
                            result=2,  # Failed
                            fail_reason="ip_locked",  # Internal log: detailed reason
                            request=request,
                        )
                        return RedirectResponse(
                            url=str(request.url_for(admin.route_name + ":login")) + "?error=Login failed",
                            status_code=303,
                        )

                    # Check if CAPTCHA is required
                    captcha_required = await should_require_captcha(client_ip, "admin_auth", db)

                    if captcha_required:
                        # Get Turnstile token from form
                        turnstile_token = str(form_data.get("cf_turnstile_response", ""))

                        if not turnstile_token:
                            await record_auth_failure(client_ip, "admin_auth", db)
                            await create_login_log(
                                db=db,
                                username=username,
                                result=2,  # Failed
                                fail_reason="captcha_not_completed",  # Internal log
                                request=request,
                            )
                            return RedirectResponse(
                                url=str(request.url_for(admin.route_name + ":login"))
                                + "?error=Login failed",
                                status_code=303,
                            )

                        # Verify Turnstile token
                        provider = await create_captcha_provider("admin", db)
                        turnstile_valid, turnstile_error = await provider.verify_token(
                            turnstile_token, client_ip
                        )

                        if not turnstile_valid:
                            await record_auth_failure(client_ip, "admin_auth", db)
                            await create_login_log(
                                db=db,
                                username=username,
                                result=2,  # Failed
                                fail_reason=f"captcha_failed: {turnstile_error}",  # Internal log: detailed reason
                                request=request,
                            )
                            return RedirectResponse(
                                url=str(request.url_for(admin.route_name + ":login"))
                                + "?error=Login failed",
                                status_code=303,
                            )

                    # Find admin user
                    admin_user = await admin_user_crud.get_by_username(db, username=username)

                    if not admin_user:
                        # Record failure and log
                        await record_auth_failure(client_ip, "admin_auth", db)
                        await create_login_log(
                            db=db,
                            username=username,
                            result=2,  # Failed
                            fail_reason="user_not_found",  # Internal log
                            request=request,
                        )
                        return RedirectResponse(
                            url=str(request.url_for(admin.route_name + ":login")) + "?error=Login failed",
                            status_code=303,
                        )

                    # Verify password
                    if not verify_password(password, admin_user.password_hash):
                        # Record failure and log
                        await record_auth_failure(client_ip, "admin_auth", db)
                        await create_login_log(
                            db=db,
                            username=username,
                            result=2,  # Failed
                            admin_user_id=admin_user.id,
                            fail_reason="invalid_password",  # Internal log
                            request=request,
                        )
                        return RedirectResponse(
                            url=str(request.url_for(admin.route_name + ":login")) + "?error=Login failed",
                            status_code=303,
                        )

                    # Check if user is active
                    if not await admin_user_crud.is_active(admin_user):
                        # Log failed login attempt
                        await create_login_log(
                            db=db,
                            username=username,
                            result=2,  # Failed
                            admin_user_id=admin_user.id,
                            fail_reason="account_disabled",  # Internal log
                            request=request,
                        )
                        return RedirectResponse(
                            url=str(request.url_for(admin.route_name + ":login")) + "?error=Login failed",
                            status_code=303,
                        )

                    # Login successful - set session
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

                    # Reset authentication failures
                    await reset_failures(client_ip, "admin_auth")

                    # Log successful login
                    await create_login_log(
                        db=db,
                        username=username,
                        result=1,  # Success
                        admin_user_id=admin_user.id,
                        request=request,
                    )

                    logger.info(
                        "admin_login_success",
                        username=username,
                        admin_user_id=admin_user.id,
                        ip=client_ip,
                    )

                    # Redirect to next page or dashboard
                    next_url = request.query_params.get(
                        "next", request.url_for(admin.route_name + ":index")
                    )
                    return RedirectResponse(url=next_url, status_code=303)

                except Exception as e:
                    logger.error("admin_login_unexpected_error", error=str(e), exc_info=True)
                    return RedirectResponse(
                        url=str(request.url_for(admin.route_name + ":login")) + "?error=Login failed",
                        status_code=303,
                    )

            # Other methods: redirect to GET
            else:
                return RedirectResponse(
                    url=request.url_for(admin.route_name + ":login"),
                    status_code=303,
                )

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

    async def render_logout(self, request: Request, admin: BaseAdmin) -> Response:
        """
        Handle admin logout with custom logic.
        """
        admin_user_data = request.session.get("admin_user")
        if admin_user_data:
            logger.info("admin_logout", username=admin_user_data["username"])

        request.session.clear()
        return RedirectResponse(url=request.url_for(admin.route_name + ":login"))
