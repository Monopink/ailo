"""App page related models."""

from sqlalchemy import (
    CheckConstraint,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SnowflakeModel


class AppPage(SnowflakeModel):
    """Rendered app pages for client display."""

    __tablename__ = "app_pages"
    __table_args__ = (
        UniqueConstraint(
            "page_key",
            "client_type",
            "locale",
            name="uq_app_pages_page_client_locale",
        ),
        CheckConstraint(
            "client_type IN ('mini-program')",
            name="ck_app_pages_client_type",
        ),
        CheckConstraint(
            "locale IN ('zh-CN')",
            name="ck_app_pages_locale",
        ),
        CheckConstraint(
            "page_category IN (1, 2)",
            name="ck_app_pages_page_category",
        ),
        CheckConstraint(
            "source_type IN (1, 2)",
            name="ck_app_pages_source_type",
        ),
        CheckConstraint("status IN (1, 2)", name="ck_app_pages_status"),
    )

    page_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="Page key")
    client_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Client type from X-Client"
    )
    locale: Mapped[str] = mapped_column(String(16), nullable=False, comment="Locale")
    page_category: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="1=policy,2=info"
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="Page title")
    source_type: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="1=markdown,2=html"
    )
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Markdown content")
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True, comment="HTML content")
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="1=active,2=inactive",
    )
