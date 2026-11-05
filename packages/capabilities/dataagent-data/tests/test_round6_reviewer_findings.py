"""Round 6 regressions for the three Reviewer blockers (B1-B3).

B1: a string value must match a whole token; ``"Acm"``/``"cme"`` are not
grounded by ``"Acme Inc."``.
B2: the rule-preparation page/clause/character budget must be declared as
``Completeness.extent=truncated`` plus an issue, never ``complete``.
B3: a rule condition may not drop an anchor qualifier (``department head``)
while otherwise matching the clause.

Also locks the two P1 non-blockers: numeric tokens may be followed by
punctuation, and ``record_key`` anchors one field instead of a whole row.
"""

from __future__ import annotations

import pytest
from conftest import build_pdf, build_pdf_pages, call, file_ref
from pydantic import ValidationError

from dataagent_contracts.core import (
    AssetRef,
    ExtractedRecordRef,
    FieldValue,
    SourceAnchor,
    VersionedRef,
)
from dataagent_data.contracts.layer import DocumentContent, PageContent
from dataagent_data.anchors import (
    anchor_supports_text,
    anchor_value_mismatch,
    find_value_span,
)

CLAUSE = "Claims above 5000 CNY require department head approval."


def _span_anchor(page_text: str, needle: str, *, source_ref: str, revision: str):
    start = page_text.index(needle)
    return {
        "source_ref": source_ref,
        "source_revision": revision,
        "selector": {
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": start,
            "char_end": start + len(needle),
        },
    }


def _document(workspace, runtime, ctx, lines, name="doc.pdf"):
    build_pdf(workspace / name, lines)
    parsed = call("parse_text_pdf", {"file_ref": file_ref(workspace, name)}, ctx, runtime)
    assert parsed.status.value == "ok", parsed.issues
    document = parsed.data.document
    page_text = runtime.content.get_json(document.blocks_ref)["pages"][0]["text"]
    return document, page_text


# -- B1: whole-token string values ------------------------------------------


def test_string_value_fragments_are_not_grounded_by_a_longer_token():
    text = "Vendor: Acme Inc."
    content = DocumentContent(pages=[PageContent(page=1, text=text)])
    anchor = SourceAnchor(
        source_ref="file:vendor",
        source_revision="r1",
        selector={
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": 0,
            "char_end": len(text),
        },
    )
    assert anchor_value_mismatch(content, anchor, "Acm") != ""
    assert anchor_value_mismatch(content, anchor, "cme") != ""
    assert anchor_value_mismatch(content, anchor, "Acme Inc.") == ""


def test_extract_fields_rejects_a_truncated_string_value(runtime, ctx, workspace):
    document, page_text = _document(workspace, runtime, ctx, ["Vendor: Acme Inc."])
    anchor = _span_anchor(
        page_text,
        "Acme Inc.",
        source_ref=document.original_ref.id,
        revision=document.original_ref.revision,
    )
    result = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": [
                {
                    "field_id": "vendor",
                    "name": "vendor",
                    "path": "/vendor",
                    "value_type": "string",
                }
            ],
            "proposal": [
                {
                    "field_id": "vendor",
                    "value": "Acm",
                    "value_type": "string",
                    "anchors": [anchor],
                }
            ],
        },
        ctx,
        runtime,
    )
    field = result.data.record.fields[0]
    assert field.status.value == "missing"
    assert field.value is None
    assert any(issue.code == "da02.anchor_not_found" for issue in result.issues)

    grounded = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": [
                {
                    "field_id": "vendor",
                    "name": "vendor",
                    "path": "/vendor",
                    "value_type": "string",
                }
            ],
            "proposal": [
                {
                    "field_id": "vendor",
                    "value": "Acme Inc.",
                    "value_type": "string",
                    "anchors": [anchor],
                }
            ],
        },
        ctx,
        runtime,
    )
    assert grounded.data.record.fields[0].status.value == "extracted"


