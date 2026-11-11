"""Read-only source boundary. Providers declare unsupported change feeds."""
from typing import Protocol, runtime_checkable
from dataagent_contracts.intake import SourceObservation


@runtime_checkable
class SourcePort(Protocol):
    def describe(self, ctx) -> SourceObservation: ...
    def read(self, ctx, *, budget_rows: int = 200) -> SourceObservation: ...
    def changes(self, ctx, *, cursor: str | None = None) -> SourceObservation: ...
