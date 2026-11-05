"""PDF text-layer parsing (pdfplumber)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dataagent_data.contracts.layer import DocumentContent, PageContent, TextBlock
from dataagent_runtime.errors import (
    CapabilityError,
    dependency_unavailable,
    execution_unknown,
    invalid_input,
)

# PDF-format problems attributable to the caller's file. Everything else is an
# internal/library failure and must surface as ``execution_unknown`` instead of
# blaming the caller (06 §14 item 5).
_PDF_INPUT_ERRORS = frozenset(
    {
        "PDFSyntaxError",
        "PDFPasswordIncorrect",
        "PDFEncryptionError",
        "PDFTextExtractionNotAllowed",
        "PDFInvalidArgumentError",
        "PdfReadError",
        "PDFPageCountError",
        "FileNotFoundError",
        "IsADirectoryError",
        "PermissionError",
    }
)


def _is_pdf_input_error(exc: BaseException, seen: set[int] | None = None) -> bool:
    """Classify a PDF failure, unwrapping library wrappers.

    pdfplumber wraps ``PDFSyntaxError`` in ``PdfminerException``; the wrapper
    class name alone is not informative, so we inspect causes, contexts and
    exception args for a known format/encryption error.
    """

    seen = seen or set()
    if id(exc) in seen:
        return False
    seen.add(id(exc))
    if any(klass.__name__ in _PDF_INPUT_ERRORS for klass in type(exc).__mro__):
        return True
    for nested in (exc.__cause__, exc.__context__):
        if nested is not None and _is_pdf_input_error(nested, seen):
            return True
    for arg in getattr(exc, "args", ()):
        if isinstance(arg, BaseException) and _is_pdf_input_error(arg, seen):
            return True
    return False


# Shared with the OCR ingestion path (``ingestion/ocr.py``), which renders the
# same caller-supplied PDFs and must classify failures the same way.
is_pdf_input_error = _is_pdf_input_error


def _pdfplumber():
    try:
        import pdfplumber  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise dependency_unavailable(
            "pdfplumber is not installed", action="install the 'pdf' dependency group"
        ) from exc
    return pdfplumber


def parse_pdf(
    path: str | Path, *, page_range: str | None = None
) -> tuple[DocumentContent, list[dict[str, Any]]]:
    pdfplumber = _pdfplumber()
    issues: list[dict[str, Any]] = []
    pages: list[PageContent] = []
    try:
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                raise invalid_input("PDF has no pages")
            if page_range:
                from dataagent_data.page_range import parse_page_range

                selected = parse_page_range(page_range, len(pdf.pages))
            else:
                selected = list(range(1, len(pdf.pages) + 1))
            for number in selected:
                page = pdf.pages[number - 1]
                page_text = page.extract_text() or ""
                lines = []
                try:
                    lines = page.extract_text_lines() or []
                except Exception:  # noqa: BLE001 - older pdfplumber fallback
                    lines = []
                blocks: list[TextBlock] = []
                cursor = 0
                if lines:
                    for line in lines:
                        text = line.get("text", "")
                        start = page_text.find(text, cursor)
                        if start < 0:
                            # The line cannot be located in the text layer. Do
                            # not fabricate a span: report it and skip the block
                            # so bbox anchors fail closed instead of pointing at
                            # unrelated characters.
                            issues.append(
                                {
                                    "code": "da01.line_not_located",
                                    "severity": "warning",
                                    "message": (
                                        f"page {number}: text line cannot be located in "
                                        f"the extracted text: {text[:80]!r}"
                                    ),
                                    "target": f"page:{number}",
                                    "suggested_action": (
                                        "check the PDF text layer or use ocr_pdf for this page"
                                    ),
                                    "retryable": False,
                                }
                            )
                            continue
                        end = start + len(text)
                        cursor = end
                        blocks.append(
                            TextBlock(
                                page=number,
                                text=text,
                                bbox=[
                                    float(line.get("x0", 0)),
                                    float(line.get("top", 0)),
                                    float(line.get("x1", 0)),
                                    float(line.get("bottom", 0)),
                                ],
                                char_start=start,
                                char_end=end,
                            )
                        )
                else:
                    blocks = [
                        TextBlock(page=number, text=page_text, bbox=None, char_start=0, char_end=len(page_text))
                    ] if page_text else []
                if not page_text.strip():
                    issues.append(
                        {
                            "code": "da01.no_text_layer",
                            "severity": "warning",
                            "message": f"page {number} has no extractable text layer",
                            "target": f"page:{number}",
                            "suggested_action": "use ocr_pdf for this page range",
                            "retryable": False,
                        }
                    )
                pages.append(
                    PageContent(
                        page=number,
                        width=float(page.width) if page.width else None,
                        height=float(page.height) if page.height else None,
                        text=page_text,
                        blocks=blocks,
                    )
                )
    except CapabilityError:
        raise
    except Exception as exc:  # noqa: BLE001 - classify, never blanket invalid_input
        message = f"cannot read PDF: {type(exc).__name__}: {exc}"
        if _is_pdf_input_error(exc):
            raise invalid_input(message) from exc
        raise execution_unknown(message) from exc
    content = DocumentContent(pages=pages)
    return content, issues
