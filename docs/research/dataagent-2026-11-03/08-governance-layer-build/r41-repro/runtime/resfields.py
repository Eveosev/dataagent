import importlib, sys
from dataagent_runtime.invoke import _to_versioned_ref
import dataagent_runtime.registry as reg
mods = sys.argv[1:]
for m in mods:
    try: importlib.import_module(m)
    except Exception as e: print("import fail", m, e)
from typing import get_args
for spec in reg.list_operations():
    for f in spec.resource_fields:
        fi = spec.input_model.model_fields.get(f)
        print(f"{spec.capability_id:12s} {spec.operation:40s} {f:20s} {'MISSING' if fi is None else fi.annotation}")
