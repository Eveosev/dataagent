import io, json, os, sys
from pydantic import BaseModel
from dataagent_contracts.core import CapabilityResult, CapabilityStatus, Issue, Severity
from dataagent_runtime import operation, reset_registry, get_spec
from dataagent_runtime.interfaces.unified import LayerHooks, main

class In(BaseModel):
    value: int
class Out(BaseModel):
    value: int

reset_registry()
@operation("T.9.2", input_model=In, output_model=Out, description="two-phase with samples")
def op(input_obj, ctx, runtime):
    issue = Issue(code="da03.proposal_required", severity=Severity.warning,
                  message="proposal required", retryable=False, suggested_action="fill the proposal",
                  inference_request={"kind": "metric", "statement": "sum(amount)",
                                     "samples": [{"row": i, "cell": "x" * 500} for i in range(80)]})
    return CapabilityResult(status=CapabilityStatus.needs_input, issues=[issue])

class FakeRuntime:
    data_root = "/tmp/probe-root2"
    enforcement = None          # default mode "warn": no egress strip
    host_subject_ref = "u"
    host_purpose = "p"
    class decisions:
        @staticmethod
        def latest_allow(s, p): return None

os.makedirs("/tmp/probe-root2", exist_ok=True)
hooks = LayerHooks(layer="data", list_operations=lambda: [get_spec("op")],
                   invoke=lambda o, p, c: op(In(**p), c, FakeRuntime()),
                   validate=lambda: None, runtime_factory=lambda: FakeRuntime())
buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
try:
    code = main(["run", "op", "--set", "value=1"], hooks=hooks)
finally:
    sys.stdout = old
out = buf.getvalue()
print("exit:", code)
print("stdout bytes:", len(out.encode()), "limit:", 32 * 1024,
      "violates:", len(out.encode()) > 32 * 1024)
summary = json.loads(out)
print("status:", summary["status"], "| next_command:", summary.get("next_command"))
print("inference_request present:", bool(summary["issues"][0].get("inference_request")))
print("data marker:", summary.get("data"))
