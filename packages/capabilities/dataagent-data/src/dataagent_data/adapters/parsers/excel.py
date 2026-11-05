"""Excel parsing primitives shared by ingestion and preparation atoms."""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from dataagent_runtime.errors import execution_unknown, invalid_input

FORMULA_PREFIX = "="

# Workbook problems attributable to the caller's file: wrong format
# (InvalidFileException), not a zip (BadZipFile), a zip without the xlsx
# parts (KeyError: "There is no item named '[Content_Types].xml' ...") and
# unreadable paths. Anything else is an internal/library failure and must
# surface as ``execution_unknown`` instead of blaming the caller's input
# (reviewer R6, 06 §14 item 5).
_WORKBOOK_INPUT_ERRORS = frozenset(
    {"InvalidFileException", "BadZipFile", "KeyError", "OSError"}
)


@dataclass
class SheetGrid:
    name: str
    rows: list[list[Any]]
    merged_ranges: list[str]
    max_row: int
    max_column: int


def _json_value(value: Any) -> Any:
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, _dt.timedelta):
        return value.total_seconds()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def open_workbook(path: str | Path, *, data_only: bool = False):
    try:
        return load_workbook(path, data_only=data_only)
    except Exception as exc:  # noqa: BLE001 - classify, never blanket invalid_input
        message = f"cannot open workbook: {type(exc).__name__}: {exc}"
        if any(klass.__name__ in _WORKBOOK_INPUT_ERRORS for klass in type(exc).__mro__):
            raise invalid_input(message) from exc
        raise execution_unknown(message) from exc


def date_system(workbook) -> str:
    return "1904" if workbook.epoch.year == 1904 else "1900"


def sheet_grid(workbook, sheet_name: str) -> SheetGrid:
    if sheet_name not in workbook.sheetnames:
        raise invalid_input(f"sheet not found: {sheet_name}")
    ws = workbook[sheet_name]
    rows = [
        [_json_value(cell.value) for cell in row]
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column)
    ]
    merged = [str(rng) for rng in ws.merged_cells.ranges]
    return SheetGrid(
        name=sheet_name,
        rows=rows,
        merged_ranges=merged,
        max_row=ws.max_row,
        max_column=ws.max_column,
    )


def trim_grid(rows: Iterable[list[Any]]) -> list[list[Any]]:
    materialized = [list(row) for row in rows]
    while materialized and all(cell in (None, "") for cell in materialized[-1]):
        materialized.pop()
    width = 0
    for row in materialized:
        for index, cell in enumerate(row):
            if cell not in (None, ""):
                width = max(width, index + 1)
    return [row[:width] for row in materialized]


def is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def row_is_empty(row: Iterable[Any]) -> bool:
    return all(is_empty(cell) for cell in row)


def trim_empty_edges(grid: list[list[Any]]) -> list[list[Any]]:
    if not grid:
        return []
    rows = [list(row) for row in grid]
    while rows and row_is_empty(rows[0]):
        rows.pop(0)
    while rows and row_is_empty(rows[-1]):
        rows.pop()
    width = max((len(row) for row in rows), default=0)
    left = width
    right = -1
    for row in rows:
        for index, cell in enumerate(row):
            if not is_empty(cell):
                left = min(left, index)
                right = max(right, index)
    if right < left:
        return []
    return [row[left : right + 1] for row in rows]


def range_ref(sheet: str, min_row: int, min_col: int, max_row: int, max_col: int) -> str:
    return f"{get_column_letter(min_col)}{min_row}:{get_column_letter(max_col)}{max_row}"


def dedupe_names(names: list[str]) -> list[str]:
    """Return deterministic, collision-free column names.

    A suffix itself can collide with an earlier explicit name (``a``, ``a_2``,
    ``a``); the used-name set makes the result stable regardless of order.
    """

    used: set[str] = set()
    out: list[str] = []
    for index, raw in enumerate(names):
        base = re.sub(r"\s+", " ", (raw or "").strip()) or f"column_{index + 1}"
        name = base
        suffix = 2
        while name in used:
            name = f"{base}_{suffix}"
            suffix += 1
        used.add(name)
        out.append(name)
    return out


def infer_scalar_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "null"
        if re.fullmatch(r"[-+]?\d+(\.\d+)?", text):
            return "number"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?", text):
            return "date"
        if text.lower() in {"true", "false"}:
            return "boolean"
        return "string"
    return "string"


def merge_type(types: set[str]) -> str:
    types = {t for t in types if t != "null"}
    if not types:
        return "unknown"
    if len(types) == 1:
        return next(iter(types))
    if types <= {"number"}:
        return "number"
    return "mixed"


def column_types(rows: list[list[Any]], width: int) -> list[str]:
    out = []
    for index in range(width):
        types = {infer_scalar_type(row[index]) for row in rows if index < len(row)}
        out.append(merge_type(types))
    return out

def trim_empty_edges_with_offset(
    grid: list[list[Any]],
) -> tuple[list[list[Any]], int, int]:
    """Trim blank borders and return the 0-based (row, col) offset.

    Region coordinates are sheet coordinates. Trimming without carrying the
    offset silently shifts every ``TableRegion.cell_range``.
    """

    if not grid:
        return [], 0, 0
    rows = [list(row) for row in grid]
    top = 0
    while top < len(rows) and row_is_empty(rows[top]):
        top += 1
    bottom = len(rows)
    while bottom > top and row_is_empty(rows[bottom - 1]):
        bottom -= 1
    rows = rows[top:bottom]
    if not rows:
        return [], top, 0
    width = max((len(row) for row in rows), default=0)
    left = width
    right = -1
    for row in rows:
        for index, cell in enumerate(row):
            if not is_empty(cell):
                left = min(left, index)
                right = max(right, index)
    if right < left:
        return [], top, 0
    return [row[left : right + 1] for row in rows], top, left
