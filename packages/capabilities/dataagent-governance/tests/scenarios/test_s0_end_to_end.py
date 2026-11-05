"""S0 end-to-end scenarios inside the governance layer (08 §10.6).

The full cross-layer skill chains (判定族/计算族, data → application →
governance) live in ``packages/capabilities/dataagent-scenarios`` once the
application layer exists. These scenarios cover the governance-internal
chain under ``enforcement = enforce``:

判定族: access decision → criteria draft → confirmation → sample isolation
        → acceptance report on unseen samples.
计算族: access decision → egress decision (masked to vendor_api) → grain and
        merge check → acceptance report.
"""

from __future__ import annotations

from dataagent_contracts.core import VersionedRef
from dataagent_runtime.enforcement import (
    EGRESS_REQUIRED_CODE,
    egress_check,
)
from dataagent_runtime.invoke import invoke

from dataagent_governance.evaluation.criteria_samples import (
    CRITERIA_KIND,
    _digest,
    confirm_acceptance_criteria,
)
from tests.conftest import content_ref


def _table_authorization(rt):
    granted = invoke(
        "check_access_scope", {"resource_ref": "table@*"}, ctx(), runtime=rt
    )
    return granted.data.decision.decision_id


def ctx(**over):
    base = {
        "request_id": "req:1",
        "scope_ref": "tenant:demo",
        "authorization_ref": "seed",
        "subject_ref": "user:alice",
        "purpose": "monthly_report",
    }
    base.update(over)
    return base


def _activate(rt, proposal):
    drafted = invoke(
        "draft_acceptance_criteria",
        {"delivery_target": "t", "proposal": proposal},
        ctx(),
        runtime=rt,
    )
    assert drafted.status == "ok", drafted.issues
    ref = drafted.data.criteria
    payload = rt.versions.get(CRITERIA_KIND, ref.id, ref.revision)
    from dataagent_governance.contracts import CriteriaConfirmation

    confirmation = CriteriaConfirmation(
        confirmation_id=f"conf:{ref.id}",
        criteria_id=ref.id,
        criteria_revision=ref.revision,
        criteria_digest=_digest(payload),
        confirmer_ref="user:boss",
        confirmed_at="2026-11-04T12:00:00Z",
        authority_ref="tenant:owner",
    )
    return confirm_acceptance_criteria(
        rt, ref.id, ref.revision, confirmation, authorized_confirmers={"user:boss"}
    )


def test_judgment_family_scenario(rt):
    # 1. access decision for the record table
    access = invoke(
        "check_access_scope", {"resource_ref": "table:claims@r1"}, ctx(), runtime=rt
    )
    assert access.data.decision.decision == "allow"

    # 2. criteria draft + confirmation
    criteria = _activate(
        rt,
        {
            "owner_ref": "user:alice",
            "family": "judgment",
            "expected_outputs": "报销判定",
            "evidence_requirements": ["rule:amount_limit"],
            "unknown_policy": "count_as_fail",
            "thresholds": {"pass_rate": 0.8},
            "strata": ["region"],
        },
    )

    # 3. sample isolation with freeze
    cases = []
    for i in range(9):
        cases.append(
            {
                "case_id": f"claim:{i}",
                "input_ref": str(content_ref(rt, {"record": f"claim:{i}"})),
                "expected_ref": str(
                    content_ref(
                        rt,
                        [
                            {
                                "record_key": f"claim:{i}",
                                "rule_id": "rule:amount_limit",
                                "expected_verdict": "pass",
                                "expected_evidence_fields": ["amount"],
                            }
                        ],
                    )
                ),
                "group_keys": {"region": "north" if i % 2 else "south"},
            }
        )
    isolated = invoke(
        "isolate_acceptance_samples",
        {
            "cases": cases,
            "group_keys": ["region"],
            "role_weights": {
                "development": 0.45,
                "regression": 0.1,
                "unseen_acceptance": 0.45,
            },
            "freeze": True,
        },
        ctx(),
        runtime=rt,
    )
    set_ref = isolated.data.evaluation_set
    assert set_ref.frozen

    # 4. acceptance on unseen samples only
    unseen = [
        c["case_id"]
        for c in rt.vault.list_cases(
            str(set_ref.id), str(set_ref.revision), "unseen_acceptance"
        )
    ]
    assert unseen
    deliveries = [
        {
            "case_id": c,
            "assessment": {
                "assessment_id": f"as:{c}",
                "target_ref": f"record:{c}@r1",
                "verdict": "pass",
                "basis_refs": ["rule:amount_limit:amount"],
            },
        }
        for c in unseen
    ]
    report = invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{criteria.id}@{criteria.revision}",
            "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
            "deliveries": deliveries,
        },
        ctx(),
        runtime=rt,
    )
    assert report.status == "ok", report.issues
    data = report.data.report
    assert data.overall == "pass"
    assert data.metrics.coverage.covered == len(unseen)
    # six metric classes populated, limits state the local-vault caveat
    assert data.metrics.quality and data.metrics.coverage and data.metrics.unknown
    assert data.metrics.human is not None and data.metrics.latency_ms is not None
    assert data.limits


