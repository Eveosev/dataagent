from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class TraceRecord:
    session_id: str
    event_id: str
    cursor: int
    kind: str
    payload: dict[str, Any]
    ts_ms: int
    # Global insertion order for the cross-task view. Per-task cursors restart
    # at 1 and cannot paginate a kernel-session-wide stream.
    seq: int | None = None


@runtime_checkable
class TraceRepository(Protocol):
    """Kernel ``StoreContract``-shaped append-only trace store (06 §6.2)."""

    def create_session(self, session_id: str) -> None: ...

    def append(
        self,
        session_id: str,
        *,
        event_id: str,
        kind: str,
        payload: dict[str, Any],
        ts_ms: int,
        kernel_session_id: str | None = None,
    ) -> tuple[TraceRecord, bool]: ...

    def read_from(
        self, session_id: str, cursor: int = 1, limit: int = 100
    ) -> list[TraceRecord]: ...

    def read_by_kernel_session(
        self, kernel_session_id: str, cursor: int = 1, limit: int = 100
    ) -> list[TraceRecord]: ...

    def get_event(self, session_id: str, event_id: str) -> TraceRecord | None: ...

    def last_cursor(self, session_id: str) -> int: ...

    def checkpoint(self, session_id: str, kind_prefix: str = "") -> dict[str, Any]: ...

    def verify_checkpoint(self, checkpoint: dict[str, Any]) -> bool: ...