def test_anchor_extracted_values_does_not_relocate_a_fragment(runtime, ctx, workspace):
    document, page_text = _document(workspace, runtime, ctx, ["Vendor: Acme Inc."])
    anchor = SourceAnchor.model_validate(
        _span_anchor(
            page_text,
            "Acme Inc.",
            source_ref=document.original_ref.id,
            revision=document.original_ref.revision,
        )
    )
    record = ExtractedRecordRef(
        asset=AssetRef(
            id="rec:fragment",
            kind="extracted_record",
            scope_ref="tenant:test",
            revision="r1",
            resolver="store",
            locator="rec/fragment",
        ),
        document_ref=document.original_ref,
        target_schema_ref=VersionedRef(id="xschema:test", revision="v1"),
        fields=[
            FieldValue(
                field_id="vendor",
                status="extracted",
                value="Acm",
                value_type="string",
                evidence=[anchor],
            )
        ],
    )
    result = call(
        "anchor_extracted_values",
        {"record": record, "document_ref": document},
        ctx,
        runtime,
    )
    field = result.data.record.fields[0]
    assert field.status.value == "missing"
    assert field.value is None
    assert "vendor" in result.data.unlocated
    assert any(issue.code == "da02.anchor_not_found" for issue in result.issues)


# -- B2: declared truncation ------------------------------------------------


def test_rule_preparation_declares_page_truncation(runtime, ctx, workspace):
    pages = [
        [f"Clause {number}: this policy clause is long enough to be collected."]
        for number in range(1, 8)
    ]
    build_pdf_pages(workspace / "long_policy.pdf", pages)
    document = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "long_policy.pdf")}, ctx, runtime
    ).data.document
    result = call(
        "define_business_rules",
        {"statement": "all clauses", "document_ref": document},
        ctx,
        runtime,
    )
    clauses = result.issues[0].inference_request["clauses"]
    assert [clause["page"] for clause in clauses] == [1, 2, 3, 4, 5]
    assert result.completeness.extent.value == "truncated"
    assert "7 pages" in (result.completeness.reason or "")
    assert result.completeness.observed == {
        "pages": 7,
        "pages_included": 5,
        "clauses": 5,
        "clauses_limit": 40,
    }
    truncated = [issue for issue in result.issues if issue.code == "da03.inference_scope_truncated"]
    assert truncated, [issue.code for issue in result.issues]
    assert truncated[0].suggested_action


def test_rule_preparation_declares_clause_and_text_truncation(runtime, ctx, workspace):
    lines = [f"Clause {number:02d}: this clause requires a review." for number in range(1, 51)]
    build_pdf_pages(workspace / "many_clauses.pdf", [lines])
    document = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "many_clauses.pdf")}, ctx, runtime
    ).data.document
    capped = call(
        "define_business_rules",
        {"statement": "all clauses", "document_ref": document},
        ctx,
        runtime,
    )
    assert len(capped.issues[0].inference_request["clauses"]) == 40
    assert capped.completeness.extent.value == "truncated"
    assert "capped at 40" in (capped.completeness.reason or "")

    long_line = "Clause 1: " + ("condition " * 40)
    build_pdf_pages(workspace / "long_clause.pdf", [[long_line]])
    long_document = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "long_clause.pdf")}, ctx, runtime
    ).data.document
    shortened = call(
        "define_business_rules",
        {"statement": "all clauses", "document_ref": long_document},
        ctx,
        runtime,
    )
    clause = shortened.issues[0].inference_request["clauses"][0]
    assert len(clause["text"]) == 300
    assert shortened.completeness.extent.value == "truncated"
    assert "capped at 300" in (shortened.completeness.reason or "")


# -- B3: no silent weakening ------------------------------------------------


def test_rule_condition_may_not_drop_an_anchor_qualifier(runtime, ctx, workspace):
    document, page_text = _document(
        workspace, runtime, ctx, ["1. Scope", CLAUSE], name="rule.pdf"
    )
    anchor = _span_anchor(
        page_text,
        CLAUSE,
        source_ref=document.original_ref.id,
        revision=document.original_ref.revision,
    )

    weakened = call(
        "define_business_rules",
        {
            "statement": "approval threshold",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": "claims above 5000 CNY require approval",
                        "anchors": [anchor],
                    }
                ],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )
    assert weakened.status.value == "needs_input"
    assert weakened.data is None
    assert any(
        issue.code == "da02.anchor_value_mismatch" and "department" in issue.message
        for issue in weakened.issues
    ), [issue.message for issue in weakened.issues]

    # A partial condition that quotes the threshold is still accepted.
    threshold_only = call(
        "define_business_rules",
        {
            "statement": "approval threshold",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": "claims above 5000 CNY",
                        "anchors": [anchor],
                    }
                ],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )
    assert threshold_only.status.value == "ok", threshold_only.issues

    # The full clause, which covers every anchor token, is accepted too.
    full = call(
        "define_business_rules",
        {
            "statement": "approval threshold",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": CLAUSE,
                        "anchors": [anchor],
                    }
                ],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )
    assert full.status.value == "ok", full.issues


