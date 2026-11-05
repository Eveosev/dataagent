"""DA02.12 extraction atoms: two-phase extraction, anchoring, schema versions."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    Completeness,
    CompletenessExtent,
    Confidence,
    DocumentRef,
    ExtractedRecordRef,
    FieldSpec,
    FieldValue,
    FieldValueStatus,
    Issue,
    Severity,
    SourceAnchor,
    VersionedRef,
)

from dataagent_data.contracts.layer import ExtractionSchemaRef
from dataagent_data.preparation.documents import load_document_content
from dataagent_data.anchors import (
    AnchorResolver,
    anchor_invalid_reason,
    anchor_value_mismatch,
    find_value_span,
)
from dataagent_data import helpers
from dataagent_runtime.errors import invalid_input, not_found, version_conflict
from dataagent_data.registry import operation


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Value types the target-schema check can verify locally. Types outside these
# sets (dates, custom types) are not verifiable without a parser and are left
# to the caller; type/unit conformance against the FieldSpec is still enforced
# for everything known (reviewer F5).
_NUMERIC_VALUE_TYPES = frozenset(
    {"number", "integer", "decimal", "float", "money", "amount", "currency",
     "percent", "percentage", "quantity"}
)
_TEXT_VALUE_TYPES = frozenset({"string", "text", "str", "char"})
_BOOLEAN_VALUE_TYPES = frozenset({"boolean", "bool"})


def _value_matches_type(value: Any, value_type: str) -> bool:
    normalized = (value_type or "").strip().lower()
    if not normalized:
        return True
    if normalized in _BOOLEAN_VALUE_TYPES:
        return isinstance(value, bool)
    if normalized in _NUMERIC_VALUE_TYPES:
        if isinstance(value, bool):
            return False
        from dataagent_data.anchors import _as_decimal

        return _as_decimal(value) is not None
    if normalized in _TEXT_VALUE_TYPES:
        return isinstance(value, str)
    return True  # unknown types cannot be verified locally


def _target_schema_mismatch(field: FieldSpec, proposal: FieldProposal) -> str:
    """Why ``proposal`` cannot fill ``field`` (empty string when it can)."""

    if (
        proposal.value_type
        and field.value_type
        and proposal.value_type.strip().lower() != field.value_type.strip().lower()
    ):
        return (
            f"proposal value_type {proposal.value_type!r} does not match the "
            f"target field type {field.value_type!r}"
        )
    if proposal.unit and field.unit and proposal.unit != field.unit:
        return (
            f"proposal unit {proposal.unit!r} does not match the target "
            f"field unit {field.unit!r}"
        )
    if not _value_matches_type(proposal.value, field.value_type):
        return (
            f"value {proposal.value!r} does not match the target field type "
            f"{field.value_type!r}"
        )
    return ""


class FieldProposal(_Model):
    field_id: str = Field(min_length=1)
    value: Any | None = None
    value_type: str = "string"
    unit: str | None = None
    confidence: Confidence | None = None
    anchors: list[SourceAnchor] = Field(default_factory=list)
    alternatives: list[Any] | None = None


class ExtractFieldsInput(_Model):
    document_ref: DocumentRef
    target_schema_ref: VersionedRef | None = None
    target_schema: ExtractionSchemaRef | None = None
    fields: list[FieldSpec] | None = None
    proposal: list[FieldProposal] | None = None
    strategy: str = "agent_structured"


class CandidateSpan(_Model):
    page: int
    char_start: int
    char_end: int
    text: str


class ExtractFieldsOutput(_Model):
    record: ExtractedRecordRef | None = None
    target_schema_ref: VersionedRef
    candidate_spans: list[CandidateSpan] = Field(default_factory=list)


def _resolve_schema(runtime, data: ExtractFieldsInput) -> tuple[list[FieldSpec], VersionedRef]:
    if data.target_schema is not None:
        return (
            data.target_schema.fields,
            VersionedRef(id=data.target_schema.schema_id, revision=data.target_schema.revision),
        )
    if data.fields:
        digest = hashlib.sha256(
            json.dumps([f.model_dump(mode="json") for f in data.fields], sort_keys=True).encode()
        ).hexdigest()
        ref = data.target_schema_ref or VersionedRef(id="xschema:adhoc", revision=digest[:12])
        return data.fields, ref
    if data.target_schema_ref is not None:
        payload = runtime.versions.get(
            "extraction_schema", data.target_schema_ref.id, data.target_schema_ref.revision
        )
        if payload is None:
            raise not_found(f"extraction schema not found: {data.target_schema_ref}")
        return [FieldSpec.model_validate(f) for f in payload["fields"]], data.target_schema_ref
    raise invalid_input("extract_fields_to_schema requires fields, target_schema or target_schema_ref")


def _candidate_spans(
    runtime, document: DocumentRef, limit: int = 30
) -> tuple[list[CandidateSpan], list[str]]:
    """Collect sentence-level candidate spans for the inference request.

    Returns the spans plus a list of truncation disclosures: span text is
    capped at 300 characters and the span list at ``limit``. Callers must
    surface the disclosures in ``Completeness`` instead of claiming the
    prepared context is complete (06 §4.1; tester r17 R5).
    """

    content = load_document_content(runtime, document)
    spans: list[CandidateSpan] = []
    truncations: list[str] = []
    for page in content.pages:
        for match in re.finditer(r"[^。；;\n]+[。；;]?", page.text):
            text = match.group(0).strip()
            if not text:
                continue
            if len(text) > 300:
                truncations.append(
                    f"span text capped at 300 of {len(text)} characters"
                )
                text = text[:300]
            spans.append(
                CandidateSpan(
                    page=page.page,
                    char_start=match.start(),
                    char_end=match.end(),
                    text=text,
                )
            )
    if len(spans) > limit:
        truncations.append(
            f"candidate spans capped at {limit} of {len(spans)} detected spans"
        )
        spans = spans[:limit]
    return spans, truncations


def _evaluate_field(
    field: FieldSpec,
    candidates: list[FieldProposal],
    resolver: AnchorResolver,
    document_ref: DocumentRef,
) -> tuple[FieldValue, list[Issue]]:
    """Resolve one field's proposal into a value plus the issues it raised.

    Extracted from :func:`extract_fields_to_schema` (06 §14 item 7) with no
    behaviour change: every branch still downgrades to ``missing``/``conflict``
    unless an anchor resolves *and* supports the value.
    """

    def ungrounded(
        status: FieldValueStatus,
        *,
        value_type: str | None = None,
        unit: str | None = None,
        alternatives: list[Any] | None = None,
        evidence: list[SourceAnchor] | None = None,
    ) -> FieldValue:
        return FieldValue(
            field_id=field.field_id,
            status=status,
            value_type=value_type or field.value_type,
            unit=unit or field.unit,
            alternatives=alternatives,
            evidence=evidence or [],
        )

    if not candidates:
        return ungrounded(FieldValueStatus.missing), [
            Issue(
                code="da02.field_missing",
                severity=Severity.warning,
                message=f"no grounded proposal for field {field.field_id}",
                target=field.field_id,
                retryable=False,
                suggested_action="supply an anchored value or leave it missing",
            )
        ]
    if len({str(item.value) for item in candidates}) > 1:
        alternatives = [item.value for item in candidates]
        return (
            ungrounded(FieldValueStatus.conflict, alternatives=alternatives),
            [
                Issue(
                    code="da02.field_conflict",
                    severity=Severity.warning,
                    message=f"multiple proposals for field {field.field_id}",
                    target=field.field_id,
                    retryable=False,
                    suggested_action="resolve the conflict with the source",
                    alternatives=alternatives,
                )
            ],
        )
    proposal = candidates[0]
    if proposal.value is None:
        return (
            ungrounded(
                FieldValueStatus.missing,
                value_type=proposal.value_type,
                unit=proposal.unit,
            ),
            [
                Issue(
                    code="da02.value_required",
                    severity=Severity.warning,
                    message=f"proposal for {field.field_id} has no value; downgraded to missing",
                    target=field.field_id,
                    retryable=False,
                    suggested_action="omit the field or supply a grounded value",
                )
            ],
        )
    valid_anchors: list[SourceAnchor] = []
    invalid_reason = ""
    for anchor in proposal.anchors:
        if anchor.source_ref != document_ref.original_ref.id:
            invalid_reason = "anchor source_ref does not match the document"
            continue
        if anchor.source_revision != document_ref.original_ref.revision:
            invalid_reason = "anchor source_revision does not match the document revision"
            continue
        reason = anchor_invalid_reason(resolver, anchor)
        if not reason:
            reason = anchor_value_mismatch(resolver, anchor, proposal.value)
        if reason:
            invalid_reason = reason
        else:
            valid_anchors.append(anchor)
    if not proposal.anchors:
        return (
            ungrounded(
                FieldValueStatus.missing,
                value_type=proposal.value_type,
                unit=proposal.unit,
            ),
            [
                Issue(
                    code="da02.unanchored_value",
                    severity=Severity.warning,
                    message=f"value for {field.field_id} has no source anchor; downgraded to missing",
                    target=field.field_id,
                    retryable=False,
                    suggested_action="provide a SourceAnchor that exists in the document",
                )
            ],
        )
    if not valid_anchors:
        return (
            ungrounded(
                FieldValueStatus.missing,
                value_type=proposal.value_type,
                unit=proposal.unit,
            ),
            [
                Issue(
                    code="da02.anchor_not_found",
                    severity=Severity.warning,
                    message=f"anchor for {field.field_id} is not present in the source: {invalid_reason}",
                    target=field.field_id,
                    retryable=False,
                    suggested_action="re-anchor the value against existing source text",
                )
            ],
        )
    if proposal.alternatives:
        return (
            ungrounded(
                FieldValueStatus.conflict,
                value_type=proposal.value_type,
                unit=proposal.unit,
                alternatives=proposal.alternatives,
                evidence=valid_anchors,
            ),
            [
                Issue(
                    code="da02.field_conflict",
                    severity=Severity.warning,
                    message=f"field {field.field_id} has competing values",
                    target=field.field_id,
                    retryable=False,
                    suggested_action="confirm one value",
                    alternatives=proposal.alternatives,
                )
            ],
        )
    # An anchored value still has to conform to the *target* field spec
    # (reviewer F5): a proposal that meets the source text but carries the
    # wrong type or unit for the schema is a conflict, not an extraction.
    mismatch = _target_schema_mismatch(field, proposal)
    if mismatch:
        return (
            FieldValue(
                field_id=field.field_id,
                status=FieldValueStatus.conflict,
                value=None,
                value_type=field.value_type,
                unit=field.unit,
                alternatives=[proposal.value],
                evidence=valid_anchors,
            ),
            [
                Issue(
                    code="da02.field_type_mismatch",
                    severity=Severity.warning,
                    message=f"field {field.field_id}: {mismatch}",
                    target=field.field_id,
                    retryable=False,
                    suggested_action=(
                        "propose a value that matches the target field's "
                        "declared type and unit"
                    ),
                )
            ],
        )
    return (
        FieldValue(
            field_id=field.field_id,
            status=FieldValueStatus.extracted,
            value=proposal.value,
            value_type=proposal.value_type or field.value_type,
            unit=proposal.unit or field.unit,
            confidence=proposal.confidence,
            evidence=valid_anchors,
        ),
        [],
    )


@operation(
    "DA02.12.1",
    input_model=ExtractFieldsInput,
    output_model=ExtractFieldsOutput,
    writes=True,
    description="按目标结构抽取字段（两段式）",
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("document_ref",),
)
def extract_fields_to_schema(
    data: ExtractFieldsInput, ctx: CallContext, runtime
) -> CapabilityResult[ExtractFieldsOutput]:
    fields, schema_ref = _resolve_schema(runtime, data)
    content = load_document_content(runtime, data.document_ref)
    resolver = AnchorResolver(content, runtime=runtime)
    known = {field.field_id for field in fields}

    if data.proposal is None:
        spans, truncations = _candidate_spans(runtime, data.document_ref)
        request = {
            "kind": "field_extraction",
            "target_schema_ref": str(schema_ref),
            "fields": [
                {"field_id": f.field_id, "name": f.name, "value_type": f.value_type}
                for f in fields
            ],
            "candidate_spans": [span.model_dump(mode="json") for span in spans],
            "instruction": (
                "Return one proposal per field with anchors that point at existing source text. "
                "Do not invent missing values; omit fields you cannot ground."
            ),
        }
        if truncations:
            request["truncations"] = truncations
        issue = Issue(
            code="da02.inference_required",
            severity=Severity.info,
            message="agent-provided structured extraction is required",
            retryable=False,
            suggested_action="replay the same tool with a proposal produced under the Skill",
            inference_request=request,
        )
        completeness = (
            helpers.truncated(
                "candidate spans prepared",
                reason="; ".join(truncations),
                observed={"spans": len(spans)},
            )
            if truncations
            else helpers.complete("candidate spans prepared", {"spans": len(spans)})
        )
        return CapabilityResult[ExtractFieldsOutput](
            status=CapabilityStatus.needs_input,
            data=ExtractFieldsOutput(
                record=None, target_schema_ref=schema_ref, candidate_spans=spans
            ),
            issues=[issue],
            provenance=[data.document_ref.original_ref],
            completeness=completeness,
        )

    proposals: dict[str, list[FieldProposal]] = {}
    for proposal in data.proposal:
        if proposal.field_id not in known:
            raise invalid_input(f"proposal references unknown field: {proposal.field_id}")
        proposals.setdefault(proposal.field_id, []).append(proposal)

    values: list[FieldValue] = []
    issues: list[Issue] = []
    for field in fields:
        value, field_issues = _evaluate_field(
            field, proposals.get(field.field_id, []), resolver, data.document_ref
        )
        values.append(value)
        issues.extend(field_issues)

    record_payload = [value.model_dump(mode="json") for value in values]
    digest = runtime.content.put(record_payload)
    asset = helpers.asset_for(digest, "extracted_record", helpers.scope_of(ctx))
    runtime.versions.save_content_addressed(
        "extracted_record",
        asset.id,
        {
            "document_ref": str(data.document_ref.original_ref),
            "target_schema_ref": str(schema_ref),
            "fields": record_payload,
        },
    )
    completeness = Completeness(
        extent=(
            CompletenessExtent.complete_in_declared_scope
            if not issues
            else CompletenessExtent.unknown
        ),
        declared_scope=f"target schema {schema_ref}",
        observed={"fields": len(fields), "missing": sum(1 for v in values if v.status is FieldValueStatus.missing)},
    )
    record = ExtractedRecordRef(
        asset=asset,
        document_ref=data.document_ref.original_ref,
        target_schema_ref=schema_ref,
        fields=values,
        issues=issues,
    )
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[ExtractFieldsOutput](
        status=status,
        data=ExtractFieldsOutput(record=record, target_schema_ref=schema_ref),
        issues=issues,
        provenance=[data.document_ref.original_ref, schema_ref],
        completeness=completeness,
    )


class AnchorExtractedValuesInput(_Model):
    record: ExtractedRecordRef
    document_ref: DocumentRef


class AnchorMapping(_Model):
    field_id: str
    anchors: list[SourceAnchor] = Field(default_factory=list)
    status: str


class AnchorExtractedValuesOutput(_Model):
    record: ExtractedRecordRef
    mappings: list[AnchorMapping]
    unlocated: list[str] = Field(default_factory=list)


@operation(
    "DA02.12.3",
    input_model=AnchorExtractedValuesInput,
    output_model=AnchorExtractedValuesOutput,
    writes=True,
    description="抽取结果原文锚定",
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("document_ref",),
)
def anchor_extracted_values(
    data: AnchorExtractedValuesInput, ctx: CallContext, runtime
) -> CapabilityResult[AnchorExtractedValuesOutput]:
    content = load_document_content(runtime, data.document_ref)
    source_ref = data.document_ref.original_ref.id
    source_revision = data.document_ref.original_ref.revision
    # The record and the document passed in must describe the same source
    # revision; otherwise an anchor from another document could be "verified"
    # against the wrong payload.
    if (
        data.record.document_ref.id != source_ref
        or data.record.document_ref.revision != source_revision
    ):
        raise invalid_input(
            "record.document_ref does not match document_ref: "
            f"{data.record.document_ref} != {source_ref}@{source_revision}",
            target="record.document_ref",
        )
    resolver = AnchorResolver(content, runtime=runtime)
    fields: list[FieldValue] = []
    mappings: list[AnchorMapping] = []
    unlocated: list[str] = []
    issues: list[Issue] = []
    for field in data.record.fields:
        if (
            field.status is FieldValueStatus.extracted
            and field.value is None
        ):
            fields.append(
                field.model_copy(
                    update={
                        "status": FieldValueStatus.missing,
                        "value": None,
                        "evidence": [],
                    }
                )
            )
            mappings.append(AnchorMapping(field_id=field.field_id, status="missing"))
            issues.append(
                Issue(
                    code="da02.value_required",
                    severity=Severity.warning,
                    message=f"extracted field {field.field_id} has no value; downgraded to missing",
                    target=field.field_id,
                    retryable=False,
                    suggested_action="supply a value or mark the field missing",
                )
            )
            continue
        anchors = list(field.evidence)
        check_value = field.status is FieldValueStatus.extracted and field.value is not None
        usable: list[SourceAnchor] = []
        invalid_reason = ""
        for anchor in anchors:
            if anchor.source_ref != source_ref or anchor.source_revision != source_revision:
                invalid_reason = (
                    "anchor source_ref/source_revision does not match the record document"
                )
                continue
            reason = anchor_invalid_reason(resolver, anchor)
            if not reason and check_value:
                # An existing anchor is not enough: its text must also support
                # the value, otherwise the field is ungrounded (DA02.12.3).
                reason = anchor_value_mismatch(resolver, anchor, field.value)
            if reason:
                invalid_reason = reason
                continue
            usable.append(anchor)
        if not usable and check_value:
            found = find_value_span(content, field.value)
            if found:
                page, start, end = found
                usable = [
                    helpers.make_anchor(
                        source_ref=source_ref,
                        source_revision=source_revision,
                        page=page,
                        char_start=start,
                        char_end=end,
                    )
                ]
            else:
                unlocated.append(field.field_id)
                fields.append(
                    field.model_copy(update={"status": FieldValueStatus.missing, "value": None, "evidence": []})
                )
                mappings.append(AnchorMapping(field_id=field.field_id, status="missing"))
                message = f"cannot locate value for {field.field_id} in the source"
                if invalid_reason:
                    message = f"{message}: {invalid_reason}"
                issues.append(
                    Issue(
                        code="da02.anchor_not_found",
                        severity=Severity.warning,
                        message=message,
                        target=field.field_id,
                        retryable=False,
                        suggested_action="mark as missing or provide a manual anchor",
                    )
                )
                continue
        updated = field.model_copy(update={"evidence": usable}) if usable else field
        fields.append(updated)
        mappings.append(
            AnchorMapping(
                field_id=field.field_id,
                anchors=usable,
                status="anchored" if usable else field.status.value,
            )
        )
    record_payload = {
        "document_ref": str(data.record.document_ref),
        "target_schema_ref": str(data.record.target_schema_ref),
        "fields": [field.model_dump(mode="json") for field in fields],
    }
    digest = runtime.content.put(record_payload)
    asset = helpers.asset_for(digest, "extracted_record", helpers.scope_of(ctx))
    runtime.versions.save_content_addressed("extracted_record", asset.id, record_payload)
    updated_record = data.record.model_copy(update={"asset": asset, "fields": fields, "issues": issues})
    status = CapabilityStatus.partial if unlocated else CapabilityStatus.ok
    return CapabilityResult[AnchorExtractedValuesOutput](
        status=status,
        data=AnchorExtractedValuesOutput(
            record=updated_record, mappings=mappings, unlocated=unlocated
        ),
        issues=issues,
        provenance=[data.record.document_ref, data.document_ref.original_ref],
        completeness=helpers.complete("record fields", {"fields": len(fields)}),
    )


class RegisterExtractionSchemaInput(_Model):
    schema_id: str = "xschema:record"
    fields: list[FieldSpec] = Field(min_length=1)
    document_type: str | None = None
    change_note: str = ""
    previous_ref: VersionedRef | None = None
    expected_revision: str | None = None


@operation(
    "DA02.12.4",
    input_model=RegisterExtractionSchemaInput,
    output_model=ExtractionSchemaRef,
    writes=True,
    description="抽取标签体系版本化",
    idempotent=True,
)
def register_extraction_schema_version(
    data: RegisterExtractionSchemaInput, ctx: CallContext, runtime
) -> CapabilityResult[ExtractionSchemaRef]:
    current = runtime.versions.current("extraction_schema", data.schema_id)
    expected = data.expected_revision or ctx.expected_revision
    if expected is not None and (current[0] if current else None) != expected:
        raise version_conflict(
            f"extraction schema {data.schema_id}: expected {expected}, "
            f"current {current[0] if current else None}"
        )
    payload = {
        "schema_id": data.schema_id,
        "fields": [field.model_dump(mode="json") for field in data.fields],
        "document_type": data.document_type,
        "change_note": data.change_note,
    }
    digest = "sha256:" + hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    revision, _, existing = runtime.versions.save_content_addressed(
        "extraction_schema",
        data.schema_id,
        payload,
        # The storage layer re-checks this under BEGIN IMMEDIATE; the read
        # above is only a fast path and cannot make the write atomic by itself.
        expected_revision=expected,
    )
    schema = ExtractionSchemaRef(
        schema_id=data.schema_id,
        revision=revision,
        fields=data.fields,
        digest=digest,
        document_type=data.document_type,
        previous_ref=data.previous_ref,
    )
    issues = []
    if existing:
        issues.append(
            Issue.standard(
                "da02.schema_version_idempotent",
                f"same schema content already registered as {revision}",
                severity=Severity.info,
            )
        )
    return CapabilityResult[ExtractionSchemaRef](
        status=CapabilityStatus.ok,
        data=schema,
        issues=issues,
        completeness=helpers.complete("extraction schema", {"fields": len(data.fields)}),
    )
