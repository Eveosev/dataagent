"""DA02.4.1 table profile and DA02.4.3 field type inference."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    Completeness,
    CompletenessExtent,
    Issue,
    SchemaRef,
    Severity,
    TableRef,
    VersionedRef,
)

from dataagent_data.adapters.parsers.excel import infer_scalar_type
from dataagent_data.contracts.layer import ProfileRef
from dataagent_data import helpers
from dataagent_runtime.errors import invalid_input
from dataagent_data.registry import operation


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _field_stats(table) -> list[dict[str, Any]]:
    stats: list[dict[str, Any]] = []
    for index, column in enumerate(table.columns):
        values = [row[index] for row in table.rows if index < len(row)]
        non_null = [value for value in values if value not in (None, "")]
        type_counts: dict[str, int] = {}
        for value in non_null:
            kind = infer_scalar_type(value)
            type_counts[kind] = type_counts.get(kind, 0) + 1
        numeric = [value for value in non_null if isinstance(value, (int, float)) and not isinstance(value, bool)]
        stat: dict[str, Any] = {
            "field_id": column.field_id,
            "name": column.name,
            "count": len(values),
            "non_null_count": len(non_null),
            "null_count": len(values) - len(non_null),
            "distinct_count": len({str(value) for value in non_null}),
            "type_counts": type_counts,
            "min": min(numeric) if numeric else None,
            "max": max(numeric) if numeric else None,
            "mean": round(sum(numeric) / len(numeric), 6) if numeric else None,
            "sample_values": [str(value)[:40] for value in non_null[:5]],
        }
        stats.append(stat)
    return stats


class ProfileTableStructureInput(_Model):
    table_ref: TableRef | None = None
    schema_ref: VersionedRef | None = None
    sample_spec: str | None = None
    budget_rows: int | None = Field(default=None, ge=1)


class ProfileTableStructureOutput(_Model):
    profile: ProfileRef
    fields: list[dict[str, Any]] = Field(default_factory=list)


@operation(
    "DA02.4.1",
    input_model=ProfileTableStructureInput,
    output_model=ProfileTableStructureOutput,
    description="表结构画像",
    writes=True,
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("table_ref",),
)
def profile_table_structure(
    data: ProfileTableStructureInput, ctx: CallContext, runtime
) -> CapabilityResult[ProfileTableStructureOutput]:
    if data.table_ref is None:
        raise invalid_input("profile_table_structure requires table_ref")
    table = helpers.load_table(runtime, data.table_ref)
    rows = table.rows
    method: Literal["exact", "sampled"] = "exact"
    if data.budget_rows is not None and len(rows) > data.budget_rows:
        rows = rows[: data.budget_rows]
        method = "sampled"
    sampled = table.model_copy(update={"rows": rows})
    stats = _field_stats(sampled)
    stats_payload = {
        "fields": stats,
        "method": method,
        "sample_spec": data.sample_spec,
        "source_table": data.table_ref.asset.id,
    }
    stats_digest = runtime.content.put(stats_payload)
    asset = helpers.asset_for(stats_digest, "profile", helpers.scope_of(ctx))
    profile = ProfileRef(
        asset=asset,
        dataset_ref=data.table_ref.asset.id,
        field_stats_ref=stats_digest,
        method=method,
        sample_spec=data.sample_spec,
        observed_at=helpers.now(),
    )
    completeness = Completeness(
        extent=(
            CompletenessExtent.complete_in_declared_scope
            if method == "exact"
            else CompletenessExtent.sampled
        ),
        declared_scope="table rows",
        observed={"rows": len(rows)},
    )
    return CapabilityResult[ProfileTableStructureOutput](
        status=CapabilityStatus.ok,
        data=ProfileTableStructureOutput(profile=profile, fields=stats),
        completeness=completeness,
        provenance=[VersionedRef(id=data.table_ref.asset.id, revision=data.table_ref.asset.revision)],
    )


class InferFieldTypesInput(_Model):
    table_ref: TableRef | None = None
    schema_ref: VersionedRef | None = None
    profile_ref: ProfileRef | None = None
    allowed_types: list[str] = Field(
        default_factory=lambda: ["string", "number", "date", "boolean"]
    )


class FieldTypeResult(_Model):
    field_id: str
    status: Literal["inferred", "conflict", "unknown"]
    inferred_type: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    observed_types: list[str] = Field(default_factory=list)
    basis: str = ""


class InferFieldTypesOutput(_Model):
    fields: list[FieldTypeResult]
    conflicts: list[str] = Field(default_factory=list)


@operation(
    "DA02.4.3",
    input_model=InferFieldTypesInput,
    output_model=InferFieldTypesOutput,
    description="字段类型推断",
    # DA12.1 access recheck reads these fields (08 §4.3, W1d): both the
    # inline table branch and the profile branch read governed content —
    # the profile's field stats are the (derived) content of the profile
    # asset, so an uncovered profile_ref is denied before any read.
    resource_fields=("table_ref", "profile_ref"),
)
def infer_field_types(
    data: InferFieldTypesInput, ctx: CallContext, runtime
) -> CapabilityResult[InferFieldTypesOutput]:
    stats: list[dict[str, Any]] = []
    if data.profile_ref is not None:
        profile = data.profile_ref
        asset = profile.asset
        # r28/r30 B1, second line of defence: the runtime recheck already
        # refuses a profile whose ``field_stats_ref`` is not the asset
        # revision/digest before any read; the handler refuses it too, so the
        # stats can never be read from an object other than the one the asset
        # (and the decision covering it) names — even when the recheck is
        # disabled. r30 B1.2: this binds for **every** resolver string: a
        # self-declared ``resolver="workspace"`` label must not opt the asset
        # out of the content binding.
        if profile.field_stats_ref != asset.revision or (
            asset.digest is not None and profile.field_stats_ref != asset.digest
        ):
            raise invalid_input(
                "profile_ref.field_stats_ref is not the profile asset's "
                "content; refusing to read unbound field stats"
            )
        stats = runtime.content.get_json(profile.field_stats_ref)["fields"]
    elif data.table_ref is not None:
        stats = _field_stats(helpers.load_table(runtime, data.table_ref))
    else:
        raise invalid_input("infer_field_types requires table_ref or profile_ref")

    allowed = set(data.allowed_types)
    results: list[FieldTypeResult] = []
    conflicts: list[str] = []
    for stat in stats:
        type_counts: dict[str, int] = stat.get("type_counts") or {}
        observed = sorted(type_counts)
        if not observed:
            results.append(
                FieldTypeResult(
                    field_id=stat["field_id"],
                    status="unknown",
                    confidence=0.0,
                    observed_types=[],
                    basis="all values null",
                )
            )
            continue
        top = max(type_counts, key=type_counts.get)
        if top not in allowed:
            results.append(
                FieldTypeResult(
                    field_id=stat["field_id"],
                    status="unknown",
                    inferred_type=None,
                    confidence=round(type_counts[top] / stat["non_null_count"], 4),
                    observed_types=observed,
                    basis=f"observed type {top!r} is not in allowed_types",
                )
            )
            continue
        if len(observed) == 1:
            results.append(
                FieldTypeResult(
                    field_id=stat["field_id"],
                    status="inferred",
                    inferred_type=top,
                    confidence=round(type_counts[top] / stat["non_null_count"], 4),
                    observed_types=observed,
                    basis="single observed scalar type",
                )
            )
        else:
            conflicts.append(stat["field_id"])
            results.append(
                FieldTypeResult(
                    field_id=stat["field_id"],
                    status="conflict",
                    inferred_type=None,
                    confidence=round(max(type_counts.values()) / stat["non_null_count"], 4),
                    observed_types=observed,
                    basis="mixed observed types; majority not used to hide the conflict",
                )
            )
    issues = [
        Issue.standard(
            "da02.type_conflict",
            f"field has mixed types: {field_id}",
            severity=Severity.warning,
            target=field_id,
            suggested_action="confirm the field type with the data owner",
        )
        for field_id in conflicts
    ]
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[InferFieldTypesOutput](
        status=status,
        data=InferFieldTypesOutput(fields=results, conflicts=conflicts),
        issues=issues,
        completeness=helpers.complete("field type candidates", {"fields": len(results)}),
    )
