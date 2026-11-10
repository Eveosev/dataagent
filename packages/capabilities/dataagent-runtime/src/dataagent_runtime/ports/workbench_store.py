"""Atomic local unit of work. No transaction extends to remote side effects."""
from dataclasses import dataclass, field
from typing import Any, Protocol


class VersionConflict(ValueError):
    code = 'version_conflict'


@dataclass(frozen=True)
class Write:
    kind: str
    id: str
    scope: str
    body: dict[str, Any]
    expected_revision: str | None = None


@dataclass
class ChangeSet:
    writes: list[Write] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    outbox: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class CommitReceipt:
    revisions: dict[str, str]
    cursor: int


class WorkbenchStore(Protocol):
    def get(self, kind: str, id: str, revision: str, *, scope: str) -> dict | None: ...
    def current(self, kind: str, id: str, *, scope: str) -> dict | None: ...
    def query(self, kind: str, scope: str, selector: dict | None = None, cursor: int = 0, limit: int = 100) -> list[dict]: ...
    def events(self, session: str, after: int, *, scope: str, limit: int = 100) -> dict: ...
    def commit(self, change_set: ChangeSet) -> CommitReceipt: ...
