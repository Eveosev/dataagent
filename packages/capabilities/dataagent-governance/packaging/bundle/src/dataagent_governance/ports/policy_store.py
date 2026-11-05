"""Policy store port (08 §3 ``ports/``)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from dataagent_contracts.core import VersionedRef

from dataagent_governance.contracts import PolicyDocument


@runtime_checkable
class PolicyStorePort(Protocol):
    """Load policy documents; S0 reads them from the versioned repository.

    The port leaves room for Cedar-style engines in stage 2 (08 §5.1).
    """

    def load(self, policy_ref: VersionedRef | None) -> PolicyDocument: ...
