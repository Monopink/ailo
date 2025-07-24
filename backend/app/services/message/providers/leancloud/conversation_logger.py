"""
Enhanced logging utilities for conversation-related operations.

Provides structured logging specifically for conversation ID management,
health checks, and error tracking.
"""

import time
from typing import Optional, Dict, Any
from utils.logging import get_logger

logger = get_logger(__name__)


class ConversationLogger:
    """
    Specialized logger for conversation-related operations.

    Provides consistent, structured logging for conversation ID management,
    health checks, error tracking, and performance monitoring.
    """

    def __init__(self, service_name: str = "backend"):
        self.service_name = service_name
        self.logger = get_logger(f"{__name__}.{service_name}")

    def log_conversation_created(
        self, conversation_id: str, creation_method: str, duration_ms: Optional[int] = None, **kwargs
    ):
        """Log successful conversation creation"""
        self.logger.info(
            "conversation_created",
            conversation_id=conversation_id,
            creation_method=creation_method,
            duration_ms=duration_ms,
            service=self.service_name,
            **kwargs,
        )

    def log_conversation_creation_failed(
        self, error: str, creation_method: str, duration_ms: Optional[int] = None, **kwargs
    ):
        """Log failed conversation creation"""
        self.logger.error(
            "conversation_creation_failed",
            error=error,
            creation_method=creation_method,
            duration_ms=duration_ms,
            service=self.service_name,
            **kwargs,
        )

    def log_conversation_health_check(
        self,
        conversation_id: str,
        is_healthy: bool,
        check_duration_ms: int,
        error: Optional[str] = None,
        **kwargs,
    ):
        """Log conversation health check results"""
        log_level = "info" if is_healthy else "warning"
        getattr(self.logger, log_level)(
            "conversation_health_check",
            conversation_id=conversation_id,
            is_healthy=is_healthy,
            check_duration_ms=check_duration_ms,
            error=error,
            service=self.service_name,
            **kwargs,
        )

    def log_conversation_access_attempt(
        self,
        conversation_id: str,
        operation: str,
        success: bool,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None,
        **kwargs,
    ):
        """Log conversation access attempts"""
        log_level = "debug" if success else "warning"
        getattr(self.logger, log_level)(
            "conversation_access_attempt",
            conversation_id=conversation_id,
            operation=operation,
            success=success,
            duration_ms=duration_ms,
            error=error,
            service=self.service_name,
            **kwargs,
        )

    def log_conversation_cache_operation(
        self, operation: str, conversation_id: Optional[str] = None, reason: Optional[str] = None, **kwargs
    ):
        """Log conversation cache operations"""
        self.logger.debug(
            "conversation_cache_operation",
            operation=operation,
            conversation_id=conversation_id,
            reason=reason,
            service=self.service_name,
            **kwargs,
        )

    def log_frontend_error_report(
        self,
        error_type: int,
        conversation_id: str,
        error_message: str,
        retry_count: int,
        user_agent: str,
        **kwargs,
    ):
        """Log frontend error reports"""
        self.logger.warning(
            "frontend_error_report_received",
            error_type=error_type,
            conversation_id=conversation_id,
            error_message=error_message,
            retry_count=retry_count,
            user_agent=user_agent,
            service=self.service_name,
            **kwargs,
        )

    def log_conversation_recovery_attempt(
        self,
        conversation_id: str,
        recovery_method: str,
        success: bool,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None,
        **kwargs,
    ):
        """Log conversation recovery attempts"""
        log_level = "info" if success else "error"
        getattr(self.logger, log_level)(
            "conversation_recovery_attempt",
            conversation_id=conversation_id,
            recovery_method=recovery_method,
            success=success,
            duration_ms=duration_ms,
            error=error,
            service=self.service_name,
            **kwargs,
        )

    def log_api_call_performance(
        self,
        api_endpoint: str,
        method: str,
        status_code: int,
        duration_ms: int,
        conversation_id: Optional[str] = None,
        **kwargs,
    ):
        """Log LeanCloud API call performance"""
        log_level = "debug" if 200 <= status_code < 300 else "warning"
        getattr(self.logger, log_level)(
            "leancloud_api_call",
            api_endpoint=api_endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            conversation_id=conversation_id,
            service=self.service_name,
            **kwargs,
        )

    def log_health_monitoring_status(
        self,
        is_monitoring: bool,
        check_interval: int,
        last_check_time: Optional[str] = None,
        total_checks: int = 0,
        failure_count: int = 0,
        **kwargs,
    ):
        """Log health monitoring status"""
        self.logger.info(
            "health_monitoring_status",
            is_monitoring=is_monitoring,
            check_interval_seconds=check_interval,
            last_check_time=last_check_time,
            total_checks=total_checks,
            failure_count=failure_count,
            service=self.service_name,
            **kwargs,
        )

    def log_configuration_status(
        self,
        conversation_configured: bool,
        leancloud_credentials_valid: bool,
        health_check_enabled: bool,
        **kwargs,
    ):
        """Log overall configuration status"""
        self.logger.info(
            "conversation_configuration_status",
            conversation_configured=conversation_configured,
            leancloud_credentials_valid=leancloud_credentials_valid,
            health_check_enabled=health_check_enabled,
            service=self.service_name,
            **kwargs,
        )


