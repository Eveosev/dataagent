"""DA12.1 decision resolution and storage ports (08 §4.3).

``authorization_ref`` may be either a saved ``AccessDecision.decision_id`` or
a policy binding ``policy:<id>@<revision>``. Resolving the latter on the spot
is what breaks the first-authorization bootstrap loop (feasibility review
2026-11-04 §7): reading the policy to *produce* the first decision must not
itself require an existing decision.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from dataagent_contracts.core import AccessDecision, EgressDecision


@runtime_checkable
class AccessDecisionResolver(Protocol):
    """Resolve ``authorization_ref`` to an AccessDecision, or None."""

    def resolve(self, authorization_ref: str) -> AccessDecision | None: ...


@runtime_checkable
class DecisionStore(Protocol):
    """Persistence for DA12.1 decisions; decision_id is the later authorization_ref."""

    def save_access(self, decision: AccessDecision) -> None: ...

    def get_access(self, decision_id: str) -> AccessDecision | None: ...

    def save_egress(self, decision: EgressDecision) -> None: ...

    def get_egress(self, decision_id: str) -> EgressDecision | None: ...
