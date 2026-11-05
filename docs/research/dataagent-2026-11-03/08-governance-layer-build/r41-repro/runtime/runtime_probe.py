import tempfile, json, os, sqlite3, traceback
from pathlib import Path
from pydantic import BaseModel
from dataagent_contracts.core import AccessDecision, AccessOutcome, CallContext, VersionedRef, EgressDecision
from dataagent_runtime import invoke, operation, reset_registry, CapabilityError
from dataagent_runtime.enforcement import EnforcementConfig, egress_check, guarded_inference, access_recheck
from dataagent_runtime.runtime import Runtime
from dataagent_runtime.adapters.sqlite import SqliteDatabase, SqliteVersionedRepository, SqliteDecisionStore
from dataagent_runtime.adapters.local_content import LocalContentStore
from dataagent_runtime.ports.tabular import decode_table_payload

tmp = Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
ENF = EnforcementConfig(mode="enforce")
rt = Runtime.create(workspace_root=tmp, data_root=tmp/"data", enforcement=ENF)
SECRET = VersionedRef(id="table:secret", revision="r1")
ALLOWED = VersionedRef(id="table:public", revision="r1")
def dec(**kw):
    base = dict(decision_id="ad:1", policy_ref=VersionedRef(id="policy:p", revision="r1"),
        subject_ref="user:alice", resource_ref=ALLOWED, purpose="report",
        decision=AccessOutcome.allow, valid_until="2030-01-01T00:00:00Z")
    base.update(kw); return AccessDecision(**base)
rt.decisions.save_access(dec())
ctx = dict(request_id="r", scope_ref="s", authorization_ref="ad:1", subject_ref="user:alice", purpose="report")

class In(BaseModel):
    source: VersionedRef
class Out(BaseModel):
    read: str
class InStr(BaseModel):
    source: str
class InDict(BaseModel):
    sources: dict[str, VersionedRef]
class Plain(BaseModel):
    x: int = 0
reset_registry()
@operation("T.1", input_model=In, output_model=Out, resource_fields=("sourcee",))
def typo_op(i, c, r): return Out(read=str(i.source))
@operation("T.2", input_model=InStr, output_model=Out, resource_fields=("source",))
def str_op(i, c, r): return Out(read=i.source)
@operation("T.3", input_model=InDict, output_model=Out, resource_fields=("sources",))
def dict_op(i, c, r): return Out(read=",".join(str(v) for v in i.sources.values()))
@operation("T.4", input_model=Plain, output_model=Out)
def whoami(i, c, r): return Out(read=f"subject={c.subject_ref} purpose={c.purpose}")
@operation("T.5", input_model=Plain, output_model=Out)
def bad_code(i, c, r): raise CapabilityError("oops", "bad")
@operation("T.6", input_model=Plain, output_model=Out)
def empty_msg(i, c, r): raise CapabilityError("da.x", "")
@operation("T.7", input_model=In, output_model=Out, resource_fields=("source",))
def normal(i, c, r): return Out(read=str(i.source))

def show(label, res):
    print(f"[{label}] status={res.status.value} data={res.data!r} issues={[ (i.code, i.message[:80]) for i in res.issues]}")
print("== R1 resource_fields typo (enforce), reading table:secret with decision for table:public")
show("typo", invoke("typo_op", {"source": "table:secret@r1"}, ctx, runtime=rt))
show("control", invoke("normal", {"source": "table:secret@r1"}, ctx, runtime=rt))
print("== R2 resource field typed str / dict container")
show("str", invoke("str_op", {"source": "table:secret@r1"}, ctx, runtime=rt))
show("dict", invoke("dict_op", {"sources": {"a": "table:secret@r1"}}, ctx, runtime=rt))
print("== R3 host authority on non-resource op")
rt2 = Runtime.create(workspace_root=tmp, data_root=tmp/"data", enforcement=ENF, host_subject_ref="user:host", host_purpose="host_purpose")
show("whoami", invoke("whoami", {}, dict(ctx, subject_ref="user:attacker", purpose="exfil"), runtime=rt2))
print("== R4 CapabilityError with non-namespaced code / empty message")
for op in ("bad_code", "empty_msg"):
    try: show(op, invoke(op, {}, ctx, runtime=rt))
    except Exception as e: print(f"[{op}] EXCEPTION ESCAPED invoke: {type(e).__name__}: {str(e).splitlines()[0]}")
