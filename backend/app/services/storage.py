"""File storage abstraction: local disk (default) or any S3-compatible bucket
(AWS S3, MinIO, Cloudflare R2, Backblaze B2...). Install `boto3` for S3."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from app.config import settings


class Storage(Protocol):
    def save_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...
    def save_file(self, key: str, src: Path) -> None: ...
    def read_bytes(self, key: str) -> bytes: ...
    def local_path(self, key: str) -> Path | None: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("invalid storage key")
        return p

    def save_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def save_file(self, key: str, src: Path) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, p)

    def read_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def local_path(self, key: str) -> Path | None:
        p = self._path(key)
        return p if p.exists() else None

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()


class S3Storage:  # pragma: no cover - requires a bucket
    def __init__(self):
        import boto3

        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )

    def save_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def save_file(self, key: str, src: Path) -> None:
        self.client.upload_file(str(src), self.bucket, key)

    def read_bytes(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def local_path(self, key: str) -> Path | None:
        return None

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage() if settings.storage_backend == "s3" else LocalStorage(settings.storage_path)
    return _storage
