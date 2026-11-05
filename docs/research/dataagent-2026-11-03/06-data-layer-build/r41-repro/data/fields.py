from dataagent_data.registry import list_operations
for s in list_operations():
    f={k:str(v.annotation).replace('typing.','').replace('dataagent_contracts.core.','')[:70] for k,v in s.input_model.model_fields.items()}
    print(s.operation, s.resource_fields)
    for k,v in f.items(): print('   ',k,':',v)
