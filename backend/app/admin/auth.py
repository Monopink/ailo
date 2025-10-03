"""
Custom authentication provider for Starlette-Admin with security features.
"""

from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from collections import deque
import httpx

from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette_admin.auth import AdminConfig, AdminUser, AuthProvider

# FormValidationError and LoginFailed not needed for custom auth flow
from starlette_admin import BaseAdmin

from core.database import SessionLocal
from crud.admin import admin_user as admin_user_crud
from services.system_config import get_config
from utils.admin_logs import create_login_log
from core.security import verify_password
from utils.logging import get_logger

logger = get_logger(__name__)

# In-memory cache for security tracking
ip_attempts: Dict[str, Dict] = {}
ip_rate_limit: Dict[str, deque] = {}

# Templates
templates = Jinja2Templates(directory="admin/templates")


async def check_ip_allowed(ip: str, db) -> Tuple[bool, Optional[str]]:
    """
    Check if IP is allowed to attempt login.

    Returns:
        (is_allowed, error_message)
    """
    # Check whitelist
    whitelist_ips_str = await get_config(db, key="admin_whitelist_ips", default="127.0.0.1,::1")
    whitelist_ips = [ip.strip() for ip in str(whitelist_ips_str).split(",")]
    if ip in whitelist_ips:
        return True, None

    # Check rate limit (requests per minute)
    rate_limit = int(await get_config(db, key="admin_rate_limit_requests", default=30))
    rate_window = int(await get_config(db, key="admin_rate_limit_window_seconds", default=60))

    now = datetime.now()
    if ip not in ip_rate_limit:
        ip_rate_limit[ip] = deque()

    # Remove old requests outside window
    while ip_rate_limit[ip] and (now - ip_rate_limit[ip][0]).seconds > rate_window:
        ip_rate_limit[ip].popleft()

    # Check if rate limit exceeded
    if len(ip_rate_limit[ip]) >= rate_limit:
        logger.warning("ip_rate_limit_exceeded", ip=ip, requests=len(ip_rate_limit[ip]))
        return False, "rate_limit_exceeded"

    # Add current request
    ip_rate_limit[ip].append(now)

    # Check IP lockout
    if ip in ip_attempts:
        ip_data = ip_attempts[ip]

        # Check if locked
        if ip_data.get("locked_until") and now < ip_data["locked_until"]:
            remaining = (ip_data["locked_until"] - now).seconds // 60
            logger.warning("ip_locked", ip=ip, remaining_minutes=remaining)
            return False, "ip_locked"

        # Reset if lockout expired
        if ip_data.get("locked_until") and now >= ip_data["locked_until"]:
            del ip_attempts[ip]

    return True, None


async def record_ip_failure(ip: str, username: str, db):
    """Record failed login attempt from IP."""
    whitelist_ips_str = await get_config(db, key="admin_whitelist_ips", default="127.0.0.1,::1")
    whitelist_ips = [ip.strip() for ip in str(whitelist_ips_str).split(",")]
    if ip in whitelist_ips:
        return

    max_ip_attempts = int(await get_config(db, key="admin_max_ip_attempts", default=10))
    ip_lockout_minutes = int(await get_config(db, key="admin_ip_lockout_duration_minutes", default=30))

    if ip not in ip_attempts:
        ip_attempts[ip] = {"count": 0, "locked_until": None, "usernames": set()}

    ip_attempts[ip]["count"] += 1
    ip_attempts[ip]["usernames"].add(username)

    # Lock IP if max attempts reached
    if ip_attempts[ip]["count"] >= max_ip_attempts:
        ip_attempts[ip]["locked_until"] = datetime.now() + timedelta(minutes=ip_lockout_minutes)
        logger.warning("ip_locked", ip=ip, attempts=ip_attempts[ip]["count"])


async def should_show_captcha(ip: str, db) -> bool:
    """Check if CAPTCHA should be shown for this IP."""
    captcha_enabled = await get_config(db, key="admin_captcha_enabled", default=True)
    if not captcha_enabled:
        return False

    threshold = int(await get_config(db, key="admin_captcha_threshold", default=3))

    if ip in ip_attempts:
        return ip_attempts[ip]["count"] >= threshold

    return False


