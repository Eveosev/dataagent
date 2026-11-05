"""Enforce mode: a decision covering ONLY orders.csv; read secret.xlsx through workbook_ref / region."""
import hashlib, sys, tempfile, pathlib, json
import openpyxl
from dataagent_contracts.core import AccessDecision, AccessOutcome, VersionedRef
from dataagent_data.runtime import create
from dataagent_data.invoke import invoke
from dataagent_runtime.enforcement import EnforcementConfig

base = pathlib.Path(tempfile.mkdtemp(dir="/tmp/claude-502/data"))
ws = base / "ws"; ws.mkdir()
(ws / "orders.csv").write_bytes(b"a,b\n1,2\n")
wb = openpyxl.Workbook(); sh = wb.active; sh.title = "Payroll"
sh.append(["name", "salary"]); sh.append(["alice", 99999]); sh.append(["bob", 88888])
wb.save(ws / "secret.xlsx")

def fref(name, media):
    p = (ws / name).read_bytes(); d = "sha256:" + hashlib.sha256(p).hexdigest()
    return {"id": f"file:{d[7:23]}", "kind": "file", "scope_ref": "tenant:t/project:p", "revision": d,
            "resolver": "workspace", "locator": name, "digest": d, "media_type": media,
            "filename": name, "size_bytes": len(p), "content_digest": d}

orders = fref("orders.csv", "text/csv")
secret = fref("secret.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
rt = create(workspace_root=ws, data_root=base / "data", enforcement=EnforcementConfig(mode="enforce"))
rt.decisions.save_access(AccessDecision(decision_id="ad:orders", policy_ref=VersionedRef(id="policy:t", revision="r1"),
    subject_ref="user:alice", resource_ref=VersionedRef(id=orders["id"], revision="*"), purpose="report",
    decision=AccessOutcome.allow, valid_until="2030-01-01T00:00:00Z"))
ctx = {"request_id": "r", "scope_ref": "tenant:t/project:p", "authorization_ref": "ad:orders",
       "subject_ref": "user:alice", "purpose": "report"}

def show(label, r):
    print(label, r.status.value, [i.code for i in r.issues])
    return r

show("control: inspect via file_ref=secret ->", invoke("inspect_workbook_calc_state", {"file_ref": secret}, ctx, runtime=rt))
r = show("bypass: inspect via workbook_ref=secret ->", invoke("inspect_workbook_calc_state", {"workbook_ref": {"file_ref": secret, "sheets": []}}, ctx, runtime=rt))
r2 = show("bypass: detect_regions via workbook_ref=secret ->", invoke("detect_workbook_regions", {"workbook_ref": {"file_ref": secret, "sheets": []}}, ctx, runtime=rt))
if r2.data:
    regions = r2.data.regions
    print("   regions:", [x.cell_range for x in regions])
    reg = regions[0].model_dump(mode="json")
    r3 = show("bypass: recover_headers via region=secret ->", invoke("recover_headers", {"region": reg}, ctx, runtime=rt))
    if r3.data:
        d = r3.data.model_dump(mode="json")
        print("   leaked:", json.dumps(d, ensure_ascii=False)[:600])
