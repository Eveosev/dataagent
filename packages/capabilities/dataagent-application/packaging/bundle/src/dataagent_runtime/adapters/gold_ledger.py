"""Cross-layer gold-exposure ledger (08 §5.2, r38 F3).

The plan requires that a gold expectation read by anything other than the
acceptance evaluator is *recorded* and the case demoted to ``regression``.
The exposure history is keyed by the gold content digest and kept in one
well-known file under the shared ``data_root`` (``vault/gold-exposure.json``),
so every layer composing on the same ``data_root`` — governance scanning and
egress, data-layer file/content reads, the CLI — sees and extends the same
irreversible index. The governance vault mirrors its own records here; the
data layer consults it before returning file bytes.

The local vault remains a conventional isolation, not a security boundary;
this ledger is the product-side closure of the *official* read paths, not a
defense against arbitrary OS access.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_FILENAME = "gold-exposure.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GoldExposureLedger:
    """Content-addressed gold registry + irreversible exposure history."""

    def __init__(self, vault_root: str | os.PathLike[str]):
        self.path = Path(vault_root) / LEDGER_FILENAME
        # Last read-hook failure (best-effort ledger; kept for diagnosis).
        self.last_error: str | None = None

    # -- internals ------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        try:
            with open(self.path, "rb") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            return {"registered": {}, "exposures": {}}
        if not isinstance(payload, dict):
            return {"registered": {}, "exposures": {}}
        return {
            "registered": payload.get("registered") or {},
            "exposures": payload.get("exposures") or {},
        }

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=1)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # -- registry -------------------------------------------------------

    def register(self, digest: str, *, set_id: str, case_id: str) -> None:
        """Register a digest as a gold expectation (idempotent)."""

        if not digest:
            return
        payload = self._load()
        entries = payload["registered"].setdefault(digest, [])
        marker = {"set_id": set_id, "case_id": case_id, "at": _now()}
        if not any(
            entry.get("set_id") == set_id and entry.get("case_id") == case_id
            for entry in entries
        ):
            entries.append(marker)
        self._save(payload)

    def is_gold(self, digest: str) -> bool:
        return bool(digest) and digest in self._load()["registered"]

    def gold_digests(self) -> set[str]:
        return set(self._load()["registered"])

    # -- exposures ------------------------------------------------------

    def note_exposure(
        self,
        digest: str,
        *,
        purpose: str,
        accessed_by: str,
        set_id: str | None = None,
        case_id: str | None = None,
    ) -> None:
        """Record an exposure of a gold digest (idempotent per entry id)."""

        if not digest:
            return
        payload = self._load()
        if digest not in payload["registered"]:
            return  # not a gold expectation: nothing to demote
        entry = {
            "entry_id": f"exp:{uuid.uuid4().hex[:12]}",
            "purpose": purpose,
            "accessed_by": accessed_by,
            "at": _now(),
        }
        if set_id is not None:
            entry["set_id"] = set_id
        if case_id is not None:
            entry["case_id"] = case_id
        payload["exposures"].setdefault(digest, []).append(entry)
        self._save(payload)

    def exposed_digests(self) -> set[str]:
        return set(self._load()["exposures"])

    def exposures(self, digest: str) -> list[dict[str, Any]]:
        return list(self._load()["exposures"].get(digest) or [])

    # -- read hook ------------------------------------------------------

    def read_hook(self, *, accessed_by: str = "content-read") -> "callable":
        """A ``LocalContentStore.read_hook`` noting gold reads as exposures."""

        def hook(digest: str) -> None:
            try:
                self.note_exposure(digest, purpose="content-read", accessed_by=accessed_by)
            except OSError as exc:
                # The ledger is best-effort on the read path: a broken
                # ledger must never break the read itself — but the last
                # failure is kept for diagnosis instead of vanishing.
                self.last_error = f"{digest}: {exc}"

        return hook


__all__ = ["GoldExposureLedger", "LEDGER_FILENAME"]
