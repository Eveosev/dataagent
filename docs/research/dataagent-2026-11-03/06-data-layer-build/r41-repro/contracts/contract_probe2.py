import warnings, json, sys
from pathlib import Path
from dataagent_contracts.core import *
from dataagent_contracts.core import AccessDecision, AccessOutcome, VersionedRef, Issue, DataBatchRef, CallContext, SemanticDraft, TraceEventType, Aggregation
ROOT = Path("/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-contracts")
sys.path.insert(0, str(ROOT/"tests"))
from samples import sample_instances
S = sample_instances()
print("== valid_until type")
d = AccessDecision(decision_id="ad:1", policy_ref="policy:p@r1", subject_ref="u", resource_ref="file@*", purpose="p", decision="allow", valid_until="2030-01-01T00:00:00Z")
print("validated type:", type(d.valid_until).__name__, d.valid_until)
c = d.model_copy(update={"valid_until": "2020-01-01T00:00:00Z"})
print("after model_copy(update=str):", type(c.valid_until).__name__)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always"); js = c.model_dump_json()
    print("dump warnings:", [str(x.message)[:120] for x in w])
from dataagent_runtime.enforcement import access_recheck, EnforcementConfig
ctx = CallContext(request_id="r", scope_ref="s", authorization_ref="ad:1", purpose="p")
try:
    print(access_recheck(ctx, lambda r: c, [VersionedRef(id="file:x", revision="r1")], config=EnforcementConfig(mode="enforce")))
except Exception as e: print("access_recheck on in-memory copy ->", type(e).__name__, e)
d.valid_until = "garbage"  # no validate_assignment
print("assignment accepted:", repr(d.valid_until), "frozen?", AccessDecision.model_config.get("frozen"), "validate_assignment?", AccessDecision.model_config.get("validate_assignment"))
print("== lax coercion (model) vs JSON schema types")
def tryv(m, data):
    try: m.model_validate(data); return "accept"
    except Exception as e: return "reject"
iss = json.loads(S["Issue"].model_dump_json())
print("Issue.retryable='yes':", tryv(Issue, {**iss, "retryable": "yes"}))
db = json.loads(S["DataBatchRef"].model_dump_json())
print("DataBatchRef.row_count='5':", tryv(DataBatchRef, {**db, "row_count": "5"}), " row_count=5.0:", tryv(DataBatchRef, {**db, "row_count": 5.0}))
print("AccessDecision.valid_until=0 (int):", tryv(AccessDecision, {**json.loads(S['AccessDecision'].model_dump_json()), "valid_until": 0}))
print("AccessDecision.valid_until=1893456000 ->", AccessDecision.model_validate({**json.loads(S['AccessDecision'].model_dump_json()), "valid_until": 1893456000}).valid_until)
print("strict JSON mode valid_until=0:", end=" ")
try: AccessDecision.model_validate_json(json.dumps({**json.loads(S['AccessDecision'].model_dump_json()), "valid_until": 0})); print("accept")
except Exception: print("reject")
sd = json.loads(S["SemanticDraft"].model_dump_json())
print("SemanticDraft status=active:", tryv(SemanticDraft, {**sd, "status": "active"}))
import jsonschema
sch = json.loads((ROOT/"schema/generated/SemanticDraft.json").read_text())
print("  schema:", "accept" if not list(jsonschema.Draft202012Validator(sch).iter_errors({**sd, "status": "active"})) else "reject")
sd2 = json.loads(S["SemanticDraft"].model_dump_json()); sd2["definition"]["combination"] = "nothing_here or c1"
print("combination 'nothing_here or c1':", tryv(SemanticDraft, sd2))
print("== open enum eviction / identity")
a = TraceEventType("acme.e0")
for i in range(1, 130): TraceEventType(f"acme.e{i}")
b = TraceEventType("acme.e0")
print("re-created after eviction: equal", a == b, "identical", a is b)
