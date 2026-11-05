"""R6: fixed filter whose referenced_fields is empty (data layer emits [] when the field cannot be resolved)
is silently dropped by DA06.3.1."""
import sys
sys.path.insert(0, "/tmp/claude-502/application")
from repro_common import *  # noqa
rt = make_runtime("warn")
_, tref, tname = store_table(rt, EXPENSE_COLS, EXPENSE_ROWS, EXPENSE_META)
M = {**METRIC, "definition": {**METRIC["definition"], "time": None,
     "filters": [{"text": "支付状态 = '已支付'", "referenced_fields": []}]}}
b = invoke("bind_metrics_and_dimensions", {"statement": "已支付金额", "table_ref": tref, "metrics": [M],
    "proposal": {"metric_ids": ["draft:metric:paid"], "dimensions": [], "grain": "total"}}, ctx(), runtime=rt)
show("bind", b)
req = b.data.requirement.model_dump(mode="json", by_alias=True)
for sql in (f"SELECT sum(c2) FROM {tname}", f"SELECT sum(c2) FROM {tname} WHERE c4 = '已支付'"):
    r = invoke("generate_single_table_sql", {"table_ref": tref, "metrics": [M], "requirement": req, "proposal": {"sql": sql}}, ctx(), runtime=rt)
    print(sql.split("FROM")[1].strip(), "->", r.status.value, r.issues[0].message[:140] if r.issues else "")
