"""Data and document references (05-contracts.md §3.3.3)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from ._base import ExtModel  # noqa: E402

from .envelope import Completeness, Issue
from .refs import AssetRef, SourceAnchor, VersionedRef
from .vocab import FieldValueStatus, OPEN_NAMESPACE_PATTERN

__all__ = [
    "FieldSpec",
    "SchemaRef",
    "TableRef",
    "DataBatchRef",
    "DocumentRef",
    "OcrInfo",
    "DocumentUnitRef",
    "ExtractedRecordRef",
    "FieldValue",
    "Confidence",
]


_Model = ExtModel


class FieldSpec(_Model):
    field_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    value_type: str = Field(min_length=1)
    nullable: bool | None = None
    unit: str | None = None


class SchemaRef(_Model):
    asset: AssetRef
    fields: list[FieldSpec] = Field(min_length=1)
    keys: list[list[str]] = Field(default_factory=list)
    inference_basis: Literal["declared", "inferred", "confirmed"]

    @model_validator(mode="after")
    def _keys_reference_fields(self) -> "SchemaRef":
        field_ids = {f.field_id for f in self.fields}
        for key in self.keys:
            if not key:
                raise ValueError("key must list at least one field_id")
            unknown = set(key) - field_ids
            if unknown:
                raise ValueError(f"key references unknown fields: {sorted(unknown)}")
        return self


class TableRef(_Model):
    asset: AssetRef
    schema_ref: VersionedRef
    data_ref: str = Field(min_length=1)
    row_identity: list[str] | None = None
    source_map_ref: str | None = None
    transform_ref: str | None = None


class DataBatchRef(_Model):
    asset: AssetRef
    schema_ref: VersionedRef | None = None
    source_ref: str = Field(min_length=1)
    row_count: int = Field(ge=0)
    completeness: Completeness
    cursor: str | None = None
    inline_rows: list[dict[str, Any]] | None = None

    @model_validator(mode="after")
    def _inline_limit(self) -> "DataBatchRef":
        if self.inline_rows is not None and len(self.inline_rows) > 500:
            raise ValueError("inline_rows is capped at 500 rows; use the asset reference")
        return self


class OcrInfo(_Model):
    engine_ref: str = Field(min_length=1)
    engine_version: str = Field(min_length=1)
    mean_confidence: float = Field(ge=0.0, le=1.0)
    low_confidence_pages: list[int] = Field(default_factory=list)


class DocumentRef(_Model):
    asset: AssetRef
    original_ref: VersionedRef
    content_type: Literal["pdf_text", "pdf_scanned", "image", "json", "text"]
    blocks_ref: str = Field(min_length=1)
    page_count: int | None = Field(default=None, ge=0)
    ocr: OcrInfo | None = None


class DocumentUnitRef(_Model):
    asset: AssetRef
    parent_document_ref: VersionedRef
    unit_type: str = Field(min_length=1)
    ordinal_path: str = Field(min_length=1)
    title: str | None = None
    content_ref: str = Field(min_length=1)
    anchors: list[SourceAnchor] = Field(min_length=1)
    context_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unit_type(self) -> "DocumentUnitRef":
        allowed = {"chapter", "section", "clause", "item", "table", "paragraph"}
        if self.unit_type not in allowed and not OPEN_NAMESPACE_PATTERN.fullmatch(
            self.unit_type
        ):
            raise ValueError(
                "unit_type must be one of the S0 values or namespaced 'ns.name'"
            )
        return self


class Confidence(_Model):
    score: float = Field(ge=0.0, le=1.0)
    method: str = Field(min_length=1)


class FieldValue(_Model):
    field_id: str = Field(min_length=1)
    status: FieldValueStatus
    value: Any | None = None
    value_type: str
    unit: str | None = None
    confidence: Confidence | None = None
    evidence: list[SourceAnchor] = Field(default_factory=list)
    alternatives: list[Any] | None = None

    @model_validator(mode="after")
    def _evidence_and_value(self) -> "FieldValue":
        if self.status is FieldValueStatus.extracted:
            if self.value is None:
                raise ValueError("extracted FieldValue requires a non-null value")
            if not self.evidence:
                raise ValueError("extracted FieldValue requires at least one SourceAnchor")
        if self.status is FieldValueStatus.missing and self.value is not None:
            raise ValueError("missing FieldValue must not carry a value")
        if self.status is FieldValueStatus.conflict and not (self.alternatives or self.evidence):
            raise ValueError("conflict FieldValue requires alternatives or evidence")
        return self


class ExtractedRecordRef(_Model):
    asset: AssetRef
    document_ref: VersionedRef
    target_schema_ref: VersionedRef
    fields: list[FieldValue] = Field(default_factory=list)
    values_ref: str | None = None
    issues: list[Issue] = Field(default_factory=list)

    @model_validator(mode="after")
    def _inline_or_external(self) -> "ExtractedRecordRef":
        if len(self.fields) > 200:
            raise ValueError("inline fields are capped at 200; use values_ref")
        if not self.fields and not self.values_ref:
            raise ValueError("ExtractedRecordRef requires either fields or values_ref")
        return self
