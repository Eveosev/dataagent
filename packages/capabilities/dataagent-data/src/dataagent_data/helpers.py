"""Shared helpers: safe paths, content/table storage, asset construction."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dataagent_contracts.core import (
    AssetRef,
    CallContext,
    Completeness,
    CompletenessExtent,
    FileRef,
    SourceAnchor,
    TableRef,
    VersionedRef,
)

from dataagent_data.contracts.layer import RowMeta, TableColumn, TableData
from dataagent_runtime.errors import invalid_input, source_changed

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
# Canonical workspace identity: ``<kind>:<first 16 digest hex chars>`` (see
# :func:`file_ref`). Ids that do not follow this shape (e.g. ``file:report``)
# are custom names, not digest-derived claims, and are not checked against it.
_DIGEST_DERIVED_ID = re.compile(r"^(?P<kind>[^:@\s]+):(?P<prefix>[0-9a-f]{16})$")


def now() -> datetime:
    return datetime.now(timezone.utc)


def scope_of(ctx: CallContext) -> str:
    return ctx.scope_ref


def asset_for(
    digest: str,
    kind: str,
    scope_ref: str,
    *,
    media_type: str | None = None,
    identifier: str | None = None,
) -> AssetRef:
    return AssetRef(
        id=identifier or f"{kind}:{digest.split(':', 1)[1][:16]}",
        kind=kind,
        scope_ref=scope_ref,
        revision=digest,
        resolver="local_content",
        locator=digest,
        digest=digest,
        media_type=media_type,
    )


def complete(declared_scope: str, observed: dict[str, int] | None = None) -> Completeness:
    return Completeness(
        extent=CompletenessExtent.complete_in_declared_scope,
        declared_scope=declared_scope,
        observed=observed,
        snapshot_consistent=True,
    )


def truncated(
    declared_scope: str,
    *,
    reason: str,
    observed: dict[str, int] | None = None,
) -> Completeness:
    """Declare that the prepared context deliberately covers a subset.

    Used where an inference request has a fixed budget (page/clause/character
    limits): returning ``complete_in_declared_scope`` would tell the agent that
    nothing was omitted (06 §5 step 1, completeness semantics).
    """

    return Completeness(
        extent=CompletenessExtent.truncated,
        declared_scope=declared_scope,
        observed=observed,
        reason=reason,
        snapshot_consistent=True,
    )


def workspace_path(workspace_root: Path, locator: str) -> Path:
    """Resolve a workspace-relative path and reject escapes.

    Rejects absolute paths, ``..`` components, empty locators, and symlink
    escapes (``resolve`` follows links before the containment check).
    """

    if not locator or locator.strip() != locator:
        raise invalid_input("file locator must be a non-empty relative path")
    candidate = Path(locator)
    if candidate.is_absolute():
        raise invalid_input("absolute paths are not allowed")
    if any(part in {"..", ""} for part in candidate.parts):
        raise invalid_input("path traversal is not allowed")
    root = workspace_root.resolve()
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise invalid_input("path escapes the workspace")
    return resolved


def read_file_ref(runtime, file_ref: FileRef) -> bytes:
    path = workspace_path(runtime.workspace_root, file_ref.locator)
    if not path.exists() or not path.is_file():
        from dataagent_runtime.errors import not_found

        raise not_found(f"file not found in workspace: {file_ref.locator}")
    if not _DIGEST.match(file_ref.content_digest):
        raise invalid_input(
            "content_digest must be 'sha256:<64 lowercase hex characters>'; "
            f"got {file_ref.content_digest!r}",
            target="file_ref.content_digest",
        )
    payload = path.read_bytes()
    actual = "sha256:" + hashlib.sha256(payload).hexdigest()
    if actual != file_ref.content_digest:
        raise source_changed(
            f"content digest mismatch for {file_ref.locator}: expected "
            f"{file_ref.content_digest}, got {actual}"
        )
    # The caller controls ``id``, but a digest-derived id claims to be
    # ``<kind>:<first 16 hex chars of the content digest>`` (see
    # :func:`file_ref`). The bytes verified above are the only authority, so
    # an id of that shape must be derived from *these* bytes: otherwise a
    # caller could parse B's real bytes while claiming A's digest-derived
    # identity and forge a binding that names A for B's body (reviewer F1,
    # tester probe 4). Free-form ids (``file:report``) are names, not digest
    # claims; they are guarded by the identity-uniqueness rule in
    # :func:`register_file_ref` instead.
    derived = _DIGEST_DERIVED_ID.match(file_ref.id)
    if derived and derived.group("prefix") != actual[7:23]:
        raise invalid_input(
            f"file_ref id {file_ref.id!r} looks digest-derived but is not "
            f"derived from the verified digest of {file_ref.locator} "
            f"({actual}); refusing a forged source identity",
            target="file_ref.id",
        )
    # r30 B1.1, second line of defence: the runtime recheck already refuses a
    # FileRef whose ``content_digest``/``digest`` is not the asset revision
    # before any read; the handler refuses it too, so a rebound file asset
    # cannot be smuggled through even with the recheck disabled. A
    # digest-shaped revision claims to *be* a content address, and the bytes
    # verified above are bound to ``content_digest`` — requiring the two to
    # be equal makes the verified bytes exactly the content the decision's
    # ``<id>@<revision>`` names. A free-form label revision (``rev:1``) is
    # not a content claim: it is bound through the immutable identity
    # registry instead, so a registered identity may only re-read the bytes
    # it was first bound to.
    if _DIGEST.match(file_ref.revision):
        if file_ref.content_digest != file_ref.revision or (
            file_ref.digest is not None and file_ref.digest != file_ref.revision
        ):
            raise invalid_input(
                "file_ref.content_digest is not the file asset's revision "
                f"({file_ref.content_digest!r} vs {file_ref.revision!r}); refusing "
                "to read file content other than the one the asset names",
                target="file_ref.content_digest",
            )
    else:
        registered = find_file_ref(runtime, file_ref.id, file_ref.revision)
        if registered is not None and registered.content_digest != file_ref.content_digest:
            raise invalid_input(
                f"file identity {file_ref.id}@{file_ref.revision} is already bound "
                f"to different bytes ({registered.content_digest}); refusing to "
                f"re-bind it to {file_ref.content_digest}",
                target="file_ref",
            )
    # r38 F3: a file read through an official data-layer operation is an
    # "other operation read" of the sample library: when the verified bytes
    # are a registered gold expectation, the cross-layer exposure ledger
    # records it and the case can no longer pass as unseen acceptance.
    # The read itself succeeds — exposure is recorded, not blocked.
    try:
        from dataagent_runtime.adapters.gold_ledger import GoldExposureLedger

        GoldExposureLedger(Path(runtime.data_root) / "vault").note_exposure(
            actual,
            purpose="file-read",
            accessed_by=str(file_ref.id),
        )
    except OSError:
        # The ledger is best-effort on the read path: a broken ledger must
        # never break the read itself.
        pass
    return payload


def file_ref(
    runtime, path: str | Path, *, scope_ref: str = "tenant:local", kind: str = "file"
) -> FileRef:
    """Test/CLI helper: build a FileRef for a workspace file with real digest."""

    relative = str(Path(path))
    data = (runtime.workspace_root / relative).read_bytes()
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    return FileRef(
        id=f"{kind}:{digest[7:23]}",
        kind=kind,
        scope_ref=scope_ref,
        revision=digest,
        resolver="workspace",
        locator=relative,
        digest=digest,
        media_type="application/octet-stream",
        filename=Path(relative).name,
        size_bytes=len(data),
        content_digest=digest,
    )


def register_file_ref(runtime, ref: FileRef) -> None:
    """Persist a source file reference so anchors can resolve it later.

    ``SourceAnchor.source_ref`` identifies a file and ``source_revision`` its
    digest. Without this index a later atom could not reopen the original
    workbook/JSON payload to verify an ``excel_cell`` or ``json_pointer``.

    A source identity is immutable once registered: ``(id, revision)`` may
    never be re-bound to different bytes. Otherwise a caller could parse B's
    real bytes while claiming the id/revision of an already-registered file A
    (reviewer F1, tester probe 4) and every anchor resolved through
    ``find_file_ref`` would silently read B for A.
    """

    object_id = f"{ref.id}@{ref.revision}"
    existing = runtime.versions.get("file_ref", object_id, "r1")
    if existing is not None:
        previous = FileRef.model_validate(existing)
        if previous.content_digest != ref.content_digest:
            raise invalid_input(
                f"source identity {object_id} is already bound to different "
                f"bytes ({previous.content_digest}); refusing to re-bind it "
                f"to {ref.content_digest}. Use the file's own id/revision.",
                target="file_ref",
            )
    runtime.versions.save_content_addressed(
        "file_ref", object_id, ref.model_dump(mode="json")
    )
    # r38 F5: source anchors must resolve against the cited source content.
    # The governance acceptance evaluator resolves anchors through the
    # shared content store alone (it never imports this package), so the
    # registered source bytes are also staged content-addressed under the
    # shared data_root — the digest the anchor's ``source_revision`` names.
    try:
        payload = (Path(runtime.workspace_root) / ref.locator).read_bytes()
    except OSError:
        return
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    if digest == ref.content_digest and not runtime.content.exists(digest):
        runtime.content.put(payload)


def find_file_ref(runtime, source_ref: str, source_revision: str) -> FileRef | None:
    object_id = f"{source_ref}@{source_revision}"
    payload = runtime.versions.get("file_ref", object_id, "r1")
    if payload is None:
        return None
    return FileRef.model_validate(payload)


def register_file_tables(runtime, file_ref: FileRef, table_refs: list[TableRef]) -> None:
    """Index the tables extracted from one source file (W0 §1 field identity).

    ``SourceAnchor.source_ref`` / ``source_revision`` identify a file. This
    index lets a later atom — ``define_metric_formula`` — resolve the human
    header names of that file to the stable ``field_id`` identities its
    extracted tables carry, so a metric draft cites the same field identity
    the application layer binds against (07 §11.4; tester r20 B1).
    """

    if not table_refs:
        return
    object_id = f"{file_ref.id}@{file_ref.revision}"
    payload = {
        "tables": [
            {"asset_id": t.asset.id, "revision": t.asset.revision, "data_ref": t.data_ref}
            for t in table_refs
        ]
    }
    runtime.versions.save_content_addressed("file_tables", object_id, payload)


def find_file_tables(runtime, source_ref: str, source_revision: str) -> list[dict[str, Any]]:
    """Latest registered table index of one source file (may be empty)."""

    current = runtime.versions.current("file_tables", f"{source_ref}@{source_revision}")
    if current is None:
        return []
    return list(current[1].get("tables") or [])


def file_field_map(runtime, sources: list[SourceAnchor]) -> dict[str, str]:
    """``{header name: field_id}`` resolved from the sources' extracted tables.

    Only unambiguous mappings survive: a header name that resolves to
    different ``field_id``s across the sources' registered tables is
    dropped (the draft keeps the human name in that case).
    """

    field_map: dict[str, str] = {}
    ambiguous: set[str] = set()
    seen: set[tuple[str, str]] = set()
    seen_ids: set[str] = set()
    for source in sources:
        for entry in find_file_tables(runtime, source.source_ref, source.source_revision):
            try:
                columns = runtime.content.get_json(entry["data_ref"]).get("columns") or []
            except Exception:  # noqa: BLE001 - a missing payload means no mapping
                continue
            for column in columns:
                name = column.get("name")
                field_id = column.get("field_id")
                if not name or not field_id:
                    continue
                seen_ids.add(field_id)
                if (name, field_id) in seen:
                    continue
                seen.add((name, field_id))
                if name in field_map and field_map[name] != field_id:
                    ambiguous.add(name)
                else:
                    field_map.setdefault(name, field_id)
    for name in ambiguous:
        field_map.pop(name, None)
    # A name that is also some column's field_id must not rewrite citations:
    # ids always win (a proposal citing that token means the id).
    for name in list(field_map):
        if name in seen_ids:
            field_map.pop(name)
    return field_map


def store_table(runtime, table: TableData, ctx: CallContext, *, asset_kind: str = "table") -> TableRef:
    payload = table.model_dump(mode="json")
    digest = runtime.content.put(payload)
    schema_fields = table.schema_fields()
    schema_payload = {"fields": [f.model_dump(mode="json") for f in schema_fields], "keys": []}
    schema_digest = runtime.content.put(schema_payload)
    schema_id = f"schema:{schema_digest.split(':', 1)[1][:16]}"
    revision = runtime.versions.save("schema", schema_id, schema_payload)
    asset = asset_for(digest, asset_kind, scope_of(ctx))
    return TableRef(
        asset=asset,
        schema_ref=VersionedRef(id=schema_id, revision=revision),
        data_ref=digest,
        row_identity=[c.field_id for c in table.columns[:1]] or None,
        source_map_ref=table.source_map_ref,
    )


def load_table(runtime, table_ref: TableRef) -> TableData:
    # r30 B1.2, second line of defence: the table asset must be bound to the
    # content actually read — ``data_ref`` is the asset's content (revision,
    # and digest when declared) whatever resolver string the caller chose.
    # The runtime recheck refuses this before any read; the handler refuses
    # it too, so a fabricated ``resolver`` label cannot detach the covered
    # asset from forbidden content even with the recheck disabled.
    asset = table_ref.asset
    if table_ref.data_ref != asset.revision or (
        asset.digest is not None and table_ref.data_ref != asset.digest
    ):
        raise invalid_input(
            "table_ref.data_ref is not the table asset's content "
            f"({table_ref.data_ref!r} vs revision {asset.revision!r}); refusing "
            "to read unbound table content",
            target="table_ref.data_ref",
        )
    try:
        payload = runtime.content.get_json(table_ref.data_ref)
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise invalid_input(f"table content missing: {table_ref.data_ref}") from exc
    return TableData.model_validate(payload)


def store_document_blocks(runtime, blocks: Any) -> str:
    return runtime.content.put(blocks.model_dump(mode="json"))


def store_json(runtime, payload: Any) -> str:
    return runtime.content.put(payload)


def make_anchor(
    *,
    source_ref: str,
    source_revision: str,
    page: int,
    char_start: int,
    char_end: int,
    extraction_ref: str | None = None,
) -> SourceAnchor:
    return SourceAnchor(
        source_ref=source_ref,
        source_revision=source_revision,
        selector={
            "kind": "pdf_text_span",
            "page": page,
            "char_start": char_start,
            "char_end": char_end,
        },
        extraction_ref=extraction_ref,
    )


def excel_cell_anchor(
    *, source_ref: str, source_revision: str, sheet: str, cell_range: str
) -> SourceAnchor:
    return SourceAnchor(
        source_ref=source_ref,
        source_revision=source_revision,
        selector={"kind": "excel_cell", "sheet": sheet, "range": cell_range},
    )


def row_meta(role: str, reason: str = "") -> RowMeta:
    return RowMeta(role=role, reason=reason)  # type: ignore[arg-type]


def table_from_rows(
    *,
    sheet: str,
    columns: list[str],
    rows: list[list[Any]],
    source: dict[str, Any],
    merged_ranges: list[str] | None = None,
    roles: list[RowMeta] | None = None,
    column_meta: list[TableColumn] | None = None,
    source_map_ref: str | None = None,
) -> TableData:
    if column_meta is None:
        column_meta = [
            TableColumn(
                name=str(name),
                field_id=f"c{index + 1}",
                source_path=f"{sheet}!{index + 1}",
                value_type="unknown",
            )
            for index, name in enumerate(columns)
        ]
    return TableData(
        sheet=sheet,
        columns=column_meta,
        rows=rows,
        row_meta=roles or [row_meta("detail") for _ in rows],
        merged_ranges=merged_ranges or [],
        source=source,
        source_map_ref=source_map_ref,
    )
