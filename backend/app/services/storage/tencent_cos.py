"""
Tencent Cloud COS storage backend (S3-compatible).
"""

from __future__ import annotations

import shutil
from datetime import timedelta
from typing import BinaryIO, cast

import fsspec

from app.services.storage.base import (
    StorageBackend,
    StorageError,
    StorageNotFoundError,
    StorageUploadError,
)


class TencentCOSBackend(StorageBackend):
    """Tencent COS implementation based on fsspec+s3fs."""

    @property
    def provider_name(self) -> str:
        return "tencent_cos"

    def __init__(
        self,
        *,
        secret_id: str,
        secret_key: str,
        region: str,
        bucket: str,
        endpoint: str | None = None,
        cdn_domain: str | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("COS bucket must be configured")

        endpoint_url = endpoint or f"https://cos.{region}.myqcloud.com"
        self.bucket = bucket
        self.region = region
        self.cdn_domain = cdn_domain.rstrip("/") if cdn_domain else None
        self.fs = fsspec.filesystem(
            "s3",
            key=secret_id or None,
            secret=secret_key or None,
            client_kwargs={"region_name": region, "endpoint_url": endpoint_url},
        )

    def _full_path(self, object_key: str) -> str:
        return f"{self.bucket}/{object_key}"

    def upload(
        self,
        object_key: str,
        file_data: bytes | BinaryIO,
        mime_type: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        path = self._full_path(object_key)
        extra_args: dict[str, object] = {"ContentType": mime_type}
        if metadata:
            extra_args["Metadata"] = metadata
        try:
            with self.fs.open(path, "wb", **extra_args) as remote:
                if isinstance(file_data, bytes):
                    remote.write(file_data)
                else:
                    shutil.copyfileobj(file_data, remote)
        except Exception as exc:  # pragma: no cover - external service
            raise StorageUploadError(f"Failed to upload {object_key}: {exc}") from exc

    def download(self, object_key: str) -> bytes:
        path = self._full_path(object_key)
        try:
            return cast(bytes, self.fs.cat_file(path))
        except FileNotFoundError as exc:
            raise StorageNotFoundError(f"Object not found: {object_key}") from exc
        except Exception as exc:  # pragma: no cover
            raise StorageError(f"Failed to download {object_key}: {exc}") from exc

    def delete(self, object_key: str) -> None:
        path = self._full_path(object_key)
        try:
            self.fs.rm(path, recursive=False)
        except FileNotFoundError:
            return
        except Exception as exc:
            raise StorageError(f"Failed to delete {object_key}: {exc}") from exc

    def exists(self, object_key: str) -> bool:
        return bool(self.fs.exists(self._full_path(object_key)))

    def get_metadata(self, object_key: str) -> dict[str, str]:
        try:
            info = self.fs.info(self._full_path(object_key))
        except FileNotFoundError as exc:
            raise StorageNotFoundError(f"Object not found: {object_key}") from exc

        return {
            "size": str(info.get("size", 0)),
            "content_type": info.get("ContentType", "application/octet-stream"),
            "etag": info.get("ETag", "").strip('"'),
            "last_modified": str(info.get("LastModified", "")),
        }

    def get_public_url(self, object_key: str) -> str:
        if self.cdn_domain:
            return f"{self.cdn_domain}/{object_key}"
        return f"https://{self.bucket}.cos.{self.region}.myqcloud.com/{object_key}"

    def get_presigned_url(
        self,
        object_key: str,
        method: str = "GET",
        expires_in: timedelta = timedelta(minutes=5),
        *,
        content_type: str | None = None,
        content_length: int | None = None,
    ) -> str:
        path = self._full_path(object_key)
        extra: dict[str, object] = {}
        if content_type:
            extra["content_type"] = content_type
        if content_length is not None:
            extra["content_length"] = content_length
        return cast(str, self.fs.sign(path, expiration=expires_in, method=method, **extra))
