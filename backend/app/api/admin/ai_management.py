"""
Admin AI Management API endpoints.
Provides AI testing and management functionality for admin panel.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

from core.database import get_db
from services.admin.managers.ai_test_manager import AITestManager
from services.admin.utils.response_formatter import (
    format_success_response,
    format_error_response,
    format_validation_error_response,
)
from utils.logging import get_logger

logger = get_logger(__name__)

ai_router = APIRouter()


class ChatTestRequest(BaseModel):
    """AI character chat test request model."""

    character_qiao_id: str = Field(..., description="Character's qiao_id")
    user_qiao_id: str = Field(..., description="Test user's qiao_id")
    llm_config_key: str = Field(..., description="LLM configuration key")
    test_message: str = Field(..., description="Test message content")
    enable_thinking: bool = Field(True, description="Enable thinking mode")
    test_session_id: Optional[str] = Field(None, description="Optional test session ID")


class AlgorithmTestRequest(BaseModel):
    """Score algorithm test request model."""

    algorithm: int = Field(..., description="Algorithm type")
    score: float = Field(..., description="Input score")
    initial_position: float = Field(..., description="Initial position")
    params: Dict[str, Any] = Field(..., description="Algorithm parameters")
    batch_test: Optional[Dict[str, Any]] = Field(None, description="Batch test configuration")


class PromptTestRequest(BaseModel):
    """Prompt preview test request model."""

    character_qiao_id: str = Field(..., description="Character's qiao_id")
    user_qiao_id: str = Field(..., description="Test user's qiao_id")
    relationship_override: Optional[Dict[str, Any]] = Field(None, description="Relationship override")
    context_length: int = Field(10, description="Context length")
    include_thinking: bool = Field(True, description="Include thinking prompt")


@ai_router.post("/test-chat")
async def test_chat(request: ChatTestRequest, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Test AI character chat functionality.

    Args:
        request: Chat test request parameters
        db: Database session

    Returns:
        Test result with conversation data and performance metrics
    """
    try:
        manager = AITestManager(db)
        result = await manager.test_character_chat(
            character_qiao_id=request.character_qiao_id,
            user_qiao_id=request.user_qiao_id,
            llm_config_key=request.llm_config_key,
            test_message=request.test_message,
            enable_thinking=request.enable_thinking,
            test_session_id=request.test_session_id,
        )

        return format_success_response(result, "AI对话测试完成")

    except ValueError as e:
        logger.warning("ai_chat_test_validation_error", error=str(e))
        return format_error_response("VALIDATION_ERROR", str(e))
    except Exception as e:
        logger.error("ai_chat_test_error", error=str(e))
        return format_error_response("AI_CHAT_TEST_ERROR", "AI对话测试失败")


@ai_router.post("/test-algorithm")
async def test_algorithm(
    request: AlgorithmTestRequest, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Test score algorithm functionality.

    Args:
        request: Algorithm test request parameters
        db: Database session

    Returns:
        Algorithm test result with calculation details
    """
    try:
        manager = AITestManager(db)
        result = await manager.test_score_algorithm(
            algorithm=request.algorithm,
            score=request.score,
            initial_position=request.initial_position,
            params=request.params,
            batch_test=request.batch_test,
        )

        return format_success_response(result, "分数算法测试完成")

    except ValueError as e:
        logger.warning("algorithm_test_validation_error", error=str(e))
        return format_error_response("ALGORITHM_VALIDATION_FAILED", str(e))
    except Exception as e:
        logger.error("algorithm_test_error", error=str(e))
        return format_error_response("ALGORITHM_TEST_ERROR", "分数算法测试失败")


@ai_router.post("/test-prompt")
async def test_prompt(request: PromptTestRequest, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Test prompt preview functionality.

    Args:
        request: Prompt test request parameters
        db: Database session

    Returns:
        Prompt preview result with placeholder information
    """
    try:
        manager = AITestManager(db)
        result = await manager.test_prompt_preview(
            character_qiao_id=request.character_qiao_id,
            user_qiao_id=request.user_qiao_id,
            relationship_override=request.relationship_override,
            context_length=request.context_length,
            include_thinking=request.include_thinking,
        )

        return format_success_response(result, "提示词预览生成完成")

    except ValueError as e:
        logger.warning("prompt_test_validation_error", error=str(e))
        return format_error_response("VALIDATION_ERROR", str(e))
    except Exception as e:
        logger.error("prompt_test_error", error=str(e))
        return format_error_response("PROMPT_TEST_ERROR", "提示词预览生成失败")
