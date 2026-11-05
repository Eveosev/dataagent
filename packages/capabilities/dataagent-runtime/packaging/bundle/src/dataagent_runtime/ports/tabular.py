"""Versioned table payload codec (07 plan W1a, minimal S0 scope).

The data layer stores logical tables as content-addressed JSON payloads
(``TableData``) and returns a ``TableRef`` whose ``data_ref`` is the payload
digest. Every layer that needs to read a table must go through a versioned
codec instead of importing the data layer: the application layer (07 §3)
depends only on ``dataagent-contracts`` and ``dataagent-runtime``.

Versioning rules (fail closed on unknown versions):

- ``1``: the payload written by ``dataagent-data`` S0 — an object with
  ``columns`` (name/field_id/value_type/...), ``rows`` (row-major cells) and
  an optional ``row_meta`` aligned one-to-one with ``rows`` carrying the row
  ``role``. An explicit ``payload_version`` / ``format_version`` key, when
  present, must be a supported version.
- anything else: ``unsupported_table_version`` is raised through the runtime
  error mapping (``invalid_input`` with a clear message), never guessed.

Row roles are preserved verbatim. Aggregate consumers must use
``detail_rows()``: subtotal/total rows must not be summed again alongside the
detail rows they already aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dataagent_runtime.errors import invalid_input, unsupported

TABLE_PAYLOAD_VERSION = 1
SUPPORTED_TABLE_PAYLOAD_VERSIONS = frozenset({1})

ROW_ROLES = frozenset({"detail", "subtotal", "total", "title", "unknown"})
# Roles excluded from aggregation: summing them together with detail rows
# would double count. ``unknown`` is excluded as well (fail closed: it may
# be a misclassified total).
NON_AGGREGATABLE_ROLES = frozenset({"subtotal", "total", "title", "unknown"})


@dataclass(frozen=True)
class DecodedColumn:
    name: str
    field_id: str
    value_type: str
    unit: str | None = None
    source_path: str = ""


@dataclass(frozen=True)
class DecodedTable:
    """A decoded table payload with row roles preserved."""

    version: int
    columns: tuple[DecodedColumn, ...]
    rows: tuple[tuple[Any, ...], ...]
    row_roles: tuple[str, ...]
    row_reasons: tuple[str, ...]
    sheet: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def field_ids(self) -> tuple[str, ...]:
        return tuple(column.field_id for column in self.columns)

    def schema_fields(self) -> list[dict[str, Any]]:
        """``FieldSpec``-shaped dicts for schema binding (05 §3.3.3)."""

        return [
            {
                "field_id": column.field_id,
                "name": column.name,
                "path": column.source_path or column.field_id,
                "value_type": column.value_type,
                "nullable": True,
                "unit": column.unit,
            }
            for column in self.columns
        ]

    def row_dict(self, index: int) -> dict[str, Any]:
        return dict(zip(self.field_ids, self.rows[index]))

    def detail_rows(self) -> list[int]:
        """Indexes of rows that participate in aggregation (role=detail)."""

        return [i for i, role in enumerate(self.row_roles) if role == "detail"]

    def non_detail_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for role in self.row_roles:
            if role != "detail":
                counts[role] = counts.get(role, 0) + 1
        return counts


def _payload_version(payload: dict[str, Any]) -> int:
    for key in ("payload_version", "format_version"):
        if key in payload:
            value = payload[key]
            if not isinstance(value, int) or isinstance(value, bool):
                raise invalid_input(
                    f"table payload {key} must be an integer, got {value!r}",
                    target=f"table.{key}",
                )
            return value
    # No explicit version: recognise the version-1 shape written by
    # dataagent-data S0 instead of guessing.
    if isinstance(payload.get("columns"), list) and isinstance(payload.get("rows"), list):
        return 1
    raise invalid_input(
        "unrecognised table payload: no payload_version and not a version-1 "
        "table (columns/rows) object",
        target="table.payload",
    )


def _decode_columns(raw_columns: Any) -> list[DecodedColumn]:
    """The payload's ``columns`` list as decoded columns (validated)."""

    if not isinstance(raw_columns, list) or not raw_columns:
        raise invalid_input("table payload requires a non-empty 'columns' list")
    columns: list[DecodedColumn] = []
    for column in raw_columns:
        if not isinstance(column, dict) or not column.get("field_id"):
            raise invalid_input("every table column requires a field_id")
        columns.append(
            DecodedColumn(
                name=str(column.get("name") or column["field_id"]),
                field_id=str(column["field_id"]),
                value_type=str(column.get("value_type") or "unknown"),
                unit=column.get("unit"),
                source_path=str(column.get("source_path") or ""),
            )
        )
    return columns


