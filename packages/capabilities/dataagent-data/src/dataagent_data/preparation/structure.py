"""DA02.2.1/2/3 header recovery, merged-cell expansion, row classification."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    CompletenessExtent,
    Issue,
    Severity,
    TableRef,
    VersionedRef,
)

from dataagent_data.adapters.parsers.excel import dedupe_names, infer_scalar_type, row_is_empty
from dataagent_data.contracts.layer import RowMeta, TableColumn, TableData, TableRegion
from dataagent_data import helpers
from dataagent_runtime.errors import invalid_input
from dataagent_data.registry import operation

TOTAL_WORDS = ("合计", "总计", "total", "grand total", "汇总")
SUBTOTAL_WORDS = ("小计", "subtotal", "sub-total")
TITLE_WORDS = ("明细", "清单")
# Tokens that denote a missing value rather than a header label. A row whose
# cells are "Alice"/"N/A" is a data row that happens to contain no number, not
# a second header row.
_MISSING_MARKERS = frozenset({"n/a", "na", "n.a.", "null", "none", "-", "—", "未知", "无"})


@dataclass
class RecoveredHeader:
    columns: list[str]
    header_rows: int
    rows: list[list[Any]]
    ambiguities: list[str] = field(default_factory=list)
    source_rows: list[int] = field(default_factory=list)


def _mostly_data(row: list[Any]) -> bool:
    values = [value for value in row if value not in (None, "")]
    if not values:
        return False
    data_like = sum(1 for value in values if infer_scalar_type(value) in {"number", "date", "boolean"})
    return data_like / len(values) >= 0.5


def _plausible_header_row(row: list[Any], width: int) -> bool:
    """Whether a row *above* a data row reads as a header, not as sparse data.

    A second header row is dense (a sparse row such as ``Alice/None/None`` is a
    data row whose other cells are empty) and carries labels, not missing-value
    markers such as ``N/A``. Numeric labels (e.g. a ``2024`` year row above
    ``Q1``/``Q2``) are allowed; dates are not.
    """

    values = [value for value in row if value not in (None, "")]
    if not values or len(values) / width < 0.5:
        return False
    for value in values:
        if infer_scalar_type(value) == "date":
            return False
        if isinstance(value, str) and value.strip().lower() in _MISSING_MARKERS:
            return False
    return True


def _suspect_as_data(row: list[Any], width: int) -> bool:
    """Whether a presumed data row looks like a lost header row."""

    values = [value for value in row if value not in (None, "")]
    if not values:
        return False
    if len(values) / width < 0.5:
        return True
    return any(
        isinstance(value, str) and value.strip().lower() in _MISSING_MARKERS
        for value in values
    )


def _detect_header_rows(padded: list[list[Any]]) -> int:
    """Return the number of header rows (1..3).

    A header is the run of non-data rows *before* the first data row. Additional
    header rows must also be dense and label-like: a sparse text row (``Alice``
    with empty ``q1``/``q2`` cells) or a row carrying ``N/A`` is data, and
    folding it into the header silently deletes a record (P1, r4-review #3).
    """

    width = max(len(row) for row in padded) if padded else 0
    for candidate in (1, 2, 3):
        if candidate >= len(padded):
            break
        if not _mostly_data(padded[candidate]):
            continue
        if any(_mostly_data(padded[row]) for row in range(1, candidate)):
            continue
        if any(
            not _plausible_header_row(padded[row], width)
            for row in range(1, candidate)
        ):
            continue
        return candidate
    return 1


def _expand_merged_header(
    padded: list[list[Any]],
    merged_ranges: list[str] | None,
    header_rows: int,
    origin_row: int,
    origin_col: int,
) -> None:
    """Propagate a merged top-left header cell down/across the header block."""

    if not merged_ranges:
        return
    from openpyxl.utils.cell import range_boundaries

    for cell_range in merged_ranges:
        try:
            min_col, min_row, max_col, max_row = range_boundaries(cell_range)
        except Exception:  # noqa: BLE001 - ignore malformed sheet metadata
            continue
        if min_row is None or min_col is None or max_row is None or max_col is None:
            continue
        local_min_row = min_row - origin_row
        local_min_col = min_col - origin_col
        local_max_row = max_row - origin_row
        local_max_col = max_col - origin_col
        if local_min_row < 0 or local_min_col < 0 or local_min_row >= header_rows:
            continue
        if local_min_row >= len(padded) or local_min_col >= len(padded[local_min_row]):
            continue
        value = padded[local_min_row][local_min_col]
        if value in (None, ""):
            continue
        for row in range(local_min_row, min(local_max_row + 1, header_rows)):
            if row >= len(padded):
                break
            for column in range(local_min_col, min(local_max_col + 1, len(padded[row]))):
                if padded[row][column] in (None, ""):
                    padded[row][column] = value


def recover_header_block(
    block: list[list[Any]],
    *,
    header_rows: int | None = None,
    merged_ranges: list[str] | None = None,
    origin_row: int = 1,
    origin_col: int = 1,
) -> RecoveredHeader:
    if not block:
        return RecoveredHeader(columns=[], header_rows=0, rows=[])
    width = max(len(row) for row in block)
    padded = [list(row) + [None] * (width - len(row)) for row in block]
    ambiguities: list[str] = []

    header_cells = padded[0]
    non_empty = [cell for cell in header_cells if cell not in (None, "")]
    if header_rows is not None:
        if not 1 <= header_rows < len(padded):
            raise invalid_input(
                f"header_rows hint {header_rows} is outside the {len(padded)}-row block"
            )
    else:
        header_rows = _detect_header_rows(padded)
        # A sparse or "N/A"-bearing first data row is exactly the shape that
        # used to be swallowed into a multi-row header. It is kept as data now,
        # but the interpretation is worth surfacing to the caller.
        if header_rows == 1 and len(padded) > 1 and _suspect_as_data(padded[1], width):
            ambiguities.append(
                "first data row is sparse or contains missing-value markers; it "
                "was kept as data -- verify whether it is a second header row"
            )
    _expand_merged_header(padded, merged_ranges, header_rows, origin_row, origin_col)
    if len(non_empty) < width:
        ambiguities.append("header row has empty cells; blank columns are preserved as column_N")

    combined: list[str] = []
    for column in range(width):
        parts: list[str] = []
        for row in range(header_rows):
            value = padded[row][column] if column < len(padded[row]) else None
            if value not in (None, ""):
                text = str(value).strip()
                if not parts or parts[-1] != text:
                    parts.append(text)
        combined.append(" / ".join(parts))
    columns = dedupe_names(combined)
    seen: dict[str, int] = {}
    for raw in combined:
        seen[raw] = seen.get(raw, 0) + 1
    duplicates = [name for name, count in seen.items() if count > 1 and name]
    if duplicates:
        ambiguities.append(f"duplicate header names preserved with suffixes: {duplicates}")

    rows: list[list[Any]] = []
    source_rows: list[int] = []
    for offset, row in enumerate(padded[header_rows:]):
        if row_is_empty(row):
            continue
        rows.append(row)
        source_rows.append(origin_row + header_rows + offset)
    return RecoveredHeader(
        columns=columns,
        header_rows=header_rows,
        rows=rows,
        ambiguities=ambiguities,
        source_rows=source_rows,
    )


class RecoverHeadersInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    region: TableRegion | None = None
    table_ref: TableRef | None = None
    header_strategy: str = "auto"


class RecoverHeadersOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: list[str]
    header_rows: int
    table: TableRef
    ambiguities: list[str] = Field(default_factory=list)


@operation(
    "DA02.2.1",
    input_model=RecoverHeadersInput,
    output_model=RecoverHeadersOutput,
    description="多行表头恢复",
    writes=True,
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("table_ref",),
)
def recover_headers(
    data: RecoverHeadersInput, ctx: CallContext, runtime
) -> CapabilityResult[RecoverHeadersOutput]:
    if data.region is not None:
        from dataagent_data.preparation.regions import load_region_grid

        grid, merged = load_region_grid(runtime, data.region)
        source = {"file": data.region.workbook_ref.file_ref.locator, "topic": "region"}
        sheet = data.region.sheet
        origin = _origin(data.region.cell_range)
        file_ref = data.region.workbook_ref.file_ref
    elif data.table_ref is not None:
        table = helpers.load_table(runtime, data.table_ref)
        # A stored table already has a recovered header. Returning it unchanged
        # avoids treating the first data row as a second header row.
        return CapabilityResult[RecoverHeadersOutput](
            status=CapabilityStatus.ok,
            data=RecoverHeadersOutput(
                columns=[column.name for column in table.columns],
                header_rows=int(table.source.get("header_rows", 1)),
                table=data.table_ref,
                ambiguities=[],
            ),
            completeness=helpers.complete(
                "existing table header", {"columns": len(table.columns)}
            ),
        )
    else:
        raise invalid_input("recover_headers requires region or table_ref")

    recovered = recover_header_block(
        grid,
        merged_ranges=merged,
        origin_row=origin["row"],
        origin_col=origin["col"],
    )
    types = [
        _merge_types([infer_scalar_type(row[index]) for row in recovered.rows if index < len(row)])
        for index in range(len(recovered.columns))
    ]
    table_data = TableData(
        sheet=sheet,
        columns=[
            TableColumn(
                name=recovered.columns[index],
                field_id=f"c{index + 1}",
                source_path=f"{sheet}!{index + 1}",
                value_type=types[index],
            )
            for index in range(len(recovered.columns))
        ],
        rows=recovered.rows,
        row_meta=[],
        merged_ranges=merged,
        source={
            **source,
            "header_rows": recovered.header_rows,
            "origin": {
                "row": origin["row"] + (recovered.header_rows if data.region is not None else 0),
                "col": origin["col"],
            },
            "row_numbers": recovered.source_rows,
        },
    )
    issues = [
        Issue.standard(
            "da02.ambiguous_header",
            ambiguity,
            severity=Severity.warning,
            suggested_action="confirm header mapping or provide a hint",
        )
        for ambiguity in recovered.ambiguities
    ]
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[RecoverHeadersOutput](
        status=status,
        data=RecoverHeadersOutput(
            columns=recovered.columns,
            header_rows=recovered.header_rows,
            table=helpers.store_table(runtime, table_data, ctx),
            ambiguities=recovered.ambiguities,
        ),
        issues=issues,
        provenance=(
            [VersionedRef(id=file_ref.id, revision=file_ref.revision)] if file_ref else []
        ),
        completeness=helpers.complete("recovered header block", {"rows": len(recovered.rows)}),
    )


def _origin(cell_range: str) -> dict[str, int]:
    from openpyxl.utils.cell import range_boundaries

    min_col, min_row, _, _ = range_boundaries(cell_range)
    return {"row": min_row, "col": min_col}


def _merge_types(types: list[str]) -> str:
    types = {item for item in types if item != "null"}
    if not types:
        return "unknown"
    if len(types) == 1:
        return next(iter(types))
    return "mixed"


class ExpandMergedCellsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_ref: TableRef
    allow_propagation: bool = True


class ExpandMergedCellsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: TableRef
    expanded_ranges: list[dict[str, Any]] = Field(default_factory=list)


@operation(
    "DA02.2.2",
    input_model=ExpandMergedCellsInput,
    output_model=ExpandMergedCellsOutput,
    description="合并单元格展开",
    writes=True,
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("table_ref",),
)
def expand_merged_cells(
    data: ExpandMergedCellsInput, ctx: CallContext, runtime
) -> CapabilityResult[ExpandMergedCellsOutput]:
    from openpyxl.utils.cell import range_boundaries

    table = helpers.load_table(runtime, data.table_ref)
    rows = [list(row) for row in table.rows]
    origin = table.source.get("origin") or {"row": 1, "col": 1}
    row_numbers = table.source.get("row_numbers")
    row_map: dict[int, int] | None = None
    if isinstance(row_numbers, list) and row_numbers:
        row_map = {int(number): index for index, number in enumerate(row_numbers)}
    expanded: list[dict[str, Any]] = []
    skipped: list[str] = []
    for cell_range in table.merged_ranges:
        min_col, min_row, max_col, max_row = range_boundaries(cell_range)
        local_min_col = min_col - int(origin["col"])
        local_max_col = max_col - int(origin["col"])
        if row_map is not None:
            local_rows = [
                row_map[number]
                for number in range(min_row, max_row + 1)
                if number in row_map
            ]
        else:
            local_rows = list(range(min_row - int(origin["row"]), max_row - int(origin["row"]) + 1))
        local_rows = [index for index in local_rows if 0 <= index < len(rows)]
        if not local_rows or local_min_col < 0:
            skipped.append(cell_range)
            continue
        first = local_rows[0]
        if local_min_col >= len(rows[first]):
            skipped.append(cell_range)
            continue
        value = rows[first][local_min_col]
        if value in (None, "") or not data.allow_propagation:
            continue
        for row_index in local_rows:
            for col_index in range(local_min_col, min(local_max_col + 1, len(rows[row_index]))):
                rows[row_index][col_index] = value
        expanded.append(
            {
                "range": cell_range,
                "value": value,
                "cells": len(local_rows)
                * (min(local_max_col + 1, len(rows[first])) - local_min_col),
            }
        )
    updated = table.model_copy(update={"rows": rows})
    issues = [
        Issue.standard(
            "da02.merged_range_outside_table",
            f"merged range outside table bounds: {cell_range}",
            severity=Severity.warning,
            target=cell_range,
        )
        for cell_range in skipped
    ]
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[ExpandMergedCellsOutput](
        status=status,
        data=ExpandMergedCellsOutput(
            table=helpers.store_table(runtime, updated, ctx), expanded_ranges=expanded
        ),
        issues=issues,
        completeness=helpers.complete("merged ranges", {"merged_ranges": len(table.merged_ranges)}),
    )


class ClassifyTableRowsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_ref: TableRef


class ClassifyTableRowsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    roles: list[RowMeta]
    table: TableRef


@operation(
    "DA02.2.3",
    input_model=ClassifyTableRowsInput,
    output_model=ClassifyTableRowsOutput,
    description="明细/合计行识别",
    writes=True,
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("table_ref",),
)
def classify_table_rows(
    data: ClassifyTableRowsInput, ctx: CallContext, runtime
) -> CapabilityResult[ClassifyTableRowsOutput]:
    table = helpers.load_table(runtime, data.table_ref)
    roles = classify_rows(table)
    updated = table.model_copy(update={"row_meta": roles})
    return CapabilityResult[ClassifyTableRowsOutput](
        status=CapabilityStatus.ok,
        data=ClassifyTableRowsOutput(roles=roles, table=helpers.store_table(runtime, updated, ctx)),
        completeness=helpers.complete("table rows", {"rows": len(table.rows)}),
    )


def classify_rows(table: TableData) -> list[RowMeta]:
    roles: list[RowMeta] = []
    for row in table.rows:
        texts = [str(value).strip() for value in row if value not in (None, "")]
        lowered = [text.lower() for text in texts]
        if not texts:
            roles.append(RowMeta(role="unknown", reason="empty_row"))
            continue
        total_hit = next((word for word in TOTAL_WORDS if any(word in text for text in lowered)), None)
        subtotal_hit = next(
            (word for word in SUBTOTAL_WORDS if any(word in text for text in lowered)), None
        )
        formula_hit = any(isinstance(value, str) and value.startswith("=") for value in row)
        if subtotal_hit:
            roles.append(RowMeta(role="subtotal", reason=f"label:{subtotal_hit}"))
        elif total_hit:
            roles.append(RowMeta(role="total", reason=f"label:{total_hit}"))
        elif formula_hit:
            roles.append(RowMeta(role="total", reason="formula_row"))
        elif len(texts) == 1 and not re.search(r"\d", texts[0]):
            roles.append(RowMeta(role="title", reason="single_text_cell"))
        else:
            roles.append(RowMeta(role="detail", reason="data_row"))
    return roles
