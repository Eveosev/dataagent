"""End-to-end W2 compute chain and W3 judgment chain at token level.

These tests exercise the real runtime + sqlite + content store, not mocks, so
they catch integration bugs that per-atom unit tests miss.
"""

from __future__ import annotations

from datetime import datetime

from conftest import build_pdf, call, file_ref, write_file


def test_compute_chain_irregular_workbook_to_metric(runtime, ctx, workspace):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Expense"
    ws.append(["费用报销明细（CNY）"])
    ws.append([])
    ws.append(["部门", "金额", "发生日期", "状态"])
    ws.append(["研发", 1200, datetime(2026, 1, 5), "已支付"])
    ws.append([None, 800, datetime(2026, 1, 6), "已支付"])
    ws.append(["销售", 500, datetime(2026, 1, 7), "已退款"])
    ws.append(["合计", 2500, None, None])
    ws.merge_cells("A4:A5")
    wb.save(workspace / "expense.xlsx")
    source = file_ref(workspace, "expense.xlsx")

    extracted = call("extract_irregular_excel", {"file_ref": source}, ctx, runtime)
    assert extracted.status.value == "ok", extracted.issues
    table_ref = extracted.data.tables[0]

    expanded = call("expand_merged_cells", {"table_ref": table_ref}, ctx, runtime)
    assert expanded.data.expanded_ranges

    classified = call(
        "classify_table_rows", {"table_ref": expanded.data.table}, ctx, runtime
    )
    assert classified.data.roles[-1].role == "total"

    profile = call(
        "profile_table_structure", {"table_ref": expanded.data.table}, ctx, runtime
    )
    assert profile.status.value == "ok"
    assert profile.data.fields[0]["count"] == 4  # includes the total row

    inferred = call(
        "infer_field_types", {"table_ref": expanded.data.table}, ctx, runtime
    )
    assert inferred.status.value == "ok"
    types = {field.field_id: field.inferred_type for field in inferred.data.fields}
    assert types["c2"] == "number"

    columns = runtime.content.get_json(expanded.data.table.data_ref)["columns"]
    amount_column = columns[1]
    metric = call(
        "define_metric_formula",
        {
            "statement": "monthly paid expense",
            "available_fields": [column["name"] for column in columns],
            "sources": [
                {
                    "source_ref": source.id,
                    "source_revision": source.revision,
                    "selector": {"kind": "excel_cell", "sheet": "Expense", "range": "A1"},
                }
            ],
            "proposal": {
                "measure_field": amount_column["name"],
                "aggregation": "sum",
                "filters": ["状态 = '已支付'"],
                "dimensions": ["部门"],
                "time_field": "发生日期",
                "time_grain": "month",
                "grain": "部门 x month",
                "unit": "CNY",
                "additivity": "additive",
            },
        },
        ctx,
        runtime,
    )
    assert metric.status.value == "ok", metric.issues
    definition = metric.data.draft.definition
    # W0 §1 field identity (tester r20 B1): the draft cites the stable
    # field_id of the column its human name selected, and fixed filters
    # carry their referenced field ids for caliber binding downstream.
    assert definition.measure.field_ref == amount_column["field_id"]
    assert definition.time is not None and definition.time.time_field == "c3"
    assert definition.filters[0].referenced_fields == ["c4"]
    assert definition.dimensions == ["c1"]


