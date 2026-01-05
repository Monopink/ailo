"""Tencent Cloud COS storage backend (S3-compatible using boto3)."""

from __future__ import annotations

import traceback
from datetime import timedelta
from typing import Any, BinaryIO, cast

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.services.storage.base import (
    StorageBackend,
    StorageError,
    StorageNotFoundError,
    StorageUploadError,
)


class TencentCOSBackend(StorageBackend):
    """Tencent COS implementation using boto3 (AWS SDK)."""

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

        # For Tencent COS, use service domain (without bucket name)
        # Bucket name will be added automatically by boto3 when using virtual addressing
        endpoint_url = endpoint or f"https://cos.{region}.myqcloud.com"

        self.bucket = bucket
        self.region = region
        self.cdn_domain = cdn_domain.rstrip("/") if cdn_domain else None

        # CRITICAL: Must explicitly configure addressing_style='virtual' for Tencent COS
        # Without this, boto3 may incorrectly add bucket prefix to object keys
        config = Config(s3={"addressing_style": "virtual"})

        # Use boto3 with virtual addressing style
        # CRITICAL: Do NOT set signature_version - COS auto-negotiates
        self.client = boto3.client(
            "s3",
            aws_access_key_id=secret_id,
            aws_secret_access_key=secret_key,
            region_name=region,
            endpoint_url=endpoint_url,
            config=config,
        )

    def _full_path(self, object_key: str) -> str:
        # boto3 doesn't need bucket prefix in key
        return object_key

    def upload(
        self,
        object_key: str,
        file_data: bytes | BinaryIO,
        mime_type: str,
        metadata: dict[str, str] | None = None,
        is_public: bool = False,
    ) -> None:
        del metadata  # maintained for interface compatibility; COS ignores metadata on upload
        # CRITICAL: Do NOT pass Metadata to put_object - causes SignatureDoesNotMatch with COS
        # ContentType is sufficient for our needs
        extra_args: dict[str, object] = {"ContentType": mime_type}

        # Set ACL for public files (e.g., avatars)
        if is_public:
            extra_args["ACL"] = "public-read"

        try:
            if isinstance(file_data, bytes):
                self.client.put_object(
                    Bucket=self.bucket,
                    Key=object_key,
                    Body=file_data,
                    **extra_args,
                )
            else:
                self.client.upload_fileobj(
                    file_data,
                    Bucket=self.bucket,
                    Key=object_key,
                    ExtraArgs=extra_args,
                )
        except ClientError as exc:
            raise StorageUploadError(f"Failed to upload {object_key}: {exc}") from exc
        except Exception as exc:  # pragma: no cover
            error_details = traceback.format_exc()
            raise StorageUploadError(
                f"Failed to upload {object_key}: {exc}\n{error_details}"
            ) from exc

    def download(self, object_key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=object_key)
            return cast(bytes, response["Body"].read())
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "NoSuchKey":
                raise StorageNotFoundError(f"Object not found: {object_key}") from exc
            raise StorageError(f"Failed to download {object_key}: {exc}") from exc
        except Exception as exc:  # pragma: no cover
            raise StorageError(f"Failed to download {object_key}: {exc}") from exc

    def delete(self, object_key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=object_key)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "NoSuchKey":
                return
            raise StorageError(f"Failed to delete {object_key}: {exc}") from exc
        except Exception as exc:
            raise StorageError(f"Failed to delete {object_key}: {exc}") from exc

    def exists(self, object_key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=object_key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                return False
            raise

    def get_metadata(self, object_key: str) -> dict[str, str]:
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=object_key)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                raise StorageNotFoundError(f"Object not found: {object_key}") from exc
            raise

        return {
            "size": str(response.get("ContentLength", 0)),
            "content_type": response.get("ContentType", "application/octet-stream"),
            "etag": response.get("ETag", "").strip('"'),
            "last_modified": str(response.get("LastModified", "")),
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
        # Map method names to boto3 operations
        operation_map = {
            "GET": "get_object",
            "PUT": "put_object",
            "HEAD": "head_object",
            "DELETE": "delete_object",
        }
        operation = operation_map.get(method.upper())
        if not operation:
            raise ValueError(f"Unsupported method: {method}")

        params: dict[str, Any] = {"Bucket": self.bucket, "Key": object_key}
        if content_type and operation == "put_object":
            params["ContentType"] = content_type
        if content_length is not None and operation == "put_object":
            params["ContentLength"] = content_length

        return cast(
            str,
            self.client.generate_presigned_url(
                ClientMethod=operation,
                Params=params,
                ExpiresIn=int(expires_in.total_seconds()),
            ),
        )
