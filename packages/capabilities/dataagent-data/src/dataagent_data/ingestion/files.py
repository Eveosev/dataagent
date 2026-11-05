"""DA01.4 file parsing atoms (regular Excel, irregular Excel, delimited, JSON, PDF, calc state)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    Completeness,
    CompletenessExtent,
    DataBatchRef,
    DocumentRef,
    FileRef,
    Issue,
    Severity,
    TableRef,
    VersionedRef,
)

from dataagent_data.adapters.parsers.delimited import parse_delimited
from dataagent_data.adapters.parsers.excel import (
    column_types,
    date_system,
    dedupe_names,
    infer_scalar_type,
    open_workbook,
    range_ref,
    row_is_empty,
    sheet_grid,
    trim_empty_edges_with_offset,
    trim_grid,
)
from dataagent_data.adapters.parsers.json_records import parse_json_records as _parse_json
from dataagent_data.adapters.parsers.pdf import parse_pdf
from dataagent_data.contracts.layer import (
    DocumentContent,
    FormulaCell,
    TableColumn,
    TableData,
    TableRegion,
    WorkbookCalcState,
    WorkbookRef,
)
from dataagent_data.preparation.documents import register_document_blocks
from dataagent_data.preparation.regions import RegionBox, detect_regions, slice_region
from dataagent_data.preparation.structure import recover_header_block
from dataagent_data import helpers
from dataagent_runtime.errors import invalid_input
from dataagent_data.registry import operation


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParseRegularExcelInput(_Model):
    file_ref: FileRef
    sheets: list[str] | None = None
    header_row: int = Field(default=1, ge=1)
    formula_policy: Literal["cached_values", "formula_text"] = "cached_values"


class ParseRegularExcelOutput(_Model):
    workbook_ref: WorkbookRef
    tables: list[TableRef] = Field(default_factory=list)
    source_content_digest: str | None = None


@operation(
    "DA01.4.1",
    input_model=ParseRegularExcelInput,
    output_model=ParseRegularExcelOutput,
    description="规整 Excel 解析：提取明确表头的单表或多 sheet 表",
    writes=True,
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("file_ref",),
)
def parse_regular_excel(
    data: ParseRegularExcelInput, ctx: CallContext, runtime
) -> CapabilityResult[ParseRegularExcelOutput]:
    payload = helpers.read_file_ref(runtime, data.file_ref)
    helpers.register_file_ref(runtime, data.file_ref)
    suffix = (data.file_ref.filename or data.file_ref.locator).lower()
    if not suffix.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
        raise invalid_input("parse_regular_excel only supports xlsx/xlsm workbooks")
    with _materialize(runtime, payload, suffix) as workbook_path:
        workbook = open_workbook(workbook_path)
    with _materialize(runtime, payload, suffix) as values_path:
        values_workbook = open_workbook(values_path, data_only=True)
    selected = data.sheets or list(workbook.sheetnames)
    tables: list[TableRef] = []
    issues: list[Issue] = []
    provenance = [VersionedRef(id=data.file_ref.id, revision=data.file_ref.revision)]

    for name in selected:
        if name not in workbook.sheetnames:
            issues.append(
                Issue.standard(
                    "da01.sheet_not_found",
                    f"sheet not found: {name}",
                    severity=Severity.warning,
                    target=name,
                )
            )
            continue
        grid = sheet_grid(workbook, name).rows
        cached = sheet_grid(values_workbook, name).rows
        grid = trim_grid(grid)
        if not grid:
            issues.append(
                Issue.standard(
                    "da01.empty_sheet",
                    f"sheet is empty: {name}",
                    severity=Severity.info,
                    target=name,
                )
            )
            continue
        if data.header_row > len(grid):
            raise invalid_input(f"header_row {data.header_row} is outside sheet {name}")
        header_cells = grid[data.header_row - 1]
        columns = dedupe_names(["" if cell is None else str(cell) for cell in header_cells])
        body = grid[data.header_row :]
        rows: list[list[Any]] = []
        # Original 1-based sheet row number of every retained row. Skipped empty
        # rows must not shift merged-range coordinates (06 §14 item 2).
        row_numbers: list[int] = []
        formula_notes: list[int] = []
        for offset, row in enumerate(body, start=data.header_row + 1):
            if row_is_empty(row):
                continue
            row_numbers.append(offset)
            materialized = []
            for index in range(len(columns)):
                value = row[index] if index < len(row) else None
                if isinstance(value, str) and value.startswith("="):
                    cached_row = cached[offset - 1] if offset - 1 < len(cached) else []
                    cached_value = cached_row[index] if index < len(cached_row) else None
                    if data.formula_policy == "cached_values":
                        value = cached_value
                        if cached_value is None:
                            formula_notes.append(
                                f"{name}!{_column_letter(index + 1)}{offset}"
                            )
                    # formula_text keeps the formula itself and must not be
                    # reported as a missing cache.
                materialized.append(value)
            rows.append(materialized)
        types = column_types(rows, len(columns))
        column_meta = [
            TableColumn(
                name=columns[index],
                field_id=f"c{index + 1}",
                source_path=f"{name}!{_column_letter(index + 1)}{data.header_row}",
                value_type=types[index],
            )
            for index in range(len(columns))
        ]
        merged = sheet_grid(workbook, name).merged_ranges
        table = TableData(
            sheet=name,
            columns=column_meta,
            rows=rows,
            row_meta=[],
            merged_ranges=merged,
            source={
                "file": data.file_ref.locator,
                "header_row": data.header_row,
                "origin": {"row": data.header_row + 1, "col": 1},
                "row_numbers": row_numbers,
            },
        )
        tables.append(helpers.store_table(runtime, table, ctx))
        for cell in formula_notes:
            issues.append(
                Issue.standard(
                    "da01.formula_cache_missing",
                    f"formula cell {cell} has no cached value; materialized as missing",
                    severity=Severity.warning,
                    target=cell,
                    suggested_action="recalculate the workbook or use formula_text policy",
                )
            )

    if not tables and not issues:
        issues.append(Issue.standard("da01.empty_sheet", "workbook contains no tables", severity=Severity.info))
    helpers.register_file_tables(runtime, data.file_ref, tables)
    workbook_ref = WorkbookRef(
        file_ref=data.file_ref,
        sheets=list(workbook.sheetnames),
        table_refs=[VersionedRef(id=t.asset.id, revision=t.asset.revision) for t in tables],
    )
    status = CapabilityStatus.partial if any(i.severity is Severity.warning for i in issues) else CapabilityStatus.ok
    return CapabilityResult[ParseRegularExcelOutput](
        status=status,
        data=ParseRegularExcelOutput(
            workbook_ref=workbook_ref,
            tables=tables,
            source_content_digest=data.file_ref.content_digest,
        ),
        issues=issues,
        provenance=provenance,
        completeness=helpers.complete("workbook sheets: " + ", ".join(selected), {"sheets": len(selected)}),
    )


class ExtractIrregularExcelInput(_Model):
    file_ref: FileRef
    sheets: list[str] | None = None
    regions: list[str] | None = None
    layout_hints: dict[str, Any] | None = None
    recovery_policy: Literal["preserve_ambiguity", "strict"] = "preserve_ambiguity"


class ExtractIrregularExcelOutput(_Model):
    workbook_ref: WorkbookRef
    tables: list[TableRef] = Field(default_factory=list)
    regions: list[TableRegion] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    source_content_digest: str | None = None


def _irregular_region_boxes(
    data: ExtractIrregularExcelInput, name: str, raw_rows: list[list[Any]]
) -> tuple[list[RegionBox], int, int, list[list[Any]]]:
    """Candidate regions and the trimmed-grid offsets for one sheet."""

    if data.regions:
        from openpyxl.utils.cell import range_boundaries

        boxes: list[RegionBox] = []
        for entry in data.regions:
            target, _, cell_range = entry.rpartition("!")
            if target.startswith("'") and target.endswith("'"):
                target = target[1:-1].replace("''", "'")
            if target and target != name:
                continue
            min_col, min_row, max_col, max_row = range_boundaries(cell_range or entry)
            boxes.append(
                RegionBox(
                    min_row=min_row - 1,
                    min_col=min_col - 1,
                    max_row=max_row - 1,
                    max_col=max_col - 1,
                    confidence=1.0,
                )
            )
        return boxes, 0, 0, raw_rows
    grid, row_offset, col_offset = trim_empty_edges_with_offset(raw_rows)
    return detect_regions(grid), row_offset, col_offset, grid


def _layout_hint(data: ExtractIrregularExcelInput) -> int | None:
    """Validated ``layout_hints.header_rows`` or ``None``."""

    if not data.layout_hints:
        return None
    raw_hint = data.layout_hints.get("header_rows")
    if raw_hint is None:
        return None
    try:
        return int(raw_hint)
    except (TypeError, ValueError) as exc:
        raise invalid_input(
            f"layout_hints.header_rows must be an integer: {raw_hint!r}"
        ) from exc


def _irregular_table(
    name: str,
    region: RegionBox,
    recovered: Any,
    merged_ranges: list[str],
    file_ref: FileRef,
    row_offset: int,
    col_offset: int,
    order: int,
) -> TableData:
    """Build one ``TableData`` from a recovered header block."""

    types = column_types(recovered.rows, len(recovered.columns))
    return TableData(
        sheet=name,
        columns=[
            TableColumn(
                name=recovered.columns[index],
                field_id=f"c{index + 1}",
                source_path=(
                    f"{name}!r{region.min_row + row_offset + 1}"
                    f"c{region.min_col + col_offset + index + 1}"
                ),
                value_type=types[index],
            )
            for index in range(len(recovered.columns))
        ],
        rows=recovered.rows,
        row_meta=[],
        merged_ranges=merged_ranges,
        source={
            "file": file_ref.locator,
            "region": order,
            "header_rows": recovered.header_rows,
            "origin": {
                "row": region.min_row + row_offset + 1 + recovered.header_rows,
                "col": region.min_col + col_offset + 1,
            },
            "row_numbers": recovered.source_rows,
        },
    )


@operation(
    "DA01.4.2",
    input_model=ExtractIrregularExcelInput,
    output_model=ExtractIrregularExcelOutput,
    description="不规则 Excel 提取：从混合布局中恢复逻辑表",
    writes=True,
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("file_ref",),
)
def extract_irregular_excel(
    data: ExtractIrregularExcelInput, ctx: CallContext, runtime
) -> CapabilityResult[ExtractIrregularExcelOutput]:
    payload = helpers.read_file_ref(runtime, data.file_ref)
    helpers.register_file_ref(runtime, data.file_ref)
    filename = (data.file_ref.filename or data.file_ref.locator).lower()
    if not filename.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
        raise invalid_input("extract_irregular_excel only supports xlsx/xlsm workbooks")
    with _materialize(runtime, payload, filename) as workbook_path:
        workbook = open_workbook(workbook_path)
    selected = data.sheets or list(workbook.sheetnames)
    workbook_ref = WorkbookRef(file_ref=data.file_ref, sheets=list(workbook.sheetnames))
    tables: list[TableRef] = []
    regions: list[TableRegion] = []
    ambiguities: list[str] = []
    issues: list[Issue] = []
    for name in selected:
        if name not in workbook.sheetnames:
            issues.append(
                Issue.standard("da01.sheet_not_found", f"sheet not found: {name}", severity=Severity.warning)
            )
            continue
        sheet = sheet_grid(workbook, name)
        raw_rows = sheet.rows
        boxes, row_offset, col_offset, grid = _irregular_region_boxes(
            data, name, raw_rows
        )
        if not data.regions and not grid:
            issues.append(
                Issue.standard(
                    "da01.empty_sheet", f"sheet is empty: {name}", severity=Severity.info
                )
            )
            continue
        if not boxes:
            issues.append(
                Issue.standard(
                    "da02.region_required",
                    f"no table region could be determined for {name}",
                    severity=Severity.warning,
                    suggested_action="provide candidate regions as Sheet!A1:C6",
                )
            )
            continue
        for order, region in enumerate(boxes, start=1):
            cell_range = range_ref(
                name,
                region.min_row + row_offset + 1,
                region.min_col + col_offset + 1,
                region.max_row + row_offset + 1,
                region.max_col + col_offset + 1,
            )
            regions.append(
                TableRegion(
                    workbook_ref=workbook_ref,
                    sheet=name,
                    cell_range=cell_range,
                    source_anchor=helpers.excel_cell_anchor(
                        source_ref=data.file_ref.id,
                        source_revision=data.file_ref.revision,
                        sheet=name,
                        cell_range=cell_range,
                    ),
                    confidence=region.confidence,
                    overlapping=False,
                )
            )
            if data.regions:
                block = [
                    list(row[region.min_col : region.max_col + 1])
                    for row in raw_rows[region.min_row : region.max_row + 1]
                ]
            else:
                block = slice_region(grid, region)
            recovered = recover_header_block(
                block,
                header_rows=_layout_hint(data),
                merged_ranges=sheet.merged_ranges,
                origin_row=region.min_row + row_offset + 1,
                origin_col=region.min_col + col_offset + 1,
            )
            if not recovered.columns:
                issues.append(
                    Issue.standard(
                        "da02.ambiguous_header",
                        f"{name} region {order} has no recoverable header",
                        severity=Severity.warning,
                        target=f"region:{name}:{order}",
                        suggested_action="supply a layout hint or choose an alternative recovery policy",
                    )
                )
                continue
            table = _irregular_table(
                name,
                region,
                recovered,
                sheet.merged_ranges,
                data.file_ref,
                row_offset,
                col_offset,
                order,
            )
            tables.append(helpers.store_table(runtime, table, ctx))
            for ambiguity in recovered.ambiguities:
                ambiguities.append(f"{name} region {order}: {ambiguity}")
                issues.append(
                    Issue.standard(
                        "da02.ambiguous_header",
                        f"{name} region {order}: {ambiguity}",
                        severity=Severity.warning,
                        target=f"region:{name}:{order}",
                        suggested_action="preserve ambiguity or provide a header hint",
                    )
                )
            if data.recovery_policy == "strict" and recovered.ambiguities:
                raise invalid_input(f"ambiguous layout in {name} region {order}: {recovered.ambiguities[0]}")
    helpers.register_file_tables(runtime, data.file_ref, tables)
    workbook_ref = workbook_ref.model_copy(
        update={
            "table_refs": [
                VersionedRef(id=t.asset.id, revision=t.asset.revision) for t in tables
            ]
        }
    )
    status = CapabilityStatus.partial if any(i.severity is Severity.warning for i in issues) else CapabilityStatus.ok
    return CapabilityResult[ExtractIrregularExcelOutput](
        status=status,
        data=ExtractIrregularExcelOutput(
            workbook_ref=workbook_ref,
            tables=tables,
            regions=regions,
            ambiguities=ambiguities,
            source_content_digest=data.file_ref.content_digest,
        ),
        issues=issues,
        provenance=[VersionedRef(id=data.file_ref.id, revision=data.file_ref.revision)],
        completeness=helpers.complete("irregular workbook regions", {"tables": len(tables)}),
    )


class ParseDelimitedInput(_Model):
    file_ref: FileRef
    delimiter: str | None = None
    encoding: str | None = None
    has_header: bool = True


class ParseDelimitedOutput(_Model):
    table: TableRef
    row_count: int
    encoding: str
    delimiter: str
    bad_rows: list[dict[str, Any]] = Field(default_factory=list)
    source_content_digest: str | None = None


@operation(
    "DA01.4.3",
    input_model=ParseDelimitedInput,
    output_model=ParseDelimitedOutput,
    description="CSV/TSV 解析：处理分隔符与编码",
    writes=True,
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("file_ref",),
)
def parse_delimited_file(
    data: ParseDelimitedInput, ctx: CallContext, runtime
) -> CapabilityResult[ParseDelimitedOutput]:
    payload = helpers.read_file_ref(runtime, data.file_ref)
    helpers.register_file_ref(runtime, data.file_ref)
    filename = data.file_ref.filename or data.file_ref.locator
    columns, rows, bad_rows, encoding, delimiter = parse_delimited(
        payload,
        filename=filename,
        encoding=data.encoding,
        delimiter=data.delimiter,
        has_header=data.has_header,
    )
    types = column_types(rows, len(columns))
    table = TableData(
        sheet="",
        columns=[
            TableColumn(name=column, field_id=f"c{index + 1}", source_path=f"column:{index + 1}", value_type=types[index])
            for index, column in enumerate(columns)
        ],
        rows=rows,
        row_meta=[],
        source={"file": filename, "encoding": encoding, "delimiter": delimiter},
    )
    issues = [
        Issue(
            code="da01.bad_row",
            severity=Severity.warning,
            message=f"row {bad['row']} has {bad['actual_columns']} columns, expected {bad['expected_columns']}",
            target=f"row:{bad['row']}",
            retryable=False,
            suggested_action="fix quoting or delimiter, or keep the row quarantined",
        )
        for bad in bad_rows
    ]
    if encoding == "latin-1":
        issues.append(
            Issue(
                code="da01.encoding_fallback",
                severity=Severity.warning,
                message="file decoded with latin-1 fallback; verify non-ASCII cells",
                target=filename,
                retryable=False,
                suggested_action="re-export as UTF-8 or pass the correct encoding",
            )
        )
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    table_ref = helpers.store_table(runtime, table, ctx)
    helpers.register_file_tables(runtime, data.file_ref, [table_ref])
    return CapabilityResult[ParseDelimitedOutput](
        status=status,
        data=ParseDelimitedOutput(
            table=table_ref,
            row_count=len(rows),
            encoding=encoding,
            delimiter=delimiter,
            bad_rows=bad_rows,
            source_content_digest=data.file_ref.content_digest,
        ),
        issues=issues,
        provenance=[VersionedRef(id=data.file_ref.id, revision=data.file_ref.revision)],
        completeness=helpers.complete("delimited file rows", {"rows": len(rows)}),
    )


class ParseJsonRecordsInput(_Model):
    file_ref: FileRef
    format: Literal["auto", "json", "jsonl"] = "auto"
    records_path: str | None = None
    encoding: str = "utf-8"


class ParseJsonRecordsOutput(_Model):
    batch: DataBatchRef
    fields: list[dict[str, Any]] = Field(default_factory=list)
    bad_records: list[dict[str, Any]] = Field(default_factory=list)
    format: str = "json"
    source_content_digest: str | None = None


@operation(
    "DA01.4.4",
    input_model=ParseJsonRecordsInput,
    output_model=ParseJsonRecordsOutput,
    description="JSON/JSONL 解析：保留嵌套记录",
    writes=True,
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("file_ref",),
)
def parse_json_records(
    data: ParseJsonRecordsInput, ctx: CallContext, runtime
) -> CapabilityResult[ParseJsonRecordsOutput]:
    payload = helpers.read_file_ref(runtime, data.file_ref)
    helpers.register_file_ref(runtime, data.file_ref)
    parsed = _parse_json(
        payload,
        fmt=data.format,
        records_path=data.records_path,
        encoding=data.encoding,
    )
    digest = runtime.content.put(
        {
            "records": parsed["records"],
            "fields": parsed["fields"],
            "bad_records": parsed["bad_records"],
            "format": parsed["format"],
        }
    )
    inline = parsed["records"][:500]
    asset = helpers.asset_for(
        digest, "data_batch", helpers.scope_of(ctx), media_type="application/json"
    )
    batch = DataBatchRef(
        asset=asset,
        source_ref=data.file_ref.id,
        row_count=parsed["record_count"],
        completeness=helpers.complete(
            "JSON records", {"records": parsed["record_count"], "bad": len(parsed["bad_records"])}
        ),
        inline_rows=inline,
    )
    issues = [
        Issue(
            code="da01.bad_record",
            severity=Severity.warning,
            message=f"record/line rejected: {bad}",
            retryable=False,
            suggested_action="repair the malformed record",
        )
        for bad in parsed["bad_records"]
    ]
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[ParseJsonRecordsOutput](
        status=status,
        data=ParseJsonRecordsOutput(
            batch=batch,
            fields=parsed["fields"],
            bad_records=parsed["bad_records"],
            format=parsed["format"],
            source_content_digest=data.file_ref.content_digest,
        ),
        issues=issues,
        provenance=[VersionedRef(id=data.file_ref.id, revision=data.file_ref.revision)],
        completeness=helpers.complete("JSON records", {"records": parsed["record_count"]}),
    )


class ParseTextPdfInput(_Model):
    file_ref: FileRef
    pages: str | None = None
    extract_layout: bool = True


class ParseTextPdfOutput(_Model):
    document: DocumentRef
    page_count: int
    source_content_digest: str | None = None


@operation(
    "DA01.4.5",
    input_model=ParseTextPdfInput,
    output_model=ParseTextPdfOutput,
    description="文本型 PDF 解析：读取文字与版面位置",
    writes=True,
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("file_ref",),
)
def parse_text_pdf(
    data: ParseTextPdfInput, ctx: CallContext, runtime
) -> CapabilityResult[ParseTextPdfOutput]:
    payload = helpers.read_file_ref(runtime, data.file_ref)
    helpers.register_file_ref(runtime, data.file_ref)
    with _materialize(runtime, payload, ".pdf") as path:
        content, raw_issues = parse_pdf(path, page_range=data.pages)
    blocks_ref = helpers.store_document_blocks(runtime, content)
    asset = helpers.asset_for(
        blocks_ref, "document", helpers.scope_of(ctx), media_type="application/pdf"
    )
    document = DocumentRef(
        asset=asset,
        original_ref=VersionedRef(id=data.file_ref.id, revision=data.file_ref.revision),
        content_type="pdf_text",
        blocks_ref=blocks_ref,
        page_count=len(content.pages),
    )
    # Bind the parsed body to its source revision so a later caller cannot
    # recombine this reference with another document's blocks (reviewer F1).
    register_document_blocks(runtime, document)
    issues = [Issue.model_validate(item) for item in raw_issues]
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[ParseTextPdfOutput](
        status=status,
        data=ParseTextPdfOutput(
            document=document,
            page_count=len(content.pages),
            source_content_digest=data.file_ref.content_digest,
        ),
        issues=issues,
        provenance=[VersionedRef(id=data.file_ref.id, revision=data.file_ref.revision)],
        completeness=helpers.complete("PDF pages", {"pages": len(content.pages)}),
    )


class InspectWorkbookCalcStateInput(_Model):
    file_ref: FileRef | None = None
    workbook_ref: WorkbookRef | None = None
    sheets: list[str] | None = None


class InspectWorkbookCalcStateOutput(_Model):
    state: WorkbookCalcState
    workbook_ref: WorkbookRef


@operation(
    "DA01.4.6",
    input_model=InspectWorkbookCalcStateInput,
    output_model=InspectWorkbookCalcStateOutput,
    description="工作簿日期系统与公式缓存识别",
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("file_ref",),
)
def inspect_workbook_calc_state(
    data: InspectWorkbookCalcStateInput, ctx: CallContext, runtime
) -> CapabilityResult[InspectWorkbookCalcStateOutput]:
    file_ref = data.file_ref or (data.workbook_ref.file_ref if data.workbook_ref else None)
    if file_ref is None:
        raise invalid_input("inspect_workbook_calc_state requires file_ref or workbook_ref")
    payload = helpers.read_file_ref(runtime, file_ref)
    filename = (file_ref.filename or file_ref.locator).lower()
    if not filename.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
        raise invalid_input("calc state inspection only supports xlsx/xlsm workbooks")
    with _materialize(runtime, payload, filename) as path:
        workbook = open_workbook(path)
        cached = open_workbook(path, data_only=True)
    selected = data.sheets or list(workbook.sheetnames)
    formula_cells: list[FormulaCell] = []
    needs_recalc: list[str] = []
    cached_available = False
    for name in selected:
        if name not in workbook.sheetnames:
            continue
        ws = workbook[name]
        ws_cached = cached[name]
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    cached_value = ws_cached[cell.coordinate].value
                    if cached_value is not None:
                        cached_available = True
                    else:
                        needs_recalc.append(f"{name}!{cell.coordinate}")
                    formula_cells.append(
                        FormulaCell(
                            sheet=name,
                            cell=cell.coordinate,
                            formula=cell.value,
                            cached_value=cached_value,
                        )
                    )
    state = WorkbookCalcState(
        date_system="1904" if date_system(workbook) == "1904" else "1900",
        formula_cells=formula_cells,
        cached_values_available=cached_available,
        last_calculated=(
            workbook.properties.modified.isoformat() if workbook.properties.modified else None
        ),
        needs_recalc=needs_recalc,
    )
    workbook_ref = WorkbookRef(file_ref=file_ref, sheets=list(workbook.sheetnames))
    return CapabilityResult[InspectWorkbookCalcStateOutput](
        status=CapabilityStatus.ok,
        data=InspectWorkbookCalcStateOutput(state=state, workbook_ref=workbook_ref),
        provenance=[VersionedRef(id=file_ref.id, revision=file_ref.revision)],
        completeness=helpers.complete(
            "workbook cells",
            {"formula_cells": len(formula_cells), "needs_recalc": len(needs_recalc)},
        ),
    )


@contextmanager
def _materialize(runtime, payload: bytes, suffix: str):
    """Yield a private scratch path and always remove it afterwards."""

    import tempfile
    from pathlib import Path

    scratch = runtime.data_root / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    # The suffix may be a locator like "nested/file.xlsx"; tempfile only accepts
    # a plain suffix, so reduce it to the final extension.
    clean = Path(suffix).suffix
    if not clean and str(suffix).startswith("."):
        clean = str(suffix)
    if not clean or len(clean) > 10:
        clean = ".bin"
    handle = tempfile.NamedTemporaryFile(delete=False, dir=scratch, suffix=clean)
    try:
        handle.write(payload)
        handle.flush()
        handle.close()
        yield handle.name
    finally:
        handle.close()
        Path(handle.name).unlink(missing_ok=True)


def _column_letter(index: int) -> str:
    from openpyxl.utils import get_column_letter

    return get_column_letter(index)
