"""Command entry for conversation archive maintenance job."""

from __future__ import annotations

import asyncio
import sys

from app.core.database import close_database
from app.exceptions import ConfigurationError, MissingConfigurationError
from app.services.ai.conversation_archiving import run_conversation_archive_job
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def _run() -> int:
    try:
        stats = await run_conversation_archive_job()
        if stats is None:
            return 0

        logger.info(
            "conversation_archive_completed",
            rounds=stats.rounds,
            scan_sessions_count=stats.scan_sessions_count,
            candidates_count=stats.candidates_count,
            archived_count=stats.archived_count,
            deleted_count=stats.deleted_count,
            duration_ms=stats.duration_ms,
            last_success_at=stats.last_success_at,
        )
        return 0
    except (MissingConfigurationError, ConfigurationError, ValueError) as exc:
        logger.error(
            "conversation_archive_failed",
            failure_reason=str(exc),
            exc_info=True,
        )
        return 2
    except Exception as exc:  # pragma: no cover - defensive boundary for job entry
        logger.error(
            "conversation_archive_failed",
            failure_reason=str(exc),
            exc_info=True,
        )
        return 1
    finally:
        await close_database()


def main() -> int:
    """Run conversation archive job once."""
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
