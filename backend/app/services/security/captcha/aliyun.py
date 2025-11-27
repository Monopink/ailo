"""
Aliyun Captcha Provider (Server-side verification for human verification)

Implements VerifyIntelligentCaptcha via Alibaba Cloud SDK.

Contract: same as other providers -> verify_token(token, ip) -> (bool, Optional[str])

Notes:
- AccessKeyId/AccessKeySecret must come from environment (settings), not DB.
- SceneId can be read from DB (system_configs) and is optional in the API.
- Region is hardcoded to 'cn' for MVP; endpoint maps to cn (Shanghai).
"""

from __future__ import annotations

import asyncio
import importlib
from typing import Optional, Tuple

from core.config import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)


class AliyunCaptchaProvider:
    """Aliyun Captcha (V2/V3) verification provider"""

    def __init__(self, *, scene_id: Optional[str] = None, region: str = "cn", mode: str = "strict") -> None:
        # region is intentionally hardcoded default to 'cn' per product decision
        self.scene_id = scene_id
        self.region = region or "cn"
        self.mode = mode  # 'strict' | 'fallback' (on infrastructure errors only)

        # Read AK/SK from environment via settings (Optional values)
        settings = get_settings()
        self.ak = getattr(settings, "ALIYUN_CAPTCHA_ACCESS_KEY_ID", None)
        self.sk = getattr(settings, "ALIYUN_CAPTCHA_ACCESS_KEY_SECRET", None)

        logger.info(
            "aliyun_captcha_provider_initialized",
            has_ak=bool(self.ak),
            has_sk=bool(self.sk),
            region=self.region,
            scene_id=bool(self.scene_id),
            mode=self.mode,
        )

    def _get_endpoint(self) -> str:
        if self.region == "cn":
            return "captcha.cn-shanghai.aliyuncs.com"
        elif self.region == "sgp":
            return "captcha.ap-southeast-1.aliyuncs.com"
        # default to cn
        return "captcha.cn-shanghai.aliyuncs.com"

    async def verify_token(self, token: str, ip: str) -> Tuple[bool, Optional[str]]:
        """Verify Aliyun captcha token (captchaVerifyParam).

        token: captchaVerifyParam returned by Aliyun plugin (V3) or client SDK
        ip: client IP (informational)
        """
        # Basic checks
        if not token:
            return False, "验证服务错误，请稍后再试"

        if not self.ak or not self.sk:
            logger.error("aliyun_captcha_missing_credentials")
            # Fallback behavior only if explicitly allowed
            if self.mode == "fallback":
                logger.warning("aliyun_captcha_fallback_allow")
                return True, None
            return False, "验证服务错误，请稍后再试"

        # Lazily import SDK to avoid hard dependency when not used
        try:
            captcha_models = importlib.import_module("alibabacloud_captcha20230305.models")
            captcha_client_module = importlib.import_module("alibabacloud_captcha20230305.client")
            CaptchaClient = getattr(captcha_client_module, "Client")
            open_api_models = importlib.import_module("alibabacloud_tea_openapi.models")
        except Exception as e:
            logger.error("aliyun_captcha_sdk_import_failed", error=str(e))
            if self.mode == "fallback":
                logger.warning("aliyun_captcha_fallback_allow_no_sdk")
                return True, None
            return False, "验证服务错误，请稍后再试"

        endpoint = self._get_endpoint()

        async def _do_verify() -> Tuple[bool, Optional[str]]:
            try:
                cfg = open_api_models.Config(
                    access_key_id=self.ak,
                    access_key_secret=self.sk,
                    endpoint=endpoint,
                )
                client = CaptchaClient(cfg)

                req = captcha_models.VerifyIntelligentCaptchaRequest(
                    captcha_verify_param=token,
                    scene_id=self.scene_id if self.scene_id else None,
                )

                # SDK is sync; run in thread
                def _call():
                    return client.verify_intelligent_captcha(req)

                resp = await asyncio.get_event_loop().run_in_executor(None, _call)
                body = getattr(resp, "body", None) or resp

                # Parse result
                success = getattr(body, "success", None)
                result = getattr(body, "result", None)
                verify_result = getattr(result, "verify_result", None) if result is not None else None
                code = getattr(body, "verify_code", None)

                logger.info(
                    "aliyun_captcha_response",
                    success=success,
                    verify_result=verify_result,
                    verify_code=code,
                )

                if success and verify_result is True:
                    return True, None

                # Non-passing cases
                return False, "验证服务错误，请稍后再试"

            except Exception as e:
                logger.error("aliyun_captcha_verify_failed", error=str(e), exc_info=True)
                if self.mode == "fallback":
                    logger.warning("aliyun_captcha_fallback_allow_error")
                    return True, None
                return False, "验证服务错误，请稍后再试"

        return await _do_verify()
