import io, json, os, sys
from pydantic import BaseModel
from dataagent_contracts.core import CapabilityResult, CapabilityStatus, Issue, Severity
from dataagent_runtime import operation, reset_registry, get_spec
from dataagent_runtime.enforcement import EnforcementConfig
from dataagent_runtime.interfaces.unified import LayerHooks, main

class In(BaseModel):
    value: int
class Out(BaseModel):
    value: int

reset_registry()
@operation("T.9.3", input_model=In, output_model=Out, description="two phase")
def op(input_obj, ctx, runtime):
    issue = Issue(code="da03.proposal_required", severity=Severity.warning,
                  message="proposal required", retryable=False,
                  suggested_action="fill the proposal",
                  inference_request={"kind": "metric", "statement": "sum(secret_col)",
                                     "fields": ["secret_col"], "egress_decision_ref": None})
    return CapabilityResult(status=CapabilityStatus.needs_input, issues=[issue])

class FakeRuntime:
    data_root = "/tmp/probe-root3"
    enforcement = EnforcementConfig(mode="enforce")
    host_subject_ref = "u"
    host_purpose = "p"
    class decisions:
        @staticmethod
        def latest_allow(s, p): return None

os.makedirs("/tmp/probe-root3", exist_ok=True)
hooks = LayerHooks(layer="data", list_operations=lambda: [get_spec("op")],
                   invoke=lambda o, p, c: op(In(**p), c, FakeRuntime()),
                   validate=lambda: None, runtime_factory=lambda: FakeRuntime())

def run(args):
    buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
    try:
        code = main(args, hooks=hooks)
    finally:
        sys.stdout = old
    return code, buf.getvalue()

code, out = run(["run", "op", "--set", "value=1"])
s = json.loads(out)
print("summary exit:", code, "| statement in stdout:", "sum(secret_col)" in out,
      "| keys:", sorted(s["issues"][0]["inference_request"]))
code, out = run(["run", "op", "--set", "value=1", "--detail", "full"])
print("detail  exit:", code, "| full stdout bytes:", len(out.encode()),
      "| statement in stdout:", "sum(secret_col)" in out)
