from __future__ import annotations

from datetime import datetime

from conftest import build_xlsx, call, file_ref, write_file


def make_workbook(workspace, name="expense.xlsx", date1904=False):
    from openpyxl import Workbook
    from openpyxl.utils.datetime import CALENDAR_MAC_1904

    wb = Workbook()
    if date1904:
        wb.epoch = CALENDAR_MAC_1904
    ws = wb.active
    ws.title = "明细"
    ws.append(["差旅报销明细"])
    ws.append([])
    ws.append(["部门", "金额", "日期"])
    ws.append(["研发", 100, datetime(2026, 1, 1)])
    ws.append([None, 200, datetime(2026, 1, 2)])
    ws.append(["合计", 300, None])
    ws.merge_cells("A4:A5")
    wb.save(workspace / name)
    return name


def test_region_then_structure_chain(runtime, ctx, workspace):
    make_workbook(workspace)
    source = file_ref(workspace, "expense.xlsx")
    regions = call("detect_workbook_regions", {"file_ref": source}, ctx, runtime)
    assert regions.status.value == "ok", regions.issues
    assert len(regions.data.regions) == 1
    region = regions.data.regions[0]
    assert region.cell_range == "A3:C6"
    assert region.source_anchor.selector.kind == "excel_cell"

    recovered = call("recover_headers", {"region": region}, ctx, runtime)
    assert recovered.status.value == "ok", recovered.issues
    assert recovered.data.columns == ["部门", "金额", "日期"]
    assert recovered.data.header_rows == 1

    expanded = call(
        "expand_merged_cells", {"table_ref": recovered.data.table}, ctx, runtime
    )
    assert expanded.status.value == "ok", expanded.issues
    assert expanded.data.expanded_ranges[0]["range"] == "A4:A5"
    stored = runtime.content.get_json(expanded.data.table.data_ref)
    assert stored["rows"][1][0] == "研发"

    classified = call(
        "classify_table_rows", {"table_ref": expanded.data.table}, ctx, runtime
    )
    assert classified.status.value == "ok"
    assert classified.data.roles[-1].role == "total"
    assert classified.data.roles[0].role == "detail"


def test_classify_rows_marks_subtotal_and_title():
    from dataagent_data.contracts.layer import TableColumn, TableData
    from dataagent_data.preparation.structure import classify_rows

    table = TableData(
        columns=[
            TableColumn(name="a", field_id="c1", value_type="string"),
            TableColumn(name="b", field_id="c2", value_type="number"),
        ],
        rows=[["小计", 10], ["合计", 20], ["备注", None], ["x", 1]],
    )
    roles = [row.role for row in classify_rows(table)]
    assert roles == ["subtotal", "total", "title", "detail"]


def test_profile_and_inference(runtime, ctx, workspace):
    build_xlsx(
        workspace / "profile.xlsx",
        {"S": [["amount", "note"], [1, "a"], [2, None], [3, "b"]]},
    )
    parsed = call(
        "parse_regular_excel", {"file_ref": file_ref(workspace, "profile.xlsx")}, ctx, runtime
    )
    table = parsed.data.tables[0]
    profile = call(
        "profile_table_structure", {"table_ref": table}, ctx, runtime
    )
    assert profile.status.value == "ok"
    assert profile.data.profile.method == "exact"
    amount = profile.data.fields[0]
    assert amount["non_null_count"] == 3
    assert amount["null_count"] == 0
    note = profile.data.fields[1]
    assert note["null_count"] == 1

    inferred = call("infer_field_types", {"table_ref": table}, ctx, runtime)
    assert inferred.status.value == "ok"
    assert all(field.status == "inferred" for field in inferred.data.fields)


def test_infer_field_types_reports_conflict(runtime, ctx, workspace):
    write_file(workspace, "mixed.csv", b"value\n1\nabc\n2\n")
    parsed = call(
        "parse_delimited_file", {"file_ref": file_ref(workspace, "mixed.csv")}, ctx, runtime
    )
    inferred = call(
        "infer_field_types", {"table_ref": parsed.data.table}, ctx, runtime
    )
    assert inferred.status.value == "partial"
    assert inferred.data.conflicts == ["c1"]
    field = inferred.data.fields[0]
    assert field.status == "conflict"
    assert field.inferred_type is None
    assert set(field.observed_types) == {"number", "string"}


def test_profile_sampled_budget(runtime, ctx, workspace):
    write_file(workspace, "many.csv", b"v\n" + b"".join(f"{i}\n".encode() for i in range(10)))
    parsed = call(
        "parse_delimited_file", {"file_ref": file_ref(workspace, "many.csv")}, ctx, runtime
    )
    profile = call(
        "profile_table_structure",
        {"table_ref": parsed.data.table, "budget_rows": 3},
        ctx,
        runtime,
    )
    assert profile.status.value == "ok"
    assert profile.data.profile.method == "sampled"
    assert profile.completeness.extent.value == "sampled"


def test_region_coordinates_account_for_leading_blanks(runtime, ctx, workspace):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "S"
    ws["B4"] = "name"
    ws["C4"] = "amount"
    ws["B5"] = "a"
    ws["C5"] = 1
    ws["B6"] = "b"
    ws["C6"] = 2
    wb.save(workspace / "offset.xlsx")
    result = call(
        "detect_workbook_regions",
        {"file_ref": file_ref(workspace, "offset.xlsx")},
        ctx,
        runtime,
    )
    assert result.status.value == "ok"
    assert [region.cell_range for region in result.data.regions] == ["B4:C6"]


def test_infer_field_types_respects_allowed_types(runtime, ctx, workspace):
    write_file(workspace, "nums.csv", b"v\n1\n2\n")
    parsed = call(
        "parse_delimited_file", {"file_ref": file_ref(workspace, "nums.csv")}, ctx, runtime
    )
    inferred = call(
        "infer_field_types",
        {"table_ref": parsed.data.table, "allowed_types": ["string"]},
        ctx,
        runtime,
    )
    assert inferred.status.value == "ok"
    assert inferred.data.fields[0].status == "unknown"
    assert inferred.data.fields[0].inferred_type is None
