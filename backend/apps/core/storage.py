"""StorageProvider abstraction.

The database stores only metadata/references to uploaded files — never the
binary content itself. Phase 1 only needs this for future document uploads,
but the interface is defined now so Knowledge document ingestion (Phase 2)
doesn't require changing callers.
"""
from abc import ABC, abstractmethod

from django.conf import settings
from django.core.files.storage import default_storage


class StorageProvider(ABC):
    @abstractmethod
    def save(self, path: str, content) -> str:
        """Persist `content` at `path`, return the stored path/key."""

    @abstractmethod
    def url(self, path: str) -> str:
        """Return a URL the file can be retrieved from."""

    @abstractmethod
    def delete(self, path: str) -> None:
        ...


class LocalStorageProvider(StorageProvider):
    def save(self, path: str, content) -> str:
        return default_storage.save(path, content)

    def url(self, path: str) -> str:
        return default_storage.url(path)

    def delete(self, path: str) -> None:
        if default_storage.exists(path):
            default_storage.delete(path)


class S3StorageProvider(StorageProvider):
    """Production storage provider. Backed by django-storages in practice;
    kept as a thin wrapper around `default_storage` so the configured
    Django STORAGES backend (set via STORAGE_BACKEND=s3) does the actual
    S3-compatible work, and callers never need to know which is active."""

    def save(self, path: str, content) -> str:
        return default_storage.save(path, content)

    def url(self, path: str) -> str:
        return default_storage.url(path)

    def delete(self, path: str) -> None:
        if default_storage.exists(path):
            default_storage.delete(path)


def get_storage_provider() -> StorageProvider:
    backend = getattr(settings, "STORAGE_BACKEND", "local")
    if backend == "s3":
        return S3StorageProvider()
    return LocalStorageProvider()
