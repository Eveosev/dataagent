import sys, time, threading
sys.path.insert(0, "/tmp/claude-502/application")
from repro_common import *  # noqa
rt = make_runtime("warn")
_, tref, tname = store_table(rt, EXPENSE_COLS, EXPENSE_ROWS, EXPENSE_META)
heavy = "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 300000000) SELECT count(*) FROM r"
spec = {"spec_id": "sql:h", "revision": "r1", "backend_kind": "sql", "expression_or_call": {"sql": heavy}}
t0 = time.time()
res = invoke("execute_duckdb_sql", {"spec": spec, "table_refs": [tref], "max_seconds": 1}, ctx(), runtime=rt)
print(f"returned after {time.time()-t0:.1f}s:", res.status.value, [(i.code, i.message[:300]) for i in res.issues], flush=True)
import os; os._exit(0)
