"""
LLM JSON Schema compatibility test service.

This service tests whether an LLM configuration supports JSON Schema mode
and automatically updates the json_schema_mode field based on the result.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLMConfig, LLMProvider, LLMTestLog
from app.services.llm.client import invoke_llm
from app.type_defs import JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def test_json_schema_compatibility(
    db: AsyncSession,
    config_id: int,
) -> JSONDict:
    """
    Test JSON Schema compatibility for an LLM configuration.

    Args:
        db: Database session
        config_id: LLM configuration ID

    Returns:
        Dictionary with test results and updated mode
    """

    # Load configuration
    result = await db.execute(
        select(LLMConfig, LLMProvider)
        .join(LLMProvider, LLMConfig.provider_id == LLMProvider.id)
        .where(LLMConfig.id == config_id)
    )
    row = result.first()

    if not row:
        raise ValueError(f"LLM configuration with ID {config_id} not found")

    config, provider = row

    # Define fixed test schema
    test_schema: JSONDict = {
        "type": "object",
        "properties": {"test_field": {"type": "string", "description": "A test field"}},
        "required": ["test_field"],
        "additionalProperties": False,
    }

    # Test message
    test_message = "Please respond with a JSON object containing a test_field with value 'success'"
    test_messages: list[JSONDict] = [{"role": "user", "content": test_message}]

    start_time = time.time()
    llm_result: JSONDict | None = None
    test_log: LLMTestLog | None = None

    try:
        # Attempt to call LLM with JSON Schema
        llm_result = await invoke_llm(
            db=db,
            messages=test_messages,
            json_schema=test_schema,
            temperature=0.7,
            max_tokens=100,
            thinking_mode="disabled",
            name=config.name,
        )

        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        completed_at = datetime.now(UTC)

        # Log the result for debugging
        logger.info(f"LLM test result: {llm_result}")

        # Extract usage info
        usage = llm_result.get("usage", {})

        # Check if response succeeded and has response content
        if llm_result.get("success") and llm_result.get("response"):
            # Test succeeded - mark as strict (verified supported)
            old_mode = config.json_schema_mode
            config.json_schema_mode = "strict"

            # Create test log record
            test_log = LLMTestLog(
                config_id=config.id,
                config_name=config.name,
                provider_name=provider.name,
                model_name=llm_result.get("model") or config.model_name,
                test_message=test_message,
                override_temperature=0.7,
                override_max_tokens=100,
                thinking_mode="disabled",
                enable_json_schema=1,
                request=llm_result.get("request_payload", {}),
                response=llm_result.get("raw_response", {}),
                status=1,  # success
                error_message=None,
                response_time_ms=response_time_ms,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
                reasoning_content=None,
                completed_at=completed_at,
            )

            db.add(test_log)
            await db.commit()

            return {
                "success": True,
                "mode": "strict",
                "message": (
                    "✅ JSON Schema is supported! Mode updated from "
                    f"'{old_mode}' to 'strict' (AI Instance ready)"
                ),
                "response": llm_result.get("response"),
                "usage": usage,
                "model": llm_result.get("model"),
                "response_time_ms": response_time_ms,
                "test_log_id": test_log.id,
            }
        # Request failed - do NOT update config, just report the failure
        error_msg = llm_result.get("error") or llm_result.get("error_code") or "Unknown error"
        logger.warning(f"LLM test failed: {error_msg}, full result: {llm_result}")

        # Create test log record for failure
        test_log = LLMTestLog(
            config_id=config.id,
            config_name=config.name,
            provider_name=provider.name,
            model_name=llm_result.get("model") or config.model_name,
            test_message=test_message,
            override_temperature=0.7,
            override_max_tokens=100,
            thinking_mode="disabled",
            enable_json_schema=1,
            request=llm_result.get("request_payload", {}),
            response=llm_result.get("raw_response"),
            status=2,  # failed
            error_message=error_msg,
            response_time_ms=response_time_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            reasoning_content=None,
            completed_at=completed_at,
        )

        db.add(test_log)
        await db.commit()

        return {
            "success": False,
            "mode": config.json_schema_mode,  # Keep current mode
            "message": (
                f"⚠️ Test failed: {error_msg}. Mode unchanged (still '{config.json_schema_mode}')"
            ),
            "test_log_id": test_log.id,
        }

    except Exception as e:
        # Exception during test - this might indicate incompatibility
        response_time_ms = int((time.time() - start_time) * 1000)
        completed_at = datetime.now(UTC)
        logger.error(f"Exception during JSON Schema test: {e!s}", exc_info=True)

        # Check if it's a known JSON Schema incompatibility error
        error_str = str(e).lower()
        if "json" in error_str and (
            "schema" in error_str or "format" in error_str or "structured" in error_str
        ):
            # Likely JSON Schema not supported - update to disabled
            old_mode = config.json_schema_mode
            config.json_schema_mode = "disabled"

            # Create test log record for incompatibility
            test_log = LLMTestLog(
                config_id=config.id,
                config_name=config.name,
                provider_name=provider.name,
                model_name=config.model_name,
                test_message=test_message,
                override_temperature=0.7,
                override_max_tokens=100,
                thinking_mode="disabled",
                enable_json_schema=1,
                request={
                    "error": "Exception before request",
                    "messages": test_messages,
                    "json_schema": test_schema,
                },
                response=None,
                status=2,  # failed
                error_message=str(e),
                response_time_ms=response_time_ms,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                reasoning_content=None,
                completed_at=completed_at,
            )

            db.add(test_log)
            await db.commit()

            return {
                "success": False,
                "mode": "disabled",
                "message": (
                    "❌ JSON Schema is NOT supported (verified). "
                    f"Mode updated from '{old_mode}' to 'disabled'. "
                    f"Error: {e!s}"
                ),
                "error": str(e),
                "test_log_id": test_log.id,
            }
        # Other error - do NOT update config
        # Create test log record for error
        test_log = LLMTestLog(
            config_id=config.id,
            config_name=config.name,
            provider_name=provider.name,
            model_name=config.model_name,
            test_message=test_message,
            override_temperature=0.7,
            override_max_tokens=100,
            thinking_mode="disabled",
            enable_json_schema=1,
            request={
                "error": "Exception before request",
                "messages": test_messages,
                "json_schema": test_schema,
            },
            response=None,
            status=2,  # failed
            error_message=str(e),
            response_time_ms=response_time_ms,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            reasoning_content=None,
            completed_at=completed_at,
        )

        db.add(test_log)
        await db.commit()

        return {
            "success": False,
            "mode": config.json_schema_mode,  # Keep current mode
            "message": (f"⚠️ Test error: {e!s}. Mode unchanged (still '{config.json_schema_mode}')"),
            "error": str(e),
            "test_log_id": test_log.id,
        }
