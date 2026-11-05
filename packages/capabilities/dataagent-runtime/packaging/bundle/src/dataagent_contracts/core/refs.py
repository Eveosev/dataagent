"""References, assets and source anchors (05-contracts.md §3.3.2)."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)

from ._base import ExtModel

__all__ = [
    "VersionedRef",
    "AssetRef",
    "FileRef",
    "SourceAnchor",
    "Selector",
    "PdfBBoxSelector",
    "PdfTextSpanSelector",
    "TextSpanSelector",
    "JsonPointerSelector",
    "ExcelCellSelector",
    "RecordKeySelector",
]


class VersionedRef(BaseModel):
    """``"<id>@<revision>"`` in JSON; accepts either the string or the object form."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    revision: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _from_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            if value.count("@") != 1:
                raise ValueError("VersionedRef string must contain exactly one '@'")
            identifier, revision = value.split("@")
            if not identifier or not revision or any(ch.isspace() for ch in value):
                raise ValueError("VersionedRef string must be '<id>@<revision>' without spaces")
            return {"id": identifier, "revision": revision}
        return value

    @field_validator("id", "revision")
    @classmethod
    def _part_has_no_separator(cls, value: str, info) -> str:
        # ``"<id>@<revision>"`` must round-trip. Either part containing '@'
        # would serialize to "a@b@r1", which the pattern (and parser) rejects.
        if "@" in value:
            raise ValueError(f"VersionedRef {info.field_name} must not contain '@'")
        if any(ch.isspace() for ch in value):
            raise ValueError(f"VersionedRef {info.field_name} must not contain whitespace")
        return value

    @model_serializer(mode="plain")
    def _to_string(self) -> str:
        return f"{self.id}@{self.revision}"

    def __str__(self) -> str:
        return f"{self.id}@{self.revision}"

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):  # noqa: ANN001
        return {
            "type": "string",
            "description": "Versioned reference serialized as '<id>@<revision>'.",
            "pattern": r"^[^@\s]+@[^@\s]+$",
        }


class AssetRef(ExtModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    scope_ref: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    resolver: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    digest: str | None = None
    media_type: str | None = None


class FileRef(AssetRef):
    """A controlled-store original. ``content_digest`` is mandatory."""

    filename: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    content_digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _digest_consistency(self) -> "FileRef":
        if self.digest is not None and self.digest != self.content_digest:
            raise ValueError("digest and content_digest must agree when both are set")
        return self


class _SelectorBase(ExtModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PdfBBoxSelector(_SelectorBase):
    kind: Literal["pdf_bbox"] = "pdf_bbox"
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float]
    unit: Literal["pt"] = "pt"

    @model_validator(mode="after")
    def _bbox_order(self) -> "PdfBBoxSelector":
        x0, y0, x1, y1 = self.bbox
        if x1 < x0 or y1 < y0:
            raise ValueError("bbox must be [x0, y0, x1, y1] with x1>=x0 and y1>=y0")
        return self


class PdfTextSpanSelector(_SelectorBase):
    kind: Literal["pdf_text_span"] = "pdf_text_span"
    page: int = Field(ge=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)

    @model_validator(mode="after")
    def _span_order(self) -> "PdfTextSpanSelector":
        if self.char_end < self.char_start:
            raise ValueError("char_end must be >= char_start")
        return self


class TextSpanSelector(_SelectorBase):
    kind: Literal["text_span"] = "text_span"
    unit_ref: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)

    @model_validator(mode="after")
    def _span_order(self) -> "TextSpanSelector":
        if self.char_end < self.char_start:
            raise ValueError("char_end must be >= char_start")
        return self


class JsonPointerSelector(_SelectorBase):
    kind: Literal["json_pointer"] = "json_pointer"
    # RFC 6901: the empty string addresses the whole document; ``/`` is the
    # empty key. The contract must be able to express both (05 §3.3.2).
    pointer: str = Field(pattern=r"^(?:/.*)?$")


class ExcelCellSelector(_SelectorBase):
    kind: Literal["excel_cell"] = "excel_cell"
    sheet: str = Field(min_length=1)
    range: str = Field(min_length=1)


class RecordKeySelector(_SelectorBase):
    kind: Literal["record_key"] = "record_key"
    keys: dict[str, Any] = Field(min_length=1)
    # The row is located by ``keys``; the anchored value is one field of that
    # row. A row-level selector is too coarse: it would accept any other field
    # in the record as "found in the source" (r5-plan item 2).
    field: str = Field(min_length=1)


Selector = Annotated[
    Union[
        PdfBBoxSelector,
        PdfTextSpanSelector,
        TextSpanSelector,
        JsonPointerSelector,
        ExcelCellSelector,
        RecordKeySelector,
    ],
    Field(discriminator="kind"),
]


class SourceAnchor(ExtModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_ref: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    selector: Selector
    extraction_ref: str | None = None
