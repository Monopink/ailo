"""Admin navigation helpers for preserving list state across views."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit

from starlette.requests import Request


def _admin_base_path(request: Request) -> str:
    """Return mounted admin base path without trailing slash (except root)."""
    route_name = str(request.app.state.ROUTE_NAME)
    base_path = str(request.url_for(route_name + ":index").path).rstrip("/")
    return base_path or "/"


def _normalize_internal_path(raw_path: str, raw_query: str) -> str:
    """Normalize query string and rebuild relative URL path."""
    query = urlencode(parse_qsl(raw_query, keep_blank_values=True), doseq=True)
    return f"{raw_path}?{query}" if query else raw_path


def get_admin_next_url(request: Request) -> str | None:
    """Read and validate `next` query parameter for safe in-admin redirects."""
    raw_next = request.query_params.get("next")
    if not raw_next:
        return None

    parsed = urlsplit(raw_next)
    if parsed.scheme or parsed.netloc:
        return None
    if not parsed.path.startswith("/"):
        return None

    base_path = _admin_base_path(request)
    is_in_admin_scope = parsed.path == base_path or parsed.path.startswith(f"{base_path}/")
    if not is_in_admin_scope:
        return None

    return _normalize_internal_path(parsed.path, parsed.query)


def get_admin_list_url(request: Request, identity: str) -> str:
    """Resolve list URL with validated `next` fallback if present."""
    fallback = str(request.url_for(str(request.app.state.ROUTE_NAME) + ":list", identity=identity))
    return get_admin_next_url(request) or fallback
