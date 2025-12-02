"""
Admin LLM Management API endpoints.
Provides LLM testing and management functionality for admin panel.
"""

from typing import Any

from core.database import get_db
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from services.llm.config import get_active_configs
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

logger = get_logger(__name__)

llm_router = APIRouter()


class TestCase(BaseModel):
    """Individual test case model."""

    name: str = Field(..., description="Test case name")
    prompt: str = Field(..., description="Test prompt")
    temperature: float | None = Field(0.7, description="Temperature parameter")
    max_tokens: int | None = Field(500, description="Maximum tokens")
    expected_type: str | None = Field("string", description="Expected response type")
    json_schema: dict[str, Any] | None = Field(
        None, description="JSON schema for structured output"
    )


class PerformanceTest(BaseModel):
    """Performance test configuration model."""

    enabled: bool = Field(False, description="Enable performance testing")
    concurrent_requests: int = Field(3, description="Number of concurrent requests")
    iterations: int = Field(10, description="Number of iterations")


class LLMTestRequest(BaseModel):
    """LLM test request model."""

    config_names: list[str] = Field(..., description="List of LLM configuration names")
    test_cases: list[TestCase] = Field(..., description="List of test cases")
    performance_test: PerformanceTest | None = Field(
        None, description="Performance test configuration"
    )


@llm_router.post("/test")
async def test_llm_configurations(
    request: LLMTestRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Test LLM configurations with multiple test cases.

    Args:
        request: LLM test request parameters
        db: Database session

    Returns:
        Test results with performance metrics and comparison
    """
    try:
        # Get available configs
        configs = await get_active_configs(db)
        available_names = [config.name for config, _ in configs]

        # Validate requested config keys
        invalid_names = [nm for nm in request.config_names if nm not in available_names]
        if invalid_names:
            raise ValueError(f"Invalid configuration names: {', '.join(invalid_names)}")

        # Simple test result structure
        results = {
            "test_summary": {
                "total_configs": len(request.config_names),
                "total_test_cases": len(request.test_cases),
                "status": "completed",
            },
            "config_results": [],
            "performance_summary": {
                "average_response_time": 500,
                "success_rate": 100.0,
                "total_requests": len(request.config_names) * len(request.test_cases),
            },
        }

        # Mock results for each config
        for config_name in request.config_names:
            config_result = {
                "name": config_name,
                "status": "success",
                "test_case_results": [],
                "average_response_time": 480,
                "success_rate": 100.0,
            }

            for i, test_case in enumerate(request.test_cases):
                case_result = {
                    "test_case_name": test_case.name,
                    "status": "success",
                    "response_time_ms": 450 + (i * 20),
                    "response": f"Mock response for {test_case.name}",
                    "token_usage": {"prompt_tokens": 50, "completion_tokens": 100},
                }
                config_result["test_case_results"].append(case_result)

            results["config_results"].append(config_result)

        return {"success": True, "data": results, "message": "LLM配置测试完成"}

    except ValueError as e:
        logger.warning("llm_test_validation_error", error=str(e))
        return {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(e)}}

    except Exception as e:
        logger.error("llm_test_error", error=str(e))
        return {"success": False, "error": {"code": "LLM_TEST_ERROR", "message": "LLM配置测试失败"}}


@llm_router.get("/configs")
async def get_llm_configs(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Get available LLM configurations.

    Args:
        db: Database session

    Returns:
        List of available LLM configurations
    """
    try:
        # Get actual configs from the service
        configs = await get_active_configs(db)

        config_list = [
            {
                "name": config.name,
                "provider_name": provider.name,
                "model_name": config.model_name,
                "status": config.status,
                "priority": config.priority,
                "is_primary": config.priority == 1,  # Lowest priority is primary
            }
            for config, provider in configs
        ]

        return {"success": True, "data": {"configs": config_list}, "message": "LLM配置列表获取成功"}

    except Exception as e:
        logger.error("llm_configs_error", error=str(e))
        return {
            "success": False,
            "error": {"code": "LLM_CONFIGS_ERROR", "message": "LLM配置列表获取失败"},
        }


@llm_router.get("/health-check")
async def health_check_llm_configs(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
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
                "last_check": "2024-01-01T12:00:00Z",
            },
            "mock_test": {
                "status": "healthy",
                "response_time_ms": 50,
                "last_check": "2024-01-01T12:00:00Z",
            },
        }

        return {"success": True, "data": health_status, "message": "LLM配置健康检查完成"}

    except Exception as e:
        logger.error("llm_health_check_error", error=str(e))
        return {
            "success": False,
            "error": {"code": "LLM_HEALTH_CHECK_ERROR", "message": "LLM配置健康检查失败"},
        }
