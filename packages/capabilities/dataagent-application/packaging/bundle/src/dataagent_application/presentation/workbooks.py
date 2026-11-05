"""Result workbook generation (DA10.1.1, 07 §5.5).

openpyxl workbook with value-only cells: the result sheet, the 口径与来源
sheet (metric versions, input versions, SQL digest) and the assumptions /
uncovered sheet. No formulas that need recalculation are written.
"""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from pydantic import BaseModel, ConfigDict, Field as PydanticField

from dataagent_contracts.core import (
    AssetRef,
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    ComputedResult,
    Issue,
    Severity,
    VersionedRef,
)

from dataagent_application import helpers
from dataagent_runtime.errors import invalid_input
from dataagent_runtime.registry import operation


class _IO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BuildResultWorkbookInput(_IO):
    result: dict[str, Any]
    title: str = "结果工作簿"


class BuildResultWorkbookOutput(_IO):
    asset: AssetRef
    sheets: list[str]


def _sheet_rows(result: ComputedResult, runtime) -> tuple[list[str], list[list[Any]]]:
    if result.form == "scalar":
        return ["value"], [[result.value]]
    table = helpers.load_computed_table(runtime, result.table_ref)
    headers = [column.name for column in table.columns]
    rows = [list(row) for row in table.rows]
    return headers, rows


@operation(
    "DA10.1.1",
    input_model=BuildResultWorkbookInput,
    output_model=BuildResultWorkbookOutput,
    description="结果工作簿生成：openpyxl 只写值；结果表、口径与来源表、未覆盖与假设表（DA10.1.1）",
    writes=True,
)
def build_result_workbook(
    data: BuildResultWorkbookInput, ctx: CallContext, runtime
) -> CapabilityResult[BuildResultWorkbookOutput]:
    result = ComputedResult.model_validate(data.result)
    headers, rows = _sheet_rows(result, runtime)

    workbook = Workbook()
    issues: list[Issue] = []

    sheet = workbook.active
    sheet.title = "结果"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)

    provenance = workbook.create_sheet("口径与来源")
    provenance.append(["项", "值"])
    provenance.append(["result_id", result.result_id])
    provenance.append(["form", result.form])
    provenance.append(["grain", result.grain])
    if result.unit:
        provenance.append(["unit", result.unit])
    if result.sql_digest:
        provenance.append(["sql_digest", result.sql_digest])
    if result.engine_binding:
        provenance.append(
            ["engine", f"{result.engine_binding.engine_id}@{result.engine_binding.engine_version}"]
        )
    for ref in result.semantic_versions:
        provenance.append(["metric_version", str(ref)])
    provenance.append(["target_ref", str(result.target_ref)])
    if result.time_range:
        provenance.append(
            [
                "time_range",
                f"{result.time_range.from_} .. {result.time_range.to}",
            ]
        )
    for applied in result.filters_applied:
        provenance.append(["filter", applied])
    provenance.append(
        ["completeness", f"{result.completeness.extent.value} ({result.completeness.declared_scope})"]
    )

    coverage = workbook.create_sheet("假设与未覆盖")
    coverage.append(["类型", "内容"])
    for assumption in result.assumptions:
        coverage.append(["assumption", assumption])
    if result.completeness.extent.value == "truncated":
        coverage.append(["not_covered", result.completeness.reason or "result was truncated"])
    if not result.assumptions and result.completeness.extent.value != "truncated":
        coverage.append(["assumption", "none"])

    buffer = io.BytesIO()
    workbook.save(buffer)
    digest = runtime.content.put(buffer.getvalue())
    asset = helpers.asset_for(
        digest, "workbook", ctx.scope_ref, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    if not rows and result.form == "table":
        issues.append(
            Issue(
                code="da10.empty_result_table",
                severity=Severity.warning,
                message="the result table is empty",
                retryable=False,
            )
        )
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[BuildResultWorkbookOutput](
        status=status,
        data=BuildResultWorkbookOutput(
            asset=asset, sheets=["结果", "口径与来源", "假设与未覆盖"]
        ),
        issues=issues,
        provenance=[result.target_ref],
        completeness=helpers.complete("workbook generation", {"rows": len(rows)}),
    )
