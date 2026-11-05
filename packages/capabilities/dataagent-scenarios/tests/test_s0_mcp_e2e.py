"""S0 end-to-end over real MCP subprocesses: the three bundles (08 §8).

判定族/计算族 Skill 顺序的跨进程子集，按 Skill 步骤经 MCP 调用：

访问判定（governance ``check_access_scope``）→ 接入与抽取（data
``parse_delimited_file``）→ 规则/引擎（application ``acquire_and_align_engine``
与 ``generate_function_expressions`` 两段式）→ 验收准备（governance
``draft_acceptance_criteria`` 两段式）。

治理层与数据层 MCP 都以 ``DATAAGENT_ENFORCEMENT_MODE=enforce`` 运行，共享同一个
``data_root``（08 §2）：治理层铸出的 AccessDecision 落在共享的
``db/decisions.sqlite3``，数据层自己的复检（W1d：22 个原子带
``resource_fields``，产品路径复检，无门卫进程）就在同一文件里解析它。三个服务都
是真实子进程（NDJSON JSON-RPC over stdio），不是进程内 invoke。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

CONTEXT = {
    "request_id": "req:s0-mcp",
    "scope_ref": "tenant:demo",
    "authorization_ref": "seed",
    "subject_ref": "user:alice",
    "purpose": "monthly_report",
}


class McpServer:
    """A real MCP stdio subprocess driven line by line."""

    def __init__(self, module: str, *, cwd, env: dict[str, str] | None = None):
        self.module = module
        merged = dict(os.environ)
        merged["PYTHONDONTWRITEBYTECODE"] = "1"
        merged.update(env or {})
        self.proc = subprocess.Popen(  # noqa: SIM115 - closed in close()
            [sys.executable, "-m", module],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=str(cwd),
            env=merged,
            text=True,
        )

    def request(self, payload: dict) -> dict:
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        assert line, f"{self.module}: server closed the stream"
        return json.loads(line)

    def initialize(self) -> dict:
        response = self.request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        )
        # notifications never get a response on the wire
        assert self.proc.stdin is not None
        self.proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        self.proc.stdin.flush()
        return response["result"]["serverInfo"]

    def tools(self) -> list[dict]:
        response = self.request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        return response["result"]["tools"]

    def call(self, name: str, arguments: dict) -> dict:
        response = self.request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        assert "result" in response, response
        return json.loads(response["result"]["content"][0]["text"])

    def close(self) -> None:
        if self.proc.stdin is not None:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            self.proc.kill()


@pytest.fixture()
def workspace(tmp_path):
    (tmp_path / "orders.csv").write_bytes(
        b"order_id,region,amount\no1,north,100\no2,south,200\no3,north,300\n"
    )
    # pre-seed the governance side: a policy for alice / monthly_report, so
    # the governance server can mint access decisions from its first call
    from dataagent_governance.contracts import EgressRule, PolicyDocument, PolicyRule
    from dataagent_governance.runtime import GovernanceRuntime
    from dataagent_runtime.enforcement import EnforcementConfig

    governance = GovernanceRuntime.create(
        workspace_root=tmp_path,
        data_root=tmp_path / ".dataagent-gov",
        enforcement=EnforcementConfig(mode="enforce"),
        host_subject_ref="user:alice",
        host_purpose="monthly_report",
    )
    governance.policy.save(
        PolicyDocument(
            policy_id="tenant:default",
            revision="r1",
            rules=[
                PolicyRule(
                    rule_id="allow-s0",
                    effect="allow",
                    subjects=["user:alice"],
                    resources=["file", "table", "doc"],
                    purposes=["monthly_report"],
                ),
                PolicyRule(
                    rule_id="allow-s0-rules",
                    effect="allow",
                    subjects=["user:alice"],
                    resources=["rule"],
                    purposes=["monthly_report"],
                ),
            ],
            egress_rules=[
                # a local model may see the governed rule content; a vendor
                # API would be forced to at least allow_masked (08 §5.1)
                EgressRule(rule_id="local-ok", effect="allow", deployments=["local"]),
            ],
        )
    )
    return tmp_path


@pytest.fixture()
def servers(workspace):
    started = {
        "governance": McpServer(
            "dataagent_governance.interfaces.mcp_server",
            cwd=workspace,
            env={
                "DATAAGENT_WORKSPACE": str(workspace),
                "DATAAGENT_DATA_ROOT": str(workspace / ".dataagent-gov"),
                "DATAAGENT_ENFORCEMENT_MODE": "enforce",
            },
        ),
        "data": McpServer(
            "dataagent_data.interfaces.mcp_server",
            cwd=workspace,
            env={
                "DATAAGENT_WORKSPACE": str(workspace),
                # shared data_root + enforce: the S0 composition's data reads
                # are rechecked on the product path against the decisions the
                # governance server minted into the same db/decisions.sqlite3
                "DATAAGENT_DATA_ROOT": str(workspace / ".dataagent-gov"),
                "DATAAGENT_ENFORCEMENT_MODE": "enforce",
            },
        ),
        "application": McpServer(
            "dataagent_application.interfaces.mcp_server",
            cwd=workspace,
            env={"DATAAGENT_WORKSPACE": str(workspace)},
        ),
    }
    yield started
    for server in started.values():
        server.close()


def _file_ref(workspace, name):
    import hashlib

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


def test_three_bundles_over_mcp_in_skill_order(servers, workspace):
    # -- all three bundles are real servers with their catalog registries --
    assert servers["governance"].initialize() == {
        "name": "dataagent-governance",
        "version": "0.1.0",
    }
    assert servers["data"].initialize()["name"] == "dataagent-data"
    assert servers["application"].initialize()["name"] == "dataagent-application"

    governance_tools = servers["governance"].tools()
    data_tools = servers["data"].tools()
    application_tools = servers["application"].tools()
    assert len(governance_tools) == 6
    assert len(data_tools) == 32
    assert len(application_tools) == 13
    assert {t["name"] for t in governance_tools} >= {
        "check_access_scope",
        "check_model_context_egress",
        "draft_acceptance_criteria",
    }
    # 08 §10.1: the two DA12.1 decision atoms persist decisions, so they are
    # not annotated read-only
    annotations = {t["name"]: t["annotations"] for t in governance_tools}
    assert annotations["check_access_scope"]["readOnlyHint"] is False
    assert annotations["check_model_context_egress"]["readOnlyHint"] is False

    # -- 1. 访问判定: governance mints the AccessDecision under enforce --
    access = servers["governance"].call(
        "check_access_scope", {"resource_ref": "file@*", "context": CONTEXT}
    )
    assert access["status"] == "ok", access["issues"]
    assert access["data"]["decision"]["decision"] == "allow"
    authorization = access["data"]["decision"]["decision_id"]

    # -- 2. 接入与抽取: the data layer parses the CSV behind that decision --
    parsed = servers["data"].call(
        "parse_delimited_file",
        {
            "file_ref": _file_ref(workspace, "orders.csv"),
            "context": {**CONTEXT, "authorization_ref": authorization},
        },
    )
    assert parsed["status"] == "ok", parsed["issues"]
    assert parsed["data"]["row_count"] == 3
    table = parsed["data"]["table"]

    # under enforce the data server itself denies an unresolvable
    # authorization — before any read happens, on the product path (W1d)
    denied = servers["data"].call(
        "parse_delimited_file",
        {
            "file_ref": _file_ref(workspace, "orders.csv"),
            "context": {**CONTEXT, "authorization_ref": "ad:someone-elses"},
        },
    )
    assert denied["status"] == "failed"
    assert denied["issues"][0]["code"] == "da12.access_denied"
    assert denied["data"] is None

    # an unrelated authorization does not unlock the recheck path: the
    # governance server (enforce) refuses to mint an allow for another subject
    stranger = servers["governance"].call(
        "check_access_scope",
        {
            "resource_ref": "file@*",
            "context": {**CONTEXT, "subject_ref": "user:mallory"},
        },
    )
    assert stranger["status"] == "ok"  # business conclusion...
    # ...but no allow: no matching rule is indeterminate (folded to deny)
    assert stranger["data"]["decision"]["decision"] in {"deny", "indeterminate"}

    # -- 3. 规则与执行: the application layer aligns the expression engine
    #    (the interpreter that the two-phase flow compiles to) --
    engine = servers["application"].call(
        "acquire_and_align_engine",
        {"engine_id": "expression", "context": CONTEXT},
    )
    assert engine["status"] == "ok", engine["issues"]
    assert engine["data"]["installed_version"]

    first_phase = servers["application"].call(
        "generate_function_expressions",
        {
            "rule": {
                "statement": "报销金额不超过 5000 元时通过",
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": "报销金额不超过 5000 元",
                        "referenced_fields": ["amount"],
                    }
                ],
                "combination": "c1",
            },
            "fields": [
                {"field_id": "amount", "name": "amount", "data_type": "number"}
            ],
            "context": CONTEXT,
        },
    )
    assert first_phase["status"] == "needs_input", first_phase
    assert first_phase["issues"][0]["inference_request"] is not None

    # -- 4. 验收准备: governance runs the two-phase criteria draft --
    criteria = servers["governance"].call(
        "draft_acceptance_criteria",
        {
            "delivery_target": "报销判定",
            "context": {**CONTEXT, "authorization_ref": authorization},
        },
    )
    assert criteria["status"] == "needs_input", criteria
    assert criteria["issues"][0]["inference_request"] is not None



def _shared_root(workspace):
    return workspace / ".dataagent-gov"


def governance_content_put(workspace, payload):
    """Store governed content into the shared data_root (test-side seeding)."""

    from dataagent_runtime.adapters.local_content import LocalContentStore

    return LocalContentStore(_shared_root(workspace) / "content").put(payload)


def governance_versions_get(workspace, kind, object_id, revision):
    from dataagent_runtime.adapters.sqlite import (
        SqliteDatabase,
        SqliteVersionedRepository,
    )

    repo = SqliteVersionedRepository(
        SqliteDatabase(_shared_root(workspace) / "db" / "governance.sqlite3")
    )
    return repo.get(kind, object_id, revision)


def data_srv_table_payload(workspace, table):
    """The parsed table's payload behind its content-addressed data_ref."""

    from dataagent_runtime.adapters.local_content import LocalContentStore

    return LocalContentStore(_shared_root(workspace) / "content").get_json(table["data_ref"])


