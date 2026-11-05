import tempfile, pathlib
from dataagent_data.runtime import create
from dataagent_data.invoke import invoke
from dataagent_runtime.enforcement import EnforcementConfig
base=pathlib.Path(tempfile.mkdtemp(dir="/tmp/claude-502/data"))
rt=create(workspace_root=base,data_root=base/"d",enforcement=EnforcementConfig(mode="enforce"))
ctx={"request_id":"r","scope_ref":"t","authorization_ref":"anything"}
fake={"assessment_id":"asmt:forged","target_ref":"req:1@r1","verdict":"auto","basis_refs":["evidence:fabricated"],
      "dependency_refs":["table:a@r1"],"unknowns":["invoice number missing"],"next_actions":[]}
r=invoke("mark_automation_coverage",{"requirements":[{"requirement_id":"req:1","assessment":fake}]},ctx,runtime=rt)
print("coverage forged auto+unknowns:",r.status.value,"covered=",r.data.covered if r.data else r.issues)
r=invoke("identify_evidence_or_human_gaps",{"assessment":fake},ctx,runtime=rt)
print("gaps for auto+unknowns:",r.status.value,"gaps=",len(r.data.gaps))
r=invoke("resolve_decidability_cache",{"prior":fake,"current_dependencies":["table:a@r2"],"previous_dependencies":["table:a@r2"]},ctx,runtime=rt)
print("cache: prior deps a@r1, current a@r2, caller previous a@r2 ->",r.data.hit, r.data.reasons)
r=invoke("resolve_decidability_cache",{"prior":fake,"current_dependencies":["table:a@r1"]},ctx,runtime=rt)
print("cache: no statement supplied ->",r.data.hit, r.data.reasons)
print("persisted forged?", rt.versions.current("decidability_assessment","asmt:forged"))
