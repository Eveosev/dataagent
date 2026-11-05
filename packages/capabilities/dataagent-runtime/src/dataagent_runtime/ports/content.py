"""Storage and boundary ports shared by every layer (08 §3)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ContentStore(Protocol):
    """Content-addressed immutable store."""

    def put(
        self, data: bytes | str | dict[str, Any], *, media_type: str = "application/json"
    ) -> str:
        """Persist content atomically and return ``sha256:<hex>``."""

    def get(self, digest: str) -> bytes: ...

    def get_json(self, digest: str) -> Any: ...

    def get_text(self, digest: str) -> str: ...

    def exists(self, digest: str) -> bool: ...
