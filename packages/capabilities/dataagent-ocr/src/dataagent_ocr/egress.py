"""DA12.1 egress gate for OCR content sent to a non-local provider.

A page image is user content. When the pinned provider's deployment is not
``local`` the image may only leave through an ``EgressDecision`` that covers
its content address (``sha256:<hex>`` of the image bytes or of the source
file) and names the provider as destination (``model_ref`` =
``openai_compat:<model>``, ``deployment`` from the profile). The check is the
shared ``dataagent_runtime.enforcement.egress_check``; mode comes from
``DATAAGENT_ENFORCEMENT_MODE`` (``enforce`` refuses, ``warn`` proceeds with a
warning, ``off`` skips).
"""

from __future__ import annotations

from pathlib import Path

from dataagent_runtime.adapters.sqlite import SqliteDatabase, SqliteDecisionStore
from dataagent_runtime.enforcement import EnforcementConfig, egress_check, enforcement_from_env

from dataagent_ocr.errors import EgressRequired
from dataagent_ocr.profiles import sha256_hex


def content_ref(label: str, data: bytes) -> str:
    return f"{label}@sha256:{sha256_hex(data)}"


def check(
    data_root: Path,
    *,
    destination: dict[str, str],
    content_refs: list[str],
    decision_ref: str | None,
    config: EnforcementConfig | None = None,
) -> list[str]:
    """Return warnings (``warn`` mode) or raise :class:`EgressRequired`."""

    config = enforcement_from_env(config)
    if config.mode == "off":
        return []
    request = {"content_refs": content_refs, "destination": destination, "egress_decision_ref": decision_ref}
    db_path = Path(data_root) / "db" / "decisions.sqlite3"

    def get_egress(ref: str):
        if not db_path.is_file():
            return None
        return SqliteDecisionStore(SqliteDatabase(db_path)).get_egress(ref)

    outcome = egress_check(request, get_egress=get_egress, config=config)
    if outcome.allowed:
        return []
    reasons = "; ".join(outcome.reasons) or (outcome.issue.message if outcome.issue else "egress not approved")
    if config.mode == "warn":
        return [f"egress not approved (warn mode, sent anyway): {reasons}"]
    raise EgressRequired(
        f"sending this content to {destination.get('model_ref')} ({destination.get('deployment')}) needs an EgressDecision: {reasons}",
        action="obtain an EgressDecision covering the content and destination, or use a local OCR provider",
    )
