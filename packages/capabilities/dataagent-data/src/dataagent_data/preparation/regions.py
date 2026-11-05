"""DA02.1.1 workbook region detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    FileRef,
    VersionedRef,
)

from dataagent_data.adapters.parsers.excel import (
    open_workbook,
    range_ref,
    row_is_empty,
    sheet_grid,
    trim_empty_edges_with_offset,
)
from dataagent_data.contracts.layer import TableRegion, WorkbookRef
from dataagent_data import helpers
from dataagent_runtime.errors import invalid_input
from dataagent_data.registry import operation


@dataclass(frozen=True)
class RegionBox:
    min_row: int  # 0-based inclusive
    min_col: int
    max_row: int
    max_col: int
    confidence: float


def detect_regions(grid: list[list[Any]]) -> list[RegionBox]:
    if not grid:
        return []
    non_empty_rows = [index for index, row in enumerate(grid) if not row_is_empty(row)]
    if not non_empty_rows:
        return []
    bands: list[tuple[int, int]] = []
    start = previous = non_empty_rows[0]
    for index in non_empty_rows[1:]:
        if index == previous + 1:
            previous = index
            continue
        bands.append((start, previous))
        start = previous = index
    bands.append((start, previous))

    regions: list[RegionBox] = []
    for row_start, row_end in bands:
        width = max(len(row) for row in grid[row_start : row_end + 1])
        column_has_data = [
            any(
                column < len(grid[row])
                and grid[row][column] not in (None, "")
                for row in range(row_start, row_end + 1)
            )
            for column in range(width)
        ]
        columns = [index for index, has_data in enumerate(column_has_data) if has_data]
        if not columns:
            continue
        col_start = previous_col = columns[0]
        spans: list[tuple[int, int]] = []
        for column in columns[1:]:
            if column == previous_col + 1:
                previous_col = column
                continue
            spans.append((col_start, previous_col))
            col_start = previous_col = column
        spans.append((col_start, previous_col))
        for left, right in spans:
            height = row_end - row_start + 1
            width_ = right - left + 1
            filled = sum(
                1
                for row in range(row_start, row_end + 1)
                for column in range(left, right + 1)
                if column < len(grid[row]) and grid[row][column] not in (None, "")
            )
            # Single title rows are layout, not tables.
            if height < 2 or width_ < 2:
                continue
            regions.append(
                RegionBox(
                    min_row=row_start,
                    min_col=left,
                    max_row=row_end,
                    max_col=right,
                    confidence=round(filled / (height * width_), 4),
                )
            )
    return regions


def slice_region(grid: list[list[Any]], region: RegionBox) -> list[list[Any]]:
    return [
        list(row[region.min_col : region.max_col + 1])
        for row in grid[region.min_row : region.max_row + 1]
    ]


def load_region_grid(runtime, region: TableRegion) -> tuple[list[list[Any]], list[str]]:
    from dataagent_data.ingestion.files import _materialize

    file_ref = region.workbook_ref.file_ref
    payload = helpers.read_file_ref(runtime, file_ref)
    with _materialize(runtime, payload, ".xlsx") as path:
        workbook = open_workbook(path)
    sheet = sheet_grid(workbook, region.sheet)
    from openpyxl.utils.cell import range_boundaries

    min_col, min_row, max_col, max_row = range_boundaries(region.cell_range)
    region_rows = [
        list(row[min_col - 1 : max_col])
        for row in sheet.rows[min_row - 1 : max_row]
    ]
    return region_rows, sheet.merged_ranges


class DetectWorkbookRegionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_ref: FileRef | None = None
    workbook_ref: WorkbookRef | None = None
    sheets: list[str] | None = None
    layout_hints: dict[str, object] | None = None


class DetectWorkbookRegionsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workbook_ref: WorkbookRef
    regions: list[TableRegion] = Field(default_factory=list)


@operation(
    "DA02.1.1",
    input_model=DetectWorkbookRegionsInput,
    output_model=DetectWorkbookRegionsOutput,
    description="工作簿表块检测",
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("file_ref",),
)
def detect_workbook_regions(
    data: DetectWorkbookRegionsInput, ctx: CallContext, runtime
) -> CapabilityResult[DetectWorkbookRegionsOutput]:
    workbook_ref = data.workbook_ref
    if workbook_ref is None:
        if data.file_ref is None:
            raise invalid_input("detect_workbook_regions requires file_ref or workbook_ref")
        workbook_ref = WorkbookRef(file_ref=data.file_ref, sheets=[])
    file_ref = workbook_ref.file_ref
    payload = helpers.read_file_ref(runtime, file_ref)
    from dataagent_data.ingestion.files import _materialize

    with _materialize(runtime, payload, ".xlsx") as path:
        workbook = open_workbook(path)
    selected = data.sheets or list(workbook.sheetnames)
    regions: list[TableRegion] = []
    for name in selected:
        if name not in workbook.sheetnames:
            continue
        sheet = sheet_grid(workbook, name)
        grid, row_offset, col_offset = trim_empty_edges_with_offset(sheet.rows)
        for box in detect_regions(grid):
            cell_range = range_ref(
                name,
                box.min_row + row_offset + 1,
                box.min_col + col_offset + 1,
                box.max_row + row_offset + 1,
                box.max_col + col_offset + 1,
            )
            regions.append(
                TableRegion(
                    workbook_ref=workbook_ref,
                    sheet=name,
                    cell_range=cell_range,
                    source_anchor=helpers.excel_cell_anchor(
                        source_ref=file_ref.id,
                        source_revision=file_ref.revision,
                        sheet=name,
                        cell_range=cell_range,
                    ),
                    confidence=box.confidence,
                    overlapping=False,
                )
            )
    if workbook_ref.sheets != list(workbook.sheetnames):
        workbook_ref = workbook_ref.model_copy(update={"sheets": list(workbook.sheetnames)})
    return CapabilityResult[DetectWorkbookRegionsOutput](
        status=CapabilityStatus.ok,
        data=DetectWorkbookRegionsOutput(workbook_ref=workbook_ref, regions=regions),
        provenance=[VersionedRef(id=file_ref.id, revision=file_ref.revision)],
        completeness=helpers.complete(
            "workbook sheets", {"sheets": len(selected), "regions": len(regions)}
        ),
    )
