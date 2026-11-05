"""Data-layer-local types (05-contracts.md §3.6).

Cross-layer information is expressed through core ``VersionedRef`` /
``TableRef`` / ``Assessment``. The eight types below stay inside the data layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dataagent_contracts.core import (
    AssetRef,
    FieldSpec,
    FileRef,
    SourceAnchor,
    VersionedRef,
)

RowRole = Literal["detail", "subtotal", "total", "title", "unknown"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RowMeta(_Model):
    role: RowRole = "detail"
    reason: str = ""


class TableColumn(_Model):
    name: str = Field(min_length=1)
    field_id: str = Field(min_length=1)
    source_path: str = ""
    value_type: str = "unknown"
    unit: str | None = None


class TableData(_Model):
    """Stored representation of a logical table (content-addressed)."""

    sheet: str = ""
    columns: list[TableColumn]
    rows: list[list[Any]] = Field(default_factory=list)
    row_meta: list[RowMeta] = Field(default_factory=list)
    merged_ranges: list[str] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    source_map_ref: str | None = None

    @model_validator(mode="after")
    def _row_shapes(self) -> "TableData":
        if self.row_meta and len(self.row_meta) != len(self.rows):
            raise ValueError("row_meta must be empty or align one-to-one with rows")
        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError("every row must have exactly len(columns) cells")
        return self

    def schema_fields(self) -> list[FieldSpec]:
        return [
            FieldSpec(
                field_id=column.field_id,
                name=column.name,
                path=column.source_path or column.field_id,
                value_type=column.value_type,
                nullable=True,
                unit=column.unit,
            )
            for column in self.columns
        ]


class FormulaCell(_Model):
    sheet: str
    cell: str
    formula: str
    cached_value: Any | None = None


class WorkbookRef(_Model):
    file_ref: FileRef
    sheets: list[str] = Field(default_factory=list)
    table_refs: list[VersionedRef] = Field(default_factory=list)
    source_map_ref: str | None = None
    calc_state_ref: str | None = None


class WorkbookCalcState(_Model):
    date_system: Literal["1900", "1904"]
    date_system_source: str = "workbookPr"
    formula_cells: list[FormulaCell] = Field(default_factory=list)
    cached_values_available: bool = False
    last_calculated: str | None = None
    needs_recalc: list[str] = Field(default_factory=list)


class TableRegion(_Model):
    workbook_ref: WorkbookRef
    sheet: str = Field(min_length=1)
    cell_range: str = Field(min_length=1)
    source_anchor: SourceAnchor
    confidence: float = Field(ge=0.0, le=1.0)
    overlapping: bool = False
    layout_ref: str | None = None


class ProfileRef(_Model):
    asset: AssetRef
    dataset_ref: str = Field(min_length=1)
    field_stats_ref: str = Field(min_length=1)
    method: Literal["exact", "sampled"]
    sample_spec: str | None = None
    observed_at: datetime


class ExtractionSchemaRef(_Model):
    schema_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    fields: list[FieldSpec] = Field(min_length=1)
    digest: str = Field(min_length=1)
    document_type: str | None = None
    previous_ref: VersionedRef | None = None
    status: Literal["draft", "validated"] = "draft"


class Gap(_Model):
    requirement_id: str = Field(min_length=1)
    kind: Literal["evidence", "data", "human", "method"]
    description: str = Field(min_length=1)
    route: str = Field(min_length=1)
    reason: str = ""


class GapPlan(_Model):
    requirement_ref: str = Field(min_length=1)
    gaps: list[Gap] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)


class CoverageItem(_Model):
    requirement_id: str = Field(min_length=1)
    verdict: Literal["auto", "needs_evidence", "needs_human"]
    reason: str = ""


class CoverageMap(_Model):
    total: int = Field(ge=0)
    covered: int = Field(ge=0)
    needs_evidence: int = Field(ge=0)
    human: int = Field(ge=0)
    items: list[CoverageItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _counts_add_up(self) -> "CoverageMap":
        if self.covered + self.needs_evidence + self.human != self.total:
            raise ValueError("coverage buckets must sum to total")
        if len(self.items) not in {0, self.total}:
            raise ValueError("items must be empty or one per requirement")
        return self


class ApplicabilityDraft(_Model):
    draft_id: str = Field(min_length=1)
    rule_ref: str = Field(min_length=1)
    scope_expression: str = Field(min_length=1)
    object_types: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    sources: list[SourceAnchor] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    status: Literal["draft", "validated"] = "draft"


class TextBlock(_Model):
    page: int = Field(ge=1)
    text: str
    bbox: list[float] | None = None
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    confidence: float | None = None


class PageContent(_Model):
    page: int = Field(ge=1)
    width: float | None = None
    height: float | None = None
    text: str = ""
    blocks: list[TextBlock] = Field(default_factory=list)


class DocumentContent(_Model):
    pages: list[PageContent] = Field(default_factory=list)
    full_text: str = ""

    def page(self, number: int) -> PageContent:
        """Return a page by its *page number*, not its list index.

        ``ParseTextPdf`` can produce a subset of pages (``pages=2-3``), so
        ``pages[page - 1]`` is wrong whenever page 1 is absent.
        """

        for item in self.pages:
            if item.page == number:
                return item
        raise KeyError(f"page not found: {number}")

    def page_text(self, page: int) -> str:
        return self.page(page).text

    @model_validator(mode="after")
    def _full_text(self) -> "DocumentContent":
        if not self.full_text and self.pages:
            self.full_text = "\n".join(page.text for page in self.pages)
        return self
