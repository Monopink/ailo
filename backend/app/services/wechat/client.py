"""
WeChat Mini Program API client
"""

import base64
import json
from typing import Any, NotRequired, TypedDict, cast

import httpx
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.core.config import get_settings
from app.services.wechat import cache
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _safe_httpx_request_url(exc: httpx.HTTPError) -> str | None:
    request = getattr(exc, "request", None)
    url = getattr(request, "url", None)
    if url is None:
        return None
    raw = str(url)
    return raw.split("?", 1)[0]


def _safe_httpx_request_method(exc: httpx.HTTPError) -> str | None:
    request = getattr(exc, "request", None)
    method = getattr(request, "method", None)
    return method if isinstance(method, str) and method else None


def _safe_httpx_status_code(exc: httpx.HTTPError) -> int | None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return status_code if isinstance(status_code, int) else None


class WeChatAccessTokenResponse(TypedDict):
    """WeChat access token API response structure."""

    access_token: str
    expires_in: int


class WeChatCode2SessionResponse(TypedDict):
    """WeChat code2session API response structure."""

    openid: str
    session_key: str
    unionid: NotRequired[str]


class WeChatPhoneNumberResponse(TypedDict):
    """WeChat phone number API response structure."""

    phone_info: dict[str, Any]


class WeChatURLLinkResponse(TypedDict):
    """WeChat URL Link API response structure."""

    url_link: str


class WeChatAPIError(Exception):
    """WeChat API error"""

    def __init__(self, errcode: int, errmsg: str) -> None:
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"WeChat API error {errcode}: {errmsg}")


