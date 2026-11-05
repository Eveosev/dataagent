from pydantic import BaseModel
from dataagent_contracts.core import VersionedRef, CallContext
from dataagent_runtime import invoke, operation, reset_registry
from dataagent_runtime.enforcement import EnforcementConfig
import tempfile, os
from pathlib import Path
from dataagent_runtime.runtime import Runtime
tmp = Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
rt = Runtime.create(workspace_root=tmp, data_root=tmp/"d", enforcement=EnforcementConfig(mode="enforce"))
class P(BaseModel): x: int = 0
class Out(BaseModel): total: int
class LD(BaseModel): tables: list[dict]
reset_registry()
@operation("T.1", input_model=P, output_model=Out)
def wrong_out(i, c, r): return {"anything": "goes"}
@operation("T.2", input_model=LD, output_model=Out, resource_fields=("tables",))
def list_dict(i, c, r): return Out(total=len(i.tables))
ctx = dict(request_id="r", scope_ref="s", authorization_ref="ad:none", purpose="p")
res = invoke("wrong_out", {}, ctx, runtime=rt); print("wrong output type ->", res.status.value, res.data)
res = invoke("list_dict", {"tables": [{"asset": {"id": "table:secret", "revision": "r1"}}]}, ctx, runtime=rt)
print("list[dict] resource field, unresolvable authorization_ref, enforce ->", res.status.value, [i.code for i in res.issues])
