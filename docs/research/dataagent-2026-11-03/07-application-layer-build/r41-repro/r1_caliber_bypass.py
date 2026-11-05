"""R1: caliber checks of DA06.3.1 are bypassable.
a) execute_duckdb_sql accepts any SQL spec + caller-stamped semantic_versions/filters_applied.
b) generate_single_table_sql without `requirement` skips caliber binding.
c) requirement with filters stripped (metric still carries the fixed filter) passes.
d) requirement.metrics points at a metric not passed in `metrics` -> measure check skipped.
"""
import sys
sys.path.insert(0, "/tmp/claude-502/application")
from repro_common import *  # noqa

rt = make_runtime("warn")
_, tref, tname = store_table(rt, EXPENSE_COLS, EXPENSE_ROWS, EXPENSE_META)

# a) forge a spec, skip DA06.3.1 entirely
spec = {"spec_id": "sql:forged", "revision": "r1", "backend_kind": "sql",
        "expression_or_call": {"sql": f"SELECT sum(c2) FROM {tname}"}}
res = show("a execute forged spec", invoke("execute_duckdb_sql", {
    "spec": spec, "table_refs": [tref], "semantic_versions": [{"id": "draft:metric:paid", "revision": "r1"}],
    "filters_applied": ["状态 = '已支付'"], "grain": "total"}, ctx(), runtime=rt))
r = res.data.result
print("   value=", r.value, "semantic_versions=", [str(v) for v in r.semantic_versions],
      "filters_applied=", r.filters_applied, "engine_binding=", r.engine_binding)
print("   (bound caliber = paid only = 140; delivered 340 under the metric version)")

# b) no requirement -> no caliber check
res = show("b gen SQL without requirement", invoke("generate_single_table_sql", {
    "table_ref": tref, "metrics": [METRIC],
    "proposal": {"sql": f"SELECT max(c2) FROM {tname} WHERE c4 = '已退款'"}}, ctx(), runtime=rt))

# c) requirement with filters stripped
bound = invoke("bind_metrics_and_dimensions", {
    "statement": "已支付金额", "table_ref": tref, "metrics": [METRIC],
    "proposal": {"metric_ids": ["draft:metric:paid"], "dimensions": [], "grain": "total"}}, ctx(), runtime=rt)
req = bound.data.requirement.model_dump(mode="json", by_alias=True)
print("   bound filters:", req["filters"])
req_stripped = dict(req, filters=[])
show("c requirement.filters stripped", invoke("generate_single_table_sql", {
    "table_ref": tref, "metrics": [METRIC], "requirement": req_stripped,
    "proposal": {"sql": f"SELECT sum(c2) FROM {tname}"}}, ctx(), runtime=rt))

# d) metrics list omitted -> measure binding skipped
show("d metrics omitted", invoke("generate_single_table_sql", {
    "table_ref": tref, "metrics": [], "requirement": req,
    "proposal": {"sql": f"SELECT max(c3) FROM {tname} WHERE c4 = '已支付'"}}, ctx(), runtime=rt))

# e) blocking ambiguity in requirement does not stop SQL generation
req_blocking = dict(req, ambiguities=[{"ambiguity_id": "a1", "kind": "time_boundary",
    "description": "no window", "result_impact": "x", "blocking": True}], unresolved=["time window"])
show("e blocking ambiguity", invoke("generate_single_table_sql", {
    "table_ref": tref, "metrics": [METRIC], "requirement": req_blocking,
    "proposal": {"sql": f"SELECT sum(c2) FROM {tname} WHERE c4 = '已支付'"}}, ctx(), runtime=rt))
