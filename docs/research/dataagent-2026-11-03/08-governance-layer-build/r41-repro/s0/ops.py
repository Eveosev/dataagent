import re, pathlib
root = pathlib.Path("/Users/payne/Vibe/AgentOS/packages/capabilities")
import dataagent_data.registry as d, dataagent_application.registry as a, dataagent_governance.registry as g
for m in (d,a,g): m.load_operations()
from dataagent_runtime.registry import list_operations
reg = {}
for s in list_operations():
    layer = s.source_file.split("/")[1].replace("dataagent_","") if s.source_file.startswith("src/") else "?"
    reg[s.operation] = (layer, s.capability_id, tuple(getattr(s,"resource_fields",()) or ()), getattr(s,"read_only",None))
from collections import Counter
print("counts:", Counter(v[0] for v in reg.values()))
for op,(l,c,rf,ro) in sorted(reg.items(), key=lambda x:(x[1][0],x[0])):
    if l!="data": print(f"  {l:12} {c:10} {op:35} rf={rf}")
files = sorted((root/"dataagent-s0/skills").rglob("SKILL.md")) + [root/"dataagent-s0/README.md"]
for b in ("data","application","governance"):
    files += sorted((root/f"dataagent-{b}/packaging/bundle/skills").rglob("SKILL.md"))
for f in files:
    text = f.read_text()
    names = sorted(set(re.findall(r"`([a-z][a-z0-9_]+)`", text)))
    print("==", f.relative_to(root))
    print("  ops:", [f"{n}[{reg[n][0]}]" for n in names if n in reg])
    print("  other snake tokens:", [n for n in names if n not in reg and "_" in n])