def test_compute_family_scenario_with_masked_egress_and_grain_check(rt):
    # 1. access decision
    access = invoke(
        "check_access_scope", {"resource_ref": "table:orders@r1"}, ctx(), runtime=rt
    )
    assert access.data.decision.decision == "allow"

    # 2. egress to a vendor API with sensitive content: masked only
    orders = {
        "sheet": "orders",
        "columns": [
            {"name": "order_id", "field_id": "order_id"},
            {"name": "region", "field_id": "region"},
            {"name": "amount", "field_id": "amount"},
            {"name": "contact_phone", "field_id": "contact_phone"},
        ],
        "rows": [["o1", "north", 100, "13800138000"]],
    }
    content = content_ref(rt, orders)
    egress = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(content)],
            "destination": {"model_ref": "model:gpt", "deployment": "vendor_api"},
            "access_decision_ref": access.data.decision.decision_id,
        },
        ctx(),
        runtime=rt,
    )
    assert egress.data.decision.decision == "allow_masked"

    def load_masked(masking_ref):
        revision = rt.versions.current("mask", masking_ref)[0]
        artifact = rt.versions.get("mask", masking_ref, revision)
        return rt.content.get_json(artifact["masked_content_ref"])

    outcome = egress_check(
        {
            "content": orders,
            "content_refs": [str(content)],
            "destination": {"model_ref": "model:gpt", "deployment": "vendor_api"},
            "egress_decision_ref": egress.data.decision.decision_id,
        },
        get_egress=rt.decisions.get_egress,
        load_masked=load_masked,
    )
    assert outcome.allowed and outcome.masked
    assert "13800138000" not in str(outcome.request["content"])

    # 3. grain and merge check on the delivery output
    regions = content_ref(
        rt,
        {
            "sheet": "regions",
            "columns": [{"name": "region", "field_id": "region"}],
            "rows": [["north"]],
        },
    )
    from dataagent_contracts.core import AssetRef, TableRef

    def as_table(name, payload, digest):
        asset = AssetRef(
            id=f"table:{name}",
            kind="table",
            scope_ref="tenant:demo",
            revision=digest,
            resolver="local_content",
            locator=digest,
            digest=digest,
        )
        return TableRef(
            asset=asset,
            schema_ref=VersionedRef(id=f"schema:{name}", revision="r1"),
            data_ref=digest,
        )

    orders_table = as_table("orders", orders, str(content).split("@")[-1])
    regions_table = as_table("regions", {}, str(regions).split("@")[-1])
    output = as_table(
        "out",
        {},
        rt.content.put(
            {
                "sheet": "out",
                "columns": [
                    {"name": "order_id", "field_id": "order_id"},
                    {"name": "region", "field_id": "region"},
                    {"name": "amount", "field_id": "amount"},
                ],
                "rows": [["o1", "north", 100]],
            }
        ),
    )
    grain = invoke(
        "check_result_grain_and_merge",
        {
            "spec": {
                "spec_id": "spec:orders-total",
                "revision": "r1",
                "backend_kind": "sql",
                "expression_or_call": {
                    "sql": "SELECT o.order_id, o.region, o.amount FROM orders o "
                    "JOIN regions r ON o.region = r.region",
                    "dialect": "duckdb",
                },
                "source_refs": [str(content)],
            },
            "input_tables": [orders_table, regions_table],
            "output_table": output,
            "declared_grain": ["order_id"],
            "measure_fields": ["amount"],
            "pagination": {"page_size": 100, "pages": 1, "declared_total_rows": 1},
        },
        ctx(authorization_ref=_table_authorization(rt)),
        runtime=rt,
    )
    assert grain.status == "ok", grain.issues
    assert grain.data.report.overall == "pass"

    # 4. acceptance over the computed delivery
    criteria = _activate(
        rt,
        {
            "owner_ref": "user:alice",
            "family": "compute",
            "expected_outputs": "订单合计",
            "evidence_requirements": ["metric:orders_total"],
            "unknown_policy": "count_as_fail",
            "thresholds": {"pass_rate": 1.0},
            "tolerance_relative": 0.0,
            "strata": ["region"],
        },
    )
    cases = [
        {
            "case_id": f"compute:{i}",
            "input_ref": str(content_ref(rt, {"table": f"t{i}"})),
            "expected_ref": str(
                content_ref(
                    rt,
                    [
                        {
                            "metric_id": "metric:orders_total",
                            "expected_value": 100.0,
                            "unit": "CNY",
                            "grain": "每月每门店",
                            "filters_applied": [],
                        }
                    ],
                )
            ),
            "group_keys": {"region": "north"},
        }
        for i in range(6)
    ]
    isolated = invoke(
        "isolate_acceptance_samples",
        {
            "cases": cases,
            "group_keys": ["region"],
            "role_weights": {
                "development": 0.34,
                "regression": 0.33,
                "unseen_acceptance": 0.33,
            },
            "freeze": True,
        },
        ctx(),
        runtime=rt,
    )
    set_ref = isolated.data.evaluation_set
    unseen = [
        c["case_id"]
        for c in rt.vault.list_cases(
            str(set_ref.id), str(set_ref.revision), "unseen_acceptance"
        )
    ]
    deliveries = [
        {
            "case_id": c,
            "computed_result": {
                "result_id": f"res:{c}",
                "target_ref": "metric:orders_total@r1",
                "form": "scalar",
                "value": 100.0,
                "unit": "CNY",
                "grain": "每月每门店",
                "filters_applied": [],
                "evidence_refs": ["ev:grain"],
                "completeness": {
                    "extent": "complete_in_declared_scope",
                    "declared_scope": "全量",
                },
            },
        }
        for c in unseen
    ]
    report = invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{criteria.id}@{criteria.revision}",
            "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
            "deliveries": deliveries,
        },
        ctx(),
        runtime=rt,
    )
    assert report.status == "ok", report.issues
    assert report.data.report.overall == "pass"


def test_enforce_mode_rejects_reads_without_covering_decision(rt):
    """Access recheck in front of resource reads (08 §4.3, enforce)."""

    # A resource-reading operation called with an unrelated authorization_ref
    # is rejected even though the operation itself is valid.
    result = invoke(
        "check_result_grain_and_merge",
        {
            "spec": {
                "spec_id": "spec:x",
                "revision": "r1",
                "backend_kind": "sql",
                "expression_or_call": {"sql": "SELECT 1"},
            },
            "input_tables": [
                {
                    "asset": {
                        "id": "table:orders",
                        "kind": "table",
                        "scope_ref": "tenant:demo",
                        "revision": "r1",
                        "resolver": "local_content",
                        "locator": "r1",
                    },
                    "schema_ref": "schema:orders@r1",
                    "data_ref": "r1",
                }
            ],
            "output_table": {
                "asset": {
                    "id": "table:out",
                    "kind": "table",
                    "scope_ref": "tenant:demo",
                    "revision": "r1",
                    "resolver": "local_content",
                    "locator": "r1",
                },
                "schema_ref": "schema:out@r1",
                "data_ref": "r1",
            },
            "declared_grain": ["k"],
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"
