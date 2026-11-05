"""R2: no application operation declares resource_fields -> DA12.1 access recheck never runs,
even in enforce mode with an authorization_ref that resolves to nothing; also no closure check
(asset revision vs data_ref)."""
import sys
sys.path.insert(0, "/tmp/claude-502/application")
from repro_common import *  # noqa
from dataagent_runtime.registry import list_operations

rt = make_runtime("enforce")
ref, tref, tname = store_table(rt, EXPENSE_COLS, EXPENSE_ROWS, EXPENSE_META)
print("ops with resource_fields:", [s.operation for s in list_operations() if s.resource_fields])

spec = {"spec_id": "sql:x", "revision": "r1", "backend_kind": "sql",
        "expression_or_call": {"sql": f"SELECT c1, c2, c4 FROM {tname}"}}
res = show("execute enforce, unknown authz", invoke("execute_duckdb_sql", {
    "spec": spec, "table_refs": [tref]}, ctx(authorization_ref="nope"), runtime=rt))
print("   rows=", res.data.row_count)

# closure: asset claims another digest, data_ref points to the real table
other_digest = rt.content.put({"columns": [{"field_id": "z"}], "rows": []})
forged = dict(tref)
forged["asset"] = dict(tref["asset"], revision=other_digest, digest=other_digest, locator=other_digest)
show("evaluate_table forged closure", invoke("evaluate_table_expression", {
    "spec": {"spec_id": "e", "revision": "r1", "backend_kind": "expression",
             "expression_or_call": {"op": "gt", "args": [{"op": "field", "field_id": "c2"}, {"op": "literal", "value": 0}]}},
    "table_ref": forged}, ctx(authorization_ref="nope"), runtime=rt))