# -- P1 non-blockers --------------------------------------------------------


@pytest.mark.parametrize("surface", ["Total: 200.", "Total: 200, net"])
def test_numeric_tokens_may_be_followed_by_punctuation(surface):
    content = DocumentContent(pages=[PageContent(page=1, text=surface)])
    anchor = SourceAnchor(
        source_ref="file:amount",
        source_revision="r1",
        selector={
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": 0,
            "char_end": len(surface),
        },
    )
    assert anchor_value_mismatch(content, anchor, 200) == ""
    assert find_value_span(content, 200) is not None


def test_record_key_requires_a_field_name():
    with pytest.raises(ValidationError, match="field"):
        SourceAnchor(
            source_ref="file:rows",
            source_revision="r1",
            selector={"kind": "record_key", "keys": {"id": 1}},
        )


# -- P2 trace-store findings ------------------------------------------------


def test_kernel_session_view_paginates_by_global_seq(tmp_path):
    from dataagent_data.adapters.storage.sqlite import (
        SqliteDatabase,
        SqliteTraceRepository,
    )

    repo = SqliteTraceRepository(SqliteDatabase(tmp_path / "trace.sqlite3"))
    for name in ("a", "b", "c"):
        repo.append(
            f"task:{name}",
            event_id=f"evt:{name}",
            kind="dataagent.note",
            payload={},
            ts_ms=1,
            kernel_session_id="kernel:1",
        )
    first = repo.read_by_kernel_session("kernel:1", limit=2)
    assert [record.event_id for record in first] == ["evt:a", "evt:b"]
    second = repo.read_by_kernel_session(
        "kernel:1", cursor=first[-1].seq + 1, limit=2
    )
    assert [record.event_id for record in second] == ["evt:c"]


def test_trace_retry_with_a_new_authorization_ref_is_idempotent(tmp_path):
    from dataagent_data.adapters.storage.sqlite import (
        SqliteDatabase,
        SqliteTraceRepository,
    )

    repo = SqliteTraceRepository(SqliteDatabase(tmp_path / "trace.sqlite3"))
    payload = {"authorization_ref": "auth:first", "payload": {"state": "running"}}
    record, duplicate = repo.append(
        "task:a", event_id="evt:a", kind="dataagent.note", payload=payload, ts_ms=1
    )
    assert duplicate is False
    retried, duplicate = repo.append(
        "task:a",
        event_id="evt:a",
        kind="dataagent.note",
        payload={**payload, "authorization_ref": "auth:retry"},
        ts_ms=2,
    )
    assert duplicate is True
    assert retried.event_id == record.event_id
    assert retried.ts_ms == record.ts_ms


def test_conflicting_trace_retry_does_not_write_orphan_content(runtime, ctx):
    def content_files() -> int:
        return sum(1 for path in runtime.content.root.rglob("*") if path.is_file())

    first = call(
        "append_task_event",
        {
            "task_ref": "task:a@r1",
            "event_id": "evt:conflict",
            "actor_ref": "agent:1",
            "payload": {"state": "first"},
            "kernel_session_id": "kernel:1",
        },
        ctx,
        runtime,
    )
    assert first.status.value == "ok", first.issues
    before = content_files()
    conflicting = call(
        "append_task_event",
        {
            "task_ref": "task:a@r1",
            "event_id": "evt:conflict",
            "actor_ref": "agent:1",
            "payload": {"state": "second"},
            "kernel_session_id": "kernel:1",
        },
        ctx,
        runtime,
    )
    assert conflicting.status.value == "failed"
    assert conflicting.issues[0].code == "version_conflict"
    assert content_files() == before


# -- P2: negation is clause-scoped -----------------------------------------


def test_negation_is_checked_per_clause_not_per_anchor():
    text = (
        "Claims above 5000 CNY require approval. "
        "Claims below 100 are not exempt."
    )
    content = DocumentContent(pages=[PageContent(page=1, text=text)])
    anchor = SourceAnchor(
        source_ref="file:policy",
        source_revision="r1",
        selector={
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": 0,
            "char_end": len(text),
        },
    )
    assert anchor_supports_text(content, anchor, "claims above 5000 CNY require approval") == ""
    assert (
        anchor_supports_text(
            content, anchor, "claims below 100 are not exempt"
        )
        == ""
    )
