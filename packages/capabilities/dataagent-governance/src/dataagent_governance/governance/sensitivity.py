"""Deterministic sensitivity identification and masking (08 §5.1).

S0 ships built-in identifiers for mainland-CN ID cards, mobile numbers,
emails and bank cards (with checksum validation where applicable), plus the
field names declared sensitive by the policy. Everything is deterministic:
no model calls, no network.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from dataagent_governance.contracts import (
    MaskedArtifactRef,
    MaskedEntry,
    SensitivityFinding,
    SensitivityReport,
)
from dataagent_governance.runtime.errors import invalid_input

__all__ = ["scan_content", "mask_content"]

# JSON scalar types the scanner understands; anything else is rejected
# instead of being silently treated as clean (review r35 F1).
_JSON_SCALARS = (str, int, float, bool)

_ID_CARD = re.compile(r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_BANK_CARD = re.compile(r"(?<!\d)\d{16,19}(?!\d)")


def _luhn_ok(number: str) -> bool:
    digits = [int(c) for c in number]
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _id_card_ok(value: str) -> bool:
    if len(value) != 18:
        return False
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    codes = "10X98765432"
    try:
        total = sum(int(value[i]) * weights[i] for i in range(17))
    except ValueError:
        return False
    return codes[total % 11] == value[17].upper()


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mask_value(value: str) -> str:
    """Keep the first and last character; mask the middle."""

    if len(value) <= 2:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1]


def scan_text(text: str) -> list[tuple[str, str, int]]:
    """Return ``(kind, value, char_start)`` triples found in free text."""

    found: list[tuple[str, str, int]] = []
    for match in _ID_CARD.finditer(text):
        if _id_card_ok(match.group(0)):
            found.append(("id_card", match.group(0), match.start()))
    for match in _PHONE.finditer(text):
        found.append(("phone", match.group(0), match.start()))
    for match in _EMAIL.finditer(text):
        found.append(("email", match.group(0), match.start()))
    for match in _BANK_CARD.finditer(text):
        if _luhn_ok(match.group(0)):
            found.append(("bank_card", match.group(0), match.start()))
    return found


def _column_identifiers(payload: dict[str, Any]) -> list[set[str]]:
    """Names and field ids per column; a declared field may use either."""

    identifiers: list[set[str]] = []
    for column in payload.get("columns") or []:
        if isinstance(column, dict):
            ids = {str(column[key]) for key in ("name", "field_id") if column.get(key)}
        else:
            ids = {str(column.name)} if getattr(column, "name", None) else set()
        identifiers.append(ids)
    return identifiers


def _scalar_text(value: Any) -> str | None:
    """The text a scalar carries when serialized; numbers included.

    Phone/bank-card numbers frequently arrive as numeric cells; skipping
    them would leak the value verbatim to the model (review B2).
    """

    if isinstance(value, str):
        return value
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _scalar_findings(value: Any) -> list[tuple[str, str, int]]:
    """Identifier findings inside one scalar cell (numeric cells included)."""

    text = _scalar_text(value)
    return scan_text(text) if text else []


def _record_finding(
    findings: dict[tuple[str, str | None], SensitivityFinding],
    kind: str,
    field: str | None,
    locator: str,
    value: str,
) -> None:
    key = (kind, field)
    existing = findings.get(key)
    if existing is None:
        findings[key] = SensitivityFinding(
            kind=kind, field=field, count=1, sample_digest=_digest(value), locator=locator
        )
    else:
        findings[key] = existing.model_copy(update={"count": existing.count + 1})


def _scan_table(
    payload: dict[str, Any], declared_fields: list[str]
) -> dict[tuple[str, str | None], SensitivityFinding]:
    findings: dict[tuple[str, str | None], SensitivityFinding] = {}
    identifiers = _column_identifiers(payload)
    names = [next(iter(ids)) if ids else "" for ids in identifiers]
    for row_index, row in enumerate(payload["rows"]):
        if not isinstance(row, list):
            continue
        for col_index, value in enumerate(row):
            if col_index >= len(names):
                break
            for kind, found, start in _scalar_findings(value):
                _record_finding(findings, kind, names[col_index], f"row:{row_index}:char:{start}", found)
    # Policy-declared sensitive fields: presence alone is a finding.
    declared = {
        name
        for ids in identifiers
        for name in ids
        if name and name in set(declared_fields)
    }
    for name in sorted(declared):
        _record_finding(findings, "declared_field", name, "column", name)
    return findings


def _reject_unsupported(value: Any) -> None:
    """Fail closed on shapes the scanner cannot walk (review r35 F1).

    Everything that reaches the model is JSON; a value outside the JSON
    vocabulary cannot be scanned, so it is rejected instead of treated as
    clean.
    """

    if value is not None and not isinstance(value, _JSON_SCALARS):
        raise invalid_input(
            f"sensitivity scan cannot walk content of type "
            f"{type(value).__name__}; refusing to treat it as clean",
            target="content",
        )


def _scan_key(
    key: Any,
    declared_fields: set[str],
    findings: dict[tuple[str, str | None], SensitivityFinding],
    locator: str,
) -> None:
    """Scan one object key: keys are model-visible content too (r38 F2).

    An identifier (phone/email/id card/bank card) sitting in a JSON key is
    serialized and sent to the model exactly like one sitting in a value;
    a declared sensitive field name as a key is a finding like any other.
    The locator is positional — the raw key never appears in it.
    """

    key_text = str(key)
    if key_text in declared_fields:
        _record_finding(findings, "declared_field", key_text, locator, key_text)
    for kind, found, start in scan_text(key_text):
        _record_finding(findings, kind, None, f"{locator}:char:{start}", found)


def _scan_structured(
    value: Any,
    declared_fields: set[str],
    findings: dict[tuple[str, str | None], SensitivityFinding],
    path: str,
) -> None:
    """Recursively scan structured JSON content (review B2, r35 F1, r38 F2).

    Declared field names match object keys anywhere in the structure; every
    scalar (numbers included) and every object **key** is checked for the
    built-in identifier patterns. Paths are positional (dict children are
    addressed by index), so a sensitive key never leaks into a locator.
    There is no "clean by shape" shortcut, and a non-JSON shape is rejected
    rather than assumed clean.
    """

    if isinstance(value, dict):
        for index, (key, item) in enumerate(value.items()):
            _scan_key(key, declared_fields, findings, f"json:{path}/key:{index}")
            _scan_structured(item, declared_fields, findings, f"{path}/{index}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_structured(item, declared_fields, findings, f"{path}/{index}")
    else:
        _reject_unsupported(value)
        for kind, found, start in _scalar_findings(value):
            _record_finding(findings, kind, None, f"json:{path}:char:{start}", found)


def _is_table_payload(payload: dict[str, Any]) -> bool:
    """Only the fully validated shared ``TableData`` shape (W0 §1.1) takes
    the table fast path (review r35 F1).

    Mirrors ``dataagent_runtime.ports.tabular.decode_table_payload``: a
    non-empty ``columns`` list of objects each carrying a ``field_id``, and
    ``rows`` made of lists with exactly one cell per column. Anything else —
    a ``rows`` list of dicts, missing/empty columns, ragged rows — is *not*
    a table and is scanned structurally, never silently treated as clean.
    """

    columns = payload.get("columns")
    rows = payload.get("rows")
    if not isinstance(columns, list) or not columns:
        return False
    if not all(
        isinstance(column, dict) and column.get("field_id") for column in columns
    ):
        return False
    if not isinstance(rows, list):
        return False
    width = len(columns)
    return all(
        isinstance(row, list) and len(row) == width for row in rows
    )


def _scan_table_envelope(
    payload: dict[str, Any],
    declared_fields: set[str],
    findings: dict[tuple[str, str | None], SensitivityFinding],
) -> None:
    """Structural scan of a validated table payload outside the scalar cells.

    The scalar cells are the table scan's job (better locators, column
    fields). Everything else that also reaches the model — metadata, extra
    top-level fields, structured (non-scalar) cells — is scanned
    structurally (review r35 F1).
    """

    extras = {key: value for key, value in payload.items() if key != "rows"}
    _scan_structured(extras, declared_fields, findings, "")
    for row_index, row in enumerate(payload["rows"]):
        for col_index, cell in enumerate(row):
            if isinstance(cell, (dict, list)):
                _scan_structured(
                    cell,
                    declared_fields,
                    findings,
                    f"/rows/{row_index}/{col_index}",
                )


def _mask_table_envelope(masked_payload: dict[str, Any], declared_fields: set[str]):
    """Masking counterpart of ``_scan_table_envelope`` (r35 F1)."""

    entries: list[MaskedEntry] = []
    extras = {key: value for key, value in masked_payload.items() if key != "rows"}
    masked_extras, extra_entries = _mask_structured(extras, declared_fields, "")
    entries.extend(extra_entries)
    new_rows = []
    for row_index, row in enumerate(masked_payload["rows"]):
        new_row = list(row)
        for col_index, cell in enumerate(row):
            if isinstance(cell, (dict, list)):
                masked_cell, cell_entries = _mask_structured(
                    cell, declared_fields, f"/rows/{row_index}/{col_index}"
                )
                new_row[col_index] = masked_cell
                entries.extend(cell_entries)
        new_rows.append(new_row)
    masked_payload = {**masked_extras, "rows": new_rows}
    return masked_payload, entries


def scan_content(payload: Any, declared_fields: list[str]) -> SensitivityReport:
    """Scan content: free text, a structured table payload, or nested JSON.

    Structured table payloads are the data-layer ``TableData`` shape
    (``columns`` with ``name``/``field_id`` and ``rows``); declared field
    names match the column name or field id, and every cell — string or
    numeric — is checked for the built-in identifiers. A validated table
    still gets a structural pass over everything the columns do not
    explain: metadata, extra top-level fields and structured cells all
    reach the model and are all scanned. Any other JSON-serializable
    content is walked structurally; a shape the scanner cannot walk is
    rejected, never assumed clean.
    """

    findings: dict[tuple[str, str | None], SensitivityFinding] = {}
    if isinstance(payload, str):
        for kind, value, start in scan_text(payload):
            _record_finding(findings, kind, None, f"char:{start}", value)
        return SensitivityReport(content_ref="inline", findings=list(findings.values()))

    if isinstance(payload, dict) and _is_table_payload(payload):
        findings = _scan_table(payload, declared_fields)
        _scan_table_envelope(payload, set(declared_fields), findings)
        return SensitivityReport(content_ref="inline", findings=list(findings.values()))

    _scan_structured(payload, set(declared_fields), findings, "")
    return SensitivityReport(content_ref="inline", findings=list(findings.values()))


def _mask_scalar(value: Any) -> str | None:
    """Masked replacement for a scalar cell; ``None`` for nothing to mask."""

    text = _scalar_text(value)
    if text is None or not text:
        return None
    return _mask_value(text)


def _mask_table(payload: dict[str, Any], declared_fields: list[str]):
    entries: list[MaskedEntry] = []
    masked_rows = []
    identifiers = _column_identifiers(payload)
    names = [next(iter(ids)) if ids else "" for ids in identifiers]
    declared = set(declared_fields)
    for row_index, row in enumerate(payload["rows"]):
        if not isinstance(row, list):
            masked_rows.append(row)
            continue
        new_row = list(row)
        for col_index, value in enumerate(row):
            if col_index >= len(names):
                break
            if identifiers[col_index] & declared:
                # A declared sensitive column is masked wholesale, whatever
                # the cell shape — structured cells included (r35 F1).
                masked_cell, item_entries = _mask_whole(
                    value, names[col_index], f"row:{row_index}"
                )
                new_row[col_index] = masked_cell
                entries.extend(item_entries)
                continue
            text = _scalar_text(value)
            if text is None:
                continue
            masked_text = text
            for _kind, found, start in scan_text(text):
                replacement = _mask_value(found)
                masked_text = masked_text.replace(found, replacement)
                entries.append(
                    MaskedEntry(
                        field=names[col_index],
                        locator=f"row:{row_index}:char:{start}",
                        replacement=replacement,
                        original_digest=_digest(found),
                    )
                )
            if masked_text != text:
                new_row[col_index] = masked_text
        masked_rows.append(new_row)
    masked_payload = dict(payload)
    masked_payload["rows"] = masked_rows
    return masked_payload, entries


def _mask_key(key: Any, locator: str) -> tuple[str, list[MaskedEntry]]:
    """Mask the identifier patterns one object key carries (r38 F2).

    The key is model-visible content exactly like a value; its identifiers
    are replaced in place. The locator is positional, never the raw key.
    """

    entries: list[MaskedEntry] = []
    key_text = str(key)
    masked_text = key_text
    for _kind, found, start in scan_text(key_text):
        replacement = _mask_value(found)
        masked_text = masked_text.replace(found, replacement)
        entries.append(
            MaskedEntry(
                field=None,
                locator=f"{locator}:char:{start}",
                replacement=replacement,
                original_digest=_digest(found),
            )
        )
    return (masked_text if masked_text != key_text else key_text), entries


def _unique_masked_key(masked: dict[str, Any], key: str) -> str:
    """A key not already taken by an earlier sibling (r40 F2).

    Two identifier keys may mask to the same text (``13800138000`` and
    ``13900139000`` both become ``1*********0``). The masked payload must
    stay faithful to the input — every entry survives — so a colliding key
    is made unique *at insertion time* with a stable ``~<n>`` suffix; a
    post-hoc pass would run after the earlier entry has already been
    silently overwritten.
    """

    if key not in masked:
        return key
    suffix = 1
    while f"{key}~{suffix}" in masked:
        suffix += 1
    return f"{key}~{suffix}"


def _mask_structured(value: Any, declared_fields: set[str], path: str):
    """Structural counterpart of ``_scan_structured`` (B2, r35 F1, r38 F2)."""

    entries: list[MaskedEntry] = []
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            child = f"{path}/{index}"
            masked_key, key_entries = _mask_key(key, f"json:{child}/key:{index}")
            entries.extend(key_entries)
            if str(key) in declared_fields:
                masked_item, item_entries = _mask_whole(item, str(key), child)
            else:
                masked_item, item_entries = _mask_structured(item, declared_fields, child)
            masked[_unique_masked_key(masked, masked_key)] = masked_item
            entries.extend(item_entries)
        return masked, entries
    if isinstance(value, list):
        masked_list = []
        for index, item in enumerate(value):
            masked_item, item_entries = _mask_structured(item, declared_fields, f"{path}/{index}")
            masked_list.append(masked_item)
            entries.extend(item_entries)
        return masked_list, entries
    # scalar: mask the identifier patterns it carries
    _reject_unsupported(value)
    text = _scalar_text(value)
    if text is None:
        return value, entries
    masked_text = text
    for _kind, found, start in scan_text(text):
        replacement = _mask_value(found)
        masked_text = masked_text.replace(found, replacement)
        entries.append(
            MaskedEntry(
                field=None,
                locator=f"json:{path}:char:{start}",
                replacement=replacement,
                original_digest=_digest(found),
            )
        )
    return masked_text if masked_text != text else value, entries


def _mask_whole(value: Any, field: str, path: str):
    """Mask the entire value of a declared sensitive field.

    Keys of nested objects under it are masked too (r38 F2): they are part
    of the cell that reaches the model, and an identifier key would leak
    the raw value even with every scalar below it masked.
    """

    entries: list[MaskedEntry] = []
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            child = f"{path}/{index}"
            masked_key, key_entries = _mask_key(key, f"json:{child}/key:{index}")
            entries.extend(key_entries)
            masked[_unique_masked_key(masked, masked_key)], item_entries = _mask_whole(
                item, field, child
            )
            entries.extend(item_entries)
        return masked, entries
    if isinstance(value, list):
        masked_list = []
        for index, item in enumerate(value):
            masked_item, item_entries = _mask_whole(item, field, f"{path}/{index}")
            masked_list.append(masked_item)
            entries.extend(item_entries)
        return masked_list, entries
    replacement = _mask_scalar(value)
    if replacement is None:
        return value, entries
    entries.append(
        MaskedEntry(
            field=field,
            locator=f"json:{path}",
            replacement=replacement,
            original_digest=_digest(_scalar_text(value) or ""),
        )
    )
    return replacement, entries


def mask_content(payload: Any, declared_fields: list[str]) -> tuple[Any, MaskedArtifactRef]:
    """Mask sensitive values; return ``(masked_payload, artifact)``."""

    entries: list[MaskedEntry] = []
    if isinstance(payload, str):
        masked = payload
        for kind, value, start in scan_text(payload):
            replacement = _mask_value(value)
            masked = masked.replace(value, replacement)
            entries.append(
                MaskedEntry(
                    field=None,
                    locator=f"char:{start}",
                    replacement=replacement,
                    original_digest=_digest(value),
                )
            )
        artifact = MaskedArtifactRef(
            mask_id="mask:pending",
            source_content_ref="inline",
            masked_content_ref="inline",
            entries=entries,
        )
        return masked, artifact

    if isinstance(payload, dict) and _is_table_payload(payload):
        # Table semantics first (column names, per-cell locators), then the
        # envelope pass: metadata, extra top-level fields and structured
        # cells are masked too, so nothing that reaches the model survives
        # unmasked (review r35 F1).
        masked_payload, entries = _mask_table(payload, declared_fields)
        masked_payload, extra_entries = _mask_table_envelope(
            masked_payload, set(declared_fields)
        )
        entries = entries + extra_entries
        artifact = MaskedArtifactRef(
            mask_id="mask:pending",
            source_content_ref="inline",
            masked_content_ref="inline",
            entries=entries,
        )
        return masked_payload, artifact

    masked, entries = _mask_structured(payload, set(declared_fields), "")
    artifact = MaskedArtifactRef(
        mask_id="mask:pending",
        source_content_ref="inline",
        masked_content_ref="inline",
        entries=entries,
    )
    return masked, artifact
