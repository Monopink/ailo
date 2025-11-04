"""
AI service integration test module.

This module provides test functions to verify the complete AI conversation
processing pipeline including score calculation and LLM integration.
"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from .conversation import process_conversation
from .relationship import calculate_new_scores, update_relationship_positions
from .prompt import build_system_prompt, build_response_schema
from .data import get_character_with_relations
from utils.logging import get_logger

logger = get_logger(__name__)


async def test_ai_conversation_flow(
    db: AsyncSession,
    character_qiao_id: str,
    user_qiao_id: str,
    test_message: str = "Hello, how are you today?",
) -> Dict[str, Any]:
    """
    Test the complete AI conversation flow.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
        user_qiao_id: User's qiao_id
        test_message: Test message content

    Returns:
        Dictionary containing test results and metadata
    """
    try:
        logger.info(
            "ai_conversation_flow_test_started",
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
        )

        # Test the complete conversation processing
        result = await process_conversation(
            db=db,
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            message_content=test_message,
        )

        test_result = {
            "success": True,
            "conversation_result": result,
            "test_metadata": {
                "character_qiao_id": character_qiao_id,
                "user_qiao_id": user_qiao_id,
                "test_message": test_message,
                "test_type": "full_conversation_flow",
            },
        }

        logger.info(
            "ai_conversation_flow_test_completed",
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
            success=True,
        )

        return test_result

    except Exception as e:
        logger.error(
            "ai_conversation_flow_test_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
        )
        return {
            "success": False,
            "error": str(e),
            "test_metadata": {
                "character_qiao_id": character_qiao_id,
                "user_qiao_id": user_qiao_id,
                "test_message": test_message,
                "test_type": "full_conversation_flow",
            },
        }


async def test_score_calculation(
    db: AsyncSession, character_qiao_id: str, test_scores: Dict[str, int] = None
) -> Dict[str, Any]:
    """
    Test the score calculation and update system.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
        test_scores: Test score values (defaults to sample scores)

    Returns:
        Dictionary containing test results
    """
    try:
        if test_scores is None:
            test_scores = {
                "affection": 650,
                "trust": 720,
                "intimacy": 580,
            }

        logger.info(
            "score_calculation_test_started",
            character_qiao_id=character_qiao_id,
            test_scores=test_scores,
        )

        # Get character information
        character_info = await get_character_with_relations(db, character_qiao_id)
        if not character_info:
            return {
                "success": False,
                "error": f"Character not found: {character_qiao_id}",
                "test_metadata": {
                    "character_qiao_id": character_qiao_id,
                    "test_type": "score_calculation",
                },
            }

        # Test score calculation
        new_scores = await calculate_new_scores(db, character_info, test_scores)

        # Test score position updates
        character_id = character_info.get("character_id")
        if character_id and new_scores:
            update_success = await update_relationship_positions(db, character_id, new_scores)
        else:
            update_success = False

        test_result = {
            "success": True,
            "original_scores": test_scores,
            "calculated_scores": new_scores,
            "update_success": update_success,
            "test_metadata": {
                "character_qiao_id": character_qiao_id,
                "character_id": character_id,
                "test_type": "score_calculation",
            },
        }

        logger.info(
            "score_calculation_test_completed",
            character_qiao_id=character_qiao_id,
            success=True,
            scores_calculated=len(new_scores) if new_scores else 0,
        )

        return test_result

    except Exception as e:
        logger.error(
            "score_calculation_test_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
        )
        return {
            "success": False,
            "error": str(e),
            "test_metadata": {
                "character_qiao_id": character_qiao_id,
                "test_type": "score_calculation",
            },
        }


async def test_prompt_building(
    db: AsyncSession, character_qiao_id: str, user_qiao_id: str
) -> Dict[str, Any]:
    """
    Test the prompt building system.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
        user_qiao_id: User's qiao_id

    Returns:
        Dictionary containing test results
    """
    try:
        logger.info(
            "prompt_building_test_started",
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
        )

        # Get character information
        character_info = await get_character_with_relations(db, character_qiao_id)
        if not character_info:
            return {
                "success": False,
                "error": f"Character not found: {character_qiao_id}",
                "test_metadata": {
                    "character_qiao_id": character_qiao_id,
                    "user_qiao_id": user_qiao_id,
                    "test_type": "prompt_building",
                },
            }

        # Test system prompt building
        system_prompt = await build_system_prompt(db, character_info, user_qiao_id)

        # Test response schema building
        response_schema = await build_response_schema(db, character_info)

        test_result = {
            "success": True,
            "system_prompt": system_prompt,
            "system_prompt_length": len(system_prompt) if system_prompt else 0,
            "response_schema": response_schema,
            "schema_properties_count": len(response_schema.get("properties", {})) if response_schema else 0,
            "test_metadata": {
                "character_qiao_id": character_qiao_id,
                "user_qiao_id": user_qiao_id,
                "test_type": "prompt_building",
            },
        }

        logger.info(
            "prompt_building_test_completed",
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
            success=True,
            prompt_length=test_result["system_prompt_length"],
        )

        return test_result

    except Exception as e:
        logger.error(
            "prompt_building_test_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
        )
        return {
            "success": False,
            "error": str(e),
            "test_metadata": {
                "character_qiao_id": character_qiao_id,
                "user_qiao_id": user_qiao_id,
                "test_type": "prompt_building",
            },
        }


async def run_all_tests(db: AsyncSession, character_qiao_id: str, user_qiao_id: str) -> Dict[str, Any]:
    """
    Run all AI integration tests.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
        user_qiao_id: User's qiao_id

    Returns:
        Dictionary containing all test results
    """
    logger.info(
        "ai_integration_tests_started",
        character_qiao_id=character_qiao_id,
        user_qiao_id=user_qiao_id,
    )

    results = {
        "prompt_building": await test_prompt_building(db, character_qiao_id, user_qiao_id),
        "score_calculation": await test_score_calculation(db, character_qiao_id),
        "conversation_flow": await test_ai_conversation_flow(db, character_qiao_id, user_qiao_id),
    }

    # Calculate overall success
    all_success = all(result.get("success", False) for result in results.values())

    final_result = {
        "overall_success": all_success,
        "test_results": results,
        "summary": {
            "total_tests": len(results),
            "passed_tests": sum(1 for result in results.values() if result.get("success", False)),
            "failed_tests": sum(1 for result in results.values() if not result.get("success", False)),
        },
    }

    logger.info(
        "ai_integration_tests_completed",
        character_qiao_id=character_qiao_id,
        user_qiao_id=user_qiao_id,
        overall_success=all_success,
        passed_tests=final_result["summary"]["passed_tests"],
        failed_tests=final_result["summary"]["failed_tests"],
    )

    return final_result
