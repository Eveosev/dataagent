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
