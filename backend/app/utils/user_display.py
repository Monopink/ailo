"""User display label helpers."""

from __future__ import annotations

from app.utils.email import mask_email
from app.utils.phone import mask_phone


def build_masked_user_display_label(
    *,
    user_id: int,
    username: str | None,
    phone: str | None,
    email: str | None,
) -> str:
    """Build one display label with masked phone/email for admin selection UIs."""
    parts: list[str] = [f"[{user_id}]"]
    if isinstance(username, str) and username.strip() != "":
        parts.append(username.strip())
    if isinstance(phone, str) and phone.strip() != "":
        parts.append(mask_phone(phone.strip()))
    if isinstance(email, str) and email.strip() != "":
        parts.append(mask_email(email.strip()))
    return " | ".join(parts)