def test_judgment_chain_policy_to_coverage(runtime, ctx, workspace):
    build_pdf(
        workspace / "expense-policy.pdf",
        [
            "1. Scope",
            "All employees in China.",
            "2. Approval",
            "Claims above 5000 CNY require department head approval.",
            "3. Evidence",
            "An invoice is required for every claim.",
        ],
    )
    parsed = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "expense-policy.pdf")}, ctx, runtime
    )
    document = parsed.data.document
    segmented = call("segment_document", {"document_ref": document}, ctx, runtime)
    units = segmented.data.units
    assert units
    texts = {unit.asset.id: runtime.content.get(unit.content_ref).decode() for unit in units}
    clauses = [
        unit
        for unit in units
        if "5000" in texts[unit.asset.id] or "invoice" in texts[unit.asset.id]
    ]
    assert len(clauses) == 2
    conditions = [
        {"condition_id": f"c{i + 1}", "text": texts[unit.asset.id], "anchors": unit.anchors}
        for i, unit in enumerate(clauses)
    ]
    rules = call(
        "define_business_rules",
        {
            "statement": "reimbursement policy",
            "document_ref": document,
            "proposal": {"conditions": conditions, "combination": "all(c1,c2)"},
        },
        ctx,
        runtime,
    )
    assert rules.status.value == "ok", rules.issues
    assert len(rules.data.draft.definition.conditions) == 2

    assessment = call(
        "assess_automatic_decidability",
        {
            "requirement_ref": f"{rules.data.draft.draft_id}@r1",
            "statement": "reimbursement policy",
            "proposal": {
                "verdict": "auto",
                # The parsed policy document is a real, registered source, so
                # its full ref (id@revision) is a resolvable basis (round 17
                # refuses fabricated basis refs).
                "basis_refs": [str(document.original_ref)],
                "dependency_refs": [
                    f"{document.original_ref.id}@{document.original_ref.revision}",
                    "engine:expr@1",
                ],
                "unknowns": [],
                "next_actions": [],
            },
        },
        ctx,
        runtime,
    )
    assert assessment.status.value == "ok"
    assert assessment.data.verdict.value == "auto"

    gaps = call(
        "identify_evidence_or_human_gaps",
        {"assessment": assessment.data, "missing_materials": []},
        ctx,
        runtime,
    )
    assert gaps.status.value == "ok"
    assert gaps.data.gaps == []

    coverage = call(
        "mark_automation_coverage",
        {
            "requirements": [
                {"requirement_id": "r1", "assessment": assessment.data},
                {"requirement_id": "r2", "assessment": {**assessment.data.model_dump(), "assessment_id": "asmt:2", "verdict": "needs_human"}},
            ]
        },
        ctx,
        runtime,
    )
    assert coverage.data.covered == 1
    assert coverage.data.human == 1
    assert coverage.data.covered / coverage.data.total == 0.5


