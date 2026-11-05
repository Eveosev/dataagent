"""Sample vault port (08 §3, §5.2)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from dataagent_contracts.core import SplitRole, VersionedRef

from dataagent_governance.contracts import (
    EvaluationCaseDraft,
    ExposureLedgerEntry,
)


@runtime_checkable
class SampleVaultPort(Protocol):
    """Sample library under ``data_root/vault/`` (08 §5.2).

    Inputs and gold expectations are stored separately. Gold is only readable
    by the acceptance evaluator; any other reader lands in the exposure
    ledger and the case is demoted to ``regression``. The local vault is a
    conventional isolation, not a security boundary — reports must say so.
    """

    def create_set(
        self,
        cases: list[EvaluationCaseDraft],
        assignments: dict[str, SplitRole],
        *,
        warnings: list[str],
    ) -> VersionedRef: ...

    def get_set(self, set_id: str, revision: str) -> dict[str, Any]: ...

    def freeze(self, set_id: str, revision: str) -> VersionedRef: ...

    def list_cases(self, set_id: str, revision: str, role: SplitRole) -> list[dict[str, Any]]: ...

    def read_input(self, set_id: str, revision: str, case_id: str) -> Any: ...

    def read_gold(
        self, set_id: str, revision: str, case_id: str, *, purpose: str, accessed_by: str
    ) -> Any: ...

    def exposure_ledger(self, set_id: str) -> list[ExposureLedgerEntry]: ...
