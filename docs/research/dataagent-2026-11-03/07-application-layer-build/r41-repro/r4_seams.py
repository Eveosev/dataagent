"""R4: cross-atom seams and delivery.
a) DA06.1.2 filter output cannot be satisfied by any SQL in DA06.3.1.
b) non-midnight time window accepted by a whole-day SQL predicate.
c) workbook writes '=...' strings as formulas.
d) html/docx export drops the evidence (anchor) section.
e) DA07.10.1 cannot align the engine id DA06.3.5 binds; wheel digest never verifiable.
f) malformed nested inputs map to execution_unknown instead of invalid_input.
"""
import sys, io
sys.path.insert(0, "/tmp/claude-502/application")
from repro_common import *  # noqa

rt = make_runtime("warn")
_, tref, tname = store_table(rt, EXPENSE_COLS, EXPENSE_ROWS, EXPENSE_META)
METRIC_NOF = {**METRIC, "definition": {**METRIC["definition"], "filters": []}}

# a) DA06.1.2 -> RequirementSpec.filters -> DA06.3.1
p = show("a parse_time_and_filters", invoke("parse_time_and_filters", {
    "statement": "只看已支付", "table_ref": tref,
    "proposal": {"filters": [{"field_id": "c4", "operator": "eq", "values": ["已支付"]}]}}, ctx(), runtime=rt))
flt = [f.model_dump(mode="json") for f in p.data.filters]
print("   DA06.1.2 filter text:", flt)
b = invoke("bind_metrics_and_dimensions", {"statement": "已支付金额", "table_ref": tref, "metrics": [METRIC_NOF],
    "proposal": {"metric_ids": ["draft:metric:paid"], "dimensions": [], "grain": "total"}}, ctx(), runtime=rt)
req = b.data.requirement.model_dump(mode="json", by_alias=True)
req["filters"] = flt
for sql in (f"SELECT sum(c2) FROM {tname} WHERE c4 = '已支付'", f"SELECT sum(c2) FROM {tname} WHERE c4 = '已退款'",
            f"SELECT sum(c2) FROM {tname}"):
    r = invoke("generate_single_table_sql", {"table_ref": tref, "metrics": [METRIC_NOF], "requirement": req,
                                             "proposal": {"sql": sql}}, ctx(), runtime=rt)
    print("   ", sql.split("FROM")[1].strip(), "->", r.status.value, (r.issues[0].message[:150] if r.issues else ""))

# a2) free-form metric filter text (data layer may emit text it cannot normalise)
METRIC_FREE = {**METRIC, "definition": {**METRIC["definition"], "time": None,
               "filters": [{"text": "仅统计已支付单据", "referenced_fields": ["c4"]}]}}
b2 = invoke("bind_metrics_and_dimensions", {"statement": "已支付金额", "table_ref": tref, "metrics": [METRIC_FREE],
    "proposal": {"metric_ids": ["draft:metric:paid"], "dimensions": [], "grain": "total"}}, ctx(), runtime=rt)
req2 = b2.data.requirement.model_dump(mode="json", by_alias=True)
r = invoke("generate_single_table_sql", {"table_ref": tref, "metrics": [METRIC_FREE], "requirement": req2,
                                         "proposal": {"sql": f"SELECT sum(c2) FROM {tname} WHERE c4 = '已支付'"}}, ctx(), runtime=rt)
print("a2 free-form filter, correct SQL ->", r.status.value, (r.issues[0].message[:200] if r.issues else ""))

# b) non-midnight window
req3 = dict(req, filters=[], time={"from": "2026-01-15T12:00:00+00:00", "to": "2026-02-01T00:00:00+00:00"})
METRIC_T = {**METRIC, "definition": {**METRIC["definition"], "filters": []}}
r = invoke("generate_single_table_sql", {"table_ref": tref, "metrics": [METRIC_T], "requirement": req3,
    "proposal": {"sql": f"SELECT sum(c2) FROM {tname} WHERE c3 >= '2026-01-15' AND c3 < '2026-02-01'"}}, ctx(), runtime=rt)