# --- full two-family chains: three real bundles → AcceptanceReport (r24 B5/B9) ---


STATEMENT = "SECRET-RULE amount is below 5000"
AST = {
    "op": "le",
    "args": [
        {"op": "field", "field_id": "amount", "condition_id": "c1"},
        {"op": "literal", "value": 5000},
    ],
}


def _enforced_app_server(workspace):
    """The application bundle under enforce, sharing the data_root."""

    return McpServer(
        "dataagent_application.interfaces.mcp_server",
        cwd=workspace,
        env={
            "DATAAGENT_WORKSPACE": str(workspace),
            "DATAAGENT_DATA_ROOT": str(workspace / ".dataagent-gov"),
            "DATAAGENT_ENFORCEMENT_MODE": "enforce",
        },
    )


def _confirm_via_cli(workspace, criteria_id, revision, digest):
    """Activate the draft through the real CLI management entry."""

    import subprocess

    from dataagent_governance.contracts import CriteriaConfirmation

    confirmation = CriteriaConfirmation(
        confirmation_id=f"conf:{criteria_id}",
        criteria_id=criteria_id,
        criteria_revision=revision,
        criteria_digest=digest,
        confirmer_ref="user:boss",
        confirmed_at="2026-11-05T00:00:00Z",
        authority_ref="tenant:owner",
    )
    body = {
        "criteria_id": criteria_id,
        "criteria_revision": revision,
        "confirmation": confirmation.model_dump(mode="json"),
    }
    proc = subprocess.run(
        [sys.executable, "-m", "dataagent_governance.interfaces.cli", "confirm-criteria"],
        input=json.dumps(body, ensure_ascii=False),
        capture_output=True,
        text=True,
        cwd=str(workspace),
        env={
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "DATAAGENT_WORKSPACE": str(workspace),
            "DATAAGENT_DATA_ROOT": str(workspace / ".dataagent-gov"),
            "DATAAGENT_CONFIRMERS": "user:boss",
        },
        timeout=60,
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    return json.loads(proc.stdout)


def test_judgment_family_three_bundle_mcp_to_acceptance_report(servers, workspace):
    """判定族完整链路（08 §10.6）：真实三 bundle MCP 子进程、enforce、未见样本.

    访问判定 → 数据层解析 → 应用层两段式表达式（enforce 下无 EgressDecision
    先脱内容）→ 真实 evaluate_scalar_expression 产物 → 判据两段式 + CLI 确认 →
    样本冻结 → evaluate_business_acceptance → AcceptanceReport（overall=pass）。
    """

    gov = servers["governance"]
    data_srv = servers["data"]
    app = _enforced_app_server(workspace)
    try:
        # 1. access decision for the file subtree (governance DA12.1.1)
        authorization = gov.call(
            "check_access_scope", {"resource_ref": "file@*", "context": CONTEXT}
        )["data"]["decision"]["decision_id"]
        ctx = {**CONTEXT, "authorization_ref": authorization}

        # 2. data layer: parse the CSV behind the recheck (real product path)
        parsed = data_srv.call(
            "parse_delimited_file",
            {"file_ref": _file_ref(workspace, "orders.csv"), "context": ctx},
        )
        assert parsed["status"] == "ok", parsed["issues"]
        table = parsed["data"]["table"]
        table_payload = data_srv_table_payload(workspace, table)

        # 3. application under enforce: no EgressDecision → content stripped
        rule = {
            "statement": STATEMENT,
            "conditions": [
                {
                    "condition_id": "c1",
                    "text": "amount <= 5000",
                    "referenced_fields": ["amount"],
                }
            ],
            "combination": "c1",
        }
        fields = [{"field_id": "amount", "value_type": "number"}]
        stripped = app.call(
            "generate_function_expressions",
            {"rule": rule, "fields": fields, "context": ctx},
        )
        assert stripped["status"] == "needs_input", stripped
        assert "SECRET-RULE" not in json.dumps(stripped, ensure_ascii=False)

        # 4. governance: access decision + EgressDecision for the rule content
        #    (the rule text is governed content; a local model destination)
        rule_digest = governance_content_put(workspace, rule)
        rule_ref = {"id": "rule:limit", "revision": rule_digest}
        rule_access = gov.call(
            "check_access_scope",
            {"resource_ref": f"rule:limit@{rule_digest}", "context": CONTEXT},
        )["data"]["decision"]["decision_id"]
        egress = gov.call(
            "check_model_context_egress",
            {
                "content_refs": [rule_ref],
                "destination": {
                    "model_ref": "model:local",
                    "deployment": "local",
                    "terms_ref": "terms:local",
                },
                "access_decision_ref": rule_access,
                "context": CONTEXT,
            },
        )
        assert egress["status"] == "ok", egress["issues"]
        assert egress["data"]["decision"]["decision"] == "allow"
        egress_decision = egress["data"]["decision"]["decision_id"]

        # 5. application: two-phase expression generation, content visible
        first = app.call(
            "generate_function_expressions",
            {
                "rule": rule,
                "rule_ref": rule_ref,
                "fields": fields,
                "egress_decision_ref": egress_decision,
                "destination": {"model_ref": "model:local", "deployment": "local"},
                "context": ctx,
            },
        )
        assert first["status"] == "needs_input", first["issues"]
        assert "SECRET-RULE" in json.dumps(first["issues"][0]["inference_request"])
        compiled = app.call(
            "generate_function_expressions",
            {
                "rule": rule,
                "rule_ref": rule_ref,
                "fields": fields,
                "egress_decision_ref": egress_decision,
                "destination": {"model_ref": "model:local", "deployment": "local"},
                "proposal": {"expression": AST},
                "context": ctx,
            },
        )
        assert compiled["status"] == "ok", compiled["issues"]
        spec = compiled["data"]["spec"]

        # 6. application: evaluate on a record built from the parsed row.
        #    The field evidence anchors at a real, content-addressed source
        #    (r38 F5: the acceptance evaluator resolves anchors against the
        #    shared content store — a label revision it cannot verify is not
        #    evidence), so the parsed row is staged as a JSON source.
        row_amount = int(table_payload["rows"][0][2])
        row_source_digest = governance_content_put(
            workspace, {"records": [{"amount": row_amount}]}
        )
        record = {
            "asset": {
                "id": "record:c1",
                "kind": "record",
                "scope_ref": "tenant:demo",
                "revision": "r1",
                "resolver": "local_content",
                "locator": "r1",
            },
            "document_ref": "doc:orders@r1",
            "target_schema_ref": "schema:orders@r1",
            "fields": [
                {
                    "field_id": "amount",
                    "status": "extracted",
                    "value": row_amount,
                    "value_type": "number",
                    "evidence": [
                        {
                            "source_ref": "content:orders-row",
                            "source_revision": row_source_digest,
                            "selector": {
                                "kind": "json_pointer",
                                "pointer": "/records/0/amount",
                            },
                        }
                    ],
                }
            ],
        }
        evaluated = app.call(
            "evaluate_scalar_expression",
            {"spec": spec, "record": record, "context": ctx},
        )
        assert evaluated["status"] == "ok", evaluated["issues"]
        assessment = evaluated["data"]["assessment"]
        # the real product verdict is gold-compatible (B5)
        assert assessment["verdict"] in {"pass", "fail", "unknown"}
        assert assessment["verdict"] == "pass"
        assert any(e["id"] == "field:amount" for e in assessment["evidence"])

        # 7. governance: two-phase criteria, CLI confirmation, isolation
        drafted = gov.call(
            "draft_acceptance_criteria",
            {"delivery_target": "amount limit judgment", "context": ctx},
        )
        assert drafted["status"] == "needs_input"
        proposal = {
            "owner_ref": "user:alice",
            "family": "judgment",
            "expected_outputs": "amount is below 5000 passes",
            "evidence_requirements": ["rule:limit"],
            "unknown_policy": "count_as_fail",
            "thresholds": {"pass_rate": 1.0},
        }
        draft = gov.call(
            "draft_acceptance_criteria",
            {"delivery_target": "amount limit judgment", "proposal": proposal, "context": ctx},
        )
        assert draft["status"] == "ok", draft["issues"]
        criteria = draft["data"]["criteria"]
        from dataagent_governance.evaluation.criteria_samples import _digest

        payload = governance_versions_get(workspace, "criteria", criteria["id"], criteria["revision"])
        active = _confirm_via_cli(
            workspace, criteria["id"], criteria["revision"], _digest(payload)
        )
        assert active["status"] == "active"

        input_digest = governance_content_put(workspace, record)
        gold_digest = governance_content_put(
            workspace,
            [
                {
                    "record_key": "c1",
                    "rule_id": "rule:limit",
                    "expected_verdict": "pass",
                    "expected_evidence_fields": ["amount"],
                }
            ],
        )
        isolated = gov.call(
            "isolate_acceptance_samples",
            {
                "cases": [
                    {
                        "case_id": "c1",
                        "input_ref": f"content:record@{input_digest}",
                        "expected_ref": f"content:gold@{gold_digest}",
                        "group_keys": {"entity": "c1"},
                    }
                ],
                "group_keys": ["entity"],
                "freeze": True,
                "context": ctx,
            },
        )
        assert isolated["status"] == "ok", isolated["issues"]
        samples = isolated["data"]["evaluation_set"]

        # 8. governance: acceptance over the *real* application delivery
        accepted = gov.call(
            "evaluate_business_acceptance",
            {
                "criteria_ref": f"{active['id']}@{active['revision']}",
                "evaluation_set_ref": f"{samples['id']}@{samples['revision']}",
                "deliveries": [{"case_id": "c1", "assessment": assessment}],
                "dependency_versions": [
                    "dataagent-data@0.1.0",
                    "dataagent-application@0.1.0",
                    "dataagent-governance@0.1.0",
                ],
                "observations": {"human_count": 0, "human_minutes": 0.0},
                "context": ctx,
            },
        )
        assert accepted["status"] == "ok", accepted["issues"]
        report = accepted["data"]["report"]
        assert report["overall"] == "pass", report
        assert report["cases"][0]["verdict"] == "pass"
        metrics = report["metrics"]
        assert metrics["quality"][0]["name"] == "pass_rate"
        assert metrics["coverage"]["covered"] == 1
        # six metric classes present; unobserved ones declared missing (B9)
        assert metrics["human"] is not None and metrics["latency_ms"] is not None
        assert metrics["cost"] is None
        assert metrics["missing_records"]
        assert any("latency" in record for record in metrics["missing_records"])
        assert any("本地样本库" in limit for limit in report["limits"])
    finally:
        app.close()


def test_compute_family_three_bundle_mcp_to_acceptance_report(servers, workspace):
    """计算族完整链路（08 §10.6）：真实三 bundle MCP 子进程、enforce、未见样本.

    访问判定 → 数据层解析 → 应用层 DuckDB 执行（真实 ComputedResult）→ 判据
    两段式 + CLI 确认 → 样本冻结 → evaluate_business_acceptance →
    AcceptanceReport（overall=pass）。
    """

    gov = servers["governance"]
    data_srv = servers["data"]
    app = _enforced_app_server(workspace)
    try:
        authorization = gov.call(
            "check_access_scope", {"resource_ref": "file@*", "context": CONTEXT}
        )["data"]["decision"]["decision_id"]
        ctx = {**CONTEXT, "authorization_ref": authorization}
        parsed = data_srv.call(
            "parse_delimited_file",
            {"file_ref": _file_ref(workspace, "orders.csv"), "context": ctx},
        )
        assert parsed["status"] == "ok", parsed["issues"]
        table = parsed["data"]["table"]
        table_payload = data_srv_table_payload(workspace, table)
        assert table_payload["columns"][2]["field_id"] == "c3"

        # access decision for the table subtree (grain/compute work on it)
        table_auth = gov.call(
            "check_access_scope", {"resource_ref": "table@*", "context": CONTEXT}
        )["data"]["decision"]["decision_id"]
        table_ctx = {**CONTEXT, "authorization_ref": table_auth}

        # application: real DuckDB execution over the parsed table (field ids!)
        sql_name = "t_" + table["asset"]["id"].split(":", 1)[1]
        executed = app.call(
            "execute_duckdb_sql",
            {
                "spec": {
                    "spec_id": "orders-total",
                    "revision": "r1",
                    "backend_kind": "sql",
                    "expression_or_call": {
                        "sql": f'SELECT SUM(c3) FROM "{sql_name}"',
                        "dialect": "duckdb",
                    },
                    "source_refs": [
                        {"id": table["asset"]["id"], "revision": table["asset"]["revision"]}
                    ],
                },
                "table_refs": [table],
                "unit": "CNY",
                "grain": "all",
                "context": ctx,
            },
        )
        assert executed["status"] == "ok", executed["issues"]
        computed = executed["data"]["result"]
        assert computed["value"] == 600.0
        assert computed["unit"] == "CNY"

        # governance: criteria → confirm → isolate → accept the real delivery
        proposal = {
            "owner_ref": "user:alice",
            "family": "compute",
            "expected_outputs": "orders amount total",
            "evidence_requirements": [str(computed["target_ref"]).split("@")[0]],
            "unknown_policy": "count_as_fail",
            "thresholds": {"pass_rate": 1.0},
        }
        draft = gov.call(
            "draft_acceptance_criteria",
            {"delivery_target": "orders total", "proposal": proposal, "context": table_ctx},
        )
        assert draft["status"] == "ok", draft["issues"]
        criteria = draft["data"]["criteria"]
        from dataagent_governance.evaluation.criteria_samples import _digest

        payload = governance_versions_get(workspace, "criteria", criteria["id"], criteria["revision"])
        active = _confirm_via_cli(
            workspace, criteria["id"], criteria["revision"], _digest(payload)
        )

        input_digest = governance_content_put(workspace, table_payload)
        gold_digest = governance_content_put(
            workspace,
            [
                {
                    "metric_id": str(computed["target_ref"]).split("@")[0],
                    "expected_value": 600.0,
                    "unit": "CNY",
                    "grain": "all",
                    "filters_applied": [],
                }
            ],
        )
        isolated = gov.call(
            "isolate_acceptance_samples",
            {
                "cases": [
                    {
                        "case_id": "c1",
                        "input_ref": f"content:table@{input_digest}",
                        "expected_ref": f"content:gold@{gold_digest}",
                        "group_keys": {"entity": "c1"},
                    }
                ],
                "group_keys": ["entity"],
                "freeze": True,
                "context": table_ctx,
            },
        )
        assert isolated["status"] == "ok", isolated["issues"]
        samples = isolated["data"]["evaluation_set"]

        accepted = gov.call(
            "evaluate_business_acceptance",
            {
                "criteria_ref": f"{active['id']}@{active['revision']}",
                "evaluation_set_ref": f"{samples['id']}@{samples['revision']}",
                "deliveries": [{"case_id": "c1", "computed_result": computed}],
                "dependency_versions": [
                    "dataagent-data@0.1.0",
                    "dataagent-application@0.1.0",
                    "dataagent-governance@0.1.0",
                ],
                "observations": {
                    "human_count": 1,
                    "human_minutes": 30.0,
                    "cost_amount": 0.5,
                    "cost_currency": "CNY",
                    "latency_ms": [120.0, 200.0, 640.0],
                },
                "context": table_ctx,
            },
        )
        assert accepted["status"] == "ok", accepted["issues"]
        report = accepted["data"]["report"]
        assert report["overall"] == "pass", report
        assert report["cases"][0]["verdict"] == "pass"
        metrics = report["metrics"]
        assert metrics["coverage"]["covered"] == 1
        # host-observed metric classes carry the real numbers (B9)
        assert metrics["human"] == {"count": 1, "minutes": 30.0, "extensions": None}
        assert metrics["cost"]["amount"] == 0.5
        assert metrics["latency_ms"]["p95"] == 640.0
        assert metrics["missing_records"] == []
    finally:
        app.close()
