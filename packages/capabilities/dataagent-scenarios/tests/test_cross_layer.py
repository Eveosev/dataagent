"""Cross-layer S0 chain: data layer → governance layer under enforce.

计算族链路（治理层视角，应用层完成前的可运行子集）：

CSV → ``parse_delimited_file``（数据层）→ TableRef → ``check_access_scope``
（DA12.1.1）→ ``check_result_grain_and_merge``（DA11.2.3）→
``draft_acceptance_criteria`` + 确认（DA11.5.1）→ ``isolate_acceptance_samples``
（DA11.5.6）→ ``evaluate_business_acceptance``（DA11.5.5）→ AcceptanceReport。
"""

from __future__ import annotations

import hashlib

import pytest
from dataagent_contracts.core import (
    AssetRef,
    TableRef,
    VersionedRef,
)
from dataagent_data.invoke import invoke as data_invoke
from dataagent_data.runtime import create as create_data_runtime
from dataagent_runtime.enforcement import EnforcementConfig
from dataagent_runtime.invoke import invoke as gov_invoke

from dataagent_governance.contracts import (
    CriteriaConfirmation,
    PolicyDocument,
    PolicyRule,
)
from dataagent_governance.evaluation.criteria_samples import (
    CRITERIA_KIND,
    _digest,
    confirm_acceptance_criteria,
)
from dataagent_governance.runtime import GovernanceRuntime

from dataagent_scenarios.gate import enforce_data_invoke


@pytest.fixture()
def workspace(tmp_path):
    (tmp_path / "orders.csv").write_bytes(
        b"order_id,region,amount\no1,north,100\no2,south,200\no3,north,300\n"
        b"o4,south,400\no5,north,500\no6,south,600\n"
    )
    return tmp_path


@pytest.fixture()
def data(workspace):
    return create_data_runtime(
        workspace_root=workspace, data_root=workspace / ".dataagent"
    )


@pytest.fixture()
def governance(tmp_path):
    rt = GovernanceRuntime.create(
        workspace_root=tmp_path,
        data_root=tmp_path / ".dataagent-gov",
        enforcement=EnforcementConfig(mode="enforce"),
        host_subject_ref="user:alice",
        host_purpose="monthly_report",
    )
    rt.policy.save(
        PolicyDocument(
            policy_id="tenant:default",
            revision="r1",
            rules=[
                PolicyRule(
                    rule_id="allow-files",
                    effect="allow",
                    subjects=["user:alice"],
                    resources=["file"],
                    purposes=["monthly_report"],
                ),
                PolicyRule(
                    rule_id="allow-tables",
                    effect="allow",
                    subjects=["user:alice"],
                    resources=["table"],
                    purposes=["monthly_report"],
                ),
            ],
        )
    )
    return rt


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


def _file_ref(workspace, name):
    payload = (workspace / name).read_bytes()
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    return {
        "id": f"file:{digest[7:23]}",
        "kind": "file",
        "scope_ref": "tenant:demo",
        "revision": digest,
        "resolver": "workspace",
        "locator": name,
        "digest": digest,
        "media_type": "text/csv",
        "filename": name,
        "size_bytes": len(payload),
        "content_digest": digest,
    }


