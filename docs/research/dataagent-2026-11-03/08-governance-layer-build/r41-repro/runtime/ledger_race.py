import os, sys, tempfile, multiprocessing as mp
from pathlib import Path
from dataagent_runtime.adapters.gold_ledger import GoldExposureLedger
D = "sha256:" + "a"*64
def worker(root, i):
    L = GoldExposureLedger(root)
    for k in range(20):
        L.note_exposure(D, purpose="p", accessed_by=f"w{i}-{k}")
if __name__ == "__main__":
    root = Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR"))) / "vault"
    L = GoldExposureLedger(root); L.register(D, set_id="s", case_id="c")
    ps = [mp.Process(target=worker, args=(root, i)) for i in range(4)]
    [p.start() for p in ps]; [p.join() for p in ps]
    print("expected exposures 80, recorded:", len(L.exposures(D)))
    # corrupt file then register another digest -> history wiped
    L.path.write_text(L.path.read_text()[:-5])
    L.register("sha256:" + "b"*64, set_id="s", case_id="c2")
    print("after truncated file + register(): registered", sorted(k[:10] for k in L._load()["registered"]), "exposures for D:", len(L.exposures(D)))
