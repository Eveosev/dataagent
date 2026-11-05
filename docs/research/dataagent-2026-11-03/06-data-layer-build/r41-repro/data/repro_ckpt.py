import tempfile, pathlib, sqlite3
from dataagent_data.runtime import create
from dataagent_data.invoke import invoke
base=pathlib.Path(tempfile.mkdtemp(dir="/tmp/claude-502/data")); rt=create(workspace_root=base,data_root=base/"d")
ctx={"request_id":"r","scope_ref":"t","authorization_ref":"a"}
ev=lambda i: invoke("append_task_event",{"task_ref":"task:c@r1","event_id":f"e{i}","event_type":"note","actor_ref":"u","payload":{"n":i}},ctx,runtime=rt)
ev(1); ck=rt.traces.checkpoint("task:c@r1"); ev(2)
print("legit append after checkpoint -> verify:", rt.traces.verify_checkpoint(ck))
db=base/"d"/"db"/"dataagent.sqlite3"
n=lambda: sqlite3.connect(db).execute("select count(*) from checkpoints").fetchone()[0]
before=n(); rt.traces.verify_checkpoint(ck); print("checkpoint rows before/after a verify:", before, n())
# tamper event 1 payload in place
c=sqlite3.connect(db); c.execute("update trace_events set payload=replace(payload,'\"n\":1','\"n\":9') where event_id='e1'"); c.commit()
print("tampered e1 -> verify:", rt.traces.verify_checkpoint(ck))