def test_compute_family_chain_produces_acceptance_report(workspace, data, governance):
    # 1. data layer: parse the CSV into a TableRef, behind the DA12.1 gate
    file_authorization = gov_invoke(
        "check_access_scope", {"resource_ref": "file@*"}, ctx(), runtime=governance
    ).data.decision.decision_id
    parsed = enforce_data_invoke(
        "parse_delimited_file",
        {"file_ref": _file_ref(workspace, "orders.csv")},
        ctx(authorization_ref=file_authorization),
        runtime=data,
        resolver=governance.access_resolver,
        enforcement=EnforcementConfig(mode="enforce"),
    )
    assert parsed.status.value == "ok", parsed.issues
    table = parsed.data.table

    # cross-package content hand-off: the governance layer's content store is
    # a different data_root; the same payload hashes to the same digest
    governance.content.put(data.content.get_json(table.data_ref))

    # 2. governance: access decision for that table (DA12.1.1)
    access = gov_invoke(
        "check_access_scope",
        {"resource_ref": f"table:{table.asset.id.split(':')[-1]}@{table.asset.revision}"},
        ctx(),
        runtime=governance,
    )
    decision = access.data.decision
    assert decision.decision == "allow"

    # 3. grain check on the parsed table (DA11.2.3) under the decision.
    # The table registers under its asset-id suffix (digest-derived name).
    table_name = table.asset.id.split(":")[-1]
    grain = gov_invoke(
        "check_result_grain_and_merge",
        {
            "spec": {
                "spec_id": "spec:orders-pass-through",
                "revision": "r1",
                "backend_kind": "sql",
                "expression_or_call": {
                    # W0 §1.2: SQL references field_ids; the parsed CSV's
                    # field ids are c1/c2/c3 (order_id/region/amount)
                    "sql": f'SELECT c1, c2, c3 FROM "{table_name}"',
                    "dialect": "duckdb",
                },
                "source_refs": [str(VersionedRef(id=table.asset.id, revision=table.asset.revision))],
                "engine_binding": {"engine_id": "duckdb", "engine_version": "runtime"},
            },
            "input_tables": [table.model_dump(mode="json")],
            "output_table": table.model_dump(mode="json"),
            "declared_grain": ["c1"],
            "measure_fields": ["c3"],
            "pagination": {
                "page_size": 100,
                "pages": 1,
                "declared_total_rows": parsed.data.row_count,
            },
        },
        ctx(authorization_ref=decision.decision_id),
        runtime=governance,
    )
    assert grain.status == "ok", grain.issues
    report = grain.data.report
    assert report.overall == "pass", [i.details for i in report.items]
    assert {i.check for i in report.items} == {
        "grain_key_uniqueness",
        "join_cardinality",
        "measure_conservation",
        "pagination_completeness",
    }

    # 4. criteria + confirmation (DA11.5.1)
    drafted = gov_invoke(
        "draft_acceptance_criteria",
        {
            "delivery_target": "订单合计",
            "proposal": {
                "owner_ref": "user:alice",
                "family": "compute",
                "expected_outputs": "各区域订单金额合计",
                "evidence_requirements": ["metric:orders_total"],
                "unknown_policy": "count_as_fail",
                "thresholds": {"pass_rate": 1.0},
                "tolerance_relative": 0.0,
                "strata": ["region"],
            },
        },
        ctx(),
        runtime=governance,
    )
    assert drafted.status == "ok", drafted.issues
    ref = drafted.data.criteria
    payload = governance.versions.get(CRITERIA_KIND, ref.id, ref.revision)
    criteria = confirm_acceptance_criteria(
        governance,
        ref.id,
        ref.revision,
        CriteriaConfirmation(
            confirmation_id=f"conf:{ref.id}",
            criteria_id=ref.id,
            criteria_revision=ref.revision,
            criteria_digest=_digest(payload),
            confirmer_ref="user:boss",
            confirmed_at="2026-11-04T12:00:00Z",
            authority_ref="tenant:owner",
        ),
        authorized_confirmers={"user:boss"},
    )

    # 5. samples: the parsed table content backs every case (DA11.5.6)
    cases = []
    for index in range(6):
        cases.append(
            {
                "case_id": f"region-{index}",
                "input_ref": str(
                    VersionedRef(
                        id=f"content:{table.data_ref[7:23]}",
                        revision=table.data_ref,
                    )
                ),
                "expected_ref": str(
                    VersionedRef(
                        id=f"content:gold-{index}",
                        revision=governance.content.put(
                            [
                                {
                                    "metric_id": "metric:orders_total",
                                    "expected_value": float(100 * (index + 1)),
                                    "unit": "CNY",
                                    "grain": "每月每门店",
                                    "filters_applied": [],
                                }
                            ]
                        ),
                    )
                ),
                "group_keys": {"region": "north" if index % 2 else "south"},
            }
        )
    isolated = gov_invoke(
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
        runtime=governance,
    )
    set_ref = isolated.data.evaluation_set
    unseen = [
        c["case_id"]
        for c in governance.vault.list_cases(
            str(set_ref.id), str(set_ref.revision), "unseen_acceptance"
        )
    ]
    assert unseen

    # 6. acceptance on unseen samples (DA11.5.5)
    deliveries = []
    for index, case_id in enumerate(unseen):
        expected = 100.0 * (int(case_id.split("-")[1]) + 1)
        deliveries.append(
            {
                "case_id": case_id,
                "computed_result": {
                    "result_id": f"res:{case_id}",
                    "target_ref": "metric:orders_total@r1",
                    "form": "scalar",
                    "value": expected,
                    "unit": "CNY",
                    "grain": "每月每门店",
                    "filters_applied": [],
                    "evidence_refs": ["ev:orders.csv"],
                    "completeness": {
                        "extent": "complete_in_declared_scope",
                        "declared_scope": "全量",
                    },
                },
            }
        )
    report_result = gov_invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{criteria.id}@{criteria.revision}",
            "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
            "deliveries": deliveries,
            "dependency_versions": [
                "dataagent-data@0.1.0",
                "dataagent-governance@0.1.0",
            ],
        },
        ctx(),
        runtime=governance,
    )
    assert report_result.status == "ok", report_result.issues
    acceptance = report_result.data.report
    assert acceptance.overall == "pass"
    assert acceptance.metrics.coverage.covered == len(unseen)
    assert acceptance.metrics.quality[0].name == "pass_rate"
    assert acceptance.dependency_versions
    # 判定族的完整链路（规则 → Assessment）依赖应用层（07），在其完成后接入
    assert acceptance.limits
