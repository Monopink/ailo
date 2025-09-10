"""
LLM Test Manager.
Manages LLM testing business processes including configuration testing
and performance evaluation.
"""

import time
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from services.llm.client import chat_completion
from ..utils.validation_utils import validate_llm_test_request
from ..utils.calculation_utils import (
    calculate_performance_metrics,
    format_test_case_result,
)
from utils.logging import get_logger

logger = get_logger(__name__)


class LLMTestManager:
    """
    Manages LLM testing business processes.

    Handles LLM configuration testing, performance evaluation,
    and result aggregation.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize LLM test manager.

        Args:
            db: Database session
        """
        self.db = db

    async def test_configurations(
        self,
        config_keys: List[str],
        test_cases: List[Dict[str, Any]],
        performance_test: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Test LLM configurations with multiple test cases.

        Args:
            config_keys: List of LLM configuration keys to test
            test_cases: List of test cases to run
            performance_test: Optional performance test configuration

        Returns:
            Test results with performance metrics

        Raises:
            ValueError: If validation fails
            Exception: If test execution fails
        """
        # Validate request parameters
        validation_errors = validate_llm_test_request(config_keys, test_cases)
        if validation_errors:
            raise ValueError(f"Validation failed: {', '.join(validation_errors)}")

        try:
            test_results = []

            # Test each configuration
            for config_key in config_keys:
                config_result = await self._test_single_configuration(
                    config_key, test_cases, performance_test
                )
                test_results.append(config_result)

            # Generate comparison if multiple configs
            comparison = None
            if len(test_results) > 1:
                comparison = self._generate_comparison(test_results)

            result = {
                "test_results": test_results,
                "comparison": comparison,
                "test_metadata": {
                    "timestamp": int(time.time()),
                    "test_id": f"llm_test_{int(time.time())}",
                    "total_configs": len(config_keys),
                    "total_test_cases": len(test_cases),
                },
            }

            logger.info(
                "llm_configuration_test_completed",
                config_keys=config_keys,
                test_cases_count=len(test_cases),
                total_results=len(test_results),
            )

            return result

        except Exception as e:
            logger.error(
                "llm_configuration_test_failed",
                config_keys=config_keys,
                error=str(e),
                exc_info=True,
            )
            raise

    async def _test_single_configuration(
        self,
        config_key: str,
        test_cases: List[Dict[str, Any]],
        performance_test: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Test a single LLM configuration.

        Args:
            config_key: LLM configuration key
            test_cases: List of test cases
            performance_test: Optional performance test configuration

        Returns:
            Configuration test result
        """
        test_case_results = []
        response_times = []
        success_count = 0
        token_usage_list = []

        # Run each test case
        for test_case in test_cases:
            try:
                start_time = time.time()

                # Prepare LLM request
                messages = [{"role": "user", "content": test_case["prompt"]}]

                # Call LLM
                llm_result = await chat_completion(
                    db=self.db,
                    messages=messages,
                    config_key=config_key,
                    temperature=test_case.get("temperature", 0.7),
                    max_tokens=test_case.get("max_tokens", 500),
                    json_schema=test_case.get("json_schema"),
                )

                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000

                if llm_result.get("success", False):
                    success_count += 1
                    response_times.append(response_time_ms)
                    token_usage_list.append(llm_result.get("usage", {}))

                    test_case_result = format_test_case_result(
                        test_case=test_case,
                        success=True,
                        response=llm_result.get("response"),
                        response_time_ms=response_time_ms,
                        token_usage=llm_result.get("usage", {}),
                    )
                else:
                    test_case_result = format_test_case_result(
                        test_case=test_case,
                        success=False,
                        response=None,
                        response_time_ms=response_time_ms,
                        token_usage={},
                        error=llm_result.get("error", "Unknown error"),
                    )

                test_case_results.append(test_case_result)

            except Exception as e:
                logger.warning(
                    "llm_test_case_failed",
                    config_key=config_key,
                    test_case_name=test_case.get("name", "Unknown"),
                    error=str(e),
                )

                test_case_result = format_test_case_result(
                    test_case=test_case,
                    success=False,
                    response=None,
                    response_time_ms=0,
                    token_usage={},
                    error=str(e),
                )
                test_case_results.append(test_case_result)

        # Calculate performance metrics
        performance_metrics = calculate_performance_metrics(
            response_times=response_times,
            success_count=success_count,
            total_count=len(test_cases),
            token_usage_list=token_usage_list,
        )

        return {
            "config_key": config_key,
            "test_cases": test_case_results,
            "performance_metrics": performance_metrics,
        }

    def _generate_comparison(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate comparison between multiple configuration test results.

        Args:
            test_results: List of configuration test results

        Returns:
            Comparison analysis
        """
        if not test_results:
            return {}

        # Find fastest configuration
        fastest_config = min(test_results, key=lambda x: x["performance_metrics"]["avg_response_time"])

        # Find most reliable configuration
        most_reliable_config = max(test_results, key=lambda x: x["performance_metrics"]["success_rate"])

        # Calculate total costs (placeholder)
        cost_analysis = {
            config["config_key"]: {
                "total_tokens": config["performance_metrics"]["total_tokens"],
                "estimated_cost": config["performance_metrics"]["total_tokens"] * 0.001,  # Placeholder
            }
            for config in test_results
        }

        return {
            "fastest_config": fastest_config["config_key"],
            "most_reliable_config": most_reliable_config["config_key"],
            "cost_analysis": cost_analysis,
        }
