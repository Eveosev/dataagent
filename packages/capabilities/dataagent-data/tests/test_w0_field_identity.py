"""W0 §1 field identity: name -> field_id canonicalization (tester r20 B1).

The extraction chain registers the tables of a source file (versioned
``file_tables`` objects); ``define_metric_formula`` resolves human header
names to the stable ``field_id`` identities those tables carry, and fixed
filters carry their referenced field ids so the application layer can bind
the caliber. Ambiguous names stay unresolved, and ids are never rewritten.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from dataagent_contracts.core import CallContext, FileRef, SourceAnchor, TableRef, VersionedRef

from dataagent_data import helpers, invoke
from dataagent_data.runtime import create as create_runtime


def _ctx() -> CallContext:
    return CallContext(
        request_id="req:w0",
        scope_ref="tenant:test/project:p1",
        authorization_ref="policy:test-read",
    )


def _xlsx(path: Path) -> None:
    """The irregular-expense shape used by the S0 scenario/probe chain."""

    from datetime import datetime

    from openpyxl import Workbook

    wb = Workbook()
    sh = wb.active
    sh.title = "Expense"
    sh.append(["费用报销明细（CNY）"])
    sh.append([])
    sh.append(["部门", "金额", "发生日期", "状态"])
    sh.append(["研发", 1200, datetime(2026, 1, 5), "已支付"])
    sh.append([None, 800, datetime(2026, 1, 6), "已支付"])
    sh.append(["销售", 500, datetime(2026, 1, 7), "已退款"])
    sh.append(["合计", 2500, None, None])
    sh.merge_cells("A4:A5")
    wb.save(path)


def _file_ref(runtime, workspace: Path, name: str) -> FileRef:
    return helpers.file_ref(runtime, name)


def _call(op: str, payload: dict, ctx, runtime):
    result = invoke.invoke(op, payload, ctx, runtime=runtime)
    assert result.status.value in {"ok", "partial"}, [i.message for i in result.issues]
    return result


def _metric_payload(file_ref: FileRef, proposal: dict) -> dict:
    return {
        "statement": "paid expense",
        "available_fields": ["部门", "金额", "状态"],
        "sources": [
            {
                "source_ref": file_ref.id,
                "source_revision": file_ref.revision,
                "selector": {"kind": "excel_cell", "sheet": "Expense", "range": "A1"},
            }
        ],
        "proposal": proposal,
    }


def _fake_file_ref(seed: str) -> FileRef:
    digest = "sha256:" + hashlib.sha256(seed.encode()).hexdigest()
    return FileRef(
        id="file:" + digest[7:23],
        kind="file",
        scope_ref="tenant:test",
        revision=digest,
        resolver="workspace",
        locator=f"{seed}.xlsx",
        digest=digest,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{seed}.xlsx",
        size_bytes=1,
        content_digest=digest,
    )


def _register_tables(runtime, ref: FileRef, payloads: list[dict]) -> None:
    helpers.register_file_ref(runtime, ref)
    helpers.register_file_tables(
        runtime,
        ref,
        [
            TableRef(
                asset=helpers.asset_for(
                    runtime.content.put(payload), "table", "tenant:test"
                ),
                schema_ref=VersionedRef(id=f"schema:{index}", revision="r1"),
                data_ref=runtime.content.put(payload),
            )
            for index, payload in enumerate(payloads)
        ],
    )


def _anchors(ref: FileRef) -> list[SourceAnchor]:
    return [
        SourceAnchor(
            source_ref=ref.id,
            source_revision=ref.revision,
            selector={"kind": "json_pointer", "pointer": "/x"},
        )
    ]


def test_extract_registers_file_tables(workspace, tmp_path):
    runtime = create_runtime(workspace_root=workspace, data_root=tmp_path / "data")
    _xlsx(workspace / "expense.xlsx")
    ref = _file_ref(runtime, workspace, "expense.xlsx")
    extracted = _call(
        "extract_irregular_excel", {"file_ref": ref.model_dump(mode="json")}, _ctx(), runtime
    )
    tables = helpers.find_file_tables(runtime, ref.id, ref.revision)
    assert tables and tables[0]["data_ref"] == extracted.data.tables[0].data_ref


def test_metric_formula_canonicalizes_names_to_field_ids(workspace, tmp_path):
    runtime = create_runtime(workspace_root=workspace, data_root=tmp_path / "data")
    _xlsx(workspace / "expense.xlsx")
    ref = _file_ref(runtime, workspace, "expense.xlsx")
    _call(
        "extract_irregular_excel", {"file_ref": ref.model_dump(mode="json")}, _ctx(), runtime
    )

    metric = _call(
        "define_metric_formula",
        _metric_payload(
            ref,
            {
                "measure_field": "金额",
                "aggregation": "sum",
                "filters": ["状态 = '已支付'"],
                "dimensions": ["部门"],
                "grain": "部门",
                "additivity": "additive",
            },
        ),
        _ctx(),
        runtime,
    )
    definition = metric.data.draft.definition
    # W0 §1.2: the draft cites stable field ids, not header names.
    assert definition.measure.field_ref == "c2"
    assert definition.dimensions == ["c1"]
    assert definition.filters[0].referenced_fields == ["c4"]
    assert not metric.data.draft.unresolved


def test_field_ids_are_accepted_directly(workspace, tmp_path):
    runtime = create_runtime(workspace_root=workspace, data_root=tmp_path / "data")
    _xlsx(workspace / "expense.xlsx")
    ref = _file_ref(runtime, workspace, "expense.xlsx")
    _call(
        "extract_irregular_excel", {"file_ref": ref.model_dump(mode="json")}, _ctx(), runtime
    )

    metric = _call(
        "define_metric_formula",
        _metric_payload(
            ref,
            {
                "measure_field": "c2",
                "aggregation": "sum",
                "filters": [],
                "dimensions": ["c1"],
                "grain": "c1",
                "additivity": "additive",
            },
        ),
        _ctx(),
        runtime,
    )
    assert metric.data.draft.definition.measure.field_ref == "c2"


def test_ambiguous_name_is_not_canonicalized(tmp_path):
    """One name resolving to two field ids keeps the human name."""

    runtime = create_runtime(workspace_root=tmp_path / "ws", data_root=tmp_path / "data")
    ref = _fake_file_ref("ambiguous")
    _register_tables(
        runtime,
        ref,
        [
            {"columns": [{"name": "金额", "field_id": "c1"}], "rows": [], "row_meta": []},
            {"columns": [{"name": "金额", "field_id": "c2"}], "rows": [], "row_meta": []},
        ],
    )
    field_map = helpers.file_field_map(runtime, _anchors(ref))
    assert "金额" not in field_map


def test_name_colliding_with_another_id_is_dropped(tmp_path):
    """A name that is also another column's id is unsafe and not resolved."""

    runtime = create_runtime(workspace_root=tmp_path / "ws", data_root=tmp_path / "data")
    ref = _fake_file_ref("collide")
    _register_tables(
        runtime,
        ref,
        [
            {
                "columns": [
                    {"name": "c1", "field_id": "c9"},
                    {"name": "金额", "field_id": "c1"},
                ],
                "rows": [],
                "row_meta": [],
            }
        ],
    )
    field_map = helpers.file_field_map(runtime, _anchors(ref))
    # The name "c1" is also column 2's field_id: rewriting a "c1" citation
    # to "c9" would silently change its meaning, so that mapping is dropped;
    # "金额" -> "c1" survives, and id citations always win.
    assert "c1" not in field_map
    assert field_map["金额"] == "c1"


def test_unrelated_sources_leave_the_draft_unchanged(workspace, tmp_path):
    """A registered file without extracted tables keeps raw citations."""

    runtime = create_runtime(workspace_root=workspace, data_root=tmp_path / "data")
    _xlsx(workspace / "expense.xlsx")
    ref = _file_ref(runtime, workspace, "expense.xlsx")
    helpers.register_file_ref(runtime, ref)
    metric = _call(
        "define_metric_formula",
        {
            "statement": "paid expense",
            "available_fields": ["金额"],
            "sources": [
                {
                    "source_ref": ref.id,
                    "source_revision": ref.revision,
                    "selector": {"kind": "excel_cell", "sheet": "Expense", "range": "A1"},
                }
            ],
            "proposal": {
                "measure_field": "金额",
                "aggregation": "sum",
                "filters": [],
                "dimensions": [],
                "grain": "row",
                "additivity": "additive",
            },
        },
        _ctx(),
        runtime,
    )
    assert metric.data.draft.definition.measure.field_ref == "金额"
    assert metric.data.draft.definition.filters == []
