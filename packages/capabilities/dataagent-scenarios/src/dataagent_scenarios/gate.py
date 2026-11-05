"""DA12.1 access gate composed in front of data-layer calls (08 §4.3, §10.2).

The data layer's product ``invoke`` rechecks its ``resource_fields`` itself
(W1d: 22 of the 32 atoms); this composition forwards ``resolver`` /
``enforcement`` into that product path so the recheck runs with the same
authority, and additionally resolves the authorization for operations that
read no data-layer resource — in the S0 composition no call runs on an
unresolvable authorization. The recheck requires: ``allow``, not expired,
resource coverage for every input resource the operation reads, and a
purpose/subject match — otherwise the call fails with ``da12.access_denied``
before any data-layer handler runs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    ExecutionRef,
    Issue,
    Severity,
    VersionedRef,
)
from dataagent_runtime.enforcement import (
    ACCESS_DENIED_CODE,
    EnforcementConfig,
    access_recheck,
)

# Input-model fields that hold the resource references each data-layer
# operation reads (file / document / table / profile assets). Operations not
# listed read no data-layer resource, so the recheck has nothing to cover —
# the decision still has to resolve, exactly like the shared runtime invoke.
RESOURCE_FIELDS: dict[str, tuple[str, ...]] = {
    "parse_regular_excel": ("file_ref",),
    "extract_irregular_excel": ("file_ref",),
    "parse_delimited_file": ("file_ref",),
    "parse_json_records": ("file_ref",),
    "parse_text_pdf": ("file_ref",),
    "inspect_workbook_calc_state": ("file_ref",),
    "ocr_pdf": ("file_ref",),
    "ocr_image": ("file_ref",),
    "detect_workbook_regions": ("file_ref",),
    "extract_fields_to_schema": ("document_ref",),
    "anchor_extracted_values": ("document_ref",),
    "recover_headers": ("table_ref",),
    "expand_merged_cells": ("table_ref",),
    "classify_table_rows": ("table_ref",),
    "profile_table_structure": ("table_ref",),
    # the profile branch reads the profile asset's derived content (B1)
    "infer_field_types": ("table_ref", "profile_ref"),
    "segment_document": ("document_ref",),
    "maintain_source_anchors": ("document_ref",),
    "define_rule_applicability": ("document_ref",),
    "define_rule_preconditions": ("document_ref",),
    "define_metric_formula": ("document_ref",),
    "define_business_rules": ("document_ref",),
}


def _as_ref(value: Any) -> VersionedRef | None:
    """Best-effort ref extraction from a raw payload value."""

    if isinstance(value, VersionedRef):
        return value
    if isinstance(value, str):
        if "@" in value:
            ref_id, _, revision = value.rpartition("@")
            if ref_id and revision:
                return VersionedRef(id=ref_id, revision=revision)
        return None
    if isinstance(value, dict):
        asset = value.get("asset")
        if isinstance(asset, dict) and asset.get("id"):
            return VersionedRef(id=str(asset["id"]), revision=str(asset.get("revision", "r1")))
        if value.get("id"):
            return VersionedRef(id=str(value["id"]), revision=str(value.get("revision", "r1")))
    return None


def gate_resource_refs(operation: str, payload: dict[str, Any] | None) -> list[VersionedRef]:
    """The input resources ``operation`` reads, extracted from the raw payload."""

    fields = RESOURCE_FIELDS.get(operation, ())
    refs: list[VersionedRef] = []
    for name in fields:
        value = (payload or {}).get(name)
        items = value if isinstance(value, (list, tuple)) else [value]
        for item in items:
            ref = _as_ref(item)
            if ref is not None:
                refs.append(ref)
    return refs


def _denied(operation: str, message: str) -> CapabilityResult[Any]:
    moment = datetime.now(timezone.utc)
    return CapabilityResult[Any](
        status=CapabilityStatus.failed,
        issues=[
            Issue(
                code=ACCESS_DENIED_CODE,
                severity=Severity.error,
                message=message,
                retryable=False,
                suggested_action="obtain an AccessDecision covering the input resources, "
                "then retry with its decision_id as authorization_ref",
            )
        ],
        execution_ref=ExecutionRef(
            invocation_id=f"inv:{uuid.uuid4().hex[:12]}",
            operation=operation,
            capability_id="DA12.1",
            implementation_ref="dataagent-scenarios/gate",
            started_at=moment,
            finished_at=moment,
        ),
    )


def enforce_data_invoke(
    operation: str,
    payload: dict[str, Any] | None,
    context: CallContext | dict[str, Any],
    *,
    runtime: Any = None,
    resolver: Any = None,
    enforcement: EnforcementConfig | None = None,
) -> CapabilityResult[Any]:
    """Run a data-layer call behind the DA12.1 access recheck.

    ``resolver`` resolves ``authorization_ref`` to an ``AccessDecision`` (a
    governance runtime's ``access_resolver``, or the data runtime's own —
    with a shared ``data_root`` both read ``db/decisions.sqlite3``);
    ``enforcement`` defaults to ``enforce`` — this composition exists to run
    the data layer under the gate (08 §10.2), unlike the shared runtime's
    development default ``warn``.
    """

    from dataagent_data.invoke import invoke as data_invoke

    ctx = context if isinstance(context, CallContext) else CallContext.model_validate(context)
    config = enforcement or EnforcementConfig(mode="enforce")
    if not ctx.authorization_ref.strip():
        return _denied(
            operation,
            "authorization_ref is required and must not be blank",
        )
    outcome = access_recheck(
        ctx,
        resolver,
        gate_resource_refs(operation, payload),
        config=config,
    )
    if outcome.ok or config.mode == "warn":
        # The product path rechecks ``resource_fields`` with the same
        # authority; warn mode keeps the call running with a warning.
        result = data_invoke(
            operation,
            payload,
            context,
            runtime=runtime,
            resolver=resolver,
            enforcement=config,
        )
        if outcome.ok:
            return result
        if outcome.issue is not None:
            result.issues.append(
                Issue(
                    code=ACCESS_DENIED_CODE,
                    severity=Severity.warning,
                    message="[warn] " + outcome.issue.message,
                    retryable=False,
                )
            )
        return result
    return _denied(
        operation,
        outcome.issue.message if outcome.issue else "access recheck failed",
    )


__all__ = [
    "RESOURCE_FIELDS",
    "gate_resource_refs",
    "enforce_data_invoke",
]
