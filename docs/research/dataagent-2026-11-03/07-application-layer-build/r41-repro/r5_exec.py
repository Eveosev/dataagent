"""R5: execution budget and spec identity.
a) timeout: does the worker thread keep running after the budget fires?
b) two different ASTs for the same rule statement/fields get the same spec_id@revision.
c) table: pass rows + exception-exempt rows -> overall unknown.
"""
import sys, time, threading
sys.path.insert(0, "/tmp/claude-502/application")
from repro_common import *  # noqa

rt = make_runtime("warn")
_, tref, tname = store_table(rt, EXPENSE_COLS, EXPENSE_ROWS, EXPENSE_META)
heavy = (f"WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 300000000) "
         f"SELECT count(*) FROM r, {tname}")
heavy = (f"WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 300000000) "
         f"SELECT count(*) FROM r")
spec = {"spec_id": "sql:h", "revision": "r1", "backend_kind": "sql", "expression_or_call": {"sql": heavy}}
t0 = time.time()
res = invoke("execute_duckdb_sql", {"spec": spec, "table_refs": [tref], "max_seconds": 1}, ctx(), runtime=rt)
print(f"a returned after {time.time()-t0:.1f}s:", res.status.value, [i.code for i in res.issues])
time.sleep(2)
print("  live threads 2s later:", [t.name for t in threading.enumerate() if t.name != "MainThread"])

RULE = {"statement": "金额上限", "conditions": [{"condition_id": "c1", "text": "金额<=5000", "referenced_fields": ["amount"]}],
        "combination": "c1"}
FIELDS = [{"field_id": "amount", "value_type": "number"}]
def ast(v):
    return {"op": "le", "args": [{"op": "field", "field_id": "amount", "condition_id": "c1"}, {"op": "literal", "value": v}]}
s1 = invoke("generate_function_expressions", {"rule": RULE, "fields": FIELDS, "proposal": {"expression": ast(5000)}}, ctx(), runtime=rt).data.spec
s2 = invoke("generate_function_expressions", {"rule": RULE, "fields": FIELDS, "proposal": {"expression": ast(50)}}, ctx(), runtime=rt).data.spec
print("b spec ids:", f"{s1.spec_id}@{s1.revision}", f"{s2.spec_id}@{s2.revision}", "same:", (s1.spec_id, s1.revision) == (s2.spec_id, s2.revision))

_, t2, _ = store_table(rt, [{"name": "a", "field_id": "amount", "value_type": "number"}], [[10], [20], [6000]])
exc = {"spec_id": "x", "revision": "r1", "backend_kind": "expression",
       "expression_or_call": {"op": "gt", "args": [{"op": "field", "field_id": "amount"}, {"op": "literal", "value": 5000}]}}
r = invoke("evaluate_table_expression", {"spec": s1.model_dump(mode="json"), "exceptions": [exc], "table_ref": t2}, ctx(), runtime=rt)
print("c counts", r.data.counts, "overall", r.data.assessment.verdict)
