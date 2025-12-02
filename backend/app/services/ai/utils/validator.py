"""
AI response validation utilities.

This module provides functions for validating AI responses against JSON schemas.
"""

import json
from typing import Any

import jsonschema
from services.llm import LLMSessionContext, invoke_llm
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

logger = get_logger(__name__)


def validate_ai_response(response: Any, json_schema: dict[str, Any]) -> dict[str, Any]:
    """
    Validate AI response against JSON schema.

    Args:
        response: AI response to validate (can be JSON string or object)
        json_schema: JSON schema for validation

    Returns:
        {
            "valid": bool,
            "error": str,
            "validated_data": Any
        }
    """
    try:
        if not json_schema:
            logger.debug("no_json_schema_provided")
            return {"valid": True, "error": "", "validated_data": response}

        # Log the raw response for debugging
        logger.debug(
            "validating_ai_response",
            response_type=type(response).__name__,
            response_length=len(str(response)) if response else 0,
            response_preview=str(response)[:200] if response else None,
        )

        # If response is a JSON string, parse it first
        # This is necessary because LLM providers (like OpenAI) return JSON strings
        # when using JSON Schema mode
        if isinstance(response, str):
            try:
                parsed_response = json.loads(response)
                logger.debug(
                    "ai_response_parsed_from_json_string",
                    parsed_type=type(parsed_response).__name__,
                )
                response = parsed_response
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse JSON response: {e!s}"
                logger.warning(
                    "ai_response_json_parse_failed",
                    error=error_msg,
                    response_preview=response[:500] if response else None,
                )
                return {"valid": False, "error": error_msg, "validated_data": None}

        # Perform JSON schema validation
        jsonschema.validate(instance=response, schema=json_schema)

        logger.debug("ai_response_validation_success")
        return {"valid": True, "error": "", "validated_data": response}

    except jsonschema.ValidationError as e:
        error_msg = f"JSON Schema validation failed: {e!s}"
        logger.warning(
            "ai_response_validation_failed",
            error=error_msg,
            response_type=type(response).__name__,
        )
        return {"valid": False, "error": error_msg, "validated_data": None}
    except Exception as e:
        error_msg = f"Validation error: {e!s}"
        logger.error("ai_response_validation_error", error=error_msg)
        return {"valid": False, "error": error_msg, "validated_data": None}


async def invoke_llm_with_validation(
    db: AsyncSession,
    messages: list[dict[str, str]],
    json_schema: dict[str, Any] | None = None,
    preemption_checker: Any | None = None,
    session_context: LLMSessionContext | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    LLM invocation with optional JSON schema validation and streaming early stop.

    This function wraps the LLM service call with validation support.
    Relies on LLM provider's native JSON schema support (strict mode) for reliability.

    Args:
        db: Database session
        messages: List of message objects with 'role' and 'content'
        json_schema: Optional JSON schema for structured output validation
        preemption_checker: Optional async callback to check if request should stop (for streaming)
        **kwargs: Additional arguments passed to invoke_llm

    Returns:
        Dictionary containing response data and metadata:
        {
            "success": bool,
            "response": Any,
            "error": Optional[str],
            "usage": Optional[Dict],
            "preempted": Optional[bool]
        }
    """
    try:
        # Call LLM service with preemption checker
        llm_result = await invoke_llm(
            db=db,
            messages=messages,
            json_schema=json_schema,
            preemption_checker=preemption_checker,
            session_context=session_context,
            **kwargs,
        )

        # Preemption means streaming was stopped intentionally (no validation needed)
        if llm_result.get("preempted"):
            logger.info("llm_call_preempted")
            return llm_result

        # Check if LLM call succeeded
        if not llm_result.get("success", False):
            logger.warning("llm_call_failed", error=llm_result.get("error"))
            return llm_result

        # Validate response if schema is provided
        if json_schema:
            validation_result = validate_ai_response(
                response=llm_result.get("response"),
                json_schema=json_schema,
            )

            if validation_result["valid"]:
                logger.debug("ai_response_validated_successfully")
                # Replace response with validated (parsed) data
                llm_result["response"] = validation_result["validated_data"]
                return llm_result
            # Validation failed
            error_msg = f"AI response validation failed: {validation_result['error']}"
            logger.error("ai_response_validation_failed", error=validation_result["error"])
            return {
                "success": False,
                "error": error_msg,
                "response": None,
                "usage": llm_result.get("usage"),
            }
        # No validation needed
        logger.debug("ai_response_validation_skipped")
        return llm_result

    except Exception as e:
        logger.error("invoke_llm_with_validation_error", error=str(e), exc_info=True)
        return {
            "success": False,
            "error": f"Chat completion with validation error: {e!s}",
            "response": None,
            "usage": None,
        }