async def verify_turnstile(token: str, ip: str, db) -> Tuple[bool, Optional[str]]:
    """
    Verify Cloudflare Turnstile token.

    Supports two modes:
    - strict: Block login on any verification failure (validation or service errors)
    - fallback: Allow login on service errors but block on validation failures

    Returns:
        (is_valid, error_message)
    """
    try:
        # Get configuration
        secret_key = await get_config(db, key="admin_turnstile_secret_key", default="")
        captcha_mode = await get_config(db, key="admin_captcha_mode", default="strict")

        if not secret_key:
            logger.warning("turnstile_secret_key_not_configured")
            return True, None  # Skip if not configured

        # Call Turnstile verification API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": secret_key, "response": token, "remoteip": ip},
                timeout=10.0,
            )

            result = response.json()

            if result.get("success"):
                logger.info("turnstile_verification_success", ip=ip)
                return True, None
            else:
                # Validation failure (wrong token, expired, etc.)
                error_codes = result.get("error-codes", [])
                logger.warning(
                    "turnstile_validation_failed",
                    ip=ip,
                    error_codes=error_codes,
                )
                return False, "Login failed"

    except Exception as e:
        # Service error (network, timeout, etc.)
        logger.error(
            "turnstile_service_error",
            ip=ip,
            error=str(e),
            mode=captcha_mode,
            exc_info=True,
        )

        # Check mode: strict or fallback
        if captcha_mode == "fallback":
            # Fallback mode: Allow login but log warning
            logger.warning(
                "turnstile_fallback_mode_allowing_login",
                ip=ip,
                reason="service_error",
            )
            return True, None
        else:
            # Strict mode: Block login
            return False, "Login failed"


async def reset_ip_attempts(ip: str):
    """Reset IP attempts after successful login."""
    if ip in ip_attempts:
        del ip_attempts[ip]


async def check_suspicious_activity(username: str, db):
    """Check for suspicious activity and send alerts."""
    alert_enabled = await get_config(db, key="admin_alert_on_suspicious_login", default=True)
    if not alert_enabled:
        return

    alert_threshold = int(await get_config(db, key="admin_alert_threshold_per_username", default=20))

    # Count unique IPs attempting this username
    unique_ips = set()
    for ip, data in ip_attempts.items():
        if username in data.get("usernames", set()):
            unique_ips.add(ip)

    if len(unique_ips) >= alert_threshold:
        logger.warning(
            "suspicious_login_activity",
            username=username,
            unique_ips=len(unique_ips),
            message=f"Username '{username}' has failed login attempts from {len(unique_ips)} different IPs",
        )
        # TODO: Send email/notification to admin


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
                show_captcha_raw = await should_show_captcha(client_ip, db)
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

                    # Check if IP is allowed
                    ip_allowed, ip_error = await check_ip_allowed(client_ip, db)
                    if not ip_allowed:
                        await create_login_log(
                            db=db,
                            username=username,
                            result=2,  # Failed
                            fail_reason=ip_error,  # Internal log: detailed reason
                            request=request,
                        )
                        return RedirectResponse(
                            url=str(request.url_for(admin.route_name + ":login")) + "?error=Login failed",
                            status_code=303,
                        )

                    # Check if CAPTCHA is required (only when secret configured)
                    secret_key = await get_config(db, key="admin_turnstile_secret_key", default="")
                    captcha_required = bool(secret_key) and await should_show_captcha(client_ip, db)

                    if captcha_required:
                        # Get Turnstile token from form
                        turnstile_token = str(form_data.get("cf_turnstile_response", ""))

                        if not turnstile_token:
                            await record_ip_failure(client_ip, username, db)
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
                        turnstile_valid, turnstile_error = await verify_turnstile(
                            turnstile_token, client_ip, db
                        )

                        if not turnstile_valid:
                            await record_ip_failure(client_ip, username, db)
                            await create_login_log(
                                db=db,
                                username=username,
                                result=2,  # Failed
                                fail_reason=turnstile_error,  # Internal log: detailed reason
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
                        await record_ip_failure(client_ip, username, db)
                        await create_login_log(
                            db=db,
                            username=username,
                            result=2,  # Failed
                            fail_reason="user_not_found",  # Internal log
                            request=request,
                        )
                        await check_suspicious_activity(username, db)
                        return RedirectResponse(
                            url=str(request.url_for(admin.route_name + ":login")) + "?error=Login failed",
                            status_code=303,
                        )

                    # Verify password
                    if not verify_password(password, admin_user.password_hash):
                        # Record failure and log
                        await record_ip_failure(client_ip, username, db)
                        await create_login_log(
                            db=db,
                            username=username,
                            result=2,  # Failed
                            admin_user_id=admin_user.id,
                            fail_reason="invalid_password",  # Internal log
                            request=request,
                        )
                        await check_suspicious_activity(username, db)
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

                    # Reset IP attempts
                    await reset_ip_attempts(client_ip)

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
