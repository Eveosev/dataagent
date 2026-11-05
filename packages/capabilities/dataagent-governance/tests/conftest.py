from __future__ import annotations

import pytest

from dataagent_contracts.core import VersionedRef
from dataagent_runtime.enforcement import EnforcementConfig

from dataagent_governance.contracts import PolicyDocument, PolicyRule, EgressRule
from dataagent_governance.runtime import GovernanceRuntime


@pytest.fixture()
def rt(tmp_path):
    runtime = GovernanceRuntime.create(
        workspace_root=tmp_path,
        data_root=tmp_path / ".dataagent",
        enforcement=EnforcementConfig(mode="enforce"),
        host_subject_ref="user:alice",
        host_purpose="monthly_report",
    )
    runtime.policy.save(POLICY)
    return runtime


POLICY = PolicyDocument(
    policy_id="tenant:default",
    revision="r1",
    rules=[
        PolicyRule(
            rule_id="allow-orders",
            effect="allow",
            subjects=["user:alice"],
            resources=["table:orders"],
            purposes=["monthly_report"],
            field_constraints=["region", "amount"],
            masking_obligations=["mask:phone"],
            sensitive_fields=["contact_phone"],
        ),
        PolicyRule(
            rule_id="deny-secrets",
            effect="deny",
            subjects=["*"],
            resources=["secret:*"],
            purposes=["*"],
        ),
        PolicyRule(
            rule_id="allow-tables",
            effect="allow",
            subjects=["user:alice"],
            resources=["table"],
            purposes=["monthly_report"],
            masking_obligations=["mask:phone"],
        ),
        PolicyRule(
            rule_id="deny-bob",
            effect="deny",
            subjects=["user:bob"],
            resources=["table:*"],
            purposes=["*"],
        ),
    ],
    egress_rules=[
        EgressRule(rule_id="local-ok", effect="allow", deployments=["local"]),
        EgressRule(rule_id="private-ok", effect="allow", deployments=["private_cloud"]),
        EgressRule(rule_id="vendor-api", effect="allow", deployments=["vendor_api"]),
    ],
)


def content_ref(runtime, payload) -> VersionedRef:
    digest = runtime.content.put(payload)
    return VersionedRef(id=f"content:{digest[7:23]}", revision=digest)


def source_anchor(runtime, payload, pointer="/records/0/amount") -> dict:
    """A source anchor that actually resolves (r38 F5).

    The acceptance evaluator only accepts evidence whose source anchors
    resolve against content the shared store holds; tests stage a real
    JSON source content-addressed and point at it with a json pointer.
    """

    digest = runtime.content.put(payload)
    return {
        "source_ref": f"content:{digest[7:23]}",
        "source_revision": digest,
        "selector": {"kind": "json_pointer", "pointer": pointer},
    }


def orders_table(rows=None):
    return {
        "sheet": "orders",
        "columns": [
            {"name": "order_id", "field_id": "c1"},
            {"name": "region", "field_id": "c2"},
            {"name": "amount", "field_id": "c3"},
            {"name": "contact_phone", "field_id": "c4"},
        ],
        "rows": rows
        if rows is not None
        else [
            ["o1", "north", 100, "13800138000"],
            ["o2", "south", 200, "user@example.com"],
            ["o3", "north", 300, "no-sensitive-value"],
        ],
        "row_meta": [],
        "merged_ranges": [],
        "source": {"origin": "fixture"},
    }
