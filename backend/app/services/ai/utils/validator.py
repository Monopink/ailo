"""
AI response validation utilities.

This module provides functions for validating AI responses against JSON schemas
with retry mechanisms and detailed error reporting.
"""

import asyncio
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from services.config import config_service
from services.llm import chat_completion
from utils.logging import get_logger

import jsonschema

logger = get_logger(__name__)


def validate_ai_response(response: Any, json_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate AI response against JSON schema.

    Args:
        response: AI response to validate
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

        # Perform JSON schema validation
        jsonschema.validate(instance=response, schema=json_schema)

        logger.debug("ai_response_validation_success")
        return {"valid": True, "error": "", "validated_data": response}

    except jsonschema.ValidationError as e:
        error_msg = f"JSON Schema validation failed: {str(e)}"
        logger.warning(
            "ai_response_validation_failed",
            error=error_msg,
            response_type=type(response).__name__,
        )
        return {"valid": False, "error": error_msg, "validated_data": None}
    except Exception as e:
        error_msg = f"Validation error: {str(e)}"
        logger.error("ai_response_validation_error", error=error_msg)
        return {"valid": False, "error": error_msg, "validated_data": None}


async def chat_completion_with_validation(
    db: AsyncSession, messages: List[Dict[str, str]], json_schema: Optional[Dict[str, Any]] = None, **kwargs
) -> Dict[str, Any]:
    """
    LLM chat completion with JSON schema validation and retry.

    This function wraps the LLM service call with business-level validation
    and retry logic specific to AI conversation needs.

    Args:
        db: Database session
        messages: List of message objects with 'role' and 'content'
        json_schema: Optional JSON schema for structured output validation
        **kwargs: Additional arguments passed to chat_completion

    Returns:
        Dictionary containing response data and metadata
    """
    try:
        # Get validation configuration from system_config
        max_retries = await config_service.get_config(db, "ai_json_schema_max_retries", 3)
        retry_delay = await config_service.get_config(db, "ai_json_schema_retry_delay", 2)
        validation_enabled = await config_service.get_config(db, "ai_json_schema_validation_enabled", True)

        last_error = None

        for attempt in range(int(max_retries) + 1):
            try:
                # Call LLM service
                llm_result = await chat_completion(
                    db=db, messages=messages, json_schema=json_schema, **kwargs
                )

                # Check if LLM call succeeded
                if not llm_result.get("success", False):
                    last_error = llm_result.get("error", "Unknown LLM error")
                    logger.warning("llm_call_failed", attempt=attempt + 1, error=last_error)

                    # For LLM failures, don't retry - return immediately
                    return llm_result

                # Validate response if validation is enabled and schema is provided
                if validation_enabled and json_schema:
                    validation_result = validate_ai_response(
                        response=llm_result.get("response"),
                        json_schema=json_schema,
                    )

                    if validation_result["valid"]:
                        logger.debug("ai_response_validated_successfully", attempt=attempt + 1)
                        return llm_result
                    else:
                        last_error = validation_result["error"]
                        logger.warning(
                            "ai_response_validation_failed",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            error=last_error,
                        )

                        # If this is not the last attempt, wait and retry
                        if attempt < int(max_retries):
                            await asyncio.sleep(float(retry_delay))
                            continue
                        else:
                            # Last attempt failed
                            return {
                                "success": False,
                                "error": f"AI response validation failed after {max_retries} retries: {last_error}",
                                "response": None,
                                "usage": llm_result.get("usage"),
                            }
                else:
                    # No validation needed or disabled
                    logger.debug("ai_response_validation_skipped")
                    return llm_result

            except Exception as e:
                last_error = str(e)
                logger.error("ai_validation_attempt_error", attempt=attempt + 1, error=last_error)

                # For unexpected errors, don't retry
                return {
                    "success": False,
                    "error": f"AI validation error: {last_error}",
                    "response": None,
                    "usage": None,
                }

        # Should not reach here, but just in case
        return {
            "success": False,
            "error": f"AI response validation failed after {max_retries} retries: {last_error}",
            "response": None,
            "usage": None,
        }

    except Exception as e:
        logger.error("chat_completion_with_validation_error", error=str(e))
        return {
            "success": False,
            "error": f"Chat completion with validation error: {str(e)}",
            "response": None,
            "usage": None,
        }
