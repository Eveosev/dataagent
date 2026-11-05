"""Source-anchor existence and value checks shared by the judgment family.

Round 4 (06 §14 item 1): every selector must be resolved against the real
source payload. A selector that cannot be resolved is *not* silently accepted;
the caller receives an explicit reason and downgrades the value to ``missing``.
"""

from __future__ import annotations

import json
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

from dataagent_contracts.core import SourceAnchor

from dataagent_data.contracts.layer import DocumentContent

# Numeric tokens with whole-word boundaries. The lookarounds deliberately
# reject a token that is adjacent to another word character or hyphen: ``-5``
# must not be carved out of ``2024-05-01`` and ``999`` must not match inside
# ``1999``. Trailing punctuation *is* allowed (``Total: 200.`` / ``200, net`` /
# JSON ``{"amount": 200, ...}``) but a following digit after a dot/comma is
# rejected so ``2024.05.01`` and ``200,00`` are not read as a bare 2024/200.
_NUMBER_TOKEN = re.compile(
    r"(?<![\w.,-])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w-])(?![.,]\d)"
)
# Surface normalisation is deliberately narrow: whitespace and currency signs
# only. Stripping ``. % / -`` used to turn ``3.5%`` into ``35`` and ``A-1`` into
# ``a1``, which made fabricated values look anchored.
_STRIPPED = set(" \t\n\r\f\v\u3000,，¥￥$")
# Sentence-final punctuation a quoted fragment may carry without changing
# the proposition it states (".", "。", "!", "?", ";", "…"). Only ever
# stripped from the *end* of a normalized condition text.
_SENTENCE_FINAL_MARKS = ".。!?;…"
_CURRENCY = "¥￥$€£ "

_INVALID_POINTER_ESCAPE = re.compile(r"~(?![01])")

# Sentinel for "this seed mapping has no value for that source revision".
_MISSING = object()


def _as_resolver(value: "DocumentContent | AnchorResolver") -> "AnchorResolver":
    return value if isinstance(value, AnchorResolver) else AnchorResolver(value)


class ResolvedAnchor:
    __slots__ = ("text", "reason")

    def __init__(self, text: str | None, reason: str) -> None:
        self.text = text
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"ResolvedAnchor(text={self.text!r}, reason={self.reason!r})"


class JsonPointerError(ValueError):
    pass


