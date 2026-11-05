"""DA02.8.1 document segmentation and DA02.8.2 source-anchor maintenance."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    DocumentRef,
    DocumentUnitRef,
    Issue,
    Severity,
    SourceAnchor,
    VersionedRef,
)

from dataagent_data.contracts.layer import DocumentContent
from dataagent_data import helpers
from dataagent_data.anchors import AnchorResolver, anchor_invalid_reason
from dataagent_runtime.errors import invalid_input
from dataagent_data.registry import operation

HEADING = re.compile(
    r"^(?P<prefix>第[〇零一二三四五六七八九十百千0-9]+[章节条款部分]"
    r"|[0-9]+(?:\.[0-9]+)*(?:[、.．\s]|$)"
    r"|[（(][一二三四五六七八九十0-9]+[）)])"
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


def document_blocks_key(source_ref: str, source_revision: str, blocks_ref: str) -> str:
    """Key binding a persisted document body to the source revision it parsed."""

    return f"{source_ref}@{source_revision}:{blocks_ref}"


def register_document_blocks(runtime, document: DocumentRef) -> None:
    """Record that ``document.blocks_ref`` was parsed from ``document.original_ref``.

    Parse atoms call this when they produce a ``DocumentRef`` (reviewer F1).
    ``load_document_content`` only accepts blocks whose (source, revision,
    blocks) triple was recorded here, so a caller cannot recombine one
    document's ``original_ref`` with another document's body.
    """

    runtime.versions.save_content_addressed(
        "document_blocks",
        document_blocks_key(
            document.original_ref.id,
            document.original_ref.revision,
            document.blocks_ref,
        ),
        {
            "source_ref": document.original_ref.id,
            "source_revision": document.original_ref.revision,
            "blocks_ref": document.blocks_ref,
            "content_type": document.content_type,
            "page_count": document.page_count,
        },
    )


def load_document_content(runtime, document: DocumentRef) -> DocumentContent:
    # r32-gov B1, first line of defence: the document asset must be bound to
    # the body actually read — ``blocks_ref`` is the asset's content
    # (revision, and digest when declared) whatever resolver string the
    # caller chose. The runtime recheck refuses this before any read; the
    # handler refuses it too, so a decision minted for asset A cannot be
    # replayed against asset B's body even with the recheck disabled.
    asset = document.asset
    if document.blocks_ref != asset.revision or (
        asset.digest is not None and document.blocks_ref != asset.digest
    ):
        raise invalid_input(
            "document_ref.blocks_ref is not the document asset's content "
            f"({document.blocks_ref!r} vs revision {asset.revision!r}); refusing "
            "to read unbound document content",
            target="document_ref.blocks_ref",
        )
    # The blocks must be the ones this exact source revision was parsed into
    # (reviewer F1): a reference that recombines document A's ``original_ref``
    # with document B's ``blocks_ref`` used to pass every downstream anchor
    # check because the anchors only ever saw B's body. Fail closed unless a
    # parse record binds the triple together.
    binding = runtime.versions.current(
        "document_blocks",
        document_blocks_key(
            document.original_ref.id,
            document.original_ref.revision,
            document.blocks_ref,
        ),
    )
    if binding is None:
        raise invalid_input(
            "document blocks are not bound to their source: no parse record "
            f"for {document.original_ref} -> {document.blocks_ref}. Re-parse "
            "the source file, or register the binding for locally built "
            "documents before use.",
            target="document_ref.blocks_ref",
        )
    try:
        payload = runtime.content.get_json(document.blocks_ref)
    except FileNotFoundError as exc:
        raise invalid_input(f"document blocks not found: {document.blocks_ref}") from exc
    return DocumentContent.model_validate(payload)


def _page_spans(content: DocumentContent) -> list[tuple[int, int, int]]:
    spans = []
    cursor = 0
    for index, page in enumerate(content.pages):
        if index:
            cursor += 1  # join newline
        start = cursor
        cursor += len(page.text)
        spans.append((page.page, start, cursor))
    return spans


def _locate(spans: list[tuple[int, int, int]], start: int, end: int):
    out = []
    for page, page_start, page_end in spans:
        if end <= page_start or start >= page_end:
            continue
        out.append(
            (
                page,
                max(start, page_start) - page_start,
                min(end, page_end) - page_start,
            )
        )
    return out


def _unit_type(prefix: str) -> str:
    if "章" in prefix:
        return "chapter"
    if "节" in prefix:
        return "section"
    if "条" in prefix:
        return "clause"
    if prefix.startswith(("（", "(")):
        return "item"
    return "paragraph"


def unit_index_key(source_ref: str, source_revision: str, content_ref: str) -> str:
    """Key binding a persisted unit body to its source document revision."""

    return f"{source_ref}@{source_revision}:{content_ref}"


class SegmentDocumentInput(_Model):
    document_ref: DocumentRef
    strategy: Literal["headings", "paragraphs"] = "headings"
    context_window: int = Field(default=1, ge=0)
    max_units: int = Field(default=2000, ge=1)


class SegmentDocumentOutput(_Model):
    units: list[DocumentUnitRef] = Field(default_factory=list)
    document_ref: VersionedRef


@operation(
    "DA02.8.1",
    input_model=SegmentDocumentInput,
    output_model=SegmentDocumentOutput,
    writes=True,
    description="章节/表格切分",
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("document_ref",),
)
def segment_document(
    data: SegmentDocumentInput, ctx: CallContext, runtime
) -> CapabilityResult[SegmentDocumentOutput]:
    content = load_document_content(runtime, data.document_ref)
    full_text = content.full_text
    if not full_text.strip():
        raise invalid_input("document has no text to segment")
    spans = _page_spans(content)
    lines = full_text.splitlines(keepends=True)

    units_text: list[tuple[str, str, int, int]] = []
    if data.strategy == "paragraphs":
        cursor = 0
        for block in re.split(r"\n\s*\n", full_text):
            start = full_text.find(block, cursor)
            if start < 0:
                continue
            cursor = start + len(block)
            if block.strip():
                units_text.append((block.strip(), "paragraph", start, start + len(block)))
    else:
        current_start = 0
        current_heading = ""
        cursor = 0
        for line in lines:
            stripped = line.strip()
            match = HEADING.match(stripped)
            if match and cursor > current_start:
                body = full_text[current_start:cursor].strip()
                if body:
                    units_text.append(
                        (body, _unit_type(current_heading), current_start, cursor)
                    )
                current_start = cursor
                current_heading = match.group("prefix")
            elif match and cursor == current_start:
                current_heading = match.group("prefix")
            cursor += len(line)
        tail = full_text[current_start:].strip()
        if tail:
            units_text.append((tail, _unit_type(current_heading), current_start, len(full_text)))
        if not units_text:
            units_text.append((full_text.strip(), "paragraph", 0, len(full_text)))

    total_units = len(units_text)
    units_text = units_text[: data.max_units]
    issues: list[Issue] = []
    source_id = data.document_ref.original_ref.id
    source_revision = data.document_ref.original_ref.revision
    built: list[DocumentUnitRef] = []
    for index, (text, unit_type, start, end) in enumerate(units_text, start=1):
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        prefix_match = HEADING.match(first_line)
        ordinal = (
            prefix_match.group("prefix").strip().replace("．", ".").rstrip("、.．")
            if prefix_match
            else str(index)
        )
        title = (
            first_line[prefix_match.end() :][:120].strip(" ：:、")
            if prefix_match
            else first_line[:120]
        )
        located = _locate(spans, start, end)
        if not located:
            raise invalid_input(
                f"document unit {ordinal} cannot be located in any page span"
            )
        anchors: list[SourceAnchor] = []
        # Persist the unit body first: non-PDF ``text_span`` anchors are
        # relative to the unit text (05 §3.3.2), not to the whole document.
        content_ref = runtime.content.put(text)
        # The unit index is the *only* binding between a content blob and the
        # source/revision it belongs to. Anchors cannot point at an arbitrary
        # content digest, and the document asset id is never a unit (W1 P1).
        runtime.versions.save_content_addressed(
            "document_unit_index",
            unit_index_key(source_id, source_revision, content_ref),
            {
                "document_ref": str(data.document_ref.original_ref),
                "source_ref": source_id,
                "source_revision": source_revision,
                "content_ref": content_ref,
                "unit_type": unit_type,
                "ordinal_path": ordinal,
            },
        )
        for page, char_start, char_end in located:
            if data.document_ref.content_type in {"pdf_text", "pdf_scanned"}:
                anchors.append(
                    helpers.make_anchor(
                        source_ref=source_id,
                        source_revision=source_revision,
                        page=page,
                        char_start=char_start,
                        char_end=char_end,
                    )
                )
            else:
                anchors.append(
                    SourceAnchor(
                        source_ref=source_id,
                        source_revision=source_revision,
                        selector={
                            "kind": "text_span",
                            "unit_ref": content_ref,
                            "char_start": 0,
                            "char_end": len(text),
                        },
                    )
                )
        asset = helpers.asset_for(content_ref, "document_unit", helpers.scope_of(ctx))
        built.append(
            DocumentUnitRef(
                asset=asset,
                parent_document_ref=data.document_ref.original_ref,
                unit_type=unit_type,
                ordinal_path=ordinal,
                title=title or None,
                content_ref=content_ref,
                anchors=anchors,
                context_refs=[],
            )
        )
    # Link parent chapters by ordinal prefix when present.
    by_ordinal = {unit.ordinal_path: unit.asset.id for unit in built}
    updated = []
    for unit in built:
        parents = []
        parts = unit.ordinal_path.replace("．", ".").split(".")
        for length in range(len(parts) - 1, 0, -1):
            candidate = ".".join(parts[:length])
            if candidate in by_ordinal and by_ordinal[candidate] != unit.asset.id:
                parents.append(by_ordinal[candidate])
                break
        updated.append(unit.model_copy(update={"context_refs": parents}))
    if all(unit.unit_type == "paragraph" for unit in updated) and len(updated) == 1:
        issues.append(
            Issue.standard(
                "da02.no_heading_detected",
                "no headings detected; document returned as a single paragraph unit",
                severity=Severity.info,
            )
        )
    status = CapabilityStatus.partial if any(i.severity is Severity.warning for i in issues) else CapabilityStatus.ok
    # A ``max_units`` cap that actually dropped units must not be reported as
    # complete-in-declared-scope: the caller would treat the subset as the
    # whole document (06 §4.1 completeness semantics; tester r17 R5).
    completeness = (
        helpers.truncated(
            "document paragraphs",
            reason=(
                f"max_units={data.max_units} returned {len(updated)} of "
                f"{total_units} detected units"
            ),
            observed={"units": len(updated), "total_units": total_units},
        )
        if total_units > data.max_units
        else helpers.complete("document paragraphs", {"units": len(updated)})
    )
    return CapabilityResult[SegmentDocumentOutput](
        status=status,
        data=SegmentDocumentOutput(units=updated, document_ref=data.document_ref.original_ref),
        issues=issues,
        provenance=[data.document_ref.original_ref],
        completeness=completeness,
    )


class MaintainSourceAnchorsInput(_Model):
    anchors: list[SourceAnchor] = Field(min_length=1)
    current_revision: str
    revision_map: dict[str, str] = Field(default_factory=dict)
    document_ref: DocumentRef | None = None


class AnchorStatus(_Model):
    status: Literal["valid", "remapped", "expired", "unresolved"]
    anchor: SourceAnchor
    reason: str = ""


class AnchorMaintenanceOutput(_Model):
    anchors: list[AnchorStatus]
    mapping_version_ref: str


@operation(
    "DA02.8.2",
    input_model=MaintainSourceAnchorsInput,
    output_model=AnchorMaintenanceOutput,
    writes=True,
    description="原文引用锚点维护",
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("document_ref",),
)
def maintain_source_anchors(
    data: MaintainSourceAnchorsInput, ctx: CallContext, runtime
) -> CapabilityResult[AnchorMaintenanceOutput]:
    # The payload used to verify an anchor must belong to the revision the
    # caller claims is current. Otherwise a stale document body would make
    # "valid" look true across revisions (W1 P1, fail-closed).
    if (
        data.document_ref is not None
        and data.document_ref.original_ref.revision != data.current_revision
    ):
        raise invalid_input(
            "document_ref revision does not match current_revision: "
            f"{data.document_ref.original_ref.revision} != {data.current_revision}",
            target="document_ref.original_ref.revision",
        )
    content = (
        load_document_content(runtime, data.document_ref) if data.document_ref is not None else None
    )
    resolver = None
    if content is not None:
        resolver = AnchorResolver(content, runtime=runtime)
    results: list[AnchorStatus] = []
    for anchor in data.anchors:
        if anchor.source_revision == data.current_revision:
            status, reason = "valid", "revision matches the current source"
        elif anchor.source_revision in data.revision_map:
            mapped = data.revision_map[anchor.source_revision]
            if mapped != data.current_revision:
                results.append(
                    AnchorStatus(
                        status="unresolved",
                        anchor=anchor,
                        reason=(
                            "revision mapping does not point at current_revision: "
                            f"{mapped} != {data.current_revision}"
                        ),
                    )
                )
                continue
            anchor = anchor.model_copy(update={"source_revision": mapped})
            status, reason = "remapped", "revision mapped to the current source"
        else:
            results.append(
                AnchorStatus(
                    status="expired",
                    anchor=anchor,
                    reason="source revision changed and no revision mapping was supplied",
                )
            )
            continue
        if resolver is None:
            # Without a document payload the anchor text cannot be verified; a
            # matching revision alone is not evidence (06 §14 item 1).
            results.append(
                AnchorStatus(
                    status="unresolved",
                    anchor=anchor,
                    reason="document_ref is required to verify the anchor text",
                )
            )
            continue
        if (
            data.document_ref is not None
            and anchor.source_ref != data.document_ref.original_ref.id
        ):
            results.append(
                AnchorStatus(
                    status="unresolved",
                    anchor=anchor,
                    reason="anchor source_ref does not match the document",
                )
            )
            continue
        invalid = anchor_invalid_reason(resolver, anchor)
        if invalid:
            results.append(
                AnchorStatus(status="unresolved", anchor=anchor, reason=invalid)
            )
            continue
        results.append(AnchorStatus(status=status, anchor=anchor, reason=reason))
    mapping_digest = runtime.content.put(
        {"anchors": [item.model_dump(mode="json") for item in results]}
    )
    return CapabilityResult[AnchorMaintenanceOutput](
        status=CapabilityStatus.ok,
        data=AnchorMaintenanceOutput(
            anchors=results, mapping_version_ref=f"anchor-map:{mapping_digest.split(':', 1)[1][:16]}"
        ),
        completeness=helpers.complete("anchors", {"anchors": len(results)}),
    )
