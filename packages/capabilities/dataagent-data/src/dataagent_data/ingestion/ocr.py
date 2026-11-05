"""DA01.5.1/2 OCR atoms. Missing engine returns dependency_unavailable."""

from __future__ import annotations

import io
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    DocumentRef,
    FileRef,
    Issue,
    OcrInfo,
    Severity,
    VersionedRef,
)

from dataagent_data.adapters.ocr.engine import OcrEngine, RapidOcrEngine
from dataagent_data.adapters.parsers.pdf import is_pdf_input_error
from dataagent_data.contracts.layer import DocumentContent, PageContent, TextBlock
from dataagent_data.preparation.documents import register_document_blocks
from dataagent_data import helpers
from dataagent_runtime.errors import (
    CapabilityError,
    dependency_unavailable,
    execution_unknown,
    invalid_input,
)
from dataagent_data.page_range import parse_page_range
from dataagent_data.registry import operation


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _engine(runtime) -> OcrEngine:
    engine = getattr(runtime, "ocr_engine", None)
    if engine is None:
        engine = RapidOcrEngine.create()
        if engine is not None:
            runtime.ocr_engine = engine
    if engine is None:
        raise dependency_unavailable(
            "OCR engine is not installed", action="install the optional 'ocr' dependency group"
        )
    return engine


def _pages_to_content(
    engine: OcrEngine,
    images: list[bytes],
    *,
    lang: str | None,
    page_numbers: list[int] | None = None,
    dpi: int = 72,
) -> tuple[DocumentContent, OcrInfo, list[Issue]]:
    pages: list[PageContent] = []
    confidences: list[float] = []
    low_pages: list[int] = []
    issues: list[Issue] = []
    numbers = page_numbers if page_numbers is not None else list(range(1, len(images) + 1))
    for number, image in zip(numbers, images):
        blocks = engine.recognize(image, lang=lang)
        text_parts = []
        text_blocks: list[TextBlock] = []
        cursor = 0
        for index, block in enumerate(blocks):
            # Page text joins block texts with "\n"; the cursor must account for
            # that separator so page_text[start:end] == block.text.
            if index:
                cursor += 1
            start = cursor
            text_parts.append(block.text)
            cursor += len(block.text)
            # Engines return pixel boxes; PDF text/bbox selectors use points.
            scale = 72.0 / dpi
            text_blocks.append(
                TextBlock(
                    page=number,
                    text=block.text,
                    bbox=(
                        [round(value * scale, 2) for value in block.bbox]
                        if block.bbox
                        else None
                    ),
                    char_start=start,
                    char_end=cursor,
                    confidence=block.confidence,
                )
            )
            confidences.append(block.confidence)
        page_text = "\n".join(text_parts)
        mean = sum(b.confidence for b in blocks) / len(blocks) if blocks else 0.0
        if blocks and mean < 0.6:
            low_pages.append(number)
            issues.append(
                Issue(
                    code="da01.low_ocr_confidence",
                    severity=Severity.warning,
                    message=f"OCR mean confidence {mean:.2f} on page {number}",
                    target=f"page:{number}",
                    retryable=False,
                    suggested_action="review low-confidence digits manually",
                )
            )
        pages.append(PageContent(page=number, text=page_text, blocks=text_blocks))
    if not confidences:
        issues.append(
            Issue.standard(
                "da01.ocr_empty",
                "OCR engine returned no text blocks",
                severity=Severity.warning,
                suggested_action="check image resolution or select another OCR engine",
            )
        )
    info = OcrInfo(
        engine_ref=engine.engine_ref,
        engine_version=engine.engine_version,
        mean_confidence=round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        low_confidence_pages=low_pages,
    )
    return DocumentContent(pages=pages), info, issues


class OcrPdfInput(_Model):
    file_ref: FileRef
    pages: str | None = None
    lang: str | None = None
    dpi: int = Field(default=150, ge=72, le=400)


class OcrPdfOutput(_Model):
    document: DocumentRef
    page_count: int
    source_content_digest: str | None = None


