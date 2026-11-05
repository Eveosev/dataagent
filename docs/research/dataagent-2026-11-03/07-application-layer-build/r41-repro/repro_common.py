"""Shared fixture for application-layer repro scripts (read-only against the repo)."""
import tempfile
from pathlib import Path

from dataagent_contracts.core import TableRef, VersionedRef
from dataagent_runtime.enforcement import EnforcementConfig
from dataagent_runtime.runtime import Runtime
from dataagent_runtime.invoke import invoke

import dataagent_application  # noqa: F401
from dataagent_application import helpers
from dataagent_application.registry import load_operations
from dataagent_application.planning.expressions import _sql_table_name

load_operations()


def make_runtime(mode="warn"):
    tmp = Path(tempfile.mkdtemp(prefix="app-repro-", dir="/tmp/claude-502/application"))
    return Runtime.create(workspace_root=tmp, data_root=tmp / "data",
                          enforcement=EnforcementConfig(mode=mode))


def ctx(**kw):
    base = {"request_id": "r1", "scope_ref": "scope-1", "authorization_ref": "authz-does-not-exist"}
    base.update(kw)
    return base


def store_table(rt, columns, rows, row_meta=None):
    payload = {"sheet": "S1", "columns": columns, "rows": rows,
               "row_meta": row_meta or [{"role": "detail", "reason": ""} for _ in rows]}
    digest = rt.content.put(payload)
    asset = helpers.asset_for(digest, "table", "scope-1")
    ref = TableRef(asset=asset, schema_ref=VersionedRef(id="schema:x", revision="r1"),
                   data_ref=digest, row_identity=[columns[0]["field_id"]])
    return ref, ref.model_dump(mode="json"), _sql_table_name(ref)


EXPENSE_COLS = [
    {"name": "部门", "field_id": "c1", "value_type": "string"},
    {"name": "金额", "field_id": "c2", "value_type": "number"},
    {"name": "日期", "field_id": "c3", "value_type": "date"},
    {"name": "状态", "field_id": "c4", "value_type": "string"},
]
EXPENSE_ROWS = [
    ["A", 100, "2026-01-01", "已支付"],
    ["A", 200, "2026-01-15", "已退款"],
    ["B", 40, "2026-01-31", "已支付"],
    ["合计", 340, None, None],
]
EXPENSE_META = [{"role": "detail"}, {"role": "detail"}, {"role": "detail"}, {"role": "total"}]

METRIC = {
    "draft_id": "draft:metric:paid", "revision": "r1", "kind": "metric",
    "definition": {
        "statement": "已支付金额之和", "measure": {"field_ref": "c2", "aggregation": "sum"},
        "grain": "c1", "additivity": "additive", "unit": "CNY",
        "filters": [{"text": "状态 = '已支付'", "referenced_fields": ["c4"]}],
        "time": {"time_field": "c3", "grain": "month"},
    },
    "scope_ref": "scope-1",
    "sources": [{"source_ref": "doc-1", "source_revision": "r1",
                 "selector": {"kind": "text_span", "unit_ref": "unit:char", "char_start": 0, "char_end": 4}}],
    "status": "validated",
}


def show(label, res):
    issues = [(i.code, i.severity.value, (i.message or "")[:160]) for i in res.issues]
    print(f"[{label}] status={res.status.value} issues={issues}")
    return res
