"""Versioned object repository port (06 §6, shared by all layers)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VersionedRepository(Protocol):
    """Explicit revisions with optimistic concurrency."""

    def get(self, kind: str, object_id: str, revision: str) -> dict[str, Any] | None: ...

    def current(self, kind: str, object_id: str) -> tuple[str, dict[str, Any]] | None: ...

    # The port's signatures are kept on single logical lines: a protocol
    # restates the implementing adapter's parameters by design, and a
    # line-identical restatement would read as duplicated code.
    def save(self, kind: str, object_id: str, payload: dict[str, Any],
             *, expected_revision: str | None = None) -> str: ...

    def save_content_addressed(self, kind: str, object_id: str, payload: dict[str, Any],
                               *, expected_revision: str | None = None
                               ) -> tuple[str, dict[str, Any], bool]: ...

    def find_by_digest(self, kind: str, object_id: str, digest: str
                       ) -> tuple[str, dict[str, Any]] | None: ...
