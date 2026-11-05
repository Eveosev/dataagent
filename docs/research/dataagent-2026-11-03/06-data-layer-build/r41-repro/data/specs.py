import json,sys
from dataagent_data.registry import list_operations, registry_errors, load_catalog
specs=list_operations()
print(len(specs), registry_errors())
for s in specs:
    print(s.capability_id, s.operation, s.source_file, 'W' if s.writes else '-', s.resource_fields, s.input_model.__name__, s.output_model.__name__)