class ConversationMetrics:
    """
    Metrics collector for conversation-related operations.

    Tracks performance metrics, error rates, and health statistics
    for monitoring and alerting purposes.
    """

    def __init__(self):
        self.metrics = {
            "health_checks": {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "avg_duration_ms": 0,
                "last_check_time": None,
            },
            "api_calls": {"total": 0, "successful": 0, "failed": 0, "avg_duration_ms": 0},
            "frontend_reports": {"total": 0, "by_error_type": {}, "last_report_time": None},
            "conversation_operations": {"creations": 0, "cache_clears": 0, "recovery_attempts": 0},
        }
        self._durations = {"health_checks": [], "api_calls": []}

    def record_health_check(self, success: bool, duration_ms: int):
        """Record health check metrics"""
        self.metrics["health_checks"]["total"] += 1
        if success:
            self.metrics["health_checks"]["successful"] += 1
        else:
            self.metrics["health_checks"]["failed"] += 1

        self._durations["health_checks"].append(duration_ms)
        self._update_avg_duration("health_checks")
        self.metrics["health_checks"]["last_check_time"] = time.time()

    def record_api_call(self, success: bool, duration_ms: int):
        """Record API call metrics"""
        self.metrics["api_calls"]["total"] += 1
        if success:
            self.metrics["api_calls"]["successful"] += 1
        else:
            self.metrics["api_calls"]["failed"] += 1

        self._durations["api_calls"].append(duration_ms)
        self._update_avg_duration("api_calls")

    def record_frontend_report(self, error_type: int):
        """Record frontend error report metrics"""
        self.metrics["frontend_reports"]["total"] += 1

        if error_type not in self.metrics["frontend_reports"]["by_error_type"]:
            self.metrics["frontend_reports"]["by_error_type"][error_type] = 0
        self.metrics["frontend_reports"]["by_error_type"][error_type] += 1

        self.metrics["frontend_reports"]["last_report_time"] = time.time()

    def record_conversation_operation(self, operation_type: str):
        """Record conversation operation metrics"""
        if operation_type in self.metrics["conversation_operations"]:
            self.metrics["conversation_operations"][operation_type] += 1

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current metrics summary"""
        return {
            "health_check_success_rate": self._calculate_success_rate("health_checks"),
            "api_call_success_rate": self._calculate_success_rate("api_calls"),
            "total_frontend_reports": self.metrics["frontend_reports"]["total"],
            "avg_health_check_duration_ms": self.metrics["health_checks"]["avg_duration_ms"],
            "avg_api_call_duration_ms": self.metrics["api_calls"]["avg_duration_ms"],
            "conversation_operations": self.metrics["conversation_operations"].copy(),
            "last_health_check": self.metrics["health_checks"]["last_check_time"],
            "last_frontend_report": self.metrics["frontend_reports"]["last_report_time"],
        }

    def _calculate_success_rate(self, metric_type: str) -> float:
        """Calculate success rate for a metric type"""
        total = self.metrics[metric_type]["total"]
        if total == 0:
            return 0.0
        successful = self.metrics[metric_type]["successful"]
        return (successful / total) * 100

    def _update_avg_duration(self, metric_type: str):
        """Update average duration for a metric type"""
        durations = self._durations[metric_type]
        if durations:
            # Keep only last 100 measurements for rolling average
            if len(durations) > 100:
                durations = durations[-100:]
                self._durations[metric_type] = durations

            avg_duration = sum(durations) / len(durations)
            self.metrics[metric_type]["avg_duration_ms"] = round(avg_duration, 2)


# Global instances
conversation_logger = ConversationLogger()
conversation_metrics = ConversationMetrics()