class AnchorResolver:
    """Resolve a :class:`SourceAnchor` against real source payloads.

    Call sites inject the payloads they already hold (document content, unit
    text, records, table grids). When no payload is available the resolver can
    fall back to a ``runtime`` file source by ``source_ref`` / ``source_revision``;
    if that also fails, :meth:`resolve` returns a reason instead of empty text.
    Runtime payloads are parsed and cached per ``(source_ref, source_revision)``,
    so two revisions of one file never share a parse result.
    """

    def __init__(
        self,
        content: DocumentContent | None = None,
        *,
        units: Mapping[str, str] | None = None,
        records: Sequence[Mapping[str, Any]] | None = None,
        tables: Mapping[str, Sequence[Sequence[Any]]] | None = None,
        json_documents: Mapping[str, Any] | None = None,
        workbooks: Mapping[str, Any] | None = None,
        runtime: Any | None = None,
    ) -> None:
        self.content = content
        self.units = dict(units or {})
        self.records = list(records or ())
        self.tables = dict(tables or {})
        # Seed payloads passed by the caller are keyed by the bare
        # ``source_ref`` they already hold and therefore describe exactly one
        # revision. Parsed payloads fetched from the runtime are cached per
        # ``(source_ref, revision)`` so two revisions of the same file can
        # never share a parse result.
        self.json_documents = dict(json_documents or {})
        self.workbooks = dict(workbooks or {})
        self._seed_revisions: dict[str, str] = {}
        self._json_cache: dict[tuple[str, str], Any] = {}
        self._workbook_cache: dict[tuple[str, str], Any] = {}
        self.runtime = runtime
        self._file_cache: dict[str, Any] = {}

    # -- file fallback -------------------------------------------------
    def _file_ref(self, source_ref: str, source_revision: str):
        if self.runtime is None:
            return None
        from dataagent_data import helpers

        try:
            return helpers.find_file_ref(self.runtime, source_ref, source_revision)
        except Exception:  # noqa: BLE001 - absence is a normal unresolved anchor
            return None

    def _source_bytes(self, source_ref: str, source_revision: str) -> bytes | None:
        key = f"{source_ref}@{source_revision}"
        if key not in self._file_cache:
            ref = self._file_ref(source_ref, source_revision)
            if ref is None:
                return None
            from dataagent_data import helpers

            try:
                self._file_cache[key] = helpers.read_file_ref(self.runtime, ref)
            except Exception:  # noqa: BLE001 - inaccessible source is unresolved
                self._file_cache[key] = None
        return self._file_cache[key]

    def _seeded(
        self, seeds: Mapping[str, Any], source_ref: str, source_revision: str
    ) -> Any:
        """Return a caller-supplied payload, or :data:`_MISSING`.

        A composite ``source_ref@revision`` seed is revision-exact. A bare
        ``source_ref`` seed only describes one revision: it is pinned to the
        first revision that uses it, and a second revision falls through to the
        runtime file source instead of reusing the wrong payload. Cross-revision
        callers must therefore inject the runtime (or composite keys), never a
        bare ``source_ref``.
        """

        composite = f"{source_ref}@{source_revision}"
        if composite in seeds:
            return seeds[composite]
        if source_ref not in seeds:
            return _MISSING
        pinned = self._seed_revisions.get(source_ref)
        if pinned is not None and pinned != source_revision:
            return _MISSING
        self._seed_revisions[source_ref] = source_revision
        return seeds[source_ref]

    def _json_document(self, source_ref: str, source_revision: str) -> Any | None:
        key = (source_ref, source_revision)
        if key in self._json_cache:
            return self._json_cache[key]
        seeded = self._seeded(self.json_documents, source_ref, source_revision)
        if seeded is not _MISSING:
            self._json_cache[key] = seeded
            return seeded
        payload = self._source_bytes(source_ref, source_revision)
        if payload is None:
            return None
        try:
            parsed = json.loads(payload.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        self._json_cache[key] = parsed
        return parsed

    def _workbook(self, source_ref: str, source_revision: str):
        key = (source_ref, source_revision)
        if key in self._workbook_cache:
            return self._workbook_cache[key]
        seeded = self._seeded(self.workbooks, source_ref, source_revision)
        if seeded is not _MISSING:
            self._workbook_cache[key] = seeded
            return seeded
        payload = self._source_bytes(source_ref, source_revision)
        if payload is None:
            return None
        temp_path: str | None = None
        try:
            from openpyxl import load_workbook  # local import: optional cost

            import tempfile

            handle = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            temp_path = handle.name
            try:
                handle.write(payload)
                handle.flush()
            finally:
                handle.close()
            workbook = load_workbook(temp_path, data_only=False)
        except Exception:  # noqa: BLE001 - not an xlsx source
            return None
        finally:
            # A failed load_workbook must not leave the scratch workbook behind.
            if temp_path is not None:
                Path(temp_path).unlink(missing_ok=True)
        self._workbook_cache[key] = workbook
        return workbook

    # -- selectors -----------------------------------------------------
    def resolve(self, anchor: SourceAnchor) -> ResolvedAnchor:
        selector = anchor.selector
        kind = getattr(selector, "kind", "")
        if kind in {"pdf_text_span", "pdf_bbox"}:
            return self._resolve_pdf(selector)
        if kind == "text_span":
            return self._resolve_text_span(selector, anchor)
        if kind == "json_pointer":
            return self._resolve_json_pointer(selector, anchor)
        if kind == "excel_cell":
            return self._resolve_excel_cell(selector, anchor)
        if kind == "record_key":
            return self._resolve_record_key(selector, anchor)
        return ResolvedAnchor(None, f"unsupported anchor kind: {kind or '<missing>'}")

    def _page(self, number: int):
        if self.content is None:
            return None
        try:
            return self.content.page(number)
        except KeyError:
            return None

    def _resolve_pdf(self, selector) -> ResolvedAnchor:
        page = self._page(selector.page)
        if page is None:
            return ResolvedAnchor(None, f"page {selector.page} does not exist")
        if selector.kind == "pdf_text_span":
            if selector.char_start >= len(page.text):
                return ResolvedAnchor(None, "character span starts outside the page")
            if selector.char_end > len(page.text):
                return ResolvedAnchor(None, "character span ends outside the page")
            text = page.text[selector.char_start : selector.char_end]
            if not text.strip():
                return ResolvedAnchor(None, "character span is empty")
            return ResolvedAnchor(text, "")
        x0, top, x1, bottom = selector.bbox
        if x1 <= x0 or bottom <= top:
            return ResolvedAnchor(None, "empty bounding box")
        pieces = [
            block.text
            for block in page.blocks
            if block.bbox
            and block.bbox[2] > x0
            and block.bbox[0] < x1
            and block.bbox[3] > top
            and block.bbox[1] < bottom
        ]
        text = "\n".join(pieces)
        if not text.strip():
            return ResolvedAnchor(None, "bounding box does not cover any text block")
        return ResolvedAnchor(text, "")

    def _unit_text(
        self, unit_ref: str, source_ref: str, source_revision: str
    ) -> str | None:
        """Read a unit body that is indexed to ``source_ref@source_revision``.

        A bare content digest is not evidence: it could have been produced by a
        different document (or a different revision). Only the persisted unit
        index written by ``segment_document`` authorises the read. The document
        asset id is deliberately not accepted as a unit reference.
        """

        if self.runtime is None:
            return None
        versions = getattr(self.runtime, "versions", None)
        if versions is None:
            return None
        key = f"{source_ref}@{source_revision}:{unit_ref}"
        try:
            current = versions.current("document_unit_index", key)
        except Exception:  # noqa: BLE001 - a missing index is unresolved
            return None
        if not current:
            return None
        entry = current[1]
        if not isinstance(entry, dict):
            return None
        if (
            entry.get("content_ref") != unit_ref
            or entry.get("source_ref") != source_ref
            or entry.get("source_revision") != source_revision
        ):
            return None
        store = getattr(self.runtime, "content", None)
        if store is None:
            return None
        try:
            if not store.exists(unit_ref):
                return None
            text = store.get_text(unit_ref)
        except Exception:  # noqa: BLE001 - an unreadable unit is unresolved
            return None
        self.units[unit_ref] = text
        return text

    def _resolve_text_span(self, selector, anchor: SourceAnchor) -> ResolvedAnchor:
        text = self.units.get(selector.unit_ref)
        if text is None:
            text = self._unit_text(
                selector.unit_ref, anchor.source_ref, anchor.source_revision
            )
        if text is None:
            return ResolvedAnchor(
                None,
                f"text_span unit_ref {selector.unit_ref!r} is not persisted for "
                f"{anchor.source_ref}@{anchor.source_revision}; "
                "the unit body is unavailable",
            )
        if selector.char_end <= selector.char_start:
            return ResolvedAnchor(None, "empty character span")
        if selector.char_start >= len(text):
            return ResolvedAnchor(None, "character span starts outside the unit text")
        if selector.char_end > len(text):
            return ResolvedAnchor(None, "character span ends outside the unit text")
        span = text[selector.char_start : selector.char_end]
        if not span.strip():
            return ResolvedAnchor(None, "character span is empty")
        return ResolvedAnchor(span, "")

    def _resolve_json_pointer(self, selector, anchor: SourceAnchor) -> ResolvedAnchor:
        document = self._json_document(anchor.source_ref, anchor.source_revision)
        if document is None:
            return ResolvedAnchor(
                None,
                f"JSON source {anchor.source_ref!r} is not available for pointer resolution",
            )
        try:
            value = resolve_json_pointer(document, selector.pointer)
        except JsonPointerError as exc:
            return ResolvedAnchor(None, str(exc))
        return ResolvedAnchor(_text_of(value), "")

    def _resolve_excel_cell(self, selector, anchor: SourceAnchor) -> ResolvedAnchor:
        if selector.sheet in self.tables:
            grid = self.tables[selector.sheet]
            return _grid_range_text(grid, selector.range, selector.sheet)
        workbook = self._workbook(anchor.source_ref, anchor.source_revision)
        if workbook is None:
            return ResolvedAnchor(
                None, f"workbook {anchor.source_ref!r} is not available for cell resolution"
            )
        if selector.sheet not in workbook.sheetnames:
            return ResolvedAnchor(None, f"sheet {selector.sheet!r} does not exist")
        ws = workbook[selector.sheet]
        try:
            from openpyxl.utils.cell import range_boundaries
        except Exception:  # pragma: no cover - dependency is required elsewhere
            return ResolvedAnchor(None, "openpyxl is unavailable")
        try:
            min_col, min_row, max_col, max_row = range_boundaries(selector.range)
        except Exception as exc:  # noqa: BLE001 - invalid range text
            return ResolvedAnchor(None, f"invalid cell range {selector.range!r}: {exc}")
        if min_row is None or min_col is None or max_row is None or max_col is None:
            return ResolvedAnchor(None, f"invalid cell range {selector.range!r}")
        pieces: list[str] = []
        for row in ws.iter_rows(
            min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col
        ):
            for cell in row:
                if cell.value not in (None, ""):
                    pieces.append(_text_of(cell.value))
        if not pieces:
            return ResolvedAnchor(None, f"cell range {selector.range!r} is empty")
        return ResolvedAnchor("\t".join(pieces), "")

    def _resolve_record_key(self, selector, anchor: SourceAnchor) -> ResolvedAnchor:
        field = getattr(selector, "field", None)
        if not field:
            return ResolvedAnchor(
                None,
                "record_key requires a field name; a whole-row anchor cannot "
                "substantiate a single value",
            )
        rows: Sequence[Mapping[str, Any]] = self.records
        if not rows:
            document = self._json_document(anchor.source_ref, anchor.source_revision)
            if isinstance(document, dict) and isinstance(document.get("records"), list):
                rows = document["records"]
            elif isinstance(document, list):
                rows = document
            elif isinstance(document, dict):
                rows = [document]
        if not rows:
            return ResolvedAnchor(
                None,
                f"record source {anchor.source_ref!r} is not available for key lookup",
            )
        matches = [
            row
            for row in rows
            if isinstance(row, Mapping)
            and all(row.get(key) == value for key, value in selector.keys.items())
        ]
        if not matches:
            return ResolvedAnchor(
                None, f"no record matches record_key {dict(selector.keys)!r}"
            )
        if len(matches) > 1:
            return ResolvedAnchor(
                None, f"record_key {dict(selector.keys)!r} matches multiple records"
            )
        row = matches[0]
        if field not in row:
            return ResolvedAnchor(
                None,
                f"record matching record_key {dict(selector.keys)!r} has no field {field!r}",
            )
        return ResolvedAnchor(_text_of(row[field]), "")


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    """RFC 6901 evaluation, including ``~0``/``~1`` escapes and array bounds."""

    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise JsonPointerError("JSON pointer must be empty or start with '/'")
    if _INVALID_POINTER_ESCAPE.search(pointer):
        raise JsonPointerError(f"invalid JSON pointer escape in {pointer!r}")
    current = document
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if token not in current:
                raise JsonPointerError(f"JSON pointer token {token!r} does not exist")
            current = current[token]
        elif isinstance(current, list):
            if token == "-":
                raise JsonPointerError("JSON pointer '-' has no value for reading")
            try:
                index = int(token)
            except ValueError as exc:
                raise JsonPointerError(
                    f"JSON pointer token {token!r} is not a valid array index"
                ) from exc
            if index < 0 or index >= len(current):
                raise JsonPointerError(f"array index {index} is out of range")
            current = current[index]
        else:
            raise JsonPointerError(
                f"JSON pointer cannot descend into {type(current).__name__}"
            )
    return current


def _text_of(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _grid_range_text(
    grid: Sequence[Sequence[Any]], cell_range: str, sheet: str
) -> ResolvedAnchor:
    try:
        from openpyxl.utils.cell import range_boundaries
    except Exception:  # pragma: no cover
        return ResolvedAnchor(None, "openpyxl is unavailable")
    try:
        min_col, min_row, max_col, max_row = range_boundaries(cell_range)
    except Exception as exc:  # noqa: BLE001
        return ResolvedAnchor(None, f"invalid cell range {cell_range!r}: {exc}")
    if min_row is None or min_col is None or max_row is None or max_col is None:
        return ResolvedAnchor(None, f"invalid cell range {cell_range!r}")
    pieces: list[str] = []
    for row_index in range(min_row - 1, max_row):
        if row_index >= len(grid):
            return ResolvedAnchor(
                None, f"cell range {cell_range!r} is outside sheet {sheet!r}"
            )
        row = grid[row_index]
        for col_index in range(min_col - 1, max_col):
            value = row[col_index] if col_index < len(row) else None
            if value not in (None, ""):
                pieces.append(_text_of(value))
    if not pieces:
        return ResolvedAnchor(None, f"cell range {cell_range!r} is empty")
    return ResolvedAnchor("\t".join(pieces), "")


def anchor_invalid_reason(
    content: "DocumentContent | AnchorResolver", anchor: SourceAnchor
) -> str:
    """Return why an anchor cannot be resolved (``""`` means it exists)."""

    try:
        return _as_resolver(content).resolve(anchor).reason
    except Exception as exc:  # noqa: BLE001 - fail closed, never open
        return f"anchor could not be resolved: {type(exc).__name__}: {exc}"


def _normalize_with_index(text: str) -> tuple[str, list[int]]:
    """Normalize while keeping a map from normalized position to source index."""

    chars: list[str] = []
    source_index: list[int] = []
    for position, char in enumerate(text):
        if char in _STRIPPED:
            continue
        for lowered in char.lower():
            chars.append(lowered)
            source_index.append(position)
    return "".join(chars), source_index


def normalize_text(text: str) -> str:
    return _normalize_with_index(text)[0]


def _match_with_index(text: str) -> tuple[str, list[int]]:
    """Normalize for whole-token matching while keeping token boundaries.

    ``normalize_text`` removes whitespace, which is right for compact currency
    comparisons but wrong for a word-boundary check: ``"Acme Inc."`` and
    ``"Acme"`` would both collapse to ``acme...`` and a fragment could look
    complete. Here whitespace is collapsed to one separator, thousands commas
    are removed, and other commas become separators. Punctuation (``.``,
    ``-``, ``%``, quotes) is preserved so it can still bound a token.
    """

    chars: list[str] = []
    source_index: list[int] = []
    for position, char in enumerate(text):
        if char in "¥￥$€£":
            continue
        if char in ",，":
            previous_is_digit = position > 0 and text[position - 1].isdigit()
            next_is_digit = position + 1 < len(text) and text[position + 1].isdigit()
            if previous_is_digit and next_is_digit:
                continue
            char = " "
        if char.isspace():
            char = " "
        for lowered in char.lower():
            if lowered == " " and chars and chars[-1] == " ":
                continue
            chars.append(lowered)
            source_index.append(position)
    while chars and chars[-1] == " ":
        chars.pop()
        source_index.pop()
    return "".join(chars), source_index


def _match_text(text: str) -> str:
    return _match_with_index(text)[0]


def _is_token_char(char: str) -> bool:
    return bool(char) and (char.isalnum() or char == "_")


def _whole_token_index(haystack: str, needle: str, start: int = 0) -> int:
    """Index of ``needle`` in ``haystack`` where both ends are token boundaries."""

    if not needle:
        return -1
    index = haystack.find(needle, start)
    while index >= 0:
        before = haystack[index - 1] if index else ""
        after_index = index + len(needle)
        after = haystack[after_index] if after_index < len(haystack) else ""
        if not _is_token_char(before) and not _is_token_char(after):
            return index
        index = haystack.find(needle, index + 1)
    return -1


def _as_decimal(value: object) -> Decimal | None:
    """Return a finite Decimal for numeric values, else ``None`` (text matching)."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, float):
        return Decimal(str(value)) if math.isfinite(value) else None
    if isinstance(value, str):
        text = value.strip()
        for symbol in _CURRENCY:
            text = text.replace(symbol, "")
        text = text.replace(",", "")
        if not text:
            return None
        try:
            parsed = Decimal(text)
        except InvalidOperation:
            return None
        return parsed if parsed.is_finite() else None
    return None


def _decimal_tokens(text: str) -> list[Decimal]:
    tokens: list[Decimal] = []
    for raw in _NUMBER_TOKEN.findall(text):
        try:
            tokens.append(Decimal(raw.replace(",", "")))
        except InvalidOperation:  # pragma: no cover - regex only yields digits
            continue
    return tokens


def find_text_span(content: DocumentContent, needle: str):
    """Locate a value in page text; returns (page, start, end) or None.

    Matching is whole-token: a short string must not be relocated onto a longer
    token (``"Acm"`` is not a match for ``"Acme"``). Thousands separators and
    whitespace differences are still tolerated, matching the value-level check.
    """

    if not needle.strip():
        return None
    normalized_needle = _match_text(needle)
    if not normalized_needle:
        return None
    for page in content.pages:
        haystack, source_index = _match_with_index(page.text)
        index = _whole_token_index(haystack, normalized_needle)
        if index < 0:
            continue
        start = source_index[index]
        end = source_index[index + len(normalized_needle) - 1] + 1
        return page.page, start, end
    return None


def find_value_span(
    content: DocumentContent, value: object
) -> tuple[int, int, int] | None:
    """Locate a value as a whole token; numeric values match by Decimal equality.

    The numeric tokenizer excludes date fragments (``-05`` in ``2024-05-01``)
    and substrings (``999`` inside ``1999``).
    """

    number = _as_decimal(value)
    if number is not None:
        for page in content.pages:
            for match in _NUMBER_TOKEN.finditer(page.text):
                try:
                    token = Decimal(match.group(0).replace(",", ""))
                except InvalidOperation:  # pragma: no cover - regex only yields digits
                    continue
                if token == number:
                    return page.page, match.start(), match.end()
        return None
    return find_text_span(content, str(value))


def anchor_span_text(
    content: "DocumentContent | AnchorResolver", anchor: SourceAnchor
) -> str | None:
    """Text covered by an anchor, or ``None`` when it cannot be resolved."""

    resolved = _as_resolver(content).resolve(anchor)
    return resolved.text if not resolved.reason else None


def anchor_value_mismatch(
    content: "DocumentContent | AnchorResolver", anchor: SourceAnchor, value: object
) -> str:
    """Return a reason when the anchored text cannot support ``value``."""

    resolved = _as_resolver(content).resolve(anchor)
    if resolved.reason:
        return resolved.reason
    span = resolved.text
    if span is None:
        return "anchor did not resolve to source text"
    if value is None:
        return "value is None and cannot be supported by an anchor"
    if not span.strip():
        return "anchored text is empty"
    number = _as_decimal(value)
    if number is not None:
        if number not in _decimal_tokens(span):
            return f"anchored text {span[:40]!r} does not contain the number {value!r}"
        return ""
    needle = _match_text(str(value))
    if not needle:
        return "value is empty and cannot be supported by an anchor"
    # Whole-token match, not a raw substring: ``"Acm"`` and ``"cme"`` are not
    # grounded by ``"Acme Inc."`` even though they occur inside it (DA02.12.1/
    # DA02.12.3; r5-plan item 2).
    if _whole_token_index(_match_text(span), needle) < 0:
        return f"anchored text {span[:40]!r} does not contain the value {value!r}"
    return ""


# Content words that carry no discriminative meaning for grounding a rule
# condition. Kept deliberately small: the coverage threshold below tolerates
# legitimate paraphrases, not unrelated sentences.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "not", "of", "to", "in", "on", "at",
        "by", "for", "with", "from", "as", "is", "are", "was", "were", "be",
        "been", "being", "must", "shall", "should", "will", "would", "can",
        "could", "may", "might", "if", "when", "then", "than", "that", "this",
        "these", "those", "it", "its", "their", "there", "which", "who",
        "above", "below", "least", "more", "less", "all", "any", "each",
    }
)
_WORD_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
# Negation markers are checked on the raw tokens, not the filtered content
# tokens: a dropped negation reverses the meaning of a clause and must never be
# tolerated as a "paraphrase" (P0 rule-condition grounding).
# Round 12 (reviewer F1): the English side had the same silent reversal the
# Chinese rounds 7-11 removed. "Expenses should avoid exceeding 5000 CNY"
# scopes the comparison exactly like "避免超过5000元", but "avoid" was not a
# negator and the bare "exceeding" pattern read an upper bound, so the
# reversed condition was accepted. English preventive verbs now invert the
# comparison they scope over and count as negation for polarity; an
# unreadable multi-verb/negated scope fails closed instead of guessing.
_EN_PREVENTIVE_TOKENS = frozenset(
    {
        "avoid", "avoids", "avoided", "avoiding",
        "prevent", "prevents", "prevented", "preventing",
        "refrain", "refrains", "refrained", "refraining",
        "prohibit", "prohibits", "prohibited", "prohibiting",
        "forbid", "forbids", "forbidden", "forbidding",
        "ban", "bans", "banned", "banning",
        "bar", "bars", "barred", "barring",
        "stop", "stops", "stopped", "stopping",
        "guard", "protect",
    }
)
_NEGATION = frozenset(
    {"not", "no", "never", "without", "none", "neither", "nor", "exclude", "except", "unless"}
)
# Verb forms, not stems: "avoidance" / "prevention" are nouns and do not scope
# a comparison ("avoidance costs exceed 5000" stays a plain upper bound).
_EN_PREVENTIVE_PATTERN = re.compile(
    r"\b(?:"
    r"avoid(?:s|ed|ing)?|"
    r"prevent(?:s|ed|ing)?|"
    r"refrain(?:s|ed|ing)?(?:\s+from)?|"
    r"prohibit(?:s|ed|ing)?|"
    r"forbid(?:s|den|ding)?|"
    r"guard(?:s|ed|ing)?\s+against|"
    r"protect(?:s|ed|ing)?\s+against"
    r")\b",
    re.I,
)
# "banned/barred/stopped from" is a preventive prefix, but the bare verbs are
# also nouns ("bar costs exceed 5000"). Only the passive ``... from`` form is
# read in front of a comparison; the postposed passive forms stay in
# ``_EN_POSTPOSED_PREVENTIVE``.
_EN_PASSIVE_PREVENTIVE_PATTERN = re.compile(
    r"\b(?:banned|barred|stopped)\s+from\b",
    re.I,
)
# A postposed comment ("expenses exceeding 5000 should be avoided") scopes the
# comparison from the right. Only a passive/relative construction is read;
# an unrelated "avoid" after a comma ("..., avoid delay") must not invert.
_EN_POSTPOSED_PREVENTIVE = re.compile(
    r"\b(?:should|must|shall|is|are|was|were|will|would|can|could|may|might|"
    r"needs?\s+to|has\s+to|have\s+to|to\s+be|be)\s+"
    r"(?P<neg>not\s+)?(?:be\s+)?"
    r"(?:avoided|prevented|prohibited|forbidden|banned|barred|stopped)\b",
    re.I,
)
_EN_NEGATOR_TOKENS = frozenset(
    {"not", "no", "never", "without", "none", "neither", "nor"}
)
_EN_SENTENCE_BOUNDARIES = frozenset(".!?\n")
_EN_CLAUSE_BOUNDARIES = frozenset(".!?;,\n")

# Comparison direction is semantic, not lexical: "above"/"more than"/"at least"
# bound a value from below, while "below"/"less than"/"at most" bound it from
# above. These words are stopwords for the *coverage* check (they carry no
# domain meaning) but the direction itself must still be compared -- otherwise
# "claims below 5000 CNY" is accepted as a paraphrase of "claims above 5000
# CNY" because the number and every content word match (P0, r4-review #1).
# Each pattern captures the number it bounds so the comparison is checked as a
# (direction, number, inclusive) triple: in an anchor that states several
# thresholds, a reversed condition cannot borrow the other clause's direction,
# and an inclusivity change ("above 5000" vs "at least 5000") cannot borrow the
# other clause's boundary (reviewer F2). Patterns require a number on the
# bound side so that spatial uses of "under" or "over" do not count as
# comparisons.
_NUMBER_CAPTURE = r"(?P<number>\d[\d,]*(?:\.\d+)?)"
# Strict bounds state "<"/">" exactly ("above", "超过"): the threshold itself
# is excluded. Negating a strict bound yields the inclusive complement
# ("不得超过5000" is <= 5000), which is why the negated and preventive groups
# below are inclusive and why an inverted English bound is marked inclusive.
_STRICT_COMPARISON_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?<![\w.])(?:above|over|greater\s+than|more\s+than|exceed(?:s|ing)?|"
            r"in\s+excess\s+of)\s+(?:[A-Za-z]{2,4}\s+)?[¥￥$€£]?\s*"
            + _NUMBER_CAPTURE,
            re.I,
        ),
        "upper",
    ),
    (
        re.compile(
            r"(?<![\w.])(?:below|under|less\s+than|fewer\s+than|lower\s+than)\s+"
            r"(?:[A-Za-z]{2,4}\s+)?[¥￥$€£]?\s*"
            + _NUMBER_CAPTURE,
            re.I,
        ),
        "lower",
    ),
    (
        re.compile(
            r"(?<![\w.])(?:exactly|equal\s+to|equals)\s+(?:[A-Za-z]{2,4}\s+)?"
            r"[¥￥$€£]?\s*" + _NUMBER_CAPTURE,
            re.I,
        ),
        "equal",
    ),
    (
        re.compile(
            r"(?:超过|高于|大于|多于|超出)\s*(?:人民币|元)?\s*" + _NUMBER_CAPTURE
        ),
        "upper",
    ),
    (
        re.compile(r"(?:低于|小于|少于)\s*(?:人民币|元)?\s*" + _NUMBER_CAPTURE),
        "lower",
    ),
    (re.compile(r"(?<![<>=!])>\s*[¥￥$€£]?\s*" + _NUMBER_CAPTURE), "upper"),
    (re.compile(r"(?<![<>=!])<\s*[¥￥$€£]?\s*" + _NUMBER_CAPTURE), "lower"),
)
# Inclusive bounds state "<="/">=" ("at least", "不低于"): the threshold itself
# is included. These are scanned *before* the strict patterns and blanked out,
# so "no less than 5000" never also reads as a strict "less than 5000" bound.
_INCLUSIVE_COMPARISON_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?<![\w.])(?:at\s+least|no\s+less\s+than|not\s+less\s+than|"
            r"minimum(?:\s+of)?|not\s+below)\s+(?:[A-Za-z]{2,4}\s+)?[¥￥$€£]?\s*"
            + _NUMBER_CAPTURE,
            re.I,
        ),
        "upper",
    ),
    (
        re.compile(
            r"(?<![\w.])(?:at\s+most|no\s+more\s+than|not\s+more\s+than|"
            r"maximum(?:\s+of)?|up\s+to|within|not\s+exceeding|no\s+greater\s+than)\s+"
            r"(?:[A-Za-z]{2,4}\s+)?[¥￥$€£]?\s*"
            + _NUMBER_CAPTURE,
            re.I,
        ),
        "lower",
    ),
    # Number-first forms: "5000 or more", "5000 and below", "5000 以上". The
    # trailing lookahead stops "5000 and below 100" from being read as a bound
    # on 5000; there "below" belongs to its own 100.
    (
        re.compile(
            _NUMBER_CAPTURE + r"\s*(?:[A-Za-z]{2,4}\s+)?(?:or\s+(?:more|above|greater)|"
            r"and\s+(?:above|over))\b"
            r"(?!\s*(?:[A-Za-z]{2,4}\s+)?[¥￥$€£]?\s*\d)",
            re.I,
        ),
        "upper",
    ),
    (
        re.compile(
            _NUMBER_CAPTURE + r"\s*(?:[A-Za-z]{2,4}\s+)?(?:or\s+(?:less|fewer|below)|"
            r"and\s+(?:below|under))\b"
            r"(?!\s*(?:[A-Za-z]{2,4}\s+)?[¥￥$€£]?\s*\d)",
            re.I,
        ),
        "lower",
    ),
    (
        re.compile(
            r"(?:不低于|不少于|至少)\s*(?:人民币|元)?\s*" + _NUMBER_CAPTURE
        ),
        "upper",
    ),
    (
        re.compile(
            r"(?:人民币|元)?\s*" + _NUMBER_CAPTURE + r"\s*(?:人民币|元)?\s*(?:及以上|以上)"
        ),
        "upper",
    ),
    (
        re.compile(
            r"(?:不超过|不高于|至多|最多)\s*(?:人民币|元)?\s*" + _NUMBER_CAPTURE
        ),
        "lower",
    ),
    (
        re.compile(
            r"(?:人民币|元)?\s*"
            + _NUMBER_CAPTURE
            + r"\s*(?:人民币|元)?\s*(?:及以下|以下|以内)"
        ),
        "lower",
    ),
    (re.compile(r">=\s*[¥￥$€£]?\s*" + _NUMBER_CAPTURE), "upper"),
    (re.compile(r"<=\s*[¥￥$€£]?\s*" + _NUMBER_CAPTURE), "lower"),
)
# Every pattern that states any comparison, used by the negation/polarity
# scan. Order is irrelevant there; each match is inspected on its own.
_COMPARISON_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    _STRICT_COMPARISON_PATTERNS + _INCLUSIVE_COMPARISON_PATTERNS
)


# Chinese negation reverses the direction, but the negated phrase *contains*
# the bare direction word ("不低于" contains "低于", "不超过" contains "超过").
# If both patterns run on the same text, one anchor states both ("upper", 5000)
# and ("lower", 5000), so a reversed condition matches whichever direction it
# claims. These patterns run first and the matched span is blanked out, so the
# bare patterns below never see a negated phrase. Prefixes are spelled out
# because a Chinese negator is not always adjacent to the direction word
# ("不得超过", "没有超过", "不得低于"), and "允许"/"准"/"许" may sit between
# "不" and the comparison ("不允许超过", "不准超过").
_CN_NEGATION_PREFIX = (
    r"(?:不允许|不准|不许|禁止|严禁|不应当|不应|不得|不能|不可|"
    r"未曾|从未|没有|没|未|不|勿)"
)
# Negated and preventive comparisons are the inclusive complement of the
# bare direction word: "不得超过5000元" states <= 5000 (reviewer F2), so a
# condition phrased "低于5000元" (< 5000) must not ground against it. The
# lexical "< number" forms ("未达到5000元") stay strict: not reaching 5000
# really is < 5000.
_CN_NEGATED_BOUNDS: tuple[tuple[re.Pattern[str], str, bool], ...] = (
    (
        re.compile(
            _CN_NEGATION_PREFIX
            + r"\s*(?:超过|高于|大于|多于|超出)\s*(?:人民币|元)?\s*"
            + _NUMBER_CAPTURE
        ),
        "lower",
        True,
    ),
    (
        re.compile(
            _CN_NEGATION_PREFIX
            + r"\s*(?:低于|小于|少于)\s*(?:人民币|元)?\s*"
            + _NUMBER_CAPTURE
        ),
        "upper",
        True,
    ),
    # Lexical "< number" forms that do not contain a direction word at all.
    (
        re.compile(
            r"(?:没有达到|没达到|未达到|达不到|不达到|未满|不满|不足|不到|"
            r"未达|不达|未及|不及)\s*(?:人民币|元)?\s*" + _NUMBER_CAPTURE
        ),
        "lower",
        False,
    ),
)


# ``_CN_NEGATED_BOUNDS`` is a finite list, and an adverb can sit between the
# negator and the direction word ("未明显超过", "不得擅自低于"). Those phrases
# escape the negation patterns; the bare patterns then read the anchor as a
# *positive* bound and a reversed condition is accepted silently -- the same
# failure the round 7 split fixed for adjacent forms. Rather than extending the
# enumeration forever, an unconsumed negator near a direction word makes the
# comparison scope ambiguous: the bound is dropped and the anchor is treated as
# unsupportable (fail-closed; plan §5 step 3 / §10 item 2).
#
# Round 9 (B2): preventive verbs invert the comparison they scope over as well
# ("避免超过5000元" states <= 5000, "防止低于5000元" states >= 5000). The verb
# may be separated from the direction word by the object it protects
# ("应防止费用超过5000元"), so the gap is bounded by the clause boundary and a
# short object window. A negator inside that gap is deliberately *not* consumed
# here; the ambiguity scan fails the double negation closed instead of guessing.
_PREVENTIVE_VERBS = (
    "防止", "防范", "严防", "谨防", "预防", "提防", "防备", "慎防",
    "以免", "以防", "避免", "避开", "避让", "避掉", "躲避", "躲开",
    "杜绝", "切忌", "力戒", "戒除", "戒掉", "戒绝", "戒断",
    "阻遏", "阻止", "制止", "遏制", "抑制", "抵制", "劝阻",
    "遏止", "抑止",
)
# Control/limit verbs ("控制", "限制") and attention verbs ("警惕") scope a
# comparison but do not state which way they invert it: "限制费用低于5000元"
# is <= 5000, the *same* direction as the bare word, while "避免低于5000元" is
# >= 5000. Parsing those as inverted would reintroduce the silent reversal, so
# they only make the scope unreadable (fail-closed) and never contribute a
# bound. They stay in the marker set so the check remains open-ended.
_PREVENTIVE_MARKERS = _PREVENTIVE_VERBS + (
    "控制", "限制", "约束", "管制", "节制", "管控", "严控", "把控",
    "克制", "压制", "防控", "消除", "根除",
    "警惕", "警觉", "戒备", "当心", "留意",
)
# "预防费用", "防范成本", "防备开支" are noun compounds meaning "prevention
# cost", not a verb scoping the comparison. When one of these verbs is not in a
# verbal context (a modal/purpose marker before it), reading it as preventive
# would flip a plain "prevention costs exceed 5000" anchor into a <= 5000
# bound -- a new silent reversal. Such a candidate is not consumed; the
# ambiguity scan then refuses it instead of guessing.
_PREVENTIVE_NOUN_RISK_VERBS = frozenset({"预防", "防范", "防备"})
_VERBAL_CONTEXT_SEARCH = re.compile(
    r"(?:应当|应该|应|须|必须|需要|需|务必|加强|做好|严格|切实|大力)"
    r"(?:严格|切实|认真|全面|大力)?$"
)
# Longest first: "防范"/"防止" must win over a shorter synonym, and the
# bound pattern below is a plain alternation (no version-dependent ordering).
_CN_PREVENTIVE_PREFIX = "(?:" + "|".join(
    sorted(_PREVENTIVE_VERBS, key=len, reverse=True)
) + ")"
_CN_PREVENTIVE_PREFIX_RE = re.compile(_CN_PREVENTIVE_PREFIX)
_CN_PREVENTIVE_GAP = r"[^。！？；，、,.!?;\n不未没无非]{0,20}?"
_CN_PREVENTIVE_BOUNDS: tuple[tuple[re.Pattern[str], str, bool], ...] = (
    (
        re.compile(
            _CN_PREVENTIVE_PREFIX
            + _CN_PREVENTIVE_GAP
            + r"(?:超过|高于|大于|多于|超出)\s*(?:人民币|元)?\s*"
            + _NUMBER_CAPTURE
        ),
        "lower",
        True,
    ),
    (
        re.compile(
            _CN_PREVENTIVE_PREFIX
            + _CN_PREVENTIVE_GAP
            + r"(?:低于|小于|少于)\s*(?:人民币|元)?\s*"
            + _NUMBER_CAPTURE
        ),
        "upper",
        True,
    ),
    # Lexical "< number" forms under a preventive verb: "避免不足5000元"
    # states >= 5000, the reverse of the bare lexical form.
    (
        re.compile(
            _CN_PREVENTIVE_PREFIX
            + _CN_PREVENTIVE_GAP
            + r"(?:不足|不到|未达到|达不到|未满|不满)\s*(?:人民币|元)?\s*"
            + _NUMBER_CAPTURE
        ),
        "upper",
        True,
    ),
)


_NEGATION_CHARS = frozenset("不未没无非勿禁否")
# Round 10 (B2): a closed verb list is not enough. "防范" (a synonym of
# "防止") was missing, and synonyms the list has never seen ("根绝", "回避")
# read as a bare direction word and accepted the reversed condition. A Chinese
# preventive verb is almost always a two-character compound whose second
# character is one of these morphemes; matching that shape keeps the check
# open-ended while the explicit list above stays authoritative for parsing.
_PREVENTIVE_MORPHEMES = "防避忌惕戒遏阻绝"
# Round 11 (B2): the round 10 shape needs a leading Han character, so it is
# blind to a preventive verb at the very start of a clause -- "避开超过5000元"
# (no "应"/"须" in front) matched no marker and read as a bare "upper" bound,
# accepting the reversed condition. The explicit list now parses the common
# clause-initial synonyms; this second shape keeps the fail-closed check
# open-ended for the ones it has never seen ("阻断", "阻挠"), without letting
# nouns that merely begin with a preventive morpheme ("防火费用") poison a
# plain threshold.
_PREVENTIVE_INITIAL_MORPHEMES = "防避戒遏阻"
_PREVENTIVE_SCOPE_SEARCH = re.compile(
    "(?:"
    + "|".join(sorted(_PREVENTIVE_MARKERS, key=len, reverse=True))
    + "|[\u4e00-\u9fff]["
    + _PREVENTIVE_MORPHEMES
    + "]"
    + "|(?<![\u4e00-\u9fff])["
    + _PREVENTIVE_INITIAL_MORPHEMES
    + r"][\u4e00-\u9fff]"
    + ")"
)
# Nouns that contain a preventive morpheme without scoping a comparison
# ("消防费用超过5000元" must stay a plain threshold). The round 11 clause-start
# shape can see the first two characters of a longer noun, so the common
# noun compounds that begin with 防/避/戒/遏/阻 are listed here too
# ("防火费用", "避险成本", "戒烟费用").
_PREVENTIVE_NOUNS = frozenset(
    {
        "消防", "国防", "边防", "海防", "城防",
        "人防", "空防", "安防", "技防", "物防",
        # 防: protection/fire/epidemic/... nouns and their modifiers.
        "防火", "防灾", "防疫", "防汛", "防洪", "防凌", "防台", "防震",
        "防冻", "防雾", "防霾", "防噪", "防务", "防线", "防护", "防爆",
        "防盗", "防潮", "防尘", "防毒", "防伪", "防滑", "防晒", "防寒",
        "防暑", "防雷", "防水", "防风", "防沙", "防弹", "防化", "防核",
        "防虫", "防病", "防腐", "防锈", "防漏", "防蛀", "防旱", "防涝",
        "防艾", "防癌", "防贫", "防返", "防走", "防拐", "防骗", "防诈",
        "防溺", "防近", "防沉", "防疲", "防作", "防污", "防辐", "防静",
        "防眩", "防抱", "防坠", "防渗", "防泄", "防跌", "防坍", "防泥",
        # 避: avoidance nouns ("避税", "避险") that do not scope a comparison.
        "避税", "避险", "避难", "避暑", "避寒", "避雨", "避风", "避孕",
        "避雷", "避嫌", "避讳", "避世", "避债", "避震", "避灾", "避乱",
        # 戒: abstention nouns and objects.
        "戒指", "戒烟", "戒酒", "戒毒", "戒赌", "戒严", "戒律", "戒心",
        "戒尺", "戒坛", "戒期", "戒疤", "戒骄", "戒躁",
        # 阻: physical nouns.
        "阻抗", "阻尼", "阻燃", "阻力", "阻值", "阻容", "阻垢", "阻聚",
    }
)
# Punctuation before the scan belongs to an earlier clause; a negator there
# ("不适用；超过5000元...") must not poison this comparison.
_CLAUSE_BOUNDARIES = frozenset("。！？；，、,.!?;\n")
# A preventive verb *after* the comparison ("费用超过5000元，应避免") still
# scopes it. A comma or semicolon continues the same statement, so the forward
# scan crosses both but stops at a sentence-ending mark.
_SENTENCE_BOUNDARIES = frozenset("。！？\n")
# Round 9 (B3): morphemes that merely *contain* a negation character without
# negating the comparison ("不含税金额", "未经批准"). They are blanked (spaces,
# so offsets survive) before the scope scan, so a verbatim condition such as
# "不含税金额超过5000元" stays grounded instead of being rejected as ambiguous.
# Idioms that embed a preventive verb ("不可避免超过") are blanked for the same
# reason: they assert the comparison, they do not negate it.
_LEXICAL_NEGATION_PREFIXES = (
    "不含", "未含", "未税", "未经",
    "不可避免", "无法避免", "无论", "不论", "不管",
    "不仅", "不但", "不同", "无形", "无息",
)


def _blank(text: str, start: int, end: int) -> str:
    return text[:start] + " " * (end - start) + text[end:]


def _strip_lexical_negations(text: str) -> str:
    """Blank morphemes that look negative but do not negate the comparison."""

    for prefix in _LEXICAL_NEGATION_PREFIXES:
        index = text.find(prefix)
        while index >= 0:
            text = _blank(text, index, index + len(prefix))
            index = text.find(prefix, index + len(prefix))
    return text


def _quote_cuts_a_negated_prefix(span: str, needle: str) -> bool:
    """Whether every occurrence of ``needle`` starts right after a negator.

    Chinese has no word delimiters, so an exact-substring quote can start in
    the middle of a token. Cutting the 不 off "不含税金额" turns "excluding
    tax" into "including tax" -- the silent weakening B3 removed at the scope
    scan, moved into the quote instead. A quote whose only occurrences begin
    immediately after a negation character is rejected; a clean occurrence
    (``"超过5000元"`` in the same anchor) is still accepted.
    """

    normalized_span, source_index = _normalize_with_index(span)
    position = normalized_span.find(needle)
    if position < 0:
        return False
    while position >= 0:
        if position == 0 or span[source_index[position] - 1] not in _NEGATION_CHARS:
            return False
        position = normalized_span.find(needle, position + 1)
    return True


def _has_preventive_scope(text: str) -> bool:
    """Whether ``text`` contains a preventive verb that scopes a comparison.

    The explicit verb list handles parsing. The morphological fallback keeps
    the fail-closed check open-ended: a synonym outside the list ("根绝",
    "回避") still marks the comparison ambiguous instead of being read as a
    bare direction word. Known nouns ("消防", "国防") are exempt because they do
    not scope the comparison.
    """

    return any(
        match.group(0) not in _PREVENTIVE_NOUNS
        for match in _PREVENTIVE_SCOPE_SEARCH.finditer(text)
    )


def _negation_scope_is_ambiguous(text: str, start: int, end: int) -> bool:
    """Whether the comparison ``text[start:end]`` has an unreadable scope.

    ``text`` is the *remaining* text after negated and preventive phrases are
    blanked, so a phrase that was already consumed is a space and is not
    reported twice. The backward scan runs to the nearest clause boundary
    rather than a fixed character count: an insertion can be longer than any
    constant ("不得以任何形式超过", "不得明显不足"), and a fixed window only
    moves the enumeration boundary one level up (round 9 / B1). A negator in an
    earlier clause is not considered.

    A preventive verb that survived -- before the comparison ("应防范费用
    超过5000元") or after it ("费用超过5000元应避免", "超过5000元的费用应
    避免") -- makes the direction unreadable too: the bound patterns could not
    consume it, so guessing the bare direction is exactly the silent reversal
    these rounds remove. The forward scan is open-ended (a synonym outside the
    list still matches the morphology rule) and crosses commas, because a
    postposed comment belongs to the same statement.
    """

    clause_start = start
    while clause_start > 0 and text[clause_start - 1] not in _CLAUSE_BOUNDARIES:
        clause_start -= 1
    prefix = text[clause_start:start]
    if any(char in _NEGATION_CHARS for char in prefix):
        return True
    if _has_preventive_scope(prefix):
        return True
    sentence_end = end
    while (
        sentence_end < len(text)
        and text[sentence_end] not in _SENTENCE_BOUNDARIES
    ):
        sentence_end += 1
    return _has_preventive_scope(text[end:sentence_end])


def _preventive_match_is_nominal(text: str, start: int) -> bool:
    """Whether a noun-risk preventive verb at ``start`` is a noun compound."""

    if text[start : start + 2] not in _PREVENTIVE_NOUN_RISK_VERBS:
        return False
    clause_start = start
    while clause_start > 0 and text[clause_start - 1] not in _CLAUSE_BOUNDARIES:
        clause_start -= 1
    return _VERBAL_CONTEXT_SEARCH.search(text[clause_start:start]) is None


def _scope_has_another_preventive(text: str, skip_until: int) -> bool:
    """Whether ``text`` scopes the comparison again after ``skip_until``.

    Two preventive verbs in one scope ("避免避开超过5000元") invert the
    comparison twice; reading only the first one would silently reverse the
    direction. A second verb that is a noun compound ("避免防范费用超过") does
    not invert anything, so it is not counted. The caller leaves a double
    scope to the ambiguity scan instead of guessing (round 11).
    """

    for match in _PREVENTIVE_SCOPE_SEARCH.finditer(text):
        if match.start() < skip_until:
            continue
        if match.group(0) in _PREVENTIVE_NOUNS:
            continue
        if _preventive_match_is_nominal(text, match.start()):
            continue
        return True
    return False


def _english_negator_present(text: str) -> bool:
    """Whether an English negator token (not a preventive verb) occurs."""

    return any(
        match.group(0).lower() in _EN_NEGATOR_TOKENS
        for match in _WORD_TOKEN.finditer(text)
    )


def _english_preventive_scope(text: str, start: int, end: int) -> str:
    """How an English preventive verb scopes the comparison at ``text[start:end]``.

    Returns ``"invert"`` when exactly one readable preventive verb scopes the
    comparison, ``"ambiguous"`` when the scope reads two of them (double
    inversion) or combines one with a negator, and ``""`` when no preventive
    verb is in scope. The backward scan stops at a comma/semicolon (English
    clauses), while the forward scan stops at the sentence end and only accepts
    a passive/relative comment ("should be avoided", "is prohibited"); an
    unrelated "avoid" after a comma ("..., avoid delay") must not invert a
    plain threshold.
    """

    clause_start = start
    while clause_start > 0 and text[clause_start - 1] not in _EN_CLAUSE_BOUNDARIES:
        clause_start -= 1
    prefix = text[clause_start:start]
    prefix_verbs = list(_EN_PREVENTIVE_PATTERN.finditer(prefix)) + list(
        _EN_PASSIVE_PREVENTIVE_PATTERN.finditer(prefix)
    )
    if len(prefix_verbs) > 1:
        return "ambiguous"
    if prefix_verbs and _english_negator_present(prefix):
        return "ambiguous"
    sentence_end = end
    while (
        sentence_end < len(text)
        and text[sentence_end] not in _EN_SENTENCE_BOUNDARIES
    ):
        sentence_end += 1
    suffix_match = _EN_POSTPOSED_PREVENTIVE.search(text[end:sentence_end])
    if prefix_verbs and suffix_match is not None:
        return "ambiguous"
    if suffix_match is not None:
        if suffix_match.group("neg"):
            return "ambiguous"
        return "invert"
    return "invert" if prefix_verbs else ""


def _invert_direction(direction: str) -> str:
    if direction == "upper":
        return "lower"
    if direction == "lower":
        return "upper"
    return direction


def _comparison_analysis(text: str) -> tuple[set[tuple[str, Decimal, bool]], bool]:
    """(direction, number, inclusive) triples stated by ``text`` plus an
    ambiguity flag.

    Negated Chinese comparisons are consumed before the bare direction
    patterns, so ``"不低于5000元"`` states exactly one bound (>= 5000) instead
    of also exporting ``("lower", 5000)``. Without that split, a condition that
    claims the opposite direction (``"低于5000元"``) intersects the anchor's
    bound set and is silently accepted (round 7; plan §5 step 3 / §10 item 2).
    Preventive verbs are consumed the same way as negations (round 9 / B2). A
    direction word with an unconsumed negator in its clause yields no bound and
    ``ambiguous=True``; callers must reject rather than guess (rounds 8-9).

    Inclusivity is part of the bound (reviewer F2): ``"above 5000"`` and
    ``"at least 5000"`` state different boundaries, so a paraphrase may not
    swap them. Negating a strict comparison yields the inclusive complement,
    which is why the negated/preventive groups and inverted English bounds are
    always inclusive. Inclusive phrases are consumed before the strict ones so
    ``"no less than 5000"`` never also exports a strict ``< 5000``.
    """

    bounds: set[tuple[str, Decimal, bool]] = set()
    ambiguous = False
    remaining = _strip_lexical_negations(text)
    # Consumed phrases are collected first and applied left to right, blanking
    # each span before the next one is scanned. Order matters: a sentence with
    # two thresholds ("不低于5000元且不超过10000元") must not let the second
    # one see the first one's negator through the clause scan (round 9 / B1).
    candidates: list[tuple[int, int, str, str, bool]] = []
    for pattern, direction, inclusive in _CN_NEGATED_BOUNDS:
        for match in pattern.finditer(remaining):
            candidates.append(
                (match.start(), match.end(), direction, match.group("number"), inclusive)
            )
    for pattern, direction, inclusive in _CN_PREVENTIVE_BOUNDS:
        for match in pattern.finditer(remaining):
            if _preventive_match_is_nominal(remaining, match.start()):
                continue
            prefix_match = _CN_PREVENTIVE_PREFIX_RE.match(remaining, match.start())
            if prefix_match is not None and _scope_has_another_preventive(
                remaining, prefix_match.end()
            ):
                # Two preventive verbs in one scope ("避免避开超过5000元")
                # invert twice. Leave the bound unconsumed; the bare direction
                # pattern below then trips the ambiguity scan (fail-closed).
                continue
            candidates.append(
                (match.start(), match.end(), direction, match.group("number"), inclusive)
            )
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    consumed_until = 0
    for start, end, direction, raw, inclusive in candidates:
        if start < consumed_until:  # already owned by an earlier, longer phrase
            continue
        if _negation_scope_is_ambiguous(remaining, start, end):
            # A second negator in front of a consumed phrase flips it again
            # ("并未明显不足5000元"); the same fail-closed rule must cover the
            # lexical forms too, not only the bare direction words (round 9).
            ambiguous = True
        else:
            try:
                number = Decimal(raw.replace(",", ""))
            except InvalidOperation:  # pragma: no cover - regex only yields digits
                number = None
            if number is not None:
                bounds.add((direction, number, inclusive))
        remaining = _blank(remaining, start, end)
        consumed_until = end

    def _bare_pass(patterns, default_inclusive: bool) -> None:
        nonlocal remaining, ambiguous
        found: list[tuple[re.Match[str], str]] = []
        for pattern, direction in patterns:
            found.extend((match, direction) for match in pattern.finditer(remaining))
        found.sort(key=lambda item: (item[0].start(), -(item[0].end() - item[0].start())))
        consumed = 0
        for match, direction in found:
            if match.start() < consumed:  # owned by an earlier, longer phrase
                continue
            if _negation_scope_is_ambiguous(remaining, match.start(), match.end()):
                ambiguous = True
                continue
            preventive = _english_preventive_scope(
                remaining, match.start(), match.end()
            )
            if preventive == "ambiguous":
                ambiguous = True
                continue
            try:
                number = Decimal(match.group("number").replace(",", ""))
            except InvalidOperation:  # pragma: no cover - regex only yields digits
                continue
            bounds.add(
                (
                    _invert_direction(direction)
                    if preventive == "invert"
                    else direction,
                    number,
                    True if preventive == "invert" else default_inclusive,
                )
            )
            # Blank inclusive phrases before the strict pass runs: "no less
            # than 5000" must not also export a strict "less than 5000".
            if default_inclusive or preventive == "invert":
                remaining = _blank(remaining, match.start(), match.end())
            consumed = match.end()

    _bare_pass(_INCLUSIVE_COMPARISON_PATTERNS, True)
    _bare_pass(_STRICT_COMPARISON_PATTERNS, False)
    return bounds, ambiguous


def _comparison_bounds(text: str) -> set[tuple[str, Decimal]]:
    """Direction/number pairs stated by ``text`` (e.g. {("upper", 5000)}).

    Inclusivity is dropped in this projection; use
    :func:`_comparison_analysis` when the boundary itself matters. Ambiguous
    negated scopes contribute no bound; use
    :func:`_comparison_scope_is_ambiguous` to tell "no comparison" apart from
    "comparison that cannot be interpreted".
    """

    return {
        (direction, number)
        for direction, number, _inclusive in _comparison_analysis(text)[0]
    }


def _comparison_scope_is_ambiguous(text: str) -> bool:
    """Whether ``text`` has a negated comparison whose direction cannot be read."""

    return _comparison_analysis(text)[1]


def _content_tokens(text: str) -> list[str]:
    return [
        token
        for token in (match.group(0).lower() for match in _WORD_TOKEN.finditer(text))
        if len(token) > 1 and token not in _STOPWORDS
    ]


def _is_contiguous_slice(needle: list[str], haystack: list[str]) -> bool:
    """Whether ``needle`` appears in ``haystack`` as an unbroken run of tokens."""

    if not needle:
        return False
    span = len(needle)
    return any(haystack[index : index + span] == needle for index in range(len(haystack) - span + 1))


def _has_negation(text: str) -> bool:
    tokens = [match.group(0).lower() for match in _WORD_TOKEN.finditer(text)]
    if any(token in _NEGATION for token in tokens):
        return True
    # An English preventive verb is negative polarity only when it scopes a
    # comparison. "Expenses exceeding 5000 require approval to avoid fraud"
    # contains "avoid" but asserts an upper bound; treating every "avoid" as a
    # negator would reject the grounded condition instead of the reversed one.
    if not any(token in _EN_PREVENTIVE_TOKENS for token in tokens):
        return False
    for pattern, _direction in _COMPARISON_PATTERNS:
        for match in pattern.finditer(text):
            if (
                _english_preventive_scope(text, match.start(), match.end())
                == "invert"
            ):
                return True
    return False


_CLAUSE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")


def _support_clause(span: str, text: str) -> str:
    """Pick the anchor clause that contains every condition content token.

    Negation is clause-scoped: a policy often states a positive rule and a
    negative exception in the same anchor. Testing the whole anchor makes the
    positive condition fail merely because another sentence contains "not".
    A clause is a candidate only when it covers *all* condition content tokens,
    so a condition cannot borrow a negation from an unrelated exception.
    """

    wanted = set(_content_tokens(text))
    wanted_numbers = set(_decimal_tokens(text))
    if not wanted and not wanted_numbers:
        return span
    for clause in _CLAUSE_SPLIT.split(span):
        clause = clause.strip()
        if not clause:
            continue
        if not wanted <= set(_content_tokens(clause)):
            continue
        if not wanted_numbers <= set(_decimal_tokens(clause)):
            continue
        if _has_negation(clause) == _has_negation(text):
            return clause
    return span


def _describe_bounds(
    bounds: "set[tuple[str, Decimal, bool]]",
) -> list[str]:
    return sorted(
        f"{direction} {number}{' inclusive' if inclusive else ''}"
        for direction, number, inclusive in bounds
    )


def _connective_signature(text: str) -> tuple[tuple[int, str], ...]:
    """Logical connectives with their positions, in the order they appear.

    Swapping a conjunction changes the rule's meaning ("claims and invoices"
    vs "claims or invoices", reviewer F2) even though every content token
    still matches. Per-kind *counts* are not enough either: reordering two
    different connectives keeps both counts while changing their scope
    ("A and B or C" binds differently than "A or B and C", reviewer R2), so
    the ordered sequence is what must agree between the anchor clause and
    the condition. Chinese 与/和 carry the same force and share one label;
    或 is its own, and all three are read per character because Chinese is
    not whitespace-tokenized.
    """

    entries: list[tuple[int, str]] = []
    for match in _WORD_TOKEN.finditer(text):
        token = match.group(0).lower()
        if token == "and":
            entries.append((match.start(), "and"))
        elif token == "or":
            entries.append((match.start(), "or"))
    for index, char in enumerate(text):
        if char in "与和":
            entries.append((index, "cn-and"))
        elif char == "或":
            entries.append((index, "cn-or"))
    entries.sort()
    return tuple(label for _position, label in entries)


# Deontic modality classes. Modals are stopwords for token coverage, so until
# Round 14 a rule could quote an obligation as a bare permission with every
# content token still matching ("must be approved" -> "may be approved",
# tester probe 3). A condition may therefore not claim a modal class its
# anchor does not state: that covers every interchange (must -> may and the
# reverse both invent a class the anchor lacks). Same-class swaps
# (must <-> shall, may <-> can) keep the deontic force and stay acceptable;
# "should" is its own class because it is weaker than must.
#
# Round 15 (tester probes 5-7): per-class *counts* still hide two rewrites
# that keep every content token -- moving a modal to another clause
# ("A must x and B may y" -> "A may x and B must y") and dropping the modal
# outright ("must be approved" -> "are approved"). A condition that restates
# the *whole* anchored clause must therefore keep the ordered sequence of
# deontic classes; a fragment quote may still drop the modal, as "not
# exceeding 5000 CNY" quotes "should avoid exceeding 5000 CNY" (round 12),
# because a fragment omits anchor content by design.
_MODAL_CLASSES: tuple[tuple[str, frozenset[str]], ...] = (
    ("strong obligation (must/shall)", frozenset({"must", "shall"})),
    ("weak obligation (should)", frozenset({"should"})),
    ("permission (may/might/can/could)", frozenset({"may", "might", "can", "could"})),
)


def _modality_signature(text: str) -> tuple[int, ...]:
    """Per-class modal counts, in :data:`_MODAL_CLASSES` order."""

    counts = [0] * len(_MODAL_CLASSES)
    for match in _WORD_TOKEN.finditer(text):
        token = match.group(0).lower()
        for index, (_, words) in enumerate(_MODAL_CLASSES):
            if token in words:
                counts[index] += 1
                break
    return tuple(counts)


def _modality_sequence(text: str) -> tuple[str, ...]:
    """Ordered deontic classes of the modals as they appear in ``text``.

    Counts alone cannot tell a cross-clause swap from a paraphrase: "A must x
    and B may y" and "A may x and B must y" share the class histogram while
    binding opposite forces to each clause (tester probe 7). The order of
    the classes follows the token order, so a clause-scoped swap shows up as
    a different sequence.
    """

    sequence: list[str] = []
    for match in _WORD_TOKEN.finditer(text):
        token = match.group(0).lower()
        for label, words in _MODAL_CLASSES:
            if token in words:
                sequence.append(label)
                break
    return tuple(sequence)


def _invented_modality(condition: str, anchored: str) -> list[str]:
    """Modal classes the condition states but the anchored text does not."""

    return [
        label
        for label, count_c, count_a in (
            (label, condition[index], anchored[index])
            for index, (label, _) in enumerate(_MODAL_CLASSES)
        )
        if count_c > count_a
    ]


# A modal's scope runs forward to the next modal or sentence boundary. ";"
# separates propositions the way "." does ("Claims must be approved;
# invoices may be filed"); a comma only decorates one proposition.
_MODAL_SCOPE_BOUNDARIES = frozenset(".!?;。\n")
_MODAL_TOKEN_TO_CLASS: dict[str, str] = {
    token: label for label, words in _MODAL_CLASSES for token in words
}


def _modal_scopes(text: str) -> list[tuple[str, frozenset[str]]]:
    """(class, scoped content tokens) for each modal occurrence, in order.

    A deontic modal binds the proposition it scopes, which runs forward from
    the modal to the next modal or sentence boundary. Binding the class to
    that content is what stops a fragment from borrowing another clause's
    force (reviewer R1): dropping the "Policy:" label or a tail qualifier
    used to skip the whole-clause modality sequence, so "Claims may be
    approved and invoices must be filed" was accepted against "Claims must
    be approved and invoices may be filed". With the scope map the
    condition's permission must cover the same content the anchor's
    permission covers, whichever tokens the quote dropped.
    """

    tokens = list(_WORD_TOKEN.finditer(text))
    scopes: list[tuple[str, frozenset[str]]] = []
    for index, match in enumerate(tokens):
        label = _MODAL_TOKEN_TO_CLASS.get(match.group(0).lower())
        if label is None:
            continue
        end = len(text)
        for later in tokens[index + 1 :]:
            if _MODAL_TOKEN_TO_CLASS.get(later.group(0).lower()) is not None:
                end = later.start()
                break
        for position in range(match.end(), end):
            if text[position] in _MODAL_SCOPE_BOUNDARIES:
                end = position
                break
        scopes.append((label, frozenset(_content_tokens(text[match.end() : end]))))
    return scopes


def _unsupported_modal_scopes(condition: str, anchored: str) -> list[str]:
    """Condition modals whose scoped content no anchor modal of that class scopes.

    The condition may keep a modal only on content the anchor states with the
    same class: "Invoices may be filed" keeps the anchor's permission, while
    "Invoices must be filed" invents an obligation for that clause even
    though the anchor states "must" somewhere else (borrowing, reviewer R1).
    A condition modal with empty scope is covered by the class counts and
    imposes no extra constraint here.
    """

    anchored_scopes = _modal_scopes(anchored)
    unsupported: list[str] = []
    for label, scoped in _modal_scopes(condition):
        if not scoped:
            continue
        if not any(
            anchor_label == label and scoped <= anchor_scoped
            for anchor_label, anchor_scoped in anchored_scopes
        ):
            unsupported.append(f"{label} on {sorted(scoped)}")
    return unsupported


def _restates_anchor_clause(anchored: str, condition: str) -> bool:
    """Whether ``condition`` restates the *whole* anchored clause.

    "Whole" is measured on content tokens, the same vocabulary as coverage:
    a full restatement keeps every anchor content token (it may only differ in
    stopwords and modals), while a fragment quote omits anchor content. Only
    a full restatement is held to the anchor's modality sequence; a fragment
    may drop the modal together with the content it already omits, but it
    still may not *keep* a modal on content the anchor states with another
    class (:func:`_unsupported_modal_scopes`).
    """

    return set(_content_tokens(anchored)) <= set(_content_tokens(condition))


# Conditionals. "If A then B" reversed into "if B then A" keeps every content
# token, the modal scope map and the connective sequence, yet states the
# opposite implication (reviewer R2). The antecedent is the content between
# the "if" marker and the "then" marker (or the next clause boundary); the
# consequent is the content after it. English uses word tokens; Chinese
# 如果/若/一旦 ... 那么/则/就 are scanned as substrings because Chinese is
# not whitespace-tokenized.
_CN_CONDITIONAL_IF = ("如果", "一旦", "若")
_CN_CONDITIONAL_THEN = ("那么", "则", "就")
_CN_SENTENCE_END = "。！？；"
_CONDITIONAL_CLAUSE_CUT = re.compile(r"[,;.!?\n。！？；]")


def _conditional_structure(
    text: str,
) -> tuple[frozenset[str], frozenset[str]] | None:
    """(antecedent, consequent) content tokens of the first conditional.

    ``None`` when the text states no conditional marker at all. The
    consequent is empty when nothing follows the "then" marker inside the
    sentence; a text with an "if" but no "then" ends its antecedent at the
    next clause boundary ("If A, B."), which is the same proposition.
    """

    if_position = None
    for match in _WORD_TOKEN.finditer(text):
        if match.group(0).lower() == "if":
            if_position = match.end()
            break
    if if_position is None:
        for marker in _CN_CONDITIONAL_IF:
            found = text.find(marker)
            if found >= 0:
                if_position = found + len(marker)
                break
    if if_position is None:
        return None
    rest = text[if_position:]
    then_position = None
    for match in _WORD_TOKEN.finditer(rest):
        if match.group(0).lower() == "then":
            then_position = match.start()
            break
    if then_position is None:
        for marker in _CN_CONDITIONAL_THEN:
            found = rest.find(marker)
            if found >= 0:
                then_position = found
                break
    if then_position is None:
        cut = _CONDITIONAL_CLAUSE_CUT.search(rest)
        antecedent, consequent = (
            (rest[: cut.end()], rest[cut.end() :])
            if cut is not None
            else (rest, "")
        )
    else:
        antecedent, consequent = rest[:then_position], rest[then_position:]
    sentence_end = len(consequent)
    for index, char in enumerate(consequent):
        if char in ".!?\n" or char in _CN_SENTENCE_END:
            sentence_end = index
            break
    return (
        frozenset(_content_tokens(antecedent)),
        frozenset(_content_tokens(consequent[:sentence_end])),
    )


def _conditional_reversal(condition: str, anchored: str) -> bool:
    """Whether ``condition`` conditions on what the anchor asserts (or vice versa).

    Only texts that both state a conditional are compared: a fragment quote
    of one clause ("Invoices may be filed.") and a conjunction restatement
    are not direction reversals, and "B only if A" states the same
    implication as "if A then B" because its "if" clause is the antecedent
    either way.
    """

    condition_structure = _conditional_structure(condition)
    anchored_structure = _conditional_structure(anchored)
    if condition_structure is None or anchored_structure is None:
        return False
    condition_antecedent, condition_consequent = condition_structure
    anchored_antecedent, anchored_consequent = anchored_structure
    if condition_antecedent != anchored_antecedent:
        return True
    return bool(
        anchored_consequent
        and condition_consequent
        and condition_consequent != anchored_consequent
    )


# Guards. A conditional ("If A then B") and its lexical variants ("B only if
# A", "B only after A", "除非A才B") state the consequent only *contingently*:
# quoting the consequent while dropping the antecedent turns "B is allowed
# once A holds" into "B is allowed", an unconditional rule no source states
# (reviewer F4). A condition that quotes such a clause must keep the guard's
# content -- which is also the legitimate precondition use: quoting the
# antecedent itself is always allowed, because that *is* the guard.
_GUARD_INTRODUCER = re.compile(
    r"\b(?:only\s+if|only\s+when|only\s+after|unless)\b",
    re.I,
)
_GUARD_SENTENCE_END = frozenset(".!?\n。！？；;")


def _cut_guard_sentence(text: str) -> str:
    for index, char in enumerate(text):
        if char in _GUARD_SENTENCE_END:
            return text[:index]
    return text


# Chinese guard forms: "只有X才Y" / "只有X方可Y" keep the guard between the
# markers, and a bare "X后方可Y" keeps it in front of the tail marker.
_CN_GUARD_HEAD = "(?:只有|仅当|须先|必须先)"
_CN_GUARD_TAIL = "(?:方可|才能够?|才可以?|才)"
_CN_GUARD_HEAD_RE = re.compile(_CN_GUARD_HEAD)
_CN_GUARD_PAIR_RE = re.compile(
    _CN_GUARD_HEAD + r"(?P<guard>[^。！？；]*?)" + _CN_GUARD_TAIL
)
_CN_GUARD_TAIL_ONLY = re.compile(r"(?P<guard>[^。！？；，,]*?)(?:方可|之后才|以后才)")
# Function characters that may pad a Chinese guard without belonging to its
# content ("只有在X后" states the same guard as "X"); they are exempt from the
# containment check instead of being stripped, so guard content characters
# must all still occur in the condition.
_CN_GUARD_FUNCTION_CHARS = frozenset("在了的后须必须应要已经其就")


def _guard_is_dropped(anchored: str, condition: str) -> str | None:
    """Description of the guard ``anchored`` states but ``condition`` drops.

    Returns ``None`` when the anchored text states no readable guard or the
    condition keeps it. English guards are compared on content tokens;
    Chinese guards are compared on content characters (excluding function
    characters) because Chinese is not whitespace-tokenized.
    """

    structure = _conditional_structure(anchored)
    if structure is not None:
        antecedent, _consequent = structure
        if antecedent:
            if not antecedent <= set(_content_tokens(condition)):
                return f"({sorted(antecedent)})"
            return None
    match = _GUARD_INTRODUCER.search(anchored)
    if match is not None:
        guard = _content_tokens(_cut_guard_sentence(anchored[match.end() :]))
        if guard and not set(guard) <= set(_content_tokens(condition)):
            return f"({sorted(guard)})"
        return None
    pair = _CN_GUARD_PAIR_RE.search(anchored)
    if pair is None and _CN_GUARD_HEAD_RE.search(anchored) is None:
        pair = _CN_GUARD_TAIL_ONLY.search(anchored)
    if pair is not None:
        guard = pair.group("guard")
        kept = all(
            char in condition or char in _CN_GUARD_FUNCTION_CHARS for char in guard
        )
        if guard and not kept:
            return f"({guard!r})"
    return None


# Comparison subject binding. Two propositions can share a threshold while the
# anchor binds opposite directions to each subject ("Claims above 5000 CNY
# and invoices below 5000 CNY"): the *set* of bounds is then identical to the
# swapped condition's set, so only the subject each direction is attached to
# separates them (reviewer R2). The subject is the nearest content token
# before the comparison inside the same clause; number-first forms ("5000 or
# more") and subject-less quotes contribute no binding -- the global bound
# set already covers single-comparison direction swaps.
_COMPARISON_SUBJECT_CUT = re.compile(r"[.!?,;:()\[\]\n。！？，；、（）【】]")


def _comparison_subject(text: str, start: int) -> str | None:
    """Nearest preceding content token of the comparison at ``text[:start]``."""

    segments = _COMPARISON_SUBJECT_CUT.split(text[:start])
    tail = segments[-1] if segments else ""
    for match in reversed(list(_WORD_TOKEN.finditer(tail))):
        token = match.group(0).lower()
        if (
            len(token) > 1
            and token not in _STOPWORDS
            and not token.isdigit()
            and token not in _EN_PREVENTIVE_TOKENS
            and token not in _NEGATION
        ):
            return token
    return None


def _comparison_bindings(
    text: str,
) -> dict[str, set[tuple[str, Decimal, bool]]]:
    """(direction, number, inclusive) triples each comparison attaches to its
    subject.

    Inclusive phrases are matched first so a strict pattern cannot re-read
    "not exceeding 5000" or "不超过5000元" as its bare direction word; the
    reading is deliberately raw (no preventive/negation inversion) because
    both sides of the comparison are scanned the same way -- the binding
    only has to agree, the interpretation is done by the global bound set.

    Inclusivity is part of the binding (reviewer F3): when two subjects
    share one threshold ("claims above 5000 and invoices at least 5000"),
    the global bound *set* is identical under an inclusivity swap, so only
    the subject-attached boundary separates the original from the rewrite.
    """

    matches: list[tuple[int, int, str, Decimal, bool]] = []
    inclusive_spans: list[tuple[int, int]] = []
    for pattern, direction in _INCLUSIVE_COMPARISON_PATTERNS:
        for match in pattern.finditer(text):
            inclusive_spans.append((match.start(), match.end()))
            matches.append(
                (
                    match.start(),
                    match.end(),
                    direction,
                    _as_decimal(match.group("number")),
                    True,
                )
            )
    for pattern, direction in _STRICT_COMPARISON_PATTERNS:
        for match in pattern.finditer(text):
            if any(
                match.start() < end and match.end() > start
                for start, end in inclusive_spans
            ):
                continue
            matches.append(
                (
                    match.start(),
                    match.end(),
                    direction,
                    _as_decimal(match.group("number")),
                    False,
                )
            )
    bindings: dict[str, set[tuple[str, Decimal, bool]]] = {}
    for start, _end, direction, number, inclusive in matches:
        if number is None:
            continue
        subject = _comparison_subject(text, start)
        if subject is not None:
            bindings.setdefault(subject, set()).add((direction, number, inclusive))
    return bindings


def _comparison_subject_conflicts(
    condition: str, anchored: str
) -> list[tuple[str, list[tuple[str, Decimal, bool]]]]:
    """Subjects whose condition bounds the anchor does not state for them.

    A subject the anchor never mentions, or whose comparison the condition
    phrases without a subject, is not a conflict: the global bound-set check
    covers those, and a paraphrase may legitimately re-attach a bound to a
    differently phrased (or dropped) subject token.
    """

    anchored_bindings = _comparison_bindings(anchored)
    conflicts: list[tuple[str, list[tuple[str, Decimal, bool]]]] = []
    for subject, bounds in _comparison_bindings(condition).items():
        anchored_bounds = anchored_bindings.get(subject)
        if anchored_bounds is None:
            continue
        unsupported = sorted(bounds - anchored_bounds)
        if unsupported:
            conflicts.append((subject, unsupported))
    return conflicts


def _is_ordered_subsequence(needle: list[str], haystack: list[str]) -> bool:
    """Whether ``needle`` appears in ``haystack`` in the same relative order.

    A full-coverage paraphrase may reorder words, but the roles of an English
    subject/verb/object chain follow the token order: "employees approve
    managers" is not a paraphrase of "managers approve employees" (reviewer F2).
    Requiring the same relative order keeps legitimate insertions ("approval
    is required for claims above 5000 CNY" -> "claims above 5000 CNY require
    approval") while refusing an argument-role swap.
    """

    cursor = 0
    for token in needle:
        while cursor < len(haystack) and haystack[cursor] != token:
            cursor += 1
        if cursor >= len(haystack):
            return False
        cursor += 1
    return True


def anchor_supports_text(
    content: "DocumentContent | AnchorResolver", anchor: SourceAnchor, text: str
) -> str:
    """Return a reason when the anchored text does not support ``text``.

    Acceptance requires, in order: identical negation polarity, the same
    comparison bounds *including inclusivity* (``above`` vs ``at least``),
    the same logical connectives *in the same order* (AND/OR scope), no
    deontic modality the anchor does not state (``must`` vs ``may``), every
    modal kept on the content it scopes in the anchor (a fragment may not
    borrow another clause's force), the same conditional direction (``if A
    then B``), each comparison attached to the same subject the anchor
    attaches it to, the same *ordered* modality sequence when restating the
    whole clause (a modal may not move to another clause or disappear), no
    number stated by the anchor being dropped,
    no number invented by the condition, and full content coverage. Only then
    is an exact substring accepted; otherwise word order may change as long as
    every content token is covered *and* keeps its relative order -- but a
    *partial* condition must be a contiguous slice of the anchor. That last
    rule is what stops ``"... require approval"`` from weakening ``"...
    require department head approval"``: it skips an anchor qualifier instead
    of quoting a clause (r5-plan item 1 / B3).

    Checking numbers and direction *before* the substring fast path is
    deliberate: "department head approval" is a substring of "Claims above 5000
    CNY require department head approval." but drops the anchor's threshold, so
    it must not be accepted (P0, r4-fixes §6).
    """

    resolved = _as_resolver(content).resolve(anchor)
    if resolved.reason:
        return resolved.reason
    span = resolved.text or ""
    if not span.strip():
        return "anchored text is empty"
    # Negative exceptions in a neighbouring sentence must not veto a positive
    # condition (r5-review P2: negation is per clause, not per whole anchor).
    span = _support_clause(span, text)
    # A sentence-final mark on a quoted fragment is punctuation, not
    # meaning: "Claims must be approved." states the same proposition as
    # "Claims must be approved", yet the raw normalized form ends in "." and
    # misses the substring fast path, falling through to the connective
    # comparison where a single-clause fragment has nothing to compare
    # against the anchor's "and" (reviewer r20 N3). Stripping the trailing
    # mark keeps the fragment exemption a stable property of the quoted
    # words; every structural check (guard, numbers, bounds, modality) has
    # already run before the fast path.
    needle = normalize_text(text).rstrip(_SENTENCE_FINAL_MARKS)
    if not needle:
        return "condition text is empty and cannot be supported by an anchor"
    if _has_negation(text) != _has_negation(span):
        return (
            f"anchored text {span[:40]!r} has different negation polarity than "
            f"the condition text {text[:40]!r}"
        )
    wanted_bounds, wanted_ambiguous = _comparison_analysis(text)
    anchored_bounds, anchored_ambiguous = _comparison_analysis(span)
    # Fail closed on a negated comparison whose direction cannot be read: a
    # missing bound is a silent reversal waiting to happen, so both the anchor
    # and the condition are rejected instead of guessed (round 8; the same
    # class as the round 7 adjacent-negation reversal).
    if anchored_ambiguous:
        return (
            f"anchored text {span[:40]!r} has a negated comparison with an "
            "ambiguous scope; refusing to guess its direction"
        )
    if wanted_ambiguous:
        return (
            f"condition text {text[:40]!r} has a negated comparison with an "
            "ambiguous scope; refusing to guess its direction"
        )
    if wanted_bounds and not anchored_bounds:
        return (
            f"condition text {text[:40]!r} adds a comparison "
            f"({_describe_bounds(wanted_bounds)}) "
            f"that the anchored text {span[:40]!r} does not state"
        )
    if not wanted_bounds and anchored_bounds:
        return (
            f"condition text {text[:40]!r} drops the comparison "
            f"({_describe_bounds(anchored_bounds)}) "
            f"stated by the anchored text {span[:40]!r}"
        )
    conflicting = wanted_bounds - anchored_bounds
    if conflicting:
        return (
            f"anchored text {span[:40]!r} bounds "
            f"{_describe_bounds(anchored_bounds)} "
            f"but the condition text {text[:40]!r} claims "
            f"{_describe_bounds(conflicting)}"
        )
    wanted_numbers = _decimal_tokens(text)
    anchored_numbers = _decimal_tokens(span)
    missing = [str(number) for number in wanted_numbers if number not in anchored_numbers]
    if missing:
        return f"anchored text {span[:40]!r} does not contain the number(s) {missing}"
    if not wanted_numbers and anchored_numbers:
        # A condition that drops the clause's threshold ("All claims require
        # approval") is broader than the source, not a paraphrase of it.
        return (
            f"condition text {text[:40]!r} drops the number(s) "
            f"{[str(number) for number in anchored_numbers]} stated by the anchor"
        )
    # A conditional/guarded anchor states its consequent only contingently;
    # quoting the consequent while dropping the guard turns that into an
    # unconditional rule ("Invoices may be filed" quoting "If claims are
    # approved then invoices may be filed", reviewer F4). The guard's content
    # must stay in the condition -- quoting the antecedent itself is the
    # legitimate precondition form and always keeps it. Checked before the
    # substring fast path: an exact substring is exactly how the guard is
    # silently dropped.
    dropped_guard = _guard_is_dropped(span, text)
    if dropped_guard is not None:
        return (
            f"condition text {text[:40]!r} drops the guard "
            f"{dropped_guard} that the anchored text {span[:40]!r} states; "
            "quote the whole conditional or keep the guard as an unresolved "
            "context"
        )
    if needle in normalize_text(span):
        if _quote_cuts_a_negated_prefix(span, needle):
            return (
                f"condition text {text[:40]!r} starts inside a negated phrase "
                f"of the anchored text {span[:40]!r}; a quoted slice must not "
                "drop the negation character"
            )
        return ""
    # A conjunction swap keeps every content token but changes who is bound
    # by the rule ("claims and invoices" vs "claims or invoices", reviewer
    # F2). Checked after the substring fast path: an exact quote agrees by
    # construction.
    if _connective_signature(span) != _connective_signature(text):
        return (
            f"anchored text {span[:40]!r} uses different logical connectives "
            f"than the condition text {text[:40]!r}"
        )
    # An obligation quoted as a permission reverses what the rule demands
    # ("must be approved" -> "may be approved") while keeping every content
    # token, because modals are coverage stopwords (tester probe 3). The
    # condition may not claim a modal class the anchor does not state; it may
    # still drop the modal, like any other qualifier.
    invented = _invented_modality(_modality_signature(text), _modality_signature(span))
    if invented:
        return (
            f"condition text {text[:40]!r} claims {', '.join(invented)} "
            f"that the anchored text {span[:40]!r} does not state"
        )
    # A modal binds the proposition it scopes, not just the clause histogram:
    # dropping the "Policy:" label or a tail qualifier used to turn a full
    # restatement into a "fragment" and skip the sequence check below, so
    # "Claims may be approved and invoices must be filed" passed against
    # "Policy: Claims must be approved and invoices may be filed" (reviewer
    # R1). Each condition modal must now be scoped by an anchor modal of the
    # same class, so a fragment may quote a clause with its own force but may
    # not borrow or move another clause's.
    unsupported_scopes = _unsupported_modal_scopes(text, span)
    if unsupported_scopes:
        return (
            f"condition text {text[:40]!r} states {', '.join(unsupported_scopes)}, "
            f"which the anchored text {span[:40]!r} states with a different force"
        )
    # "If A then B" reversed into "B if A" keeps every content token, every
    # modal scope and the connective counts, yet asserts the opposite
    # implication (reviewer R2). The antecedent content must be the anchor's.
    if _conditional_reversal(text, span):
        return (
            f"condition text {text[:40]!r} conditions on what the anchored text "
            f"{span[:40]!r} asserts (reversed 'if/then' direction)"
        )
    # Two subjects sharing a threshold with swapped directions keep the
    # global bound set identical ("claims above 5000 and invoices below
    # 5000" vs the reverse, reviewer R2), so each comparison must stay
    # attached to the subject the anchor attaches it to.
    subject_conflicts = _comparison_subject_conflicts(text, span)
    if subject_conflicts:
        described = ", ".join(
            f"{subject} -> "
            + str(
                [
                    (direction, str(number), "inclusive" if inclusive else "strict")
                    for direction, number, inclusive in bounds
                ]
            )
            for subject, bounds in subject_conflicts
        )
        return (
            f"condition text {text[:40]!r} binds the comparison(s) {described} "
            f"that the anchored text {span[:40]!r} states for other subjects"
        )
    # A full restatement of the anchored clause must also keep each modal on
    # its own clause: aggregate counts accepted "A must x and B may y"
    # restated as "A may x and B must y" (swap, tester probe 7) and as
    # "A x and B y" (wholesale drop, tester probes 5-6), because in both
    # cases every content token and every class histogram still matches.
    # Fragments keep their exemption: they omit anchor content by design, so
    # "not exceeding 5000 CNY" still quotes "should avoid exceeding 5000
    # CNY" (round 12).
    if _restates_anchor_clause(span, text):
        wanted_modality = _modality_sequence(text)
        anchored_modality = _modality_sequence(span)
        if wanted_modality != anchored_modality:
            return (
                f"condition text {text[:40]!r} changes the deontic modality "
                f"of the anchored text {span[:40]!r} from {anchored_modality} "
                f"to {wanted_modality}"
            )
    wanted = _content_tokens(text)
    if not wanted:
        return f"anchored text {span[:40]!r} shares no content token with {text[:40]!r}"
    anchored_tokens = _content_tokens(span)
    anchored = set(anchored_tokens)
    covered = sum(1 for token in wanted if token in anchored)
    coverage = covered / len(wanted)
    if coverage < 1.0:
        return (
            f"anchored text {span[:40]!r} covers only {coverage:.0%} of the "
            f"condition text {text[:40]!r}"
        )
    # A paraphrase may reorder words, but a *partial* condition may only quote
    # a contiguous clause. Skipping an anchor token is a silent weakening of
    # the rule (e.g. dropping "department head"), not a paraphrase.
    if not _is_contiguous_slice(wanted, anchored_tokens):
        dropped = [token for token in anchored_tokens if token not in set(wanted)]
        if dropped:
            return (
                f"condition text {text[:40]!r} drops anchor qualifier(s) "
                f"{dropped} instead of quoting a contiguous clause from "
                f"{span[:40]!r}"
            )
        if not _is_ordered_subsequence(wanted, anchored_tokens):
            # Same tokens, different order and nothing dropped: the only
            # remaining difference is who does what to whom ("managers approve
            # employees" vs "employees approve managers"). Argument roles
            # cannot be verified from a bag of words, so fail closed
            # (reviewer F2).
            return (
                f"condition text {text[:40]!r} reorders the anchored tokens "
                f"of {span[:40]!r}; argument roles cannot be verified from a "
                "reordered paraphrase"
            )
    return ""


def ungrounded_terms(text: str, source_text: str) -> list[str]:
    """Content terms and numbers of ``text`` that ``source_text`` does not state.

    Semantics atoms use this to keep proposal fields that no supplied source
    supports out of an "ok" draft (reviewer F4): a scope of "Martian
    spacecraft in 2099" is not grounded by "This policy covers expense claims
    in CN." Terms are matched whole-token (underscores split) and tolerate a
    simple plural; numbers must occur exactly.
    """

    supported = {token for token in _WORD_TOKEN.findall(source_text.lower())}

    def term_supported(term: str) -> bool:
        singular = term.rstrip("s")
        return (
            term in supported
            or term + "s" in supported
            or (singular != term and singular in supported)
        )

    missing = [
        token
        for token in _content_tokens(text)
        if not term_supported(token)
    ]
    source_numbers = set(_decimal_tokens(source_text))
    missing.extend(
        str(number) for number in _decimal_tokens(text) if number not in source_numbers
    )
    return list(dict.fromkeys(missing))


def semantic_divergence(condition: str, source_text: str) -> list[str]:
    """Deterministic semantic conflicts between ``condition`` and ``source_text``.

    Semantics atoms whose proposal fields are *expressions* rather than quotes
    (e.g. an applicability scope) may not reuse :func:`anchor_supports_text`
    wholesale -- coverage/contiguity rules are for quoting a clause -- but the
    deterministic structure still has to agree (reviewer F1): a scope that
    flips negation ("covered" -> "not covered"), reverses a comparison bound
    ("above" -> "below", or "above" -> "at least"), swaps a connective ("and"
    -> "or"), invents a deontic force, reverses an implication, rebinds a
    comparison to the other subject or drops a guard states something no
    supplied source states, even when every content term is grounded.

    Returns one human-readable reason per violated invariant; an empty list
    means no deterministic conflict was found (which is *not* the same as
    "the source supports the text" -- term grounding is a separate check).
    """

    span = _support_clause(source_text, condition)
    reasons: list[str] = []
    if _has_negation(condition) != _has_negation(span):
        reasons.append(
            "states a different negation polarity than the supplied sources"
        )
    wanted_bounds, wanted_ambiguous = _comparison_analysis(condition)
    anchored_bounds, anchored_ambiguous = _comparison_analysis(span)
    # Fail closed on an unreadable negated comparison before comparing bounds.
    if wanted_ambiguous or anchored_ambiguous:
        reasons.append("contains a negated comparison with an ambiguous scope")
    elif wanted_bounds and not anchored_bounds:
        reasons.append(
            "adds a comparison "
            f"({_describe_bounds(wanted_bounds)}) the supplied sources do not state"
        )
    elif not wanted_bounds and anchored_bounds:
        reasons.append(
            "drops the comparison "
            f"({_describe_bounds(anchored_bounds)}) the supplied sources state"
        )
    else:
        conflicting = wanted_bounds - anchored_bounds
        if conflicting:
            reasons.append(
                "claims the comparison "
                f"({_describe_bounds(conflicting)}) the supplied sources do not state"
            )
    if _connective_signature(span) != _connective_signature(condition):
        reasons.append(
            "uses different logical connectives than the supplied sources"
        )
    invented = _invented_modality(
        _modality_signature(condition), _modality_signature(span)
    )
    if invented:
        reasons.append(
            f"claims {', '.join(invented)} the supplied sources do not state"
        )
    unsupported_scopes = _unsupported_modal_scopes(condition, span)
    if unsupported_scopes:
        reasons.append(
            f"states {', '.join(unsupported_scopes)}, which the supplied sources "
            "state with a different force"
        )
    if _conditional_reversal(condition, span):
        reasons.append("reverses the 'if/then' direction of the supplied sources")
    subject_conflicts = _comparison_subject_conflicts(condition, span)
    if subject_conflicts:
        described = ", ".join(
            f"{subject} -> "
            + str(
                [
                    (direction, str(number), "inclusive" if inclusive else "strict")
                    for direction, number, inclusive in bounds
                ]
            )
            for subject, bounds in subject_conflicts
        )
        reasons.append(
            f"binds the comparison(s) {described} that the supplied sources "
            "state for other subjects"
        )
    dropped_guard = _guard_is_dropped(span, condition)
    if dropped_guard is not None:
        reasons.append(
            f"drops the guard {dropped_guard} that the supplied sources state"
        )
    if _restates_anchor_clause(span, condition):
        if _modality_sequence(condition) != _modality_sequence(span):
            reasons.append(
                "changes the deontic modality sequence of the supplied sources"
            )
    return reasons
