import hashlib, tempfile, pathlib, json
import openpyxl
from dataagent_data.runtime import create
from dataagent_data.invoke import invoke
from dataagent_runtime.enforcement import EnforcementConfig
base=pathlib.Path(tempfile.mkdtemp(dir="/tmp/claude-502/data")); ws=base/"ws"; ws.mkdir()
rt=create(workspace_root=ws,data_root=base/"d",enforcement=EnforcementConfig(mode="off"))
ctx={"request_id":"r","scope_ref":"t","authorization_ref":"a"}
def fr(name, media="application/octet-stream"):
    p=(ws/name).read_bytes(); d="sha256:"+hashlib.sha256(p).hexdigest()
    return {"id":f"file:{d[7:23]}","kind":"file","scope_ref":"t","revision":d,"resolver":"workspace","locator":name,"digest":d,"media_type":media,"filename":name,"size_bytes":len(p),"content_digest":d}
def run(op, payload, show=lambda d: ""):
    r=invoke(op,payload,ctx,runtime=rt)
    extra = show(r.data) if r.data is not None else ""
    print(f"{op}: {r.status.value} {[ (i.code, i.message[:80]) for i in r.issues]} {extra}")
    return r
def rows(d):
    t=getattr(d,"table",None) or (d.tables[0] if getattr(d,"tables",None) else None)
    if t is None: return ""
    c=rt.content.get_json(t.data_ref); return f"cols={[x.get('name') for x in c.get('columns',[])]} rows={c.get('rows')[:4]}"
(ws/"empty.csv").write_bytes(b"")
run("parse_delimited_file",{"file_ref":fr("empty.csv")},rows)
(ws/"ragged.csv").write_bytes(b"a,b\n1,2,3\n4\n")
run("parse_delimited_file",{"file_ref":fr("ragged.csv")},rows)
(ws/"dup.csv").write_bytes(b"a,a,\n1,2,3\n")
run("parse_delimited_file",{"file_ref":fr("dup.csv")},rows)
(ws/"gbk.csv").write_bytes("名称,金额\n差旅,100\n".encode("gbk"))
run("parse_delimited_file",{"file_ref":fr("gbk.csv")},rows)
(ws/"scalar.json").write_bytes(b"42")
run("parse_json_records",{"file_ref":fr("scalar.json")},rows)
(ws/"recs.json").write_bytes(b'{"data":{"items":[{"a":1},{"a":2,"b":{"c":3}}]}}')
run("parse_json_records",{"file_ref":fr("recs.json"),"records_path":"/data/missing"},rows)
run("parse_json_records",{"file_ref":fr("recs.json"),"records_path":"/data/items"},rows)
(ws/"bad.jsonl").write_bytes(b'{"a":1}\n{bad\n{"a":3}\n')
run("parse_json_records",{"file_ref":fr("bad.jsonl"),"format":"jsonl"},rows)
wb=openpyxl.Workbook(); s=wb.active; s.append(["x","y"]); s.append([1,2]); wb.save(ws/"w.xlsx")
run("parse_regular_excel",{"file_ref":fr("w.xlsx"),"header_row":10},rows)
run("parse_regular_excel",{"file_ref":fr("w.xlsx"),"sheets":["Nope"]},rows)
run("parse_regular_excel",{"file_ref":fr("w.xlsx"),"header_row":0},rows)
(ws/"notx.xlsx").write_bytes(b"hello")
run("parse_regular_excel",{"file_ref":fr("notx.xlsx")},rows)
run("parse_text_pdf",{"file_ref":fr("notx.xlsx")})
run("ocr_image",{"file_ref":fr("notx.xlsx")})
