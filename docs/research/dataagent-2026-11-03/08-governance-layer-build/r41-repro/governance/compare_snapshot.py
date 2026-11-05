import json, hashlib, sys, os, re
from pathlib import Path
from collections import Counter
DOC = Path("/Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/catalog/atomic-capability-catalog.json")
PKG = Path("/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-governance")
cat = json.loads(DOC.read_text())
gov = [a for a in cat["atoms"] if a["layer"] == "03-governance-layer.md"]
fde = [a for a in gov if a["fde"]]
nonfde = [a for a in gov if not a["fde"]]
print("governance atoms", len(gov), "fde", len(fde), "non-fde", len(nonfde))
print("slices non-fde:", Counter(a["slice"] for a in nonfde))
s0 = [a for a in nonfde if a["slice"] == "S0"]
keys = ["group","group_name","id","name","operation","s0_family","source_file"]
expected = sorted(({k:a[k] for k in keys} for a in s0), key=lambda x:x["id"])
for snap_path in [PKG/"packaging/catalog-snapshot.json", PKG/"src/dataagent_governance/catalog-snapshot.json", PKG/"packaging/bundle/packaging/catalog-snapshot.json", PKG/"packaging/bundle/src/dataagent_governance/catalog-snapshot.json"]:
    if not snap_path.exists():
        print("MISSING", snap_path); continue
    snap = json.loads(snap_path.read_text())
    got = sorted(({k:a.get(k) for k in keys} for a in snap["atoms"]), key=lambda x:x["id"])
    extra_keys = set().union(*(set(a) for a in snap["atoms"])) - set(keys)
    print(snap_path.relative_to(PKG), "atoms", len(got), "equal:", got == expected, "extra keys:", extra_keys, "top keys:", sorted(snap))
    if got != expected:
        for e,g in zip(expected,got):
            if e!=g: print("  DIFF", e, g)
    print("   sha256", hashlib.sha256(snap_path.read_bytes()).hexdigest())
    meta = {k:v for k,v in snap.items() if k!="atoms"}
    print("   meta", json.dumps(meta, ensure_ascii=False)[:400])
print("catalog sha256", hashlib.sha256(DOC.read_bytes()).hexdigest())
# source files exist?
for a in s0:
    p = PKG / a["source_file"]
    src = p.read_text() if p.exists() else ""
    reg = re.search(r"def %s\(" % a["operation"], src) is not None
    print(a["id"], a["operation"], a["source_file"], "exists" if p.exists() else "MISSING", "def-found" if reg else "no-def")
# on-demand: which source files exist / operation defined anywhere
srcroot = PKG/"src"
alltext = "\n".join(p.read_text() for p in srcroot.rglob("*.py"))
od = [a for a in nonfde if a["slice"] != "S0"]
have_file = [a for a in od if (PKG/a["source_file"]).exists()]
have_def = [a for a in od if re.search(r"def %s\(" % a["operation"], alltext)]
print("on-demand", len(od), "source_file exists:", len(have_file), "operation def found:", len(have_def))
for a in have_file: print("  file exists:", a["id"], a["operation"], a["source_file"])
for a in have_def: print("  def:", a["id"], a["operation"])
print("on-demand groups:", Counter(a["group"] for a in od))
print("fde groups:", sorted(Counter(a["group"] for a in fde).items()))