def _decode_rows(rows_raw: Any, width: int) -> list[tuple[Any, ...]]:
    """The payload's ``rows`` list as cell tuples, one cell per column."""

    if not isinstance(rows_raw, list):
        raise invalid_input("table payload requires a 'rows' list")
    rows: list[tuple[Any, ...]] = []
    for row in rows_raw:
        if not isinstance(row, list) or len(row) != width:
            raise invalid_input(
                f"table row must be a list with exactly {width} cells "
                f"(one per column), got {len(row) if isinstance(row, list) else type(row).__name__}"
            )
        rows.append(tuple(row))
    return rows


def _decode_row_meta(row_meta: Any, row_count: int) -> tuple[list[str], list[str]]:
    """Row roles and reasons, aligned one-to-one with the rows."""

    if not isinstance(row_meta, list):
        raise invalid_input("row_meta must be a list when present")
    if row_meta and len(row_meta) != row_count:
        raise invalid_input(
            f"row_meta must align one-to-one with rows ({len(row_meta)} vs {row_count})"
        )
    roles: list[str] = []
    reasons: list[str] = []
    for meta in row_meta or [{} for _ in range(row_count)]:
        role = "detail" if not isinstance(meta, dict) else str(meta.get("role") or "detail")
        if role not in ROW_ROLES:
            raise invalid_input(f"unknown row role: {role!r}")
        roles.append(role)
        reasons.append("" if not isinstance(meta, dict) else str(meta.get("reason") or ""))
    return roles, reasons


_RESERVED_PAYLOAD_KEYS = {
    "columns",
    "rows",
    "row_meta",
    "sheet",
    "payload_version",
    "format_version",
}


def decode_table_payload(payload: Any) -> DecodedTable:
    """Decode one stored table payload into a role-preserving table."""

    if not isinstance(payload, dict):
        raise invalid_input(
            f"table payload must be a JSON object, got {type(payload).__name__}",
            action="pass the TableRef.data_ref content of a stored table",
        )
    version = _payload_version(payload)
    if version not in SUPPORTED_TABLE_PAYLOAD_VERSIONS:
        raise unsupported(
            f"unsupported table payload version: {version} "
            f"(supported: {sorted(SUPPORTED_TABLE_PAYLOAD_VERSIONS)})",
        )

    columns = _decode_columns(payload.get("columns"))
    rows = _decode_rows(payload.get("rows"), len(columns))
    roles, reasons = _decode_row_meta(payload.get("row_meta") or [], len(rows))

    return DecodedTable(
        version=version,
        columns=tuple(columns),
        rows=tuple(rows),
        row_roles=tuple(roles),
        row_reasons=tuple(reasons),
        sheet=str(payload.get("sheet") or ""),
        extras={
            key: value for key, value in payload.items() if key not in _RESERVED_PAYLOAD_KEYS
        },
    )


def decode_table(content_store: Any, table_ref: Any) -> DecodedTable:
    """Load and decode the payload behind a ``TableRef`` from a content store."""

    try:
        payload = content_store.get_json(table_ref.data_ref)
    except FileNotFoundError as exc:
        raise invalid_input(
            f"table content missing: {table_ref.data_ref}",
            target="table_ref.data_ref",
        ) from exc
    return decode_table_payload(payload)
