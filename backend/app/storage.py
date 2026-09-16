"""Object storage for cached, assembled artifacts — currently just PDFs.

CLAUDE.md puts assembled PDFs in Cloud Storage with a 30-day lifecycle rule.
This environment has no GCP project yet (see docs/BACKLOG.md), so this module
follows the same shape as everything else in this project that depends on
infrastructure that doesn't exist locally: a narrow protocol the caller
depends on, a real Cloud Storage implementation behind a lazy import, and a
disk-backed one that makes dev and tests fully functional without either.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from app.config.settings import Settings

logger = logging.getLogger(__name__)


class ObjectStorage(Protocol):
    def get(self, key: str) -> bytes | None: ...

    def put(self, key: str, data: bytes, *, content_type: str) -> None: ...


class LocalObjectStorage:
    """Dev and tests: a plain directory on disk. No lifecycle rule enforced."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Keys are always ours, built from UUIDs and genre slugs, never from
        # a request path or query string — this guards against a coding
        # mistake, not an attacker.
        if ".." in key or key.startswith("/") or key.startswith("\\"):
            raise ValueError(f"unsafe storage key: {key!r}")
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.exists() else None

    def put(self, key: str, data: bytes, *, content_type: str) -> None:
        del content_type  # a filesystem has no content-type metadata to set
        self._path(key).write_bytes(data)


class GcsObjectStorage:
    """Production. Never exercised: this environment has no GCP project yet."""

    def __init__(self, bucket_name: str) -> None:
        self._bucket_name = bucket_name
        self._bucket: object | None = None

    def _bucket_handle(self) -> object:
        if self._bucket is None:
            # Imported here, not at module load, so a dev machine without the
            # SDK's transitive dependencies installed can still import this
            # module freely — it just can't construct this class's bucket.
            from google.cloud import storage

            self._bucket = storage.Client().bucket(self._bucket_name)
        return self._bucket

    def get(self, key: str) -> bytes | None:
        blob = self._bucket_handle().blob(key)  # type: ignore[attr-defined]
        if not blob.exists():
            return None
        data: bytes = blob.download_as_bytes()
        return data

    def put(self, key: str, data: bytes, *, content_type: str) -> None:
        blob = self._bucket_handle().blob(key)  # type: ignore[attr-defined]
        blob.upload_from_string(data, content_type=content_type)


def get_object_storage(settings: Settings) -> ObjectStorage:
    if settings.gcs_pdf_bucket:
        return GcsObjectStorage(settings.gcs_pdf_bucket)
    if settings.is_prod:
        raise RuntimeError("GCS_PDF_BUCKET is not configured")
    return LocalObjectStorage(Path(settings.pdf_cache_dir))
