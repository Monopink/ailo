"""
Admin LLM Management API endpoints.
Provides LLM testing and management functionality for admin panel.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

from core.database import get_db
from services.admin.managers.llm_test_manager import LLMTestManager
from services.admin.utils.response_formatter import (
    format_success_response,
    format_error_response,
)
from utils.logging import get_logger

logger = get_logger(__name__)

llm_router = APIRouter()


class TestCase(BaseModel):
    """Individual test case model."""
    name: str = Field(..., description="Test case name")
    prompt: str = Field(..., description="Test prompt")
    temperature: Optional[float] = Field(0.7, description="Temperature parameter")
    max_tokens: Optional[int] = Field(500, description="Maximum tokens")
    expected_type: Optional[str] = Field("string", description="Expected response type")
    json_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema for structured output")


class PerformanceTest(BaseModel):
    """Performance test configuration model."""
    enabled: bool = Field(False, description="Enable performance testing")
    concurrent_requests: int = Field(3, description="Number of concurrent requests")
    iterations: int = Field(10, description="Number of iterations")


class LLMTestRequest(BaseModel):
    """LLM test request model."""
    config_keys: List[str] = Field(..., description="List of LLM configuration keys")
    test_cases: List[TestCase] = Field(..., description="List of test cases")
    performance_test: Optional[PerformanceTest] = Field(None, description="Performance test configuration")


@llm_router.post("/test")
async def test_llm_configurations(
    request: LLMTestRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Test LLM configurations with multiple test cases.
    
    Args:
        request: LLM test request parameters
        db: Database session
        
    Returns:
        Test results with performance metrics and comparison
    """
    try:
        manager = LLMTestManager(db)
        
        # Convert Pydantic models to dictionaries
        test_cases = [test_case.dict() for test_case in request.test_cases]
        performance_test = request.performance_test.dict() if request.performance_test else None
        
        result = await manager.test_configurations(
            config_keys=request.config_keys,
            test_cases=test_cases,
            performance_test=performance_test
        )
        
        return format_success_response(result, "LLM配置测试完成")
        
    except ValueError as e:
        logger.warning("llm_test_validation_error", error=str(e))
        return format_error_response("VALIDATION_ERROR", str(e))
        
    except Exception as e:
        logger.error("llm_test_error", error=str(e))
        return format_error_response("LLM_TEST_ERROR", "LLM配置测试失败")


@llm_router.get("/configs")
async def get_llm_configs(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get available LLM configurations.
    
    Args:
        db: Database session
        
    Returns:
        List of available LLM configurations
    """
    try:
        # TODO: Implement actual config retrieval from database
        # This is a placeholder implementation
        configs = [
            {
                "config_key": "doubao_primary",
                "provider_name": "doubao",
                "model_name": "doubao-pro-4k",
                "status": 1,
                "priority": 1,
                "is_primary": True
            },
            {
                "config_key": "mock_test",
                "provider_name": "mock",
                "model_name": "mock-model-v1",
                "status": 1,
                "priority": 99,
                "is_primary": False
            }
        ]
        
        return format_success_response({"configs": configs}, "LLM配置列表获取成功")
        
    except Exception as e:
        logger.error("llm_configs_error", error=str(e))
        return format_error_response("LLM_CONFIGS_ERROR", "LLM配置列表获取失败")


@llm_router.get("/health-check")
async def health_check_llm_configs(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Check health status of all LLM configurations.
    
    Args:
        db: Database session
        
    Returns:
        Health status of all LLM configurations
    """
    try:
        # TODO: Implement actual health check
        # This is a placeholder implementation
        health_status = {
            "doubao_primary": {
                "status": "healthy",
                "response_time_ms": 850,
                "last_check": "2024-01-01T12:00:00Z"
            },
            "mock_test": {
                "status": "healthy", 
                "response_time_ms": 50,
                "last_check": "2024-01-01T12:00:00Z"
            }
        }
        
        return format_success_response(health_status, "LLM配置健康检查完成")
        
    except Exception as e:
        logger.error("llm_health_check_error", error=str(e))
        return format_error_response("LLM_HEALTH_CHECK_ERROR", "LLM配置健康检查失败")