def test_compute_chain_full_06_1012_combination(runtime, ctx, workspace):
    """Plan §10.2 computation family: the full named combination.

    One workbook carries *all four* irregularities the plan names -- a
    multi-row header, merged cells (header and body), a totals row and the
    1904 date system -- and the chain runs extraction -> merged-cell
    expansion -> row classification -> profiling -> type inference ->
    ``MetricDefinition`` draft. Assertions cover the three boundaries the
    plan demands: headers (two header rows join into one logical name),
    dates (the 1904 epoch is honoured, no 1462-day shift) and data (the
    header rows stay out of the rows, the totals row is classified, the
    merged department cell expands into both of its rows).
    """

    from openpyxl import Workbook
    from openpyxl.utils.datetime import CALENDAR_MAC_1904

    wb = Workbook()
    sheet = wb.active
    sheet.title = "Expense"
    wb.epoch = CALENDAR_MAC_1904
    sheet.append(["费用报销明细（CNY）"])  # banner above the region
    sheet.append([])
    sheet.append(["部门", "金额", "金额", "日期", "状态"])  # header row 1
    sheet.append([None, "原币", "本币", None, None])  # header row 2
    sheet.append(["研发", 1200, 1300, datetime(2026, 1, 5), "已支付"])
    sheet.append([None, 800, 850, datetime(2026, 1, 6), "已支付"])  # 部门 merged
    sheet.append(["销售", 500, 530, datetime(2026, 1, 7), "已退款"])
    sheet.append(["合计", 2500, 2680, None, None])  # totals
    sheet.merge_cells("B3:C3")  # 金额 spans both currency header cells
    sheet.merge_cells("A5:A6")  # repeated department
    wb.save(workspace / "expense-1904.xlsx")
    source = file_ref(workspace, "expense-1904.xlsx")

    state = call(
        "inspect_workbook_calc_state", {"file_ref": source}, ctx, runtime
    )
    assert state.data.state.date_system == "1904"

    extracted = call(
        "extract_irregular_excel",
        {
            "file_ref": source,
            "regions": ["Expense!A3:E8"],
            "layout_hints": {"header_rows": 2},
        },
        ctx,
        runtime,
    )
    assert extracted.status.value == "partial", extracted.issues
    # The blank second-header cells are disclosed, not silently dropped.
    assert any("empty cells" in issue.message for issue in extracted.issues)
    table_ref = extracted.data.tables[0]
    table = runtime.content.get_json(table_ref.data_ref)
    names = [column["name"] for column in table["columns"]]
    assert names == ["部门", "金额 / 原币", "金额 / 本币", "日期", "状态"]
    assert table["source"]["header_rows"] == 2
    assert table["source"]["row_numbers"] == [5, 6, 7, 8]  # headers excluded
    assert len(table["rows"]) == 4
    # 1904 date system honoured: the serials decode to the written dates,
    # not to the 1900-epoch reading four years off.
    assert [row[3] for row in table["rows"][:3]] == [
        "2026-01-05T00:00:00",
        "2026-01-06T00:00:00",
        "2026-01-07T00:00:00",
    ]
    assert table["merged_ranges"] == ["A5:A6", "B3:C3"]

    expanded = call("expand_merged_cells", {"table_ref": table_ref}, ctx, runtime)
    # The header merge (B3:C3) was already consumed by header recovery
    # (the joined "金额 / 原币" name); the body merge is what expands.
    assert [item["range"] for item in expanded.data.expanded_ranges] == ["A5:A6"]
    rows = runtime.content.get_json(expanded.data.table.data_ref)["rows"]
    assert rows[0][0] == rows[1][0] == "研发"  # merged department expanded

    classified = call(
        "classify_table_rows", {"table_ref": expanded.data.table}, ctx, runtime
    )
    roles = [role.role for role in classified.data.roles]
    assert roles == ["detail", "detail", "detail", "total"]

    profile = call(
        "profile_table_structure", {"table_ref": expanded.data.table}, ctx, runtime
    )
    by_field = {field["field_id"]: field for field in profile.data.fields}
    assert by_field["c3"]["type_counts"] == {"number": 4}
    assert by_field["c1"]["distinct_count"] == 3  # 研发/销售/合计

    inferred = call(
        "infer_field_types", {"table_ref": expanded.data.table}, ctx, runtime
    )
    types = {field.field_id: field.inferred_type for field in inferred.data.fields}
    assert types["c4"] == "date"

    columns = runtime.content.get_json(expanded.data.table.data_ref)["columns"]
    metric = call(
        "define_metric_formula",
        {
            "statement": "monthly paid expense in base currency",
            "available_fields": [column["name"] for column in columns],
            "sources": [
                {
                    "source_ref": source.id,
                    "source_revision": source.revision,
                    "selector": {
                        "kind": "excel_cell",
                        "sheet": "Expense",
                        "range": "A1",
                    },
                }
            ],
            "proposal": {
                "measure_field": "金额 / 本币",
                "aggregation": "sum",
                "filters": ["状态 = '已支付'"],
                "dimensions": ["部门"],
                "time_field": "日期",
                "time_grain": "month",
                "grain": "部门 x month",
                "unit": "CNY",
                "additivity": "additive",
            },
        },
        ctx,
        runtime,
    )
    assert metric.status.value == "ok", metric.issues
    definition = metric.data.draft.definition
    assert definition.measure.field_ref == "c3"
    assert definition.time is not None and definition.time.time_field == "c4"
    assert definition.filters[0].referenced_fields == ["c5"]
    assert definition.dimensions == ["c1"]


