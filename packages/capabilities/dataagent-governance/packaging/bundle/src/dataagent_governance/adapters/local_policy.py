"""Local policy store: policy documents in the versioned repository."""

from __future__ import annotations

from dataagent_contracts.core import VersionedRef

from dataagent_governance.contracts import PolicyDocument
from dataagent_governance.runtime.errors import not_found


class LocalPolicyStore:
    """Policies live under the ``policy`` kind; ``*`` ids are rejected.

    Loading a policy to mint the *first* AccessDecision does not require an
    existing decision (bootstrap fix, review §7.1): policy reads are part of
    the authorization entry point, not a resource read.
    """

    KIND = "policy"

    def __init__(self, versions):  # noqa: ANN001 - VersionedRepository
        self.versions = versions

    def save(self, policy: PolicyDocument) -> VersionedRef:
        revision = self.versions.save(
            self.KIND, policy.policy_id, policy.model_dump(mode="json")
        )
        return VersionedRef(id=policy.policy_id, revision=revision)

    def load(self, policy_ref: VersionedRef | None) -> PolicyDocument:
        if policy_ref is not None:
            payload = self.versions.get(self.KIND, str(policy_ref.id), str(policy_ref.revision))
            if payload is None:
                raise not_found(f"policy not found: {policy_ref}")
            return PolicyDocument.model_validate(payload)
        current = self.versions.current(self.KIND, "tenant:default")
        if current is not None and current[1]:
            return PolicyDocument.model_validate(current[1])
        raise not_found("no policy document is configured for this tenant")
