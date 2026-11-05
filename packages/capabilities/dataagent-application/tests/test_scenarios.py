"""End-to-end chains (07 §11.4): 判定族 and 计算族."""

from __future__ import annotations

from dataagent_contracts.core import CapabilityStatus

from dataagent_application.execution import expressions as exe
from dataagent_application.planning import expressions as plan
from dataagent_application.presentation import reports, workbooks
from dataagent_application.execution import sql as sql_exec

from tests.conftest import store_table
from tests.test_planning_expressions import FIELDS, RULE
from tests.test_execution_expressions import LE, _record, _field

REPORT_RULE = {
    "title": "单据判定报告",
    "conclusion": "该单据金额满足上限规则。",
    "sections": [
        {
            "heading": "规则与求值",
            "body_markdown": "金额 1200 元，上限 5000 元，判定 satisfied。",
            "evidence_refs": ["field:amount"],
        }
    ],
    "evidence": [
        {
            "id": "field:amount",
            "evidence_type": "extracted_value",
            "value": 1200,
            "obtained_by": "da07.5.1/evaluate_scalar_expression",
            "source_anchors": [
                {
                    "source_ref": "invoice-1",
                    "source_revision": "r1",
                    "selector": {"kind": "excel_cell", "sheet": "S1", "range": "C2"},
                }
            ],
        }
    ],
}


def test_judgment_family_chain(runtime, ctx):
    """RuleDefinition → AST → Assessment; unknown 不折算，evidence 带锚点。"""

    ast = {
        "op": "and",
        "args": [
            {
                "op": "le",
                "args": [
                    {"op": "field", "field_id": "amount", "condition_id": "c1"},
                    {"op": "literal", "value": 5000},
                ],
            },
            {
                "op": "in",
                "args": [
                    {"op": "field", "field_id": "region", "condition_id": "c2"},
                    {"op": "literal", "value": ["north", "south"]},
                ],
            },
        ],
    }
    generated = plan.generate_function_expressions(
        plan.GenerateFunctionExpressionsInput.model_validate(
            {"rule": RULE, "fields": FIELDS, "proposal": {"expression": ast}}
        ),
        ctx,
        runtime,
    )
    # rule has an exception clause not compiled by the proposal: partial + warning
    assert generated.status is CapabilityStatus.partial
    assert any(i.code == "da06.exceptions_not_compiled" for i in generated.issues)

    record = _record(
        [
            _field("amount", 1200),
            _field(
                "region",
                "north",
                anchors=[
                    {
                        "source_ref": "invoice-1",
                        "source_revision": "r1",
                        "selector": {"kind": "excel_cell", "sheet": "S1", "range": "B2"},
                    }
                ],
            ),
        ]
    )
    evaluated = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate(
            {"spec": generated.data.spec.model_dump(mode="json"), "record": record}
        ),
        ctx,
        runtime,
    )
    assert evaluated.data.assessment.verdict == "pass"
    ids = {e.id for e in evaluated.data.assessment.evidence}
    assert ids == {"field:amount", "field:region"}
    anchors = [a.source_ref for e in evaluated.data.assessment.evidence for a in e.source_anchors]
    assert set(anchors) == {"invoice-1"}

    # Missing region must give unknown, never satisfied/violated.
    record_missing = _record([_field("amount", 1200), _field("region", None, status="missing")])
    unknown = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate(
            {"spec": generated.data.spec.model_dump(mode="json"), "record": record_missing}
        ),
        ctx,
        runtime,
    )
    assert unknown.data.assessment.verdict == "unknown"


def test_compute_family_chain(runtime, ctx):
    """不规则工作簿表 → TableRef → MetricDefinition → RequirementSpec → SQL → ComputedResult → 工作簿/报告。"""

    table = store_table(
        runtime,
        columns=[
            {"name": "Region", "field_id": "region", "value_type": "string"},
            {"name": "Amount", "field_id": "amount", "value_type": "number", "unit": "CNY"},
        ],
        rows=[["north", 100], ["south", 200], ["TOTAL", 300]],
        row_meta=[
            {"role": "detail", "reason": ""},
            {"role": "detail", "reason": ""},
            {"role": "total", "reason": "grand total"},
        ],
    )
    table_payload = {
        "asset": table.asset.model_dump(mode="json"),
        "schema_ref": "schema:x@r1",
        "data_ref": table.data_ref,
    }
    metric = {
        "draft_id": "mtd-amount",
        "revision": "r1",
        "kind": "metric",
        "definition": {
            "statement": "费用总额 = 明细行金额之和",
            "measure": {"field_ref": "amount", "aggregation": "sum"},
            "grain": "region",
            "additivity": "additive",
            "unit": "CNY",
        },
        "scope_ref": "scope-1",
        "sources": [
            {
                "source_ref": "doc-1",
                "source_revision": "r1",
                "selector": {"kind": "text_span", "unit_ref": "unit:char", "char_start": 0, "char_end": 8},
            }
        ],
        "status": "validated",
    }
    from dataagent_application.planning import requirements as req

    bound = req.bind_metrics_and_dimensions(
        req.BindMetricsAndDimensionsInput.model_validate(
            {
                "statement": "按区域统计费用总额",
                "table_ref": table_payload,
                "metrics": [metric],
                "proposal": {"metric_ids": ["mtd-amount"], "dimensions": ["region"], "grain": "region"},
            }
        ),
        ctx,
        runtime,
    )
    assert bound.status is CapabilityStatus.ok

    sql_name = plan._sql_table_name(table)
    generated = plan.generate_single_table_sql(
        plan.GenerateSingleTableSqlInput.model_validate(
            {
                "table_ref": table_payload,
                "metrics": [metric],
                "requirement": bound.data.requirement.model_dump(mode="json"),
                "proposal": {
                    "sql": f"SELECT region, sum(amount) AS total FROM {sql_name} GROUP BY region"
                },
            }
        ),
        ctx,
        runtime,
    )
    assert generated.status is CapabilityStatus.ok

    executed = sql_exec.execute_duckdb_sql(
        sql_exec.ExecuteDuckdbSqlInput.model_validate(
            {
                "spec": generated.data.spec.model_dump(mode="json"),
                "table_refs": [table_payload],
                "semantic_versions": ["mtd-amount@r1"],
                "grain": "region",
                "unit": "CNY",
            }
        ),
        ctx,
        runtime,
    )
    assert executed.status is CapabilityStatus.ok
    assert executed.data.result.form == "table"
    from dataagent_application.planning.expressions import sql_digest
    assert executed.data.result.sql_digest == sql_digest(generated.data.spec.sql)
    assert str(executed.data.result.semantic_versions[0]) == "mtd-amount@r1"

    workbook = workbooks.build_result_workbook(
        workbooks.BuildResultWorkbookInput.model_validate(
            {"result": executed.data.result.model_dump(mode="json")}
        ),
        ctx,
        runtime,
    )
    assert workbook.status is CapabilityStatus.ok
    assert workbook.data.sheets[0] == "结果"

    report = reports.compose_document_report(
        reports.ComposeDocumentReportInput.model_validate(REPORT_RULE), ctx, runtime
    )
    assert report.status is CapabilityStatus.ok
    exported = reports.export_report_format(
        reports.ExportReportFormatInput.model_validate(
            {"report_ref": report.data.report_ref.model_dump(mode="json"), "format": "md"}
        ),
        ctx,
        runtime,
    )
    assert exported.status is CapabilityStatus.ok
    assert runtime.content.exists(exported.data.asset.digest)