class WeChatClient:
    """
    WeChat Mini Program API client

    Provides methods to interact with WeChat APIs:
        - get_access_token(): Get access token
        - code2session(): Exchange login code for openid
        - get_phone_number(): Exchange phone code for phone number
    """

    BASE_URL = "https://api.weixin.qq.com"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=10.0)

    async def get_access_token(self) -> str:
        """
        Get WeChat access token

        API: GET https://api.weixin.qq.com/cgi-bin/token

        Returns:
            access_token: string

        Raises:
            WeChatAPIError: If API call fails
        """
        # Check cache first
        cached_token = cache.get_token()
        if cached_token:
            return cached_token

        # Call WeChat API
        url = f"{self.BASE_URL}/cgi-bin/token"
        settings = get_settings()
        params = {
            "grant_type": "client_credential",
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
        }

        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Check for errors
            if "errcode" in data and data["errcode"] != 0:
                logger.error(f"Failed to get access token: {data}")
                raise WeChatAPIError(data["errcode"], data.get("errmsg", "Unknown error"))

            # Cast to TypedDict after error check
            typed_data = cast(WeChatAccessTokenResponse, data)

            # Cache token
            access_token = typed_data["access_token"]
            expires_in = typed_data.get("expires_in", 7200)
            cache.set_token(access_token, expires_in)

            logger.info("Access token obtained successfully")
            return access_token

        except httpx.HTTPError as e:
            logger.error(
                "wechat_httpx_error",
                api="get_access_token",
                error_type=type(e).__name__,
                method=_safe_httpx_request_method(e),
                url=_safe_httpx_request_url(e),
                status_code=_safe_httpx_status_code(e),
            )
            raise WeChatAPIError(-1, f"http_error:{type(e).__name__}")

    async def code2session(self, js_code: str) -> dict[str, str]:
        """
        Exchange login code for openid and session_key

        API: GET https://api.weixin.qq.com/sns/jscode2session

        Args:
            js_code: Login code from wx.login()

        Returns:
            {
                "openid": "xxx",
                "session_key": "xxx",
                "unionid": "xxx"  # optional
            }

        Raises:
            WeChatAPIError: If API call fails
        """
        url = f"{self.BASE_URL}/sns/jscode2session"
        settings = get_settings()
        params = {
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
            "js_code": js_code,
            "grant_type": "authorization_code",
        }

        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Check for errors
            if "errcode" in data and data["errcode"] != 0:
                logger.error(f"Failed to exchange code for session: {data}")
                raise WeChatAPIError(data["errcode"], data.get("errmsg", "Unknown error"))

            # Cast to TypedDict after error check
            typed_data = cast(WeChatCode2SessionResponse, data)

            logger.info(f"Code2session successful, openid: {typed_data['openid'][:8]}...")
            return {
                "openid": typed_data["openid"],
                "session_key": typed_data["session_key"],
                # Include unionid if present
                **({"unionid": typed_data["unionid"]} if "unionid" in typed_data else {}),
            }

        except httpx.HTTPError as e:
            logger.error(
                "wechat_httpx_error",
                api="code2session",
                error_type=type(e).__name__,
                method=_safe_httpx_request_method(e),
                url=_safe_httpx_request_url(e),
                status_code=_safe_httpx_status_code(e),
            )
            raise WeChatAPIError(-1, f"http_error:{type(e).__name__}")

    async def get_phone_number(self, code: str, access_token: str) -> dict[str, Any]:
        """
        Exchange phone code for phone number

        API: POST https://api.weixin.qq.com/wxa/business/getuserphonenumber

        Args:
            code: Phone code from getPhoneNumber button
            access_token: Access token from get_access_token()

        Returns:
            {
                "phone_info": {
                    "phoneNumber": "+8613800138000",
                    "purePhoneNumber": "13800138000",
                    "countryCode": 86
                }
            }

        Raises:
            WeChatAPIError: If API call fails
        """
        url = f"{self.BASE_URL}/wxa/business/getuserphonenumber"
        params = {"access_token": access_token}
        json_data = {"code": code}

        try:
            response = await self._client.post(url, params=params, json=json_data)
            response.raise_for_status()
            data = response.json()

            # Check for errors
            if "errcode" in data and data["errcode"] != 0:
                logger.error(f"Failed to get phone number: {data}")
                raise WeChatAPIError(data["errcode"], data.get("errmsg", "Unknown error"))

            # Cast to TypedDict after error check
            typed_data = cast(WeChatPhoneNumberResponse, data)

            phone_info = typed_data.get("phone_info", {})
            logger.info(
                f"Got phone number, country_code: {phone_info.get('countryCode')}, "
                f"phone: {phone_info.get('phoneNumber', '')[:8]}..."
            )
            # Return as dict[str, Any] as per function signature
            return cast(dict[str, Any], typed_data)

        except httpx.HTTPError as e:
            logger.error(
                "wechat_httpx_error",
                api="get_phone_number",
                error_type=type(e).__name__,
                method=_safe_httpx_request_method(e),
                url=_safe_httpx_request_url(e),
                status_code=_safe_httpx_status_code(e),
            )
            raise WeChatAPIError(-1, f"http_error:{type(e).__name__}")

    async def generate_url_link(
        self,
        *,
        path: str,
        query: str,
        env_version: str = "release",
    ) -> str:
        """Generate a WeChat URL Link that opens the mini-program page."""
        access_token = await self.get_access_token()
        url = f"{self.BASE_URL}/wxa/generate_urllink"
        params = {"access_token": access_token}
        json_data = {
            "path": path,
            "query": query,
            "env_version": env_version,
            "is_expire": False,
        }

        try:
            response = await self._client.post(url, params=params, json=json_data)
            response.raise_for_status()
            data = response.json()

            if "errcode" in data and data["errcode"] != 0:
                logger.error("wechat_generate_urllink_failed", response=data)
                raise WeChatAPIError(data["errcode"], data.get("errmsg", "Unknown error"))

            typed_data = cast(WeChatURLLinkResponse, data)
            url_link = str(typed_data.get("url_link", "")).strip()
            if url_link == "":
                raise WeChatAPIError(-1, "empty_url_link")
            return url_link

        except httpx.HTTPError as e:
            logger.error(
                "wechat_httpx_error",
                api="generate_urllink",
                error_type=type(e).__name__,
                method=_safe_httpx_request_method(e),
                url=_safe_httpx_request_url(e),
                status_code=_safe_httpx_status_code(e),
            )
            raise WeChatAPIError(-1, f"http_error:{type(e).__name__}")

    async def close(self) -> None:
        """Close HTTP client"""
        await self._client.aclose()

    def decrypt_user_data(self, encrypted_data: str, iv: str, session_key: str) -> dict[str, Any]:
        """Decrypt encrypted user payload from legacy getPhoneNumber callback."""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data)
            iv_bytes = base64.b64decode(iv)
            session_key_bytes = base64.b64decode(session_key)

            cipher = Cipher(algorithms.AES(session_key_bytes), modes.CBC(iv_bytes))
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(encrypted_bytes) + decryptor.finalize()

            unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
            plaintext = unpadder.update(decrypted) + unpadder.finalize()

            payload = json.loads(plaintext.decode("utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("invalid decrypted payload type")

            return cast(dict[str, Any], payload)
        except Exception as exc:
            logger.warning("wechat_decrypt_user_data_failed", error=str(exc))
            raise WeChatAPIError(-2, "failed_to_decrypt_user_data") from exc
