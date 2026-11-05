import collections, importlib.util, sys
spec = importlib.util.spec_from_file_location("g", "/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-scenarios/tests/test_data_layer_gate.py")
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
governance = g.governance; data = g.data
def test_probe(governance, data, tmp_path):
    from dataagent_data.invoke import invoke as di
    from dataagent_scenarios.gate import enforce_data_invoke
    from dataagent_runtime.enforcement import EnforcementConfig
    from dataagent_data.runtime import create
    parsed = di("parse_delimited_file", {"file_ref": g._file_ref(tmp_path,"orders.csv")}, g._ctx(), runtime=data)
    table = parsed.data.table.model_dump(mode="json")
    profile = di("profile_table_structure", {"table_ref": table}, g._ctx(), runtime=data).data.profile.model_dump(mode="json")
    dec = {k: g._mint_decision(governance, f"{k}@*") for k in ("file","doc","table","profile")}
    rows = []
    for spec in g.data_operations():
        if not spec.source_file.startswith("src/dataagent_data/"): continue
        p = g._gate_payload(spec.operation, tmp_path, table, profile)
        r = enforce_data_invoke(spec.operation, p, g._ctx(authorization_ref=g._covering_decision_for(p, dec)), runtime=data, resolver=governance.access_resolver, enforcement=g.ENFORCE)
        rows.append((spec.operation, r.status.value, r.issues[0].code if r.issues else ""))
    c = collections.Counter((s, c) for _, s, c in rows)
    print("\nSTATUS/CODE counts:", dict(c))
    for row in rows: print("  ", *row)
    # product path, enforce, bogus auth, ops w/o resource_fields with a valid payload
    prod = create(workspace_root=tmp_path, data_root=tmp_path/".dataagent", enforcement=EnforcementConfig(mode="enforce"))
    for op, payload in [("append_task_event", {"event": {"task_id":"t1","event_type":"created","payload":{}}}),]:
        r = di(op, payload, g._ctx(authorization_ref="ad:totally-bogus"), runtime=prod)
        print("\nPRODUCT", op, r.status.value, [(i.code, i.message[:100]) for i in r.issues][:3])
