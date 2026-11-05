"""Local split vault: sample library under the versioned repository.

Conventions (08 §5.2):

- inputs and gold expectations are stored as separate content objects;
- gold is readable only by the acceptance evaluator; any other reader is
  recorded in the exposure ledger and the case is demoted to ``regression``
  in a new revision;
- frozen revisions are immutable (the repository is append-only); new
  samples produce a new revision.

The local vault is a conventional isolation, not a security boundary; the
acceptance report must list this as a limit.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from dataagent_contracts.core import SplitRole, VersionedRef

from dataagent_governance.contracts import (
    EvaluationCaseDraft,
    ExposureLedgerEntry,
)
from dataagent_governance.runtime.errors import invalid_input, not_found, version_conflict

GOLD_PURPOSE = "evaluate_business_acceptance"

# The exposure history is keyed by the *gold content digest*, not by
# set/case identity: re-isolating the same content under a new set id, a new
# case id or a new revision cannot launder an exposure back to unseen
# (review B3). The index lives in the versioned repository, so it survives
# every re-split of every set on the same data_root — and it is mirrored
# into the cross-layer ledger file (r38 F3) so official reads made by the
# data/application layers on the same data_root extend the same history.
EXPOSURE_KIND = "gold_exposure"
EXPOSURE_INDEX_ID = "vault:exposure-index"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gold_digest(case: dict[str, Any]) -> str:
    return str(case["expected_ref"]).split("@")[-1]


class LocalSplitVault:
    KIND = "eval_set"

    def __init__(self, versions, content, gold_ledger=None):  # noqa: ANN001
        self.versions = versions
        self.content = content
        # Cross-layer gold registry + exposure history (r38 F3). May be
        # ``None`` in legacy compositions; the versioned-repo index alone
        # then decides eligibility, as before.
        self.gold_ledger = gold_ledger

    # -- exposure index --------------------------------------------------

    def _exposure_index(self) -> dict[str, list[dict[str, Any]]]:
        current = self.versions.current(EXPOSURE_KIND, EXPOSURE_INDEX_ID)
        if current is None:
            return {}
        digests = current[1].get("digests") or {}
        return {str(digest): list(entries) for digest, entries in digests.items()}

    def _note_exposure(self, digest: str, entry: dict[str, Any]) -> None:
        """Record a gold exposure by content digest (idempotent)."""

        index = self._exposure_index()
        entries = list(index.get(digest) or [])
        if any(existing.get("entry_id") == entry.get("entry_id") for existing in entries):
            return
        entries.append(entry)
        index[digest] = entries
        self.versions.save(EXPOSURE_KIND, EXPOSURE_INDEX_ID, {"digests": index})
        # Mirror into the cross-layer ledger (r38 F3): every layer on the
        # same data_root sees the same irreversible history.
        if self.gold_ledger is not None and digest not in self.gold_ledger.exposed_digests():
            self.gold_ledger.note_exposure(
                digest,
                purpose=str(entry.get("purpose") or "vault-read"),
                accessed_by=str(entry.get("accessed_by") or "vault"),
                set_id=entry.get("set_id"),
                case_id=entry.get("case_id"),
            )

    def note_external_read(self, digest: str, *, purpose: str, accessed_by: str) -> None:
        """An official read path outside the evaluator touched ``digest``.

        Reading gold through any product path other than the acceptance
        evaluator is an exposure (08 §5.2, r38 F3): the case cannot pass as
        unseen acceptance afterwards. Only a *registered* gold digest is
        recorded; every other read is a no-op.
        """

        if self.gold_ledger is None:
            return
        self.gold_ledger.note_exposure(digest, purpose=purpose, accessed_by=accessed_by)

    # -- set lifecycle -------------------------------------------------

    def create_set(
        self,
        cases: list[EvaluationCaseDraft],
        assignments: dict[str, SplitRole],
        *,
        warnings: list[str],
        set_id: str | None = None,
    ) -> VersionedRef:
        set_id = set_id or f"evalset:{uuid.uuid4().hex[:12]}"
        # Register every gold digest in the cross-layer ledger (r38 F3) so
        # official reads made by *any* layer on this data_root — governance
        # scanning/egress, data file/content reads, the CLI — can recognize
        # and record an exposure of it.
        if self.gold_ledger is not None:
            for case in cases:
                self.gold_ledger.register(
                    str(case.expected_ref).split("@")[-1],
                    set_id=set_id,
                    case_id=case.case_id,
                )
        # Exposure history is content-addressed and irreversible: a case
        # whose gold content was ever read outside the acceptance evaluator
        # inherits its ledger entries here, whatever the caller assigns.
        # Cross-layer exposures (data/application reads on the same
        # data_root, r38 F3) count the same as vault-side ones.
        index = self._exposure_index()
        ledger_exposed = (
            self.gold_ledger.exposed_digests() if self.gold_ledger is not None else set()
        )
        inherited: list[dict[str, Any]] = []
        seen_entry: set[str] = set()
        for case in cases:
            digest = str(case.expected_ref).split("@")[-1]
            for entry in index.get(digest) or []:
                if entry.get("entry_id") not in seen_entry:
                    seen_entry.add(str(entry.get("entry_id")))
                    inherited.append(entry)
            if digest in ledger_exposed and digest not in index:
                inherited.append(
                    {
                        "entry_id": f"cross-layer:{digest}",
                        "set_id": set_id,
                        "case_id": case.case_id,
                        "accessed_by": "cross-layer-read",
                        "purpose": "content-read",
                        "demoted_to": "regression",
                    }
                )
        if inherited:
            warnings = [
                *warnings,
                (
                    f"{len(inherited)} gold exposure entr{'y is' if len(inherited) == 1 else 'ies are'} "
                    "inherited from the irreversible exposure history; those cases "
                    "cannot be unseen"
                ),
            ]
        manifest = {
            "set_id": set_id,
            "frozen": False,
            "cases": [],
            "counts": {role.value: 0 for role in SplitRole},
            "warnings": list(warnings),
            "ledger": inherited,
        }
        for case in cases:
            role = assignments[case.case_id]
            manifest["cases"].append(
                {
                    "case_id": case.case_id,
                    "input_ref": str(case.input_ref),
                    "expected_ref": str(case.expected_ref),
                    "group_keys": case.group_keys,
                    "role": role.value,
                }
            )
            manifest["counts"][role.value] += 1
        revision = self.versions.save(self.KIND, set_id, manifest)
        return VersionedRef(id=set_id, revision=revision)

    def get_set(self, set_id: str, revision: str) -> dict[str, Any]:
        payload = self.versions.get(self.KIND, set_id, revision)
        if payload is None:
            raise not_found(f"evaluation set not found: {set_id}@{revision}")
        return payload

    def freeze(self, set_id: str, revision: str) -> VersionedRef:
        manifest = self.get_set(set_id, revision)
        if manifest.get("frozen"):
            raise version_conflict(f"evaluation set {set_id}@{revision} is already frozen")
        manifest["frozen"] = True
        new_revision = self.versions.save(
            self.KIND, set_id, manifest, expected_revision=revision
        )
        return VersionedRef(id=set_id, revision=new_revision)

    def add_samples(
        self, set_id: str, revision: str, cases: list[EvaluationCaseDraft]
    ) -> VersionedRef:
        """New samples create a new revision (08 §5.2)."""

        manifest = self.get_set(set_id, revision)
        manifest["frozen"] = False
        existing = {case["case_id"] for case in manifest["cases"]}
        for case in cases:
            if case.case_id in existing:
                raise invalid_input(f"duplicate case id: {case.case_id}")
            manifest["cases"].append(
                {
                    "case_id": case.case_id,
                    "input_ref": str(case.input_ref),
                    "expected_ref": str(case.expected_ref),
                    "group_keys": case.group_keys,
                    "role": SplitRole.development.value,
                }
            )
            manifest["counts"][SplitRole.development.value] += 1
        new_revision = self.versions.save(
            self.KIND, set_id, manifest, expected_revision=revision
        )
        return VersionedRef(id=set_id, revision=new_revision)

    # -- reads ----------------------------------------------------------

    def list_cases(
        self, set_id: str, revision: str, role: SplitRole | str
    ) -> list[dict[str, Any]]:
        role_value = role.value if isinstance(role, SplitRole) else str(role)
        manifest = self.get_set(set_id, revision)
        return [case for case in manifest["cases"] if case["role"] == role_value]

    def read_input(self, set_id: str, revision: str, case_id: str) -> Any:
        manifest = self.get_set(set_id, revision)
        case = self._case(manifest, case_id)
        return self.content.get_json(str(case["input_ref"]).split("@")[-1])

    def read_gold(
        self, set_id: str, revision: str, case_id: str, *, purpose: str, accessed_by: str
    ) -> Any:
        manifest = self.get_set(set_id, revision)
        case = self._case(manifest, case_id)
        if purpose != GOLD_PURPOSE:
            self._record_exposure(manifest, set_id, revision, case, purpose, accessed_by)
        # The evaluator's own read is the one trusted read of gold: suspend
        # the content-store read hook so DA11.5.5 does not record an
        # exposure of the very content it is appointed to read (r38 F3).
        # Any other purpose has already recorded its exposure above.
        with self.content.suspend_read_hook():
            return self.content.get_json(str(case["expected_ref"]).split("@")[-1])

    def exposure_ledger(self, set_id: str) -> list[ExposureLedgerEntry]:
        current = self.versions.current(self.KIND, set_id)
        if current is None:
            raise not_found(f"evaluation set not found: {set_id}")
        return [ExposureLedgerEntry.model_validate(e) for e in current[1].get("ledger", [])]

    def exposed_digests(self) -> set[str]:
        """Gold digests with an irreversible exposure record (B3, r35 F2, r38 F3).

        Eligibility must be decided against *these digests* directly: the
        current revision's case list can be rewritten (a case removed, a
        case id rebound to fresh gold) without ever undoing an exposure,
        so a case-id/role snapshot alone cannot decide who is still unseen.
        The versioned-repo index is unioned with the cross-layer ledger —
        exposures recorded by the data/application layers on the same
        data_root count exactly the same.
        """

        digests = set(self._exposure_index())
        if self.gold_ledger is not None:
            digests |= self.gold_ledger.exposed_digests()
        return digests

    def current_roles(self, set_id: str) -> dict[str, str]:
        """Case-id → role in the current revision, exposure history included.

        Exposure demotions land in the current revision; the frozen
        manifest stays immutable. Acceptance eligibility is "frozen manifest
        + this snapshot" (review §10), so a case demoted after the freeze is
        visible here even when the caller cites the old revision — and the
        irreversible, content-addressed exposure index (B3) demotes a case
        whose gold content was exposed through *any* set, including a
        re-isolation that reset the manifest roles.
        """

        current = self.versions.current(self.KIND, set_id)
        if current is None:
            raise not_found(f"evaluation set not found: {set_id}")
        exposed = self.exposed_digests()
        roles: dict[str, str] = {}
        for case in current[1]["cases"]:
            role = case["role"]
            if role != SplitRole.regression.value and _gold_digest(case) in exposed:
                role = SplitRole.regression.value
            roles[case["case_id"]] = role
        return roles

    # -- internals ------------------------------------------------------

    @staticmethod
    def _case(manifest: dict[str, Any], case_id: str) -> dict[str, Any]:
        for case in manifest["cases"]:
            if case["case_id"] == case_id:
                return case
        raise not_found(f"case not found: {case_id}")

    def _record_exposure(
        self,
        manifest: dict[str, Any],
        set_id: str,
        revision: str,
        case: dict[str, Any],
        purpose: str,
        accessed_by: str,
    ) -> None:
        entry = ExposureLedgerEntry(
            entry_id=f"exp:{uuid.uuid4().hex[:12]}",
            set_id=set_id,
            case_id=case["case_id"],
            accessed_by=accessed_by,
            purpose=purpose,
            demoted_to=SplitRole.regression,
            at=_now(),
        )
        if case["role"] != SplitRole.regression.value:
            case["role"] = SplitRole.regression.value
            manifest["counts"] = {role.value: 0 for role in SplitRole}
            for item in manifest["cases"]:
                manifest["counts"][item["role"]] += 1
        manifest.setdefault("ledger", []).append(entry.model_dump(mode="json"))
        # The exposure is also recorded against the gold *content digest*:
        # irreversible, and immune to re-isolation or case-id rewriting (B3).
        self._note_exposure(_gold_digest(case), entry.model_dump(mode="json"))
        self.versions.save(self.KIND, set_id, manifest, expected_revision=revision)
