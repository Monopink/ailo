"""Business logic for app page APIs and admin rendering."""

from __future__ import annotations

import re

from markdown_it import MarkdownIt
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AppPageCategory, AppPageSourceType, ClientType, LocaleCode
from app.models.content import AppPage
from app.schemas.app_page import AppPageResponse
from app.services.pages import data as page_data

DEFAULT_PAGE_LOCALE = LocaleCode.ZH_CN.value
CONTENT_RENDERED_FORMAT_HTML = "html"
DEFAULT_CLIENT_TYPE = ClientType.MINI_PROGRAM.value

_PAGE_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MARKDOWN_RENDERER = MarkdownIt(
    "commonmark",
    {
        "html": False,
        "linkify": False,
        "typographer": False,
    },
).enable("table")
_STYLE_ATTR_PATTERN = re.compile(
    r"(?P<prefix>\sstyle\s*=\s*)(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.IGNORECASE,
)
_MARKDOWN_TAG_INLINE_STYLES: dict[str, str] = {
    "h1": "margin: 0 0 16px; font-size: 22px; line-height: 1.4; font-weight: 700; color: #111827;",
    "h2": "margin: 0 0 14px; font-size: 20px; line-height: 1.45; font-weight: 700; color: #111827;",
    "h3": "margin: 0 0 12px; font-size: 18px; line-height: 1.5; font-weight: 600; color: #111827;",
    "h4": "margin: 0 0 10px; font-size: 16px; line-height: 1.5; font-weight: 600; color: #111827;",
    "p": "margin: 0 0 12px; font-size: 15px; line-height: 1.75; color: #374151;",
    "ul": "margin: 0 0 12px; padding-left: 22px;",
    "ol": "margin: 0 0 12px; padding-left: 22px;",
    "li": "margin: 0 0 8px; font-size: 15px; line-height: 1.75; color: #374151;",
    "table": (
        "width: 100%; margin: 0 0 16px; border-collapse: collapse; table-layout: fixed; "
        "font-size: 14px; line-height: 1.6; color: #374151;"
    ),
    "th": (
        "padding: 8px 10px; border: 1px solid #d1d5db; background-color: #f3f4f6; "
        "font-weight: 600; text-align: left; vertical-align: top;"
    ),
    "td": (
        "padding: 8px 10px; border: 1px solid #d1d5db; vertical-align: top; word-break: break-word;"
    ),
    "blockquote": (
        "margin: 0 0 12px; padding: 8px 12px; border-left: 4px solid #d1d5db; "
        "color: #4b5563; background-color: #f9fafb;"
    ),
    "pre": (
        "margin: 0 0 12px; padding: 10px 12px; overflow-x: auto; border-radius: 8px; "
        "background-color: #111827; color: #f9fafb;"
    ),
    "code": (
        "padding: 2px 4px; border-radius: 4px; background-color: #f3f4f6; "
        "font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;"
    ),
}
_SCRIPT_STYLE_BLOCK_PATTERN = re.compile(
    r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL
)
_EVENT_HANDLER_ATTR_PATTERN = re.compile(
    r"\s+on[a-zA-Z0-9_:-]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)
_JAVASCRIPT_URL_ATTR_PATTERN = re.compile(
    r"\s+(href|src)\s*=\s*(['\"])\s*javascript:[^'\"]*\2",
    re.IGNORECASE,
)


class AppPageValidationError(ValueError):
    """Raised when app page inputs are invalid."""


class AppPageNotFoundError(LookupError):
    """Raised when requested app pages are missing."""


def _merge_inline_style(attrs: str, style: str) -> str:
    style_match = _STYLE_ATTR_PATTERN.search(attrs)
    if style_match is None:
        return f'{attrs} style="{style}"'

    existing_style = style_match.group("value").strip()
    merged_style = style if not existing_style else f"{existing_style.rstrip(';')}; {style}"
    replacement = (
        f"{style_match.group('prefix')}"
        f"{style_match.group('quote')}"
        f"{merged_style}"
        f"{style_match.group('quote')}"
    )
    return _STYLE_ATTR_PATTERN.sub(replacement, attrs, count=1)


def apply_markdown_typography_styles(content_html: str) -> str:
    """Inject inline typography/table styles into rendered markdown tags."""
    styled = content_html
    for tag, style in _MARKDOWN_TAG_INLINE_STYLES.items():
        opening_tag_pattern = re.compile(rf"<{tag}(?P<attrs>\s[^>]*)?>", re.IGNORECASE)

        def _replace(
            match: re.Match[str], current_tag: str = tag, current_style: str = style
        ) -> str:
            attrs = match.group("attrs") or ""
            return f"<{current_tag}{_merge_inline_style(attrs, current_style)}>"

        styled = opening_tag_pattern.sub(_replace, styled)
    return styled


def normalize_client_type(client_type: str) -> str:
    """Normalize and validate client type."""
    normalized = client_type.strip().lower()
    if not normalized:
        raise AppPageValidationError("invalid client type")
    try:
        return ClientType(normalized).value
    except ValueError as exc:
        raise AppPageValidationError("invalid client type") from exc


def normalize_locale(locale: str) -> str:
    """Normalize and validate locale."""
    normalized = locale.strip()
    if not normalized:
        raise AppPageValidationError("invalid locale")
    try:
        return LocaleCode(normalized).value
    except ValueError as exc:
        raise AppPageValidationError("invalid locale") from exc


def normalize_page_key(page_key: str) -> str:
    """Normalize and validate page key."""
    normalized = page_key.strip().lower()
    if not normalized or not _PAGE_KEY_PATTERN.match(normalized):
        raise AppPageValidationError("invalid page key")
    return normalized


def parse_page_keys(raw_page_keys: str) -> list[str]:
    """Parse batch page_keys into deduplicated ordered keys."""
    if not raw_page_keys or not raw_page_keys.strip():
        raise AppPageValidationError("page_keys is required")

    ordered_keys: list[str] = []
    seen: set[str] = set()
    for item in raw_page_keys.split(","):
        key = normalize_page_key(item)
        if key in seen:
            continue
        seen.add(key)
        ordered_keys.append(key)

    if not ordered_keys:
        raise AppPageValidationError("page_keys is required")
    return ordered_keys


def render_markdown_to_html(content_md: str) -> str:
    """Render markdown to HTML for storage."""
    if not content_md or not content_md.strip():
        return ""

    rendered = str(_MARKDOWN_RENDERER.render(content_md)).strip()
    return apply_markdown_typography_styles(rendered)


def sanitize_html(content_html: str) -> str:
    """Sanitize HTML content before persistence."""
    if not content_html:
        return ""

    sanitized = _SCRIPT_STYLE_BLOCK_PATTERN.sub("", content_html)
    sanitized = _EVENT_HANDLER_ATTR_PATTERN.sub("", sanitized)
    sanitized = _JAVASCRIPT_URL_ATTR_PATTERN.sub("", sanitized)
    return sanitized.strip()


def normalize_page_category(raw_value: int | str) -> int:
    """Normalize and validate page category."""
    try:
        return AppPageCategory(int(raw_value)).value
    except (TypeError, ValueError) as exc:
        raise AppPageValidationError("invalid page category") from exc


def normalize_source_type(raw_value: int | str) -> int:
    """Normalize and validate source type."""
    try:
        return AppPageSourceType(int(raw_value)).value
    except (TypeError, ValueError) as exc:
        raise AppPageValidationError("invalid source type") from exc


def resolve_page_contents(
    *,
    source_type: int,
    content_md: str | None,
    content_html: str | None,
) -> tuple[str, str]:
    """Resolve persisted markdown/html content based on source type policy."""
    normalized_md = str(content_md or "")
    normalized_html = str(content_html or "")

    if source_type == AppPageSourceType.MARKDOWN.value:
        generated_html = render_markdown_to_html(normalized_md)
        return normalized_md, sanitize_html(generated_html)

    if source_type == AppPageSourceType.HTML.value:
        return normalized_md, sanitize_html(normalized_html)

    raise AppPageValidationError("invalid source type")


def _to_response(page: AppPage) -> AppPageResponse:
    return AppPageResponse(
        page_key=page.page_key,
        page_category=page.page_category,
        title=str(page.title or ""),
        locale=page.locale,
        content_rendered_format=CONTENT_RENDERED_FORMAT_HTML,
        content_rendered=str(page.content_html or ""),
        updated_at=page.updated_at,
    )


async def get_pages(
    db: AsyncSession,
    *,
    client_type: str,
    raw_page_keys: str,
) -> list[AppPageResponse]:
    """Get app pages by page_keys with all-or-nothing semantics."""
    normalized_client = normalize_client_type(client_type)
    page_keys = parse_page_keys(raw_page_keys)

    pages = await page_data.get_active_pages_by_keys(
        db,
        client_type=normalized_client,
        locale=DEFAULT_PAGE_LOCALE,
        page_keys=page_keys,
    )

    page_map = {page.page_key: page for page in pages}
    missing_page_keys = [page_key for page_key in page_keys if page_key not in page_map]
    if missing_page_keys:
        raise AppPageNotFoundError("missing app pages")

    return [_to_response(page_map[page_key]) for page_key in page_keys]


async def get_page(
    db: AsyncSession,
    *,
    client_type: str,
    page_key: str,
) -> AppPageResponse:
    """Get a single app page by key."""
    normalized_client = normalize_client_type(client_type)
    normalized_key = normalize_page_key(page_key)

    page = await page_data.get_active_page_by_key(
        db,
        client_type=normalized_client,
        locale=DEFAULT_PAGE_LOCALE,
        page_key=normalized_key,
    )
    if page is None:
        raise AppPageNotFoundError("app page not found")

    return _to_response(page)