@operation(
    "DA01.5.1",
    input_model=OcrPdfInput,
    output_model=OcrPdfOutput,
    description="扫描 PDF OCR",
    writes=True,
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("file_ref",),
)
def ocr_pdf(data: OcrPdfInput, ctx: CallContext, runtime) -> CapabilityResult[OcrPdfOutput]:
    engine = _engine(runtime)
    payload = helpers.read_file_ref(runtime, data.file_ref)
    helpers.register_file_ref(runtime, data.file_ref)
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - declared dependency
        raise dependency_unavailable("pdfplumber is required to render scanned pages") from exc
    images: list[bytes] = []
    selected: list[int] = []
    try:
        with pdfplumber.open(io.BytesIO(payload)) as pdf:
            selected = (
                parse_page_range(data.pages, len(pdf.pages))
                if data.pages
                else list(range(1, len(pdf.pages) + 1))
            )
            for number in selected:
                image = pdf.pages[number - 1].to_image(resolution=data.dpi).original
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                images.append(buffer.getvalue())
    except CapabilityError:
        raise
    except Exception as exc:  # noqa: BLE001 - classify, never blanket invalid_input
        # Only PDF-format/encryption problems are the caller's fault; an
        # internal renderer failure must not be reported as invalid input
        # (reviewer R6, 06 §14 item 5).
        message = f"cannot render PDF pages: {type(exc).__name__}: {exc}"
        if is_pdf_input_error(exc):
            raise invalid_input(message) from exc
        raise execution_unknown(message) from exc
    content, info, issues = _pages_to_content(
        engine, images, lang=data.lang, page_numbers=selected, dpi=data.dpi
    )
    blocks_ref = helpers.store_document_blocks(runtime, content)
    asset = helpers.asset_for(
        blocks_ref, "document", helpers.scope_of(ctx), media_type="application/pdf"
    )
    document = DocumentRef(
        asset=asset,
        original_ref=VersionedRef(id=data.file_ref.id, revision=data.file_ref.revision),
        content_type="pdf_scanned",
        blocks_ref=blocks_ref,
        page_count=len(content.pages),
        ocr=info,
    )
    # Bind the OCR body to its source revision (reviewer F1).
    register_document_blocks(runtime, document)
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[OcrPdfOutput](
        status=status,
        data=OcrPdfOutput(
            document=document,
            page_count=len(content.pages),
            source_content_digest=data.file_ref.content_digest,
        ),
        issues=issues,
        provenance=[VersionedRef(id=data.file_ref.id, revision=data.file_ref.revision)],
        completeness=helpers.complete("OCR pages", {"pages": len(content.pages)}),
    )


class OcrImageInput(_Model):
    file_ref: FileRef
    region: str | None = None
    orientation: Literal["auto", "0", "90", "180", "270"] = "auto"
    lang: str | None = None


class OcrImageOutput(_Model):
    document: DocumentRef
    low_confidence_blocks: int = 0
    source_content_digest: str | None = None


def _parse_region(region: str, size: tuple[int, int]) -> tuple[int, int, int, int]:
    """Parse ``"x0,y0,x1,y1"`` pixel crop coordinates."""

    parts = [part.strip() for part in region.split(",")]
    if len(parts) != 4:
        raise invalid_input(
            "region must be 'x0,y0,x1,y1' in pixels", target="region"
        )
    try:
        x0, y0, x1, y1 = (int(part) for part in parts)
    except ValueError as exc:
        raise invalid_input("region coordinates must be integers", target="region") from exc
    width, height = size
    if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
        raise invalid_input(
            "region must satisfy 0 <= x0 < x1 and 0 <= y0 < y1", target="region"
        )
    if x1 > width or y1 > height:
        raise invalid_input(
            f"region {region} exceeds the image bounds {width}x{height}", target="region"
        )
    return x0, y0, x1, y1


def _prepare_image(payload: bytes, region: str | None, orientation: str) -> bytes:
    """Crop/rotate image bytes before OCR; missing Pillow is dependency_unavailable."""

    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover - declared dependency
        raise dependency_unavailable(
            "Pillow is required for image preprocessing", action="install Pillow"
        ) from exc
    try:
        image = Image.open(io.BytesIO(payload))
        image.load()
    except Exception as exc:  # noqa: BLE001 - corrupt image bytes are client input
        raise invalid_input(f"cannot decode image: {type(exc).__name__}: {exc}") from exc
    if region:
        image = image.crop(_parse_region(region, image.size))
    if orientation == "auto":
        image = ImageOps.exif_transpose(image)
    else:
        angle = int(orientation)
        if angle:
            image = image.rotate(angle, expand=True)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


@operation(
    "DA01.5.2",
    input_model=OcrImageInput,
    output_model=OcrImageOutput,
    description="图片 OCR",
    writes=True,
    idempotent=True,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("file_ref",),
)
def ocr_image(data: OcrImageInput, ctx: CallContext, runtime) -> CapabilityResult[OcrImageOutput]:
    engine = _engine(runtime)
    payload = helpers.read_file_ref(runtime, data.file_ref)
    helpers.register_file_ref(runtime, data.file_ref)
    prepared = (
        _prepare_image(payload, data.region, data.orientation)
        if data.region or data.orientation != "auto"
        else payload
    )
    content, info, issues = _pages_to_content(engine, [prepared], lang=data.lang)
    blocks_ref = helpers.store_document_blocks(runtime, content)
    asset = helpers.asset_for(
        blocks_ref, "document", helpers.scope_of(ctx), media_type="image/*"
    )
    document = DocumentRef(
        asset=asset,
        original_ref=VersionedRef(id=data.file_ref.id, revision=data.file_ref.revision),
        content_type="image",
        blocks_ref=blocks_ref,
        page_count=1,
        ocr=info,
    )
    # Bind the OCR body to its source revision (reviewer F1).
    register_document_blocks(runtime, document)
    low = sum(1 for page in content.pages for block in page.blocks if _confidence_of(block) < 0.6)
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[OcrImageOutput](
        status=status,
        data=OcrImageOutput(
            document=document,
            low_confidence_blocks=low,
            source_content_digest=data.file_ref.content_digest,
        ),
        issues=issues,
        provenance=[VersionedRef(id=data.file_ref.id, revision=data.file_ref.revision)],
        completeness=helpers.complete("OCR image", {"pages": 1}),
    )


def _confidence_of(block: TextBlock) -> float:
    return block.confidence if block.confidence is not None else 1.0