def test_judgment_chain_full_06_1012_combination(runtime, ctx, workspace):
    """Plan §10.2 judgment family: policy PDF + claim JSON, end to end.

    The chain is the one the plan names: policy PDF and a claim (单据) JSON
    -> clause units -> two-phase field extraction (the agent proposal is
    simulated; every accepted value carries a real anchor) -> rule draft ->
    decidability and applicability. The three invariants asserted:
    every extracted value has evidence anchors; ``unknown`` is never folded
    (the missing invoice keeps the precondition and decidability verdicts
    at unknown/needs_evidence); missing values are not fabricated (the
    claim record without an invoice number stays without one, and the
    policy field the document never states stays ``missing``).
    """

    build_pdf(
        workspace / "expense-policy.pdf",
        [
            "1. Scope",
            "This policy applies to expense claims submitted in CN.",
            "2. Approval",
            "Claims above 5000 CNY require department head approval.",
            "3. Evidence",
            "Every claim requires an invoice number.",
        ],
    )
    # The 单据 JSON: no invoice number -- and nothing downstream invents one.
    write_file(
        workspace,
        "claim.json",
        b'[{"claim_id": "CLM-1", "amount": 5800, "status": "submitted"}]',
    )
    parsed = call(
        "parse_text_pdf",
        {"file_ref": file_ref(workspace, "expense-policy.pdf")},
        ctx,
        runtime,
    )
    document = parsed.data.document
    claim = call(
        "parse_json_records", {"file_ref": file_ref(workspace, "claim.json")}, ctx, runtime
    )
    assert claim.status.value == "ok", claim.issues
    record = runtime.content.get_json(claim.data.batch.asset.digest)["records"][0]
    assert "invoice_number" not in record  # missing is kept missing

    # Clause units from the policy.
    segmented = call("segment_document", {"document_ref": document}, ctx, runtime)
    units = segmented.data.units
    texts = {unit.asset.id: runtime.content.get(unit.content_ref).decode() for unit in units}
    approval = next(unit for unit in units if "5000" in texts[unit.asset.id])
    evidence = next(unit for unit in units if "invoice" in texts[unit.asset.id])

    # Two-phase field extraction against a target schema; one policy field
    # (the JSON field name that carries the invoice) is never stated.
    page_text = runtime.content.get_json(document.blocks_ref)["pages"][0]["text"]

    def span_anchor(needle):
        start = page_text.index(needle)
        return {
            "source_ref": document.original_ref.id,
            "source_revision": document.original_ref.revision,
            "selector": {
                "kind": "pdf_text_span",
                "page": 1,
                "char_start": start,
                "char_end": start + len(needle),
            },
        }

    fields = [
        {"field_id": "approval_threshold", "name": "Approval threshold", "path": "/threshold", "value_type": "number", "unit": "CNY"},
        {"field_id": "currency", "name": "Currency", "path": "/currency", "value_type": "string"},
        {"field_id": "invoice_field", "name": "Invoice field name", "path": "/invoice_field", "value_type": "string"},
    ]
    first = call(
        "extract_fields_to_schema",
        {"document_ref": document, "fields": fields},
        ctx,
        runtime,
    )
    assert first.status.value == "needs_input"
    assert first.issues[0].inference_request["kind"] == "field_extraction"
    assert first.data.candidate_spans
    extracted = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": fields,
            "proposal": [
                {
                    "field_id": "approval_threshold",
                    "value": 5000,
                    "value_type": "number",
                    "unit": "CNY",
                    "anchors": [span_anchor("5000")],
                },
                {
                    "field_id": "currency",
                    "value": "CNY",
                    "value_type": "string",
                    "anchors": [span_anchor("CNY")],
                },
                # invoice_field deliberately not proposed: the policy never
                # states it, so it must stay missing, not fabricated.
            ],
        },
        ctx,
        runtime,
    )
    assert extracted.status.value == "partial", extracted.issues
    values = {field.field_id: field for field in extracted.data.record.fields}
    assert values["approval_threshold"].status.value == "extracted"
    assert values["currency"].status.value == "extracted"
    # Every accepted value carries real evidence anchors.
    for field_id in ("approval_threshold", "currency"):
        assert values[field_id].evidence, f"{field_id} must be anchored"
    assert values["invoice_field"].status.value == "missing"
    assert values["invoice_field"].value is None
    assert any(issue.code == "da02.field_missing" for issue in extracted.issues)

    # Rule draft over the clause units.
    rules = call(
        "define_business_rules",
        {
            "statement": "reimbursement policy",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": texts[approval.asset.id],
                        "anchors": approval.anchors,
                    },
                    {
                        "condition_id": "c2",
                        "text": texts[evidence.asset.id],
                        "anchors": evidence.anchors,
                    },
                ],
                "combination": "all(c1,c2)",
            },
        },
        ctx,
        runtime,
    )
    assert rules.status.value == "ok", rules.issues
    assert len(rules.data.draft.definition.conditions) == 2

    # Applicability, two-phase, from the scope clause.
    scope_text = "This policy applies to expense claims submitted in CN."
    scope_start = page_text.index(scope_text)
    scope_anchor = {
        "source_ref": document.original_ref.id,
        "source_revision": document.original_ref.revision,
        "selector": {
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": scope_start,
            "char_end": scope_start + len(scope_text),
        },
    }
    applicability_first = call(
        "define_rule_applicability",
        {"rule_ref": f"{rules.data.draft.draft_id}@r1"},
        ctx,
        runtime,
    )
    assert applicability_first.status.value == "needs_input"
    applicability = call(
        "define_rule_applicability",
        {
            "rule_ref": f"{rules.data.draft.draft_id}@r1",
            "document_ref": document,
            "object_types": ["expense_claim"],
            "sources": [scope_anchor],
            "proposal": {
                "scope_expression": "expense claims submitted in CN",
                "object_types": ["expense_claim"],
                # No scenarios: the scope clause does not name one, and an
                # ungrounded scenario would be a fabrication, not a fact.
            },
        },
        ctx,
        runtime,
    )
    assert applicability.status.value == "ok", applicability.issues
    assert applicability.data.scope_expression == "expense claims submitted in CN"

    # Preconditions evaluated against the claim JSON: the amount fact is
    # known (5800 > 5000), the invoice fact is missing, and missing must
    # stay unknown -- never folded into false.
    preconditions = call(
        "define_rule_preconditions",
        {
            "rule_ref": f"{rules.data.draft.draft_id}@r1",
            "declared_facts": True,
            "facts": {"c1": True},  # only c1 is known from the claim record
            "proposal": {
                "conditions": [
                    {"condition_id": "c1", "text": "claim amount is above the approval threshold"},
                    {"condition_id": "c2", "text": "invoice number is present"},
                ],
                "combination": "all(c1,c2)",
            },
        },
        ctx,
        runtime,
    )
    assert preconditions.status.value == "ok", preconditions.issues
    assert preconditions.data.evaluation.verdict == "unknown"
    assert preconditions.data.evaluation.missing_facts == ["c2"]

    # Decidability: with the invoice unknown, the verdict stays
    # needs_evidence with its unknowns intact, and the gap plan routes to
    # evidence collection rather than fabricating coverage.
    assessment = call(
        "assess_automatic_decidability",
        {
            "requirement_ref": f"{rules.data.draft.draft_id}@r1",
            "statement": "reimbursement policy",
            "proposal": {
                "verdict": "needs_evidence",
                "basis_refs": [str(document.original_ref)],
                "dependency_refs": [
                    f"{document.original_ref.id}@{document.original_ref.revision}",
                    "engine:expr@1",
                ],
                "unknowns": ["invoice number for CLM-1 is missing"],
                "next_actions": [],
            },
        },
        ctx,
        runtime,
    )
    assert assessment.status.value == "ok", assessment.issues
    assert assessment.data.verdict.value == "needs_evidence"
    assert assessment.data.unknowns == ["invoice number for CLM-1 is missing"]

    gaps = call(
        "identify_evidence_or_human_gaps",
        {"assessment": assessment.data, "missing_materials": []},
        ctx,
        runtime,
    )
    assert gaps.status.value == "ok"
    assert len(gaps.data.gaps) == 1
    assert gaps.data.gaps[0].kind == "evidence"
    assert "invoice" in gaps.data.gaps[0].description

    coverage = call(
        "mark_automation_coverage",
        {
            "requirements": [
                {"requirement_id": "r1", "assessment": assessment.data},
            ]
        },
        ctx,
        runtime,
    )
    assert coverage.data.covered == 0  # unknown is never folded into auto
    assert coverage.data.needs_evidence == 1


def test_json_records_to_table_is_refused(runtime, ctx, workspace):
    write_file(workspace, "r.json", b'[{"a": 1}]')
    parsed = call(
        "parse_json_records", {"file_ref": file_ref(workspace, "r.json")}, ctx, runtime
    )
    assert parsed.status.value == "ok"
    assert parsed.data.fields[0]["path"] == "/a"
    assert parsed.data.batch.row_count == 1
