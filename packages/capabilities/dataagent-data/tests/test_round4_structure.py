"""Round 4 table-structure and formula-policy checks (06 §14 item 2)."""

from __future__ import annotations

from openpyxl import Workbook

from conftest import build_xlsx, call, file_ref

from dataagent_data.contracts.layer import RowMeta, TableColumn, TableData
from dataagent_data.preparation.structure import (
    expand_merged_cells,
    recover_header_block,
)
from dataagent_data import helpers


def test_pure_text_table_keeps_every_data_row():
    recovered = recover_header_block(
        [
            ["部门", "负责人"],
            ["研发", "张三"],
            ["销售", "李四"],
        ]
    )
    assert recovered.header_rows == 1
    assert recovered.columns == ["部门", "负责人"]
    assert len(recovered.rows) == 2


def test_two_row_header_without_spaces_is_detected():
    recovered = recover_header_block(
        [
            ["Amount", "Amount"],
            ["Budget", "Actual"],
            [10, 9],
            [20, 18],
        ]
    )
    assert recovered.header_rows == 2
    assert recovered.columns == ["Amount / Budget", "Amount / Actual"]
    assert recovered.rows == [[10, 9], [20, 18]]


def test_merged_header_expands_down_and_right():
    recovered = recover_header_block(
        [
            ["部门", "金额", None],
            [None, "预算", "实际"],
            ["研发", 100, 90],
        ],
        merged_ranges=["A1:A2", "B1:C1"],
        origin_row=1,
        origin_col=1,
    )
    assert recovered.header_rows == 2
    assert recovered.columns == ["部门", "金额 / 预算", "金额 / 实际"]


def test_empty_rows_do_not_shift_merged_cell_mapping(runtime, ctx):
    table = TableData(
        sheet="S",
        columns=[
            TableColumn(name="a", field_id="c1", source_path="S!A1", value_type="string"),
            TableColumn(name="b", field_id="c2", source_path="S!B1", value_type="number"),
        ],
        rows=[
            ["x", 1],
            [None, 2],
        ],
        row_meta=[],
        merged_ranges=["A2:A4"],
        source={"origin": {"row": 2, "col": 1}, "row_numbers": [2, 4]},
    )
    ref = helpers.store_table(runtime, table, ctx)
    result = call("expand_merged_cells", {"table_ref": ref}, ctx, runtime)
    assert result.status.value == "ok", result.issues
    stored = helpers.load_table(runtime, result.data.table)
    assert stored.rows == [["x", 1], ["x", 2]]
    assert result.data.expanded_ranges[0]["cells"] == 2


def _formula_workbook(workspace):
    wb = Workbook()
    ws = wb.active
    ws.title = "S"
    ws.append(["amount", "double"])
    ws.append([2, "=A2*2"])
    ws.append([3, "=A3*2"])
    path = workspace / "formula.xlsx"
    wb.save(path)
    return path


def test_cached_values_policy_reports_missing_cache(runtime, ctx, workspace):
    path = _formula_workbook(workspace)
    result = call(
        "parse_regular_excel",
        {"file_ref": file_ref(workspace, path.name), "formula_policy": "cached_values"},
        ctx,
        runtime,
    )
    assert result.status.value == "partial"
    assert any(issue.code == "da01.formula_cache_missing" for issue in result.issues)
    table = runtime.content.get_json(result.data.tables[0].data_ref)
    assert [row[1] for row in table["rows"]] == [None, None]


def test_formula_text_policy_keeps_formula_without_cache_issue(runtime, ctx, workspace):
    path = _formula_workbook(workspace)
    result = call(
        "parse_regular_excel",
        {"file_ref": file_ref(workspace, path.name), "formula_policy": "formula_text"},
        ctx,
        runtime,
    )
    assert result.status.value == "ok"
    assert not any(issue.code == "da01.formula_cache_missing" for issue in result.issues)
    table = runtime.content.get_json(result.data.tables[0].data_ref)
    assert [row[1] for row in table["rows"]] == ["=A2*2", "=A3*2"]


def test_header_origin_matches_first_data_row(runtime, ctx, workspace):
    build_xlsx(
        workspace / "plain.xlsx",
        {"S": [["title"], ["name", "value"], ["a", 1], ["b", 2]]},
    )
    result = call(
        "parse_regular_excel",
        {"file_ref": file_ref(workspace, "plain.xlsx"), "header_row": 2},
        ctx,
        runtime,
    )
    table = helpers.load_table(runtime, result.data.tables[0])
    assert table.source["origin"]["row"] == 3
    assert table.rows[0] == ["a", 1]


def test_quoted_sheet_name_region_is_not_ignored(runtime, ctx, workspace):
    build_xlsx(
        workspace / "quoted.xlsx",
        {"Expense Sheet": [["name", "amount"], ["a", 1], ["b", 2]]},
    )
    result = call(
        "extract_irregular_excel",
        {
            "file_ref": file_ref(workspace, "quoted.xlsx"),
            "regions": ["'Expense Sheet'!A1:B3"],
        },
        ctx,
        runtime,
    )
    assert result.status.value == "ok", result.issues
    table = helpers.load_table(runtime, result.data.tables[0])
    assert table.sheet == "Expense Sheet"
    assert table.rows == [["a", 1], ["b", 2]]
