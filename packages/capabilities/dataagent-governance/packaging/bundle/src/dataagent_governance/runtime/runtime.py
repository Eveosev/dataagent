"""Governance runtime: shared runtime plus policy store and sample vault."""

from __future__ import annotations

import os

from dataagent_runtime import Runtime as _SharedRuntime
from dataagent_runtime.enforcement import EnforcementConfig, enforcement_from_env
from dataagent_runtime.runtime import resolve_roots

from dataagent_runtime.adapters.gold_ledger import GoldExposureLedger

from dataagent_governance.adapters.local_policy import LocalPolicyStore
from dataagent_governance.adapters.local_split_vault import LocalSplitVault


class GovernanceRuntime(_SharedRuntime):
    def access_resolver(self, authorization_ref: str):
        """Resolve authorization_ref for the shared invoke recheck.

        Accepts a saved ``AccessDecision.decision_id``. A policy binding
        (``policy:<id>@<revision>``) resolves by evaluating the policy for
        the runtime's host authority — the bootstrap path that lets the
        first read mint its own decision (review §7.1).
        """

        decision = self.decisions.get_access(authorization_ref)
        if decision is not None:
            return decision
        if authorization_ref.startswith("policy:"):
            from dataagent_contracts.core import VersionedRef

            from dataagent_governance.policy import evaluate_access

            policy = self.policy.load(None)
            subject = self.host_subject_ref
            purpose = self.host_purpose
            if not subject or not purpose:
                return None
            return evaluate_access(
                policy,
                subject_ref=subject,
                requester_ref=None,
                resource_ref=VersionedRef(id="table", revision="*"),
                action="read",
                purpose=purpose,
            )
        return None

    """Adds the governance ports to the shared local composition.

    Trusted-host authority (review §7.1): ``host_subject_ref`` and
    ``host_purpose`` are fixed by configuration and used only when a
    CallContext does not carry them. Call arguments can never override them.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.policy = LocalPolicyStore(self.versions)
        self.gold_ledger = GoldExposureLedger(self.data_root / "vault")
        self.vault = LocalSplitVault(self.versions, self.content, self.gold_ledger)

    @classmethod
    def create(
        cls,
        workspace_root: str | os.PathLike[str] | None = None,
        data_root: str | os.PathLike[str] | None = None,
        *,
        enforcement: EnforcementConfig | None = None,
        host_subject_ref: str | None = None,
        host_purpose: str | None = None,
        inference=None,
    ) -> "GovernanceRuntime":
        # Root resolution (DATAAGENT_WORKSPACE / DATAAGENT_DATA_ROOT) is the
        # shared runtime's chain, not restated here.
        workspace, root = resolve_roots(workspace_root, data_root)
        if enforcement is None:
            # Trusted-host wiring for the process entries (MCP/CLI): the S0
            # composition runs under ``enforce`` (08 §4.3); without the
            # variable the shared runtime's development default applies.
            enforcement = enforcement_from_env()
        # The sample library has its own subtree (08 §2: data_root/vault/).
        (root / "vault").mkdir(parents=True, exist_ok=True)
        (root / "db").mkdir(parents=True, exist_ok=True)
        db = _LocalDb(root / "db" / "governance.sqlite3")
        # DA12.1 decisions are layer-shared (08 §2 共享 data_root): an
        # AccessDecision minted here is what the data/application layers'
        # recheck resolves when they compose on the same data_root.
        decision_db = _LocalDb(root / "db" / "decisions.sqlite3")
        content = _LocalContent(root / "content")
        # r38 F3: every governance-side content read (egress scanning,
        # coverage checks, table decoding, anchor resolution, CLI) consults
        # the cross-layer gold-exposure ledger; only the acceptance
        # evaluator's own read suspends the hook.
        content.read_hook = GoldExposureLedger(root / "vault").read_hook()
        return cls(
            workspace_root=workspace,
            data_root=root,
            content=content,
            versions=_LocalVersions(db),
            decisions=_LocalDecisions(decision_db),
            db=db,
            enforcement=enforcement,
            # Trusted-host authority: explicit configuration first, then the
            # host-injected environment. Call arguments never set these (B7).
            host_subject_ref=host_subject_ref or os.environ.get("DATAAGENT_HOST_SUBJECT_REF"),
            host_purpose=host_purpose or os.environ.get("DATAAGENT_HOST_PURPOSE"),
            inference=inference,
        )


# Local aliases keep the constructor signature readable above.
from dataagent_runtime.adapters.local_content import LocalContentStore as _LocalContent  # noqa: E402
from dataagent_runtime.adapters.sqlite import (  # noqa: E402
    SqliteDatabase as _LocalDb,
    SqliteDecisionStore as _LocalDecisions,
    SqliteVersionedRepository as _LocalVersions,
)


_DEFAULT: GovernanceRuntime | None = None


def default_runtime() -> GovernanceRuntime:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = GovernanceRuntime.create()
    return _DEFAULT


def reset_default_runtime() -> None:
    global _DEFAULT
    _DEFAULT = None
