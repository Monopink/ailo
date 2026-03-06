"""Data access layer for app page queries."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AppPageStatus
from app.models.content import AppPage


async def get_active_pages_by_keys(
    db: AsyncSession,
    *,
    client_type: str,
    locale: str,
    page_keys: list[str],
) -> list[AppPage]:
    """Fetch active app pages by keys."""
    if not page_keys:
        return []

    stmt = (
        select(AppPage)
        .where(
            AppPage.client_type == client_type,
            AppPage.locale == locale,
            AppPage.status == AppPageStatus.ACTIVE,
            AppPage.page_key.in_(page_keys),
        )
        .order_by(AppPage.updated_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_active_page_by_key(
    db: AsyncSession,
    *,
    client_type: str,
    locale: str,
    page_key: str,
) -> AppPage | None:
    """Fetch one active app page by key."""
    stmt = select(AppPage).where(
        AppPage.client_type == client_type,
        AppPage.locale == locale,
        AppPage.status == AppPageStatus.ACTIVE,
        AppPage.page_key == page_key,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
