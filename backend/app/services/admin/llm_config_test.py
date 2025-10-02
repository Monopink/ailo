"""
LLM configuration testing service.

This service provides functionality for testing LLM configurations
through the admin interface. It orchestrates the test execution by:
1. Validating configuration
2. Calling LLM API using existing client (reuse!)
3. Detecting JSON Schema support and auto-updating json_schema_mode
4. Recording test results to database
5. Returning formatted results
"""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from services.llm.client import chat_completion
from services.llm.config import get_llm_config
from services.llm.utils import is_valid_json
from models.llm import LLMTestLog
from utils.logging import get_logger
from utils.snowflake import generate_snowflake_id
from enums.common import LLMTestStatus

logger = get_logger(__name__)

# Simple test schema for detecting JSON Schema support
TEST_SCHEMA = {
    "type": "object",
    "properties": {
        "response": {"type": "string", "description": "Response content"},
        "status": {"type": "string", "description": "Response status"},
    },
    "required": ["response"],
}


async def execute_llm_config_test(
    db: AsyncSession,
    config_id: int,
    test_message: str,
    override_temperature: Optional[float] = None,
    override_max_tokens: Optional[int] = None,
    enable_thinking: bool = False,
) -> Dict[str, Any]:
    """
    Execute LLM configuration test.

    This function orchestrates the complete test flow:
    1. Validates the configuration exists and is accessible
    2. Calls LLM API using the unified client (reuses existing code)
    3. Records test results to llm_test_logs table
    4. Returns formatted results for display

    Args:
        db: Database session
        config_id: LLM configuration ID
        test_message: Test message content
        override_temperature: Optional temperature override (0.0-2.0)
        override_max_tokens: Optional max tokens override
        enable_thinking: Enable thinking mode if supported

    Returns:
        Dictionary containing test results and metadata:
        {
            "success": bool,
            "log_id": int,
            "response_content": Any,
            "raw_content": str,
            "reasoning_content": Optional[str],
            "usage": dict,
            "response_time_ms": int,
            "model_used": str,
            "finish_reason": str,
            "request_payload": dict,
            "error": Optional[str]
        }
    """
    start_time = datetime.now()

    try:
        # Step 1: Get and validate configuration
        config_result = await get_llm_config(db, config_id=config_id)
        if not config_result:
            logger.warning("llm_config_test_config_not_found", config_id=config_id)
            return {
                "success": False,
                "error": "Configuration not found",
            }

        config, provider = config_result

        logger.info(
            "llm_config_test_started",
            config_id=config_id,
            config_key=config.config_key,
            provider=provider.name,
        )

        # Step 2: Build messages for LLM
        messages = [{"role": "user", "content": test_message}]

        # Step 3: Call LLM with test schema to detect JSON Schema support
        llm_result = await chat_completion(
            db=db,
            messages=messages,
            json_schema=TEST_SCHEMA,  # Use test schema to detect JSON Schema support
            temperature=override_temperature,
            max_tokens=override_max_tokens,
            enable_thinking=enable_thinking,
            config_key=config.config_key,
        )

        # Step 4: Calculate response time
        end_time = datetime.now()
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Step 5: Detect JSON Schema support and auto-update json_schema_mode
        json_schema_supported = False
        json_schema_warning = None

        if llm_result.get("success"):
            # Check if response is valid JSON
            response_content = llm_result.get("response", "")
            is_json, parsed_json = is_valid_json(response_content)

            if is_json:
                # Response is JSON - supports JSON Schema
                json_schema_supported = True
                if config.json_schema_mode != "strict":
                    logger.info(
                        "llm_config_test_json_schema_detected",
                        config_id=config_id,
                        old_mode=config.json_schema_mode,
                        new_mode="strict",
                    )
                    config.json_schema_mode = "strict"
                    await db.commit()
            else:
                # Response is plain text - does not support JSON Schema
                json_schema_supported = False
                json_schema_warning = "⚠️ 此配置不支持JSON Schema，无法用于AI Character功能"
                if config.json_schema_mode != "disabled":
                    logger.info(
                        "llm_config_test_json_schema_not_supported",
                        config_id=config_id,
                        old_mode=config.json_schema_mode,
                        new_mode="disabled",
                    )
                    config.json_schema_mode = "disabled"
                    await db.commit()

        # Step 6: Safely extract data with defaults
        usage = llm_result.get("usage") or {}
        config_used = llm_result.get("config_used") or {}
        request_payload = llm_result.get("request_payload") or {}

        # Determine status using enum
        if llm_result.get("success"):
            status = LLMTestStatus.SUCCESS
            error_message = None
        else:
            error_code = llm_result.get("error_code", "UNKNOWN")
            if "TIMEOUT" in error_code:
                status = LLMTestStatus.TIMEOUT
            else:
                status = LLMTestStatus.FAILED
            error_message = llm_result.get("error", "Unknown error")

        # Step 7: Prepare log data
        log_data = {
            "id": generate_snowflake_id(),
            "config_id": config_id,
            "config_key": config.config_key,
            "provider_name": provider.name,
            "model_name": llm_result.get("model") or config.model_name or provider.default_model,
            "test_message": test_message,
            "override_temperature": override_temperature,
            "override_max_tokens": override_max_tokens,
            "enable_thinking": 1 if enable_thinking else 0,
            "request": request_payload,  # Store full request parameters
            "response": llm_result.get("raw_response"),  # Store full OpenAI API response
            "status": status,
            "error_message": error_message,
            "response_time_ms": response_time_ms,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "reasoning_content": llm_result.get("reasoning_content"),
            "completed_at": end_time,
        }

        # Step 8: Save to database
        db_log = LLMTestLog(**log_data)
        db.add(db_log)
        await db.commit()
        await db.refresh(db_log)

        logger.info(
            "llm_config_test_completed",
            config_id=config_id,
            log_id=log_data["id"],
            success=llm_result["success"],
            response_time_ms=response_time_ms,
            json_schema_supported=json_schema_supported,
        )

        # Step 9: Return formatted result with JSON Schema support info
        result = {
            "success": llm_result.get("success", False),
            "status": status,
            "error": error_message,  # Frontend expects 'error' field
            "log_id": log_data["id"],
            "response_content": llm_result.get("response"),
            "raw_content": llm_result.get("raw_content"),
            "raw_response": llm_result.get("raw_response"),  # Include raw API response
            "reasoning_content": llm_result.get("reasoning_content"),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
            "response_time_ms": response_time_ms,
            "model_used": config_used.get("model") or config.model_name or provider.default_model,
            "finish_reason": llm_result.get("finish_reason"),
            "request_payload": request_payload,
            # JSON Schema support info
            "json_schema_supported": json_schema_supported,
            "json_schema_mode": config.json_schema_mode,
        }

        # Add warning if JSON Schema not supported
        if json_schema_warning:
            result["warning"] = json_schema_warning
            result["recommendation"] = "此配置无法用于AI Character功能，仅供查看测试响应"

        return result

    except Exception as e:
        logger.error("llm_config_test_failed", error=str(e), config_id=config_id, exc_info=True)
        return {
            "success": False,
            "status": LLMTestStatus.FAILED,
            "error": f"测试执行失败: {str(e)}",  # Frontend expects 'error' field
            "response_content": None,
            "reasoning_content": None,
            "response_time_ms": 0,
            "usage": {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            },
            "model_used": None,
            "finish_reason": None,
            "request_payload": None,
        }
