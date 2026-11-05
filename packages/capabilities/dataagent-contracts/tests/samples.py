"""Representative instances for every core type (round-trip fixtures)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dataagent_contracts.core import *  # noqa: F401,F403
from dataagent_contracts.core import (
    AccessDecision,
    AccessOutcome,
    AcceptanceReport,
    Assessment,
    AssetRef,
    Budget,
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    CaseResult,
    Completeness,
    CompletenessExtent,
    ComponentMeta,
    ComputedResult,
    Confidence,
    Continuation,
    CorrectionRef,
    Cost,
    Coverage,
    CriteriaRef,
    DataBatchRef,
    DocumentRef,
    DocumentUnitRef,
    EgressDecision,
    EgressOutcome,
    EvidenceRef,
    EngineBinding,
    EvidenceType,
    ExceptionClause,
    ExecutableSpec,
    ExecutionRef,
    ExtractedRecordRef,
    FieldSpec,
    FieldValue,
    FieldValueStatus,
    FileRef,
    HumanEffort,
    Issue,
    Latency,
    LifecycleStatus,
    Measure,
    MetricBundle,
    MetricDefinition,
    MetricFilter,
    MetricTime,
    PdfTextSpanSelector,
    QualityMetric,
    RuleCondition,
    RuleDefinition,
    SchemaRef,
    SemanticDraft,
    Severity,
    SourceAnchor,
    SplitRole,
    StandardErrorCode,
    Stratum,
    TableRef,
    TaskContextRef,
    TimeRange,
    TraceEventRef,
    UnknownRate,
    Verdict,
    VersionedRef,
)

NOW = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)


def anchor() -> SourceAnchor:
    return SourceAnchor(
        source_ref="file:policy",
        source_revision="sha256:aa11",
        selector=PdfTextSpanSelector(page=3, char_start=10, char_end=42),
    )


def asset(kind: str = "file", identifier: str = "asset:1") -> AssetRef:
    return AssetRef(
        id=identifier,
        kind=kind,
        scope_ref="tenant:demo/project:p1",
        revision="r1",
        resolver="store",
        locator=f"locator/{identifier}",
        digest="sha256:deadbeef",
        media_type="application/octet-stream",
    )


def completeness() -> Completeness:
    return Completeness(
        extent=CompletenessExtent.complete_in_declared_scope,
        declared_scope="declared scope",
        observed={"rows": 1},
        snapshot_consistent=True,
    )


def field_spec() -> FieldSpec:
    return FieldSpec(field_id="amount", name="金额", path="/amount", value_type="money", nullable=False, unit="CNY")


def schema_ref() -> SchemaRef:
    return SchemaRef(asset=asset("schema", "schema:1"), fields=[field_spec()], keys=[["amount"]], inference_basis="declared")


def sample_instances() -> dict[str, Any]:
    """34 concrete + 2 generic representative instances."""

    rule = RuleDefinition(
        statement="单笔金额超过 5000 元须审批。",
        conditions=[
            RuleCondition(
                condition_id="c1",
                text="单笔金额 > 5000 元",
                referenced_fields=["amount"],
                anchors=[anchor()],
            )
        ],
        combination="all(c1)",
        exceptions=[ExceptionClause(text="差旅例外", anchors=[anchor()])],
        precondition_refs=["pre:approver"],
    )
    metric = MetricDefinition(
        statement="月度净收入",
        measure=Measure(field_ref="amount", aggregation=Aggregation.sum),
        filters=[MetricFilter(text="status != refunded", referenced_fields=["status"])],
        dimensions=["store"],
        time=MetricTime(time_field="paid_at", grain="month"),
        unit="CNY",
        grain="每月每门店",
        additivity="additive",
        depends_on=[VersionedRef(id="metric:gross", revision="r1")],
    )
    metric_bundle = MetricBundle(
        quality=[QualityMetric(name="accuracy", value=0.97, numerator=97, denominator=100)],
        coverage=Coverage(covered=10, total=12),
        unknown=UnknownRate(count=1, rate=0.1),
        human=HumanEffort(count=2, minutes=15.0),
        cost=Cost(amount=1.5, currency="CNY"),
        latency_ms=Latency(p50=100.0, p95=250.0),
        strata=[Stratum(key="type=a", metrics={"accuracy": 1.0})],
        missing_records=[],
    )
    return {
        # envelope
        "CallContext": CallContext(
            request_id="req:1",
            scope_ref="tenant:demo",
            authorization_ref="policy:read",
            task_ref=VersionedRef(id="task:a", revision="r1"),
            budget=Budget(max_seconds=10, max_rows=100),
        ),
        "Issue": Issue.standard(
            StandardErrorCode.invalid_input,
            "bad input",
            severity=Severity.error,
            suggested_action="fix",
        ),
        "ExecutionRef": ExecutionRef(
            invocation_id="inv:1",
            operation="parse_regular_excel",
            capability_id="DA01.4.1",
            implementation_ref="dataagent-data@0.1.0",
            input_versions=[VersionedRef(id="file:a", revision="r1")],
            started_at=NOW,
            finished_at=NOW,
        ),
        "Continuation": Continuation(cursor="10", job_ref=None),
        "Completeness": completeness(),
        "Budget": Budget(max_seconds=10, max_rows=100, max_tokens=1000, max_cost=1.0, currency="CNY"),
        # refs
        "VersionedRef": VersionedRef(id="rule:12", revision="r2"),
        "AssetRef": asset(),
        "FileRef": FileRef(
            **asset().model_dump(),
            filename="a.xlsx",
            size_bytes=10,
            content_digest="sha256:deadbeef",
        ),
        "SourceAnchor": anchor(),
        "Selector": PdfTextSpanSelector(page=1, char_start=0, char_end=5),
        # data
        "SchemaRef": schema_ref(),
        "TableRef": TableRef(
            asset=asset("table", "table:1"),
            schema_ref=VersionedRef(id="schema:1", revision="r1"),
            data_ref="sha256:table",
            row_identity=["amount"],
            source_map_ref="mapping:1",
        ),
        "DataBatchRef": DataBatchRef(
            asset=asset("batch", "batch:1"),
            schema_ref=VersionedRef(id="schema:1", revision="r1"),
            source_ref="file:1",
            row_count=1,
            completeness=completeness(),
            inline_rows=[{"a": 1}],
        ),
        "DocumentRef": DocumentRef(
            asset=asset("document", "doc:1"),
            original_ref=VersionedRef(id="file:1", revision="r1"),
            content_type="pdf_text",
            blocks_ref="sha256:blocks",
            page_count=3,
            ocr=OcrInfo(
                engine_ref="rapidocr",
                engine_version="1.3.0",
                mean_confidence=0.95,
                low_confidence_pages=[],
            ),
        ),
        "DocumentUnitRef": DocumentUnitRef(
            asset=asset("document_unit", "unit:1"),
            parent_document_ref=VersionedRef(id="doc:1", revision="r1"),
            unit_type="clause",
            ordinal_path="3.12.2",
            title="审批",
            content_ref="sha256:unit",
            anchors=[anchor()],
            context_refs=["unit:0"],
        ),
        "ExtractedRecordRef": ExtractedRecordRef(
            asset=asset("extracted_record", "rec:1"),
            document_ref=VersionedRef(id="doc:1", revision="r1"),
            target_schema_ref=VersionedRef(id="xschema:record", revision="v3"),
            fields=[
                FieldValue(
                    field_id="amount",
                    status=FieldValueStatus.extracted,
                    value=5800,
                    value_type="money",
                    unit="CNY",
                    confidence=Confidence(score=0.97, method="llm"),
                    evidence=[anchor()],
                ),
                FieldValue(field_id="approver", status=FieldValueStatus.missing, value_type="string"),
            ],
        ),
        "FieldValue": FieldValue(
            field_id="amount",
            status=FieldValueStatus.extracted,
            value=1,
            value_type="number",
            evidence=[anchor()],
        ),
        # semantics
        "SemanticDraft": SemanticDraft(
            draft_id="draft:rule:12",
            revision="r1",
            kind="rule",
            definition=rule,
            scope_ref="tenant:demo",
            sources=[anchor()],
            status=LifecycleStatus.draft,
            effective_time=TimeRange(from_=NOW, to=None),
        ),
        "EvidenceRef": EvidenceRef(
            id="ev:1",
            evidence_type=EvidenceType.source_text,
            source_anchors=[anchor()],
            obtained_by="inv:1",
        ),
        "RuleDefinition": rule,
        "MetricDefinition": metric,
        "ExecutableSpec": ExecutableSpec(
            spec_id="spec:1",
            revision="r1",
            backend_kind="sql",
            expression_or_call={"sql": "SELECT region, SUM(amount) FROM orders GROUP BY region", "dialect": "duckdb"},
            source_refs=[VersionedRef(id="table:orders", revision="r1")],
            engine_binding=EngineBinding(engine_id="duckdb", engine_version="1.1.0"),
        ),
        "ComputedResult": ComputedResult(
            result_id="res:1",
            target_ref=VersionedRef(id="metric:1", revision="r1"),
            form="scalar",
            value=1284500.0,
            unit="CNY",
            grain="每月每门店",
            filters_applied=["status != refunded"],
            time_range=TimeRange(from_=NOW),
            semantic_versions=[VersionedRef(id="metric:1", revision="r1")],
            assumptions=["自然月"],
            certified=False,
            evidence_refs=["ev:1"],
            completeness=completeness(),
        ),
        # task
        "TaskContextRef": TaskContextRef(
            task_id="task:a",
            revision="r2",
            parent_revision="r1",
            selected_refs=[VersionedRef(id="doc:1", revision="r1")],
            assumptions=["自然月"],
            policy_refs=["policy:read"],
            unresolved=[],
        ),
        "TraceEventRef": TraceEventRef(
            event_id="evt:1",
            task_ref=VersionedRef(id="task:a", revision="r2"),
            event_type="note",
            timestamp=NOW,
            actor_ref="agent:1",
            payload_ref="sha256:payload",
            kernel_call_id="call:1",
        ),
        "CorrectionRef": CorrectionRef(
            event_id="evt:2",
            task_ref=VersionedRef(id="task:a", revision="r2"),
            event_type="correction",
            timestamp=NOW,
            actor_ref="user:1",
            payload_ref="sha256:payload2",
            target_ref=VersionedRef(id="rec:1", revision="r1"),
            field_id="amount",
            old_value=1,
            new_value=2,
            explanation="金额录错",
            scope_ref="tenant:demo",
        ),
        # evaluation
        "CriteriaRef": CriteriaRef(
            id="crit:1",
            revision="r1",
            status=LifecycleStatus.active,
            owner_ref="user:1",
            confirmation_ref="confirm:1",
            expected_outputs="逐条判定及依据",
            evidence_requirements=["定位到条款和字段"],
            unknown_policy="report_separately",
            thresholds={"accuracy": 0.95},
        ),
        "EvaluationSetRef": EvaluationSetRef(
            id="es:1",
            revision="r1",
            frozen=True,
            split_manifest_ref="manifest:1",
            counts={SplitRole.development: 10, SplitRole.unseen_acceptance: 5},
            exposure_ledger_ref="ledger:1",
        ),
        "AcceptanceReport": AcceptanceReport(
            id="report:1",
            criteria_ref=VersionedRef(id="crit:1", revision="r1"),
            evaluation_set_ref=VersionedRef(id="es:1", revision="r1"),
            target_ref=VersionedRef(id="delivery:1", revision="r1"),
            dependency_versions=[VersionedRef(id="model:1", revision="r1")],
            overall=Verdict.pass_,
            cases=[CaseResult(case_id="c1", verdict=Verdict.pass_, evidence_refs=["ev:1"])],
            metrics=metric_bundle,
            coverage_scope="s0",
            limits=[],
            run_ref="inv:9",
        ),
        "CaseResult": CaseResult(case_id="c1", verdict=Verdict.unknown, evidence_refs=["ev:1"]),
        "MetricBundle": metric_bundle,
        # governance
        "AccessDecision": AccessDecision(
            decision_id="dec:1",
            policy_ref=VersionedRef(id="policy:read", revision="r1"),
            subject_ref="agent:1",
            action="read",
            resource_ref=VersionedRef(id="file:1", revision="r1"),
            purpose="analysis",
            decision=AccessOutcome.indeterminate,
            valid_until=NOW,
            reasons=["policy missing"],
        ),
        "EgressDecision": EgressDecision(
            decision_id="egress:1",
            content_refs=[VersionedRef(id="doc:1", revision="r1")],
            destination=ModelDestination(model_ref="model:1", deployment="local"),
            decision=EgressOutcome.allow,
            access_decision_ref="dec:1",
        ),
        "ComponentMeta": ComponentMeta(
            component_id="dataagent-data",
            version="0.1.0",
            capability_ids=["DA01.4.1"],
            operations=["parse_regular_excel"],
            implementation_ref="dataagent-data@0.1.0",
            license="Apache-2.0",
            distribution=["internal", "customer_site"],
            requires_contracts=">=0.1.0,<0.2.0",
            runtime_requirements=["python>=3.11"],
        ),
        # generics
        "CapabilityResult": CapabilityResult[dict](
            status=CapabilityStatus.ok, data={"x": 1}, completeness=completeness()
        ),
        "Assessment": Assessment[str](
            assessment_id="asmt:1",
            target_ref=VersionedRef(id="rule:1", revision="r1"),
            verdict="unknown",
            basis_refs=["ev:1"],
            dependency_refs=[VersionedRef(id="rule:1", revision="r1")],
            unknowns=["missing amount"],
            next_actions=["collect evidence"],
        ),
    }
