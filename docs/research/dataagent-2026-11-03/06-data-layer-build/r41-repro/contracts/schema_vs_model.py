import json, sys, copy
from pathlib import Path
import jsonschema
from jsonschema import Draft202012Validator, FormatChecker
ROOT = Path("/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-contracts")
sys.path.insert(0, str(ROOT/"src")); sys.path.insert(0, str(ROOT/"tests"))
from dataagent_contracts import core
from samples import sample_instances
S = sample_instances()
def schema(n): return json.loads((ROOT/"schema/generated"/f"{n}.json").read_text())
def jcheck(n, inst, fmt=False):
    v = Draft202012Validator(schema(n), format_checker=FormatChecker() if fmt else None)
    errs = list(v.iter_errors(inst)); return "accept" if not errs else "reject"
def mcheck(n, inst):
    m = getattr(core, n)
    if n=="CapabilityResult": m = core.CapabilityResult[dict]
    if n=="Assessment": m = core.Assessment[str]
    try: m.model_validate(inst); return "accept"
    except Exception as e: return "reject"
def probe(label, n, mutate, fmt=False):
    inst = json.loads(S[n].model_dump_json()) if not isinstance(S[n], dict) else copy.deepcopy(S[n])
    mutate(inst)
    print(f"{label:55s} model={mcheck(n,inst):6s} schema={jcheck(n,inst,fmt)}")
print("additionalProperties on CallContext:", schema("CallContext").get("additionalProperties"))
def setk(k,v):
    def f(d): d[k]=v
    return f
probe("CallContext extensions key not namespaced", "CallContext", setk("extensions", {"vendor_field": 1}))
probe("CallContext unknown top-level field", "CallContext", setk("foo", 1))
probe("Issue.code non-namespaced 'oops'", "Issue", setk("code","oops"))
probe("Issue.code colon 'da02:x'", "Issue", setk("code","da02:x"))
probe("CallContext.deadline naive '2026-01-01T00:00:00'", "CallContext", setk("deadline","2026-01-01T00:00:00"))
probe("  same, with FormatChecker", "CallContext", setk("deadline","2026-01-01T00:00:00"), fmt=True)
probe("CallContext.deadline 'not-a-date'", "CallContext", setk("deadline","not-a-date"))
def agg(d): d["measure"]["aggregation"]="acme.weighted_mean"
probe("MetricDefinition aggregation acme.weighted_mean", "MetricDefinition", agg)
probe("EvidenceRef evidence_type acme.foo", "EvidenceRef", setk("evidence_type","acme.foo"))
probe("TraceEventRef event_type acme.foo", "TraceEventRef", setk("event_type","acme.foo"))
def capr(d): d["status"]="failed"; d["issues"]=[]; 
probe("CapabilityResult failed w/o issues", "CapabilityResult", capr)
def rows(d): d["inline_rows"]=[{"a":1}]*501
probe("DataBatchRef inline_rows=501", "DataBatchRef", rows)
def bbox(d): d["selector"]={"kind":"pdf_bbox","page":1,"bbox":[10,10,0,0],"unit":"pt"}
probe("SourceAnchor bbox inverted", "SourceAnchor", bbox)
probe("VersionedRef-bearing: AccessDecision policy_ref 'a@b@c'", "AccessDecision", setk("policy_ref","a@b@c"))
def cr(d): d["status"]="active"; d["confirmation_ref"]=None
probe("CriteriaRef active w/o confirmation", "CriteriaRef", cr)
def cnt(d): d["counts"]={"unseen_acceptance": -1}
probe("EvaluationSetRef counts negative", "EvaluationSetRef", cnt)
def comb(d): d["definition"]["combination"]="c1 and anything_else"
if "SemanticDraft" in S: probe("SemanticDraft combination unknown token 'anything_else'", "SemanticDraft", comb)
def comb2(d): d["definition"]["combination"]="c1 and zzz"
if "SemanticDraft" in S: probe("SemanticDraft combination unknown token 'zzz'", "SemanticDraft", comb2)
def kindent(d): d["kind"]="entity"
if "SemanticDraft" in S: probe("SemanticDraft kind=entity with RuleDefinition", "SemanticDraft", kindent)
def es(d): d["backend_kind"]="expression"; d["expression_or_call"]={"op":"os.system","args":["rm -rf /"]}
probe("ExecutableSpec expression op 'os.system'", "ExecutableSpec", es)
def tr(d): d["effective_time"]={"from":"2026-12-01T00:00:00Z","to":"2026-01-01T00:00:00Z"}
if "SemanticDraft" in S: probe("SemanticDraft effective_time from>to", "SemanticDraft", tr)
def ex(d): d["started_at"]="2026-12-01T00:00:00Z"; d["finished_at"]="2026-01-01T00:00:00Z"
probe("ExecutionRef finished_at < started_at", "ExecutionRef", ex)
def qm(d): d["quality"]=[{"name":"acc","value":5.0,"numerator":10,"denominator":2}]
probe("MetricBundle quality numerator>denominator, value=5", "MetricBundle", qm)
def ur(d): d["unknown"]={"count":0,"rate":0.9}
probe("MetricBundle unknown count=0 rate=0.9", "MetricBundle", ur)
