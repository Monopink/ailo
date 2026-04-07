"""
Avatar image normalization helpers for admin/profile flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from fastapi import HTTPException
from PIL import (
    Image,
    ImageOps,
    UnidentifiedImageError,
)

AVATAR_OUTPUT_SIZE = 512
AVATAR_OUTPUT_MIME = "image/webp"
AVATAR_OUTPUT_QUALITY = 80


@dataclass(frozen=True)
class AvatarCrop:
    """Square crop box in source image pixel coordinates."""

    x: int
    y: int
    size: int


def normalize_avatar_image(
    *, file_bytes: bytes, mime_type: str, crop: AvatarCrop | None
) -> tuple[bytes, str]:
    """
    Normalize image into fixed avatar output.

    Output format is always WebP 512x512.
    """
    del mime_type

    try:
        with Image.open(BytesIO(file_bytes)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGBA")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=415, detail="不支持的文件格式") from exc

    width, height = image.size
    if width <= 0 or height <= 0:
        raise HTTPException(status_code=400, detail="图片处理失败")

    left, top, right, bottom = _resolve_crop_box(width=width, height=height, crop=crop)
    square = image.crop((left, top, right, bottom))
    resized = square.resize((AVATAR_OUTPUT_SIZE, AVATAR_OUTPUT_SIZE), Image.Resampling.LANCZOS)

    out = BytesIO()
    resized.save(out, format="WEBP", quality=AVATAR_OUTPUT_QUALITY, method=6)
    return out.getvalue(), AVATAR_OUTPUT_MIME


def _resolve_crop_box(
    *, width: int, height: int, crop: AvatarCrop | None
) -> tuple[int, int, int, int]:
    side = min(width, height)
    default_left = (width - side) // 2
    default_top = (height - side) // 2

    if crop is None:
        return default_left, default_top, default_left + side, default_top + side

    if crop.size <= 0:
        return default_left, default_top, default_left + side, default_top + side

    crop_side = min(crop.size, width, height)
    left = max(0, min(crop.x, width - crop_side))
    top = max(0, min(crop.y, height - crop_side))
    return left, top, left + crop_side, top + crop_side