print("b window from 2026-01-15T12:00Z, SQL >= '2026-01-15' ->", r.status.value)
req4 = dict(req3, time={"from": "2026-01-01T00:00:00+08:00", "to": "2026-02-01T00:00:00+08:00"})
r = invoke("generate_single_table_sql", {"table_ref": tref, "metrics": [METRIC_T], "requirement": req4,
    "proposal": {"sql": f"SELECT sum(c2) FROM {tname} WHERE c3 >= '2026-01-01' AND c3 < '2026-02-01'"}}, ctx(), runtime=rt)
print("b2 +08:00 window vs naive dates ->", r.status.value)

# c) formula injection
_, t2, n2 = store_table(rt, [{"name": "名称", "field_id": "n", "value_type": "string"}], [["=HYPERLINK(\"http://x\",\"点我\")"], ["=1+1"]])
spec = {"spec_id": "sql:n", "revision": "r1", "backend_kind": "sql", "expression_or_call": {"sql": f"SELECT n FROM {n2}"}}
ex = invoke("execute_duckdb_sql", {"spec": spec, "table_refs": [t2]}, ctx(), runtime=rt)
wb = invoke("build_result_workbook", {"result": ex.data.result.model_dump(mode="json", by_alias=True)}, ctx(), runtime=rt)
from openpyxl import load_workbook
data = rt.content.get_bytes(wb.data.asset.digest) if hasattr(rt.content, "get_bytes") else None
if data is None:
    import pathlib
    data = next(p for p in pathlib.Path(rt.data_root, "content").rglob("*") if p.is_file() and p.name.startswith(wb.data.asset.digest.split(":")[1][:8]) or wb.data.asset.digest.split(":")[1] in str(p)).read_bytes()
ws = load_workbook(io.BytesIO(data))["结果"]
print("c cells:", [(c.value, c.data_type) for c in ws["A"]][1:])

# d) export drops evidence
draft = invoke("compose_document_report", {"title": "T", "conclusion": "C",
    "sections": [{"heading": "H", "body_markdown": "B", "evidence_refs": ["field:amount"]}],
    "evidence": [{"id": "field:amount", "evidence_type": "extracted_value", "value": 1, "obtained_by": "x",
                  "source_anchors": [{"source_ref": "doc-9", "source_revision": "r7",
                                      "selector": {"kind": "excel_cell", "sheet": "S1", "range": "C2"}}]}]}, ctx(), runtime=rt)
print("d md has anchor:", "doc-9@r7" in draft.data.markdown)
h = invoke("export_report_format", {"report_ref": draft.data.report_ref.model_dump(), "format": "html"}, ctx(), runtime=rt)
import pathlib
hp = [p for p in pathlib.Path(rt.data_root, "content").rglob("*") if p.is_file() and h.data.asset.digest.split(":")[1] in str(p)]
html = hp[0].read_bytes().decode() if hp else "?"
print("d html has anchor:", "doc-9" in html, "| draft.revision", draft.data.draft.revision, "report_ref.revision", draft.data.report_ref.revision)

# e) engine
show("e acquire dataagent-expression", invoke("acquire_and_align_engine", {"engine_id": "dataagent-expression"}, ctx(), runtime=rt))
import re, pathlib
lock = pathlib.Path("/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-application/uv.lock").read_text()
m = re.search(r'name = "duckdb"\nversion = "[^"]+"\n.*?wheels = \[\n\s*\{ url = "[^"]+", hash = "(sha256:[0-9a-f]+)"', lock, re.S)
show("e acquire duckdb with lock wheel hash", invoke("acquire_and_align_engine", {"engine_id": "duckdb", "wheel_digest": m.group(1)}, ctx(), runtime=rt))

# f) malformed nested inputs
show("f bind metrics bad draft", invoke("bind_metrics_and_dimensions", {"statement": "x", "metrics": [{"draft_id": "m"}],
     "proposal": {"metric_ids": ["m"], "grain": "g"}}, ctx(), runtime=rt))
show("f ambiguity bad item", invoke("identify_calculation_ambiguities", {"statement": "x", "proposal": {"items": [{"kind": "bogus"}]}}, ctx(), runtime=rt))
show("f sql bad table_ref", invoke("generate_single_table_sql", {"table_ref": {"asset": {}}, "proposal": {"sql": "SELECT 1"}}, ctx(), runtime=rt))
