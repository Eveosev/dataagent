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
@operation("T.9.1", input_model=In, output_model=Out, description="x")
def op(input_obj, ctx, runtime):
    issues = [Issue(code="da02.x%d" % i, severity=Severity.warning, message="y" * 3000,
                    retryable=False) for i in range(30)]
    return CapabilityResult(status=CapabilityStatus.failed, issues=issues)

class FakeRuntime:
    data_root = "/tmp/probe-root"
    enforcement = None
    host_subject_ref = "u"
    host_purpose = "p"
    class decisions:
        @staticmethod
        def latest_allow(s, p):
            return None

os.makedirs("/tmp/probe-root", exist_ok=True)
hooks = LayerHooks(layer="data", list_operations=lambda: [get_spec("op")],
                   invoke=lambda o, p, c: op(In(**p), c, FakeRuntime()),
                   validate=lambda: None, runtime_factory=lambda: FakeRuntime())
buf = io.StringIO()
old = sys.stdout
sys.stdout = buf
try:
    code = main(["run", "op", "--set", "value=1"], hooks=hooks)
finally:
    sys.stdout = old
out = buf.getvalue()
print("exit:", code)
print("stdout bytes:", len(out.encode()))
print("limit:", 32 * 1024)
print("violates 32KiB:", len(out.encode()) > 32 * 1024)
data = json.loads(out)
print("issues count after trim:", len(data.get("issues") or []))
print("data marker:", json.dumps(data.get("data"))[:80])