print("== R5 corrupt decision row -> resolver raises")
with sqlite3.connect(tmp/"data/db/decisions.sqlite3") as c:
    c.execute("INSERT OR REPLACE INTO access_decisions(decision_id,payload) VALUES('ad:bad','{\"decision_id\":\"ad:bad\"}')")
try: show("corrupt", invoke("normal", {"source": "table:public@r1"}, dict(ctx, authorization_ref="ad:bad"), runtime=rt))
except Exception as e: print(f"[corrupt] EXCEPTION ESCAPED invoke: {type(e).__name__}")
print("== R6 recheck ignores subject when ctx.subject_ref is None, ignores scope, ignores row/field constraints")
rt.decisions.save_access(dec(decision_id="ad:bob", subject_ref="user:bob", row_constraints="region = 'north'", field_constraints=["id"]))
show("no-subject", invoke("normal", {"source": "table:public@r1"}, dict(ctx, authorization_ref="ad:bob", subject_ref=None, scope_ref="tenant:other"), runtime=rt))
print("== R7 egress_check: deny decision, content under 'statement', no content_refs")
rt.decisions.save_egress(EgressDecision(decision_id="eg:deny", content_refs=[SECRET],
    destination={"model_ref": "m", "deployment": "vendor_api"}, decision="deny", access_decision_ref="ad:1"))
req = {"kind": "x", "statement": "SECRET TEXT", "egress_decision_ref": "eg:deny",
       "destination": {"model_ref": "m", "deployment": "vendor_api"}}
o = egress_check(req, get_egress=rt.decisions.get_egress, config=ENF)
print("egress allowed:", o.allowed, "request keeps statement:", "statement" in o.request)
called = []
g = guarded_inference(lambda r: called.append(r) or {"ok": True}, get_egress=rt.decisions.get_egress, config=ENF)
print("guarded_inference result:", g(req), "model called with:", called)
print("== R8 save_content_addressed A->B->A and stale expected_revision")
repo = rt.versions
print(repo.save_content_addressed("k", "o", {"v": "A"}))
print(repo.save_content_addressed("k", "o", {"v": "B"}, expected_revision="r1"))
print("A again, expected r2:", repo.save_content_addressed("k", "o", {"v": "A"}, expected_revision="r2"))
print("current:", repo.current("k", "o"))
print("B again with stale expected r1:", repo.save_content_addressed("k", "o", {"v": "B"}, expected_revision="r1"))
print("== R9 decision overwrite")
rt.decisions.save_access(dec(decision_id="ad:x", decision=AccessOutcome.deny))
rt.decisions.save_access(dec(decision_id="ad:x", decision=AccessOutcome.allow, valid_until="2099-01-01T00:00:00Z"))
d = rt.decisions.get_access("ad:x"); print("ad:x now", d.decision.value, d.valid_until)
print("== R10 codec")
try: decode_table_payload([1,2])
except Exception as e: print("non-dict payload ->", type(e).__name__, str(e)[:90])
t = decode_table_payload({"columns":[{"field_id":"a"}], "rows":[[1],[2],[3]], "row_meta":["total", None, 5]})
print("non-dict row_meta roles:", t.row_roles, "detail_rows:", t.detail_rows())
t = decode_table_payload({"columns":[{"field_id":"a"},{"field_id":"a"}], "rows":[[1,2]]})
print("duplicate field_id accepted; row_dict:", t.row_dict(0))
print("== R11 content store does not verify digest on read")
cs = rt.content; dg = cs.put({"x": 1}); p = cs._path(dg); os.chmod(p, 0o644); p.write_bytes(b'{"x":999}')
print("get after tamper:", cs.get(dg), "exists:", cs.exists(dg))
